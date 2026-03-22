"""
MapSplat - Dockable Widget

This module contains the dockable widget that provides the main UI
for layer selection, export options, and triggering exports.
"""

__version__ = "0.6.16"

import os

try:
    from .log_utils import format_log_line
except ImportError:
    from log_utils import format_log_line  # test environment (no package)

try:
    from . import config_manager
except ImportError:
    import config_manager  # test environment (no package)

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt, QSettings
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QFileDialog,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSizePolicy,
    QSpinBox,
    QRadioButton,
    QButtonGroup,
    QTabWidget,
    QScrollArea,
    QFrame,
)

from qgis.core import (
    QgsProject,
    QgsMapLayer,
    QgsVectorLayer,
    QgsRasterLayer,
    Qgis,
)

from .exporter import MapSplatExporter

# Qt6 compatibility: handle scoped enums
try:
    # Qt6 style
    _ItemIsEnabled = Qt.ItemFlag.ItemIsEnabled
    _UserRole = Qt.ItemDataRole.UserRole
except AttributeError:
    # Qt5 style
    _ItemIsEnabled = Qt.ItemIsEnabled
    _UserRole = Qt.UserRole

try:
    # Qt6 style
    from qgis.PyQt.QtWidgets import QAbstractItemView
    _MultiSelection = QAbstractItemView.SelectionMode.MultiSelection
except (ImportError, AttributeError):
    # Qt5 style
    _MultiSelection = QListWidget.MultiSelection


class MapSplatDockWidget(QDockWidget):
    """Dockable widget for MapSplat plugin."""

    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("MapSplat")
        self.setObjectName("MapSplatDockWidget")

        # Create main widget and layout
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        self._setup_ui()
        self.setWidget(self.main_widget)

        # Connect to project layer changes
        QgsProject.instance().layersAdded.connect(self.refresh_layer_list)
        QgsProject.instance().layersRemoved.connect(self.refresh_layer_list)

        # Initial population
        self.refresh_layer_list()

    def _setup_ui(self):
        """Set up the user interface."""
        # ==================== Tab Widget ====================
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # --- Export tab ---
        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)
        export_layout.setContentsMargins(8, 8, 8, 8)
        export_layout.setSpacing(8)

        # ==================== Layer Selection ====================
        layer_group = QGroupBox("Layers to Export")
        layer_layout = QVBoxLayout(layer_group)

        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(_MultiSelection)
        self.layer_list.itemSelectionChanged.connect(self._update_layer_count)
        layer_layout.addWidget(self.layer_list)

        # Select all / none buttons
        btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_none = QPushButton("Select None")
        self.btn_select_all.clicked.connect(self._select_all_layers)
        self.btn_select_none.clicked.connect(self._select_no_layers)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_select_none)
        layer_layout.addLayout(btn_layout)

        # Layer count summary label
        self.lbl_layer_count = QLabel("0 of 0 layers selected")
        self.lbl_layer_count.setStyleSheet("color: gray; font-style: italic;")
        layer_layout.addWidget(self.lbl_layer_count)

        # ---- Scroll area wraps all groups ----
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setMinimumHeight(80)  # allow shrinking; content scrolls
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(8)

        scroll_layout.addWidget(layer_group)

        # ==================== Export Options ====================
        options_group = QGroupBox("Export Options")
        options_layout = QVBoxLayout(options_group)

        # Export mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("PMTiles mode:"))
        self.combo_export_mode = QComboBox()
        self.combo_export_mode.addItems([
            "Single file (all layers)",
            "Separate files per layer"
        ])
        mode_layout.addWidget(self.combo_export_mode)
        options_layout.addLayout(mode_layout)

        # Max zoom level
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Max zoom:"))
        self.spin_max_zoom = QSpinBox()
        self.spin_max_zoom.setRange(4, 18)
        self.spin_max_zoom.setValue(6)
        self.spin_max_zoom.setToolTip(
            "Higher zoom = more detail but exponentially longer processing.\n"
            "10 is good for most data. 14+ can take hours for large datasets."
        )
        zoom_layout.addWidget(self.spin_max_zoom)
        zoom_layout.addStretch()
        options_layout.addLayout(zoom_layout)

        # Style options
        self.chk_export_style = QCheckBox("Export separate style.json")
        self.chk_export_style.setChecked(True)
        options_layout.addWidget(self.chk_export_style)

        self.chk_style_only = QCheckBox("Style only (skip data export)")
        self.chk_style_only.setToolTip(
            "Export only style.json and HTML viewer without converting data.\n"
            "Use when data already exists or for quick style iteration."
        )
        options_layout.addWidget(self.chk_style_only)

        # Export extent layer
        extent_layout = QHBoxLayout()
        extent_layout.addWidget(QLabel("Export extent:"))
        self.combo_extent_layer = QComboBox()
        self.combo_extent_layer.addItem("Full extent of data", None)
        extent_layout.addWidget(self.combo_extent_layer, 1)
        options_layout.addLayout(extent_layout)

        # Import style button
        style_import_layout = QHBoxLayout()
        self.btn_import_style = QPushButton("Import style.json...")
        self.btn_import_style.clicked.connect(self._import_style)
        self.lbl_imported_style = QLabel("No style imported")
        self.lbl_imported_style.setStyleSheet("color: gray; font-style: italic;")
        style_import_layout.addWidget(self.btn_import_style)
        style_import_layout.addWidget(self.lbl_imported_style, 1)
        options_layout.addLayout(style_import_layout)

        scroll_layout.addWidget(options_group)

        # ==================== Basemap Overlay ====================
        self.basemap_group = QGroupBox("Basemap Overlay")
        self.basemap_group.setCheckable(True)
        self.basemap_group.setChecked(False)
        basemap_layout = QVBoxLayout(self.basemap_group)

        # Source type radio buttons
        source_type_layout = QHBoxLayout()
        source_type_layout.addWidget(QLabel("Source:"))
        self.radio_basemap_url = QRadioButton("Remote URL")
        self.radio_basemap_file = QRadioButton("Local file")
        self.radio_basemap_url.setChecked(True)
        self._basemap_source_group = QButtonGroup()
        self._basemap_source_group.addButton(self.radio_basemap_url)
        self._basemap_source_group.addButton(self.radio_basemap_file)
        source_type_layout.addWidget(self.radio_basemap_url)
        source_type_layout.addWidget(self.radio_basemap_file)
        source_type_layout.addStretch()
        basemap_layout.addLayout(source_type_layout)

        # Source URL / file path row
        basemap_src_layout = QHBoxLayout()
        self.txt_basemap_source = QLineEdit()
        self.txt_basemap_source.setPlaceholderText(
            "https://build.protomaps.com/20260217.pmtiles"
        )
        self.btn_basemap_browse = QPushButton("Browse...")
        self.btn_basemap_browse.setVisible(False)
        self.btn_basemap_browse.clicked.connect(self._browse_basemap_file)
        basemap_src_layout.addWidget(self.txt_basemap_source, 1)
        basemap_src_layout.addWidget(self.btn_basemap_browse)
        basemap_layout.addLayout(basemap_src_layout)

        # Basemap style.json row
        basemap_style_layout = QHBoxLayout()
        basemap_style_layout.addWidget(QLabel("Basemap style:"))
        self.txt_basemap_style = QLineEdit()
        self.txt_basemap_style.setPlaceholderText("path/to/basemap_style.json")
        self.btn_basemap_style_browse = QPushButton("Browse...")
        self.btn_basemap_style_browse.clicked.connect(self._browse_basemap_style)
        basemap_style_layout.addWidget(self.txt_basemap_style, 1)
        basemap_style_layout.addWidget(self.btn_basemap_style_browse)
        basemap_layout.addLayout(basemap_style_layout)

        scroll_layout.addWidget(self.basemap_group)

        # Connect radio buttons to show/hide browse button
        self.radio_basemap_url.toggled.connect(self._on_basemap_source_type_changed)
        self.radio_basemap_file.toggled.connect(self._on_basemap_source_type_changed)

        # ==================== Output Settings ====================
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)

        # Project name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Project name:"))
        self.txt_project_name = QLineEdit()
        self.txt_project_name.setPlaceholderText("my_webmap")
        name_layout.addWidget(self.txt_project_name)
        output_layout.addLayout(name_layout)

        # Output folder
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Output folder:"))
        self.txt_output_folder = QLineEdit()
        self.txt_output_folder.setPlaceholderText("Select output folder...")
        self.txt_output_folder.textChanged.connect(self._save_last_output_folder)
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_output_folder)
        folder_layout.addWidget(self.txt_output_folder, 1)
        folder_layout.addWidget(self.btn_browse)
        output_layout.addLayout(folder_layout)

        self.chk_save_log = QCheckBox("Save export log to file (export.log)")
        self.chk_save_log.setChecked(False)
        output_layout.addWidget(self.chk_save_log)

        scroll_layout.addWidget(output_group)

        # Finish scroll area setup
        scroll_area.setWidget(scroll_widget)
        export_layout.addWidget(scroll_area)

        # ==================== Separator ====================
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        export_layout.addWidget(separator)

        # ==================== Config Save/Load (pinned) ====================
        config_btn_layout = QHBoxLayout()
        self.btn_save_config = QPushButton("Save Config...")
        self.btn_load_config = QPushButton("Load Config...")
        self.btn_save_config.clicked.connect(self._save_config)
        self.btn_load_config.clicked.connect(self._load_config)
        config_btn_layout.addWidget(self.btn_save_config)
        config_btn_layout.addWidget(self.btn_load_config)
        export_layout.addLayout(config_btn_layout)

        # ==================== Export Button (pinned) ====================
        self.btn_export = QPushButton("Export Web Map")
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
            QPushButton:disabled {
                background-color: #a5d6a7;
            }
        """)
        self.btn_export.clicked.connect(self._do_export)
        export_layout.addWidget(self.btn_export)

        # ==================== Progress ====================
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setMaximumWidth(70)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
        """)
        self.btn_cancel.clicked.connect(self._cancel_export)
        progress_layout.addWidget(self.btn_cancel)

        export_layout.addLayout(progress_layout)

        # --- Viewer tab ---
        viewer_tab = QWidget()
        viewer_layout = QVBoxLayout(viewer_tab)
        viewer_layout.setContentsMargins(8, 8, 8, 8)
        viewer_layout.setSpacing(6)

        viewer_group = QGroupBox("Map Controls")
        viewer_group_layout = QVBoxLayout(viewer_group)

        self.chk_viewer_scale_bar = QCheckBox("Scale bar")
        self.chk_viewer_scale_bar.setChecked(True)
        viewer_group_layout.addWidget(self.chk_viewer_scale_bar)

        self.chk_viewer_geolocate = QCheckBox("Geolocate (show my location)")
        self.chk_viewer_geolocate.setChecked(True)
        viewer_group_layout.addWidget(self.chk_viewer_geolocate)

        self.chk_viewer_fullscreen = QCheckBox("Fullscreen button")
        self.chk_viewer_fullscreen.setChecked(True)
        viewer_group_layout.addWidget(self.chk_viewer_fullscreen)

        self.chk_viewer_coords = QCheckBox("Coordinate display (mouse position)")
        self.chk_viewer_coords.setChecked(True)
        viewer_group_layout.addWidget(self.chk_viewer_coords)

        self.chk_viewer_zoom_display = QCheckBox("Zoom level display")
        self.chk_viewer_zoom_display.setChecked(True)
        viewer_group_layout.addWidget(self.chk_viewer_zoom_display)

        self.chk_viewer_reset_view = QCheckBox("Reset view button (fit to data)")
        self.chk_viewer_reset_view.setChecked(True)
        viewer_group_layout.addWidget(self.chk_viewer_reset_view)

        self.chk_viewer_north_reset = QCheckBox("North-up / reset rotation button")
        self.chk_viewer_north_reset.setChecked(True)
        viewer_group_layout.addWidget(self.chk_viewer_north_reset)

        # Label placement mode
        placement_row = QHBoxLayout()
        placement_row.addWidget(QLabel("Label placement:"))
        self.combo_label_placement = QComboBox()
        self.combo_label_placement.addItems([
            "Match QGIS (exact positions)",
            "Auto-place (avoid overlaps)",
        ])
        placement_row.addWidget(self.combo_label_placement)
        viewer_group_layout.addLayout(placement_row)

        self.chk_advanced_legend = QCheckBox("Advanced Legend (show categories and class breaks)")
        self.chk_advanced_legend.setChecked(False)
        viewer_group_layout.addWidget(self.chk_advanced_legend)

        viewer_layout.addWidget(viewer_group)

        # Map Dimensions group
        dim_group = QGroupBox("Map Dimensions")
        dim_layout = QHBoxLayout(dim_group)
        dim_layout.addWidget(QLabel("Width:"))
        self.spin_map_width = QSpinBox()
        self.spin_map_width.setRange(0, 9999)
        self.spin_map_width.setValue(0)
        self.spin_map_width.setSpecialValueText("responsive")
        self.spin_map_width.setSuffix(" px")
        dim_layout.addWidget(self.spin_map_width)
        dim_layout.addSpacing(12)
        dim_layout.addWidget(QLabel("Height:"))
        self.spin_map_height = QSpinBox()
        self.spin_map_height.setRange(0, 9999)
        self.spin_map_height.setValue(0)
        self.spin_map_height.setSpecialValueText("responsive")
        self.spin_map_height.setSuffix(" px")
        dim_layout.addWidget(self.spin_map_height)
        dim_layout.addStretch()
        viewer_layout.addWidget(dim_group)
        viewer_layout.addStretch()

        # --- Log tab ---
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(8, 8, 8, 8)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("font-family: monospace; font-size: 11px;")
        log_layout.addWidget(self.txt_log)

        # --- Offline tab ---
        offline_tab = QWidget()
        offline_layout = QVBoxLayout(offline_tab)
        offline_layout.setContentsMargins(8, 8, 8, 8)
        offline_layout.setSpacing(6)

        offline_group = QGroupBox("Offline Asset Bundling")
        offline_group_layout = QVBoxLayout(offline_group)

        self.chk_bundle_offline = QCheckBox("Bundle JS/CSS for offline viewing")
        self.chk_bundle_offline.setChecked(False)
        offline_group_layout.addWidget(self.chk_bundle_offline)

        offline_note = QLabel(
            "When checked, MapLibre GL JS, its CSS, and PMTiles JS are downloaded "
            "from unpkg.com at export time and saved to lib/. The viewer then works "
            "without an internet connection.\n\n"
            "If the download fails, the export continues using CDN links instead."
        )
        offline_note.setWordWrap(True)
        offline_note.setStyleSheet("color: gray; font-style: italic;")
        offline_group_layout.addWidget(offline_note)

        offline_layout.addWidget(offline_group)
        offline_layout.addStretch()

        # Register tabs
        self.tabs.addTab(export_tab, "Export")
        self.tabs.addTab(viewer_tab, "Viewer")
        self.tabs.addTab(offline_tab, "Offline")
        self.tabs.addTab(log_tab, "Log")

        # Store imported style path
        self.imported_style_path = None

        # Log file handle (opened at export start, closed at finish)
        self._log_file = None

        # Remember last config directory for file dialogs
        self._last_config_dir = ""

        # Restore last output folder from QSettings
        settings = QSettings("MapSplat", "MapSplat")
        last_folder = settings.value("last_output_folder", "")
        if last_folder and os.path.isdir(last_folder):
            self.txt_output_folder.setText(last_folder)

    def refresh_layer_list(self):
        """Refresh the layer list and extent combo from the current project."""
        self.layer_list.clear()

        # Repopulate extent-layer combo, preserving current selection by layer id
        current_extent_id = self.combo_extent_layer.currentData()
        self.combo_extent_layer.clear()
        self.combo_extent_layer.addItem("Full extent of data", None)

        project = QgsProject.instance()
        # Use layerTreeRoot().layerOrder() so the list reflects QGIS panel order (top → bottom)
        for layer in project.layerTreeRoot().layerOrder():
            item = QListWidgetItem()

            # Determine layer type icon/prefix
            if isinstance(layer, QgsVectorLayer):
                geom_type = layer.geometryType()
                if geom_type == 0:  # Point
                    prefix = "[Point]"
                elif geom_type == 1:  # Line
                    prefix = "[Line]"
                elif geom_type == 2:  # Polygon
                    prefix = "[Polygon]"
                else:
                    prefix = "[Vector]"
            elif isinstance(layer, QgsRasterLayer):
                prefix = "[Raster]"
            else:
                prefix = "[Other]"
                item.setFlags(item.flags() & ~_ItemIsEnabled)

            item.setText(f"{prefix} {layer.name()}")
            item.setData(_UserRole, layer.id())
            self.layer_list.addItem(item)

            # Also add to extent combo (all layer types accepted)
            self.combo_extent_layer.addItem(layer.name(), layer.id())

        # Restore previously selected extent layer if it still exists
        if current_extent_id:
            idx = self.combo_extent_layer.findData(current_extent_id)
            if idx >= 0:
                self.combo_extent_layer.setCurrentIndex(idx)

        # Auto-populate project name from QGIS project
        project_name = project.baseName()
        if project_name and not self.txt_project_name.text():
            # Clean up name for filesystem
            clean_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
            self.txt_project_name.setText(clean_name)

        self._update_layer_count()

    def _select_all_layers(self):
        """Select all layers in the list."""
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            if item.flags() & _ItemIsEnabled:
                item.setSelected(True)

    def _select_no_layers(self):
        """Deselect all layers."""
        self.layer_list.clearSelection()

    def _update_layer_count(self):
        """Update the 'X of Y layers selected' label."""
        total = self.layer_list.count()
        selected = len(self.layer_list.selectedItems())
        self.lbl_layer_count.setText(f"{selected} of {total} layers selected")

    def _save_last_output_folder(self, text):
        """Persist the current output folder to QSettings."""
        folder = text.strip()
        if folder and os.path.isdir(folder):
            QSettings("MapSplat", "MapSplat").setValue("last_output_folder", folder)

    def _browse_output_folder(self):
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.txt_output_folder.text() or os.path.expanduser("~")
        )
        if folder:
            self.txt_output_folder.setText(folder)

    def _import_style(self):
        """Import an existing style.json file, with structural validation."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import MapLibre Style JSON",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not file_path:
            return

        # Parse and validate before accepting
        import json as _json
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                style_data = _json.load(f)
        except OSError as e:
            QMessageBox.warning(self, "Cannot Read File",
                                f"Could not open the file:\n{e}")
            return
        except _json.JSONDecodeError as e:
            QMessageBox.warning(self, "Invalid JSON",
                                f"The file is not valid JSON:\n{e}")
            return

        if not isinstance(style_data, dict):
            QMessageBox.warning(self, "Invalid Style",
                                "Expected a JSON object at the top level.")
            return

        if style_data.get("version") != 8:
            got = style_data.get("version", "<missing>")
            QMessageBox.warning(self, "Invalid Style",
                                f"This does not look like a MapLibre Style JSON v8 file.\n"
                                f"Expected \"version\": 8, found: {got!r}")
            return

        if "layers" not in style_data:
            QMessageBox.warning(self, "Invalid Style",
                                "The style file has no \"layers\" key.")
            return

        self.imported_style_path = file_path
        basename = os.path.basename(file_path)
        self.lbl_imported_style.setText(f"Imported: {basename}")
        self.lbl_imported_style.setStyleSheet("color: green;")
        self._log(f"Imported style: {file_path}")

    def _on_basemap_source_type_changed(self):
        """Show/hide browse button based on source type selection."""
        is_file = self.radio_basemap_file.isChecked()
        self.btn_basemap_browse.setVisible(is_file)
        if is_file:
            self.txt_basemap_source.setPlaceholderText("path/to/basemap.pmtiles")
        else:
            self.txt_basemap_source.setPlaceholderText(
                "https://build.protomaps.com/20260217.pmtiles"
            )

    def _browse_basemap_file(self):
        """Open file browser for local basemap PMTiles file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Basemap PMTiles File",
            self.txt_basemap_source.text() or os.path.expanduser("~"),
            "PMTiles Files (*.pmtiles);;All Files (*)"
        )
        if file_path:
            self.txt_basemap_source.setText(file_path)

    def _browse_basemap_style(self):
        """Open file browser for basemap style.json."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Basemap Style JSON",
            self.txt_basemap_style.text() or os.path.expanduser("~"),
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.txt_basemap_style.setText(file_path)

    def _log(self, message, level="info"):
        """Add a message to the log area.

        :param message: Message to log
        :param level: Log level (info, warning, error, success)
        """
        color_map = {
            "info": "black",
            "warning": "orange",
            "error": "red",
            "success": "green",
        }
        color = color_map.get(level, "black")
        self.txt_log.append(f'<span style="color:{color}">{message}</span>')
        if self._log_file:
            try:
                self._log_file.write(format_log_line(message, level))
                self._log_file.flush()
            except OSError:
                pass

    def _close_log_file(self):
        """Close the export log file if open."""
        if self._log_file:
            try:
                self._log_file.close()
            except OSError:
                pass
            self._log_file = None

    def _validate_export(self):
        """Validate export settings before proceeding.

        :returns: True if valid, False otherwise
        """
        # Check layers selected
        selected_items = self.layer_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Layers", "Please select at least one layer to export.")
            return False

        # Check output folder
        output_folder = self.txt_output_folder.text().strip()
        if not output_folder:
            QMessageBox.warning(self, "No Output Folder", "Please select an output folder.")
            return False

        if not os.path.isdir(output_folder):
            QMessageBox.warning(self, "Invalid Folder", "The output folder does not exist.")
            return False

        if not os.access(output_folder, os.W_OK):
            QMessageBox.warning(self, "Folder Not Writable",
                                "Cannot write to the output folder.\n"
                                "Check that you have write permissions for:\n"
                                f"{output_folder}")
            return False

        # Check project name
        project_name = self.txt_project_name.text().strip()
        if not project_name:
            QMessageBox.warning(self, "No Project Name", "Please enter a project name.")
            return False

        # Basemap validation (only when enabled)
        if self.basemap_group.isChecked():
            basemap_source = self.txt_basemap_source.text().strip()
            if not basemap_source:
                QMessageBox.warning(self, "No Basemap Source",
                                    "Please enter a basemap PMTiles URL or file path.")
                return False

            if self.radio_basemap_file.isChecked() and not os.path.isfile(basemap_source):
                QMessageBox.warning(self, "Invalid Basemap File",
                                    "The basemap PMTiles file does not exist.")
                return False

            basemap_style = self.txt_basemap_style.text().strip()
            if not basemap_style:
                QMessageBox.warning(self, "No Basemap Style",
                                    "Please select a basemap style.json file.")
                return False

            if not os.path.isfile(basemap_style):
                QMessageBox.warning(self, "Invalid Basemap Style",
                                    "The basemap style.json file does not exist.")
                return False

        return True

    def _do_export(self):
        """Perform the export."""
        if not self._validate_export():
            return

        self.txt_log.clear()

        # Open log file before first message so the header is captured
        if self.chk_save_log.isChecked():
            output_folder = self.txt_output_folder.text().strip()
            project_name = self.txt_project_name.text().strip()
            log_path = os.path.join(output_folder, f"{project_name}_webmap", "export.log")
            os.makedirs(os.path.join(output_folder, f"{project_name}_webmap"), exist_ok=True)
            try:
                from datetime import datetime
                self._log_file = open(log_path, "a", encoding="utf-8")
                self._log_file.write(
                    f"\n--- Export run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
            except OSError as e:
                self._log_file = None
                self._log(f"Warning: could not open log file: {e}", "warning")

        self._log("Starting export...", "info")
        self.tabs.setCurrentIndex(3)  # Log tab

        # Gather selected layers
        selected_layer_ids = []
        for item in self.layer_list.selectedItems():
            layer_id = item.data(_UserRole)
            selected_layer_ids.append(layer_id)

        # Gather settings
        settings = {
            "layer_ids": selected_layer_ids,
            "output_folder": self.txt_output_folder.text().strip(),
            "project_name": self.txt_project_name.text().strip(),
            "single_file": self.combo_export_mode.currentIndex() == 0,
            "style_only": self.chk_style_only.isChecked(),
            "export_style_json": self.chk_export_style.isChecked(),
            "imported_style_path": self.imported_style_path,
            "max_zoom": self.spin_max_zoom.value(),
            "use_basemap": self.basemap_group.isChecked(),
            "basemap_source_type": "file" if self.radio_basemap_file.isChecked() else "url",
            "basemap_source": self.txt_basemap_source.text().strip(),
            "basemap_style_path": self.txt_basemap_style.text().strip(),
            "viewer_scale_bar": self.chk_viewer_scale_bar.isChecked(),
            "viewer_geolocate": self.chk_viewer_geolocate.isChecked(),
            "viewer_fullscreen": self.chk_viewer_fullscreen.isChecked(),
            "viewer_coords": self.chk_viewer_coords.isChecked(),
            "viewer_zoom_display": self.chk_viewer_zoom_display.isChecked(),
            "viewer_reset_view": self.chk_viewer_reset_view.isChecked(),
            "viewer_north_reset": self.chk_viewer_north_reset.isChecked(),
            "bundle_offline": self.chk_bundle_offline.isChecked(),
            "label_placement_mode": (
                "exact" if self.combo_label_placement.currentIndex() == 0 else "auto"
            ),
            "advanced_legend": self.chk_advanced_legend.isChecked(),
            "map_width": self.spin_map_width.value(),
            "map_height": self.spin_map_height.value(),
            "extent_layer_id": self.combo_extent_layer.currentData(),
        }

        # Show progress and cancel button
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_export.setEnabled(False)
        self.btn_cancel.setVisible(True)

        try:
            # Create exporter (uses QProcess internally, no separate thread needed)
            self._exporter = MapSplatExporter(self.iface, settings)

            # Connect signals
            self._exporter.progress.connect(self._on_progress)
            self._exporter.log_message.connect(self._on_log_message)
            self._exporter.finished.connect(self._on_export_finished)

            # Run export (QProcess keeps UI responsive via processEvents)
            self._exporter.run()

        except Exception as e:
            self._log(f"Export failed: {str(e)}", "error")
            self._close_log_file()
            self.btn_export.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.btn_cancel.setVisible(False)

    def _on_progress(self, value):
        """Handle progress updates."""
        self.progress_bar.setValue(value)

    def _on_log_message(self, message, level):
        """Handle log messages from exporter."""
        self._log(message, level)

    def _on_export_finished(self, success, output_path):
        """Handle export completion."""
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)  # Re-enable for next export
        self.btn_export.setEnabled(True)

        if success:
            self._log(f"Export complete: {output_path}", "success")
            self._close_log_file()
            QMessageBox.information(
                self,
                "Export Complete",
                f"Web map exported successfully to:\n{output_path}"
            )
        else:
            self._log("Export failed.", "error")
            self._close_log_file()

    def _cancel_export(self):
        """Cancel the running export."""
        if hasattr(self, '_exporter') and self._exporter:
            self._log("Cancelling export...", "warning")
            self._exporter.cancel()
            self.btn_cancel.setEnabled(False)

    def _save_config(self):
        """Save current UI settings to a TOML config file."""
        # Determine default directory for the dialog
        default_dir = (
            self.txt_output_folder.text().strip()
            or self._last_config_dir
            or os.path.expanduser("~")
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save MapSplat Config",
            os.path.join(default_dir, "mapsplat_config.toml"),
            "MapSplat Config (*.toml);;All Files (*)",
        )
        if not file_path:
            return

        self._last_config_dir = os.path.dirname(file_path)

        # Collect layer names from selected items
        layer_names = []
        project = QgsProject.instance()
        for item in self.layer_list.selectedItems():
            layer_id = item.data(_UserRole)
            layer = project.mapLayer(layer_id)
            if layer:
                layer_names.append(layer.name())

        config_dict = {
            "export": {
                "project_name": self.txt_project_name.text().strip(),
                "output_folder": self.txt_output_folder.text().strip(),
                "layer_names": layer_names,
                "pmtiles_mode": "single" if self.combo_export_mode.currentIndex() == 0 else "separate",
                "max_zoom": self.spin_max_zoom.value(),
                "export_style_json": self.chk_export_style.isChecked(),
                "style_only": self.chk_style_only.isChecked(),
                "imported_style_path": self.imported_style_path or "",
                "write_log": self.chk_save_log.isChecked(),
                "bundle_offline": self.chk_bundle_offline.isChecked(),
                "extent_layer_name": (
                    self.combo_extent_layer.currentText()
                    if self.combo_extent_layer.currentData() is not None
                    else ""
                ),
            },
            "basemap": {
                "enabled": self.basemap_group.isChecked(),
                "source_type": "file" if self.radio_basemap_file.isChecked() else "url",
                "source": self.txt_basemap_source.text().strip(),
                "style_path": self.txt_basemap_style.text().strip(),
            },
            "viewer": {
                "scale_bar": self.chk_viewer_scale_bar.isChecked(),
                "geolocate": self.chk_viewer_geolocate.isChecked(),
                "fullscreen": self.chk_viewer_fullscreen.isChecked(),
                "coords": self.chk_viewer_coords.isChecked(),
                "zoom_display": self.chk_viewer_zoom_display.isChecked(),
                "reset_view": self.chk_viewer_reset_view.isChecked(),
                "north_reset": self.chk_viewer_north_reset.isChecked(),
                "label_placement_mode": (
                    "exact" if self.combo_label_placement.currentIndex() == 0 else "auto"
                ),
                "advanced_legend": self.chk_advanced_legend.isChecked(),
                "map_width": self.spin_map_width.value(),
                "map_height": self.spin_map_height.value(),
            },
        }

        try:
            config_manager.write_config(file_path, config_dict)
            self._log(f"Config saved: {file_path}", "success")
        except OSError as e:
            self._log(f"Failed to save config: {e}", "error")

    def _load_config(self):
        """Load settings from a TOML config file into the UI."""
        default_dir = self._last_config_dir or os.path.expanduser("~")

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load MapSplat Config",
            default_dir,
            "MapSplat Config (*.toml);;All Files (*)",
        )
        if not file_path:
            return

        self._last_config_dir = os.path.dirname(file_path)

        try:
            config_dict = config_manager.read_config(file_path)
        except (FileNotFoundError, ValueError) as e:
            self._log(f"Failed to load config: {e}", "error")
            return

        applied = 0

        # --- [export] section ---
        export = config_dict.get("export", {})

        if "project_name" in export:
            self.txt_project_name.setText(export["project_name"])
            applied += 1

        if "output_folder" in export:
            self.txt_output_folder.setText(export["output_folder"])
            applied += 1

        if "layer_names" in export:
            saved_names = set(export["layer_names"])
            project = QgsProject.instance()
            for i in range(self.layer_list.count()):
                item = self.layer_list.item(i)
                layer_id = item.data(_UserRole)
                layer = project.mapLayer(layer_id)
                if layer and layer.name() in saved_names:
                    item.setSelected(True)
                else:
                    item.setSelected(False)
            applied += 1

        if "pmtiles_mode" in export:
            mode = export["pmtiles_mode"]
            self.combo_export_mode.setCurrentIndex(0 if mode == "single" else 1)
            applied += 1

        if "max_zoom" in export:
            self.spin_max_zoom.setValue(int(export["max_zoom"]))
            applied += 1

        if "export_style_json" in export:
            self.chk_export_style.setChecked(bool(export["export_style_json"]))
            applied += 1

        if "style_only" in export:
            self.chk_style_only.setChecked(bool(export["style_only"]))
            applied += 1

        if "imported_style_path" in export:
            path_val = export["imported_style_path"]
            if path_val:
                self.imported_style_path = path_val
                self.lbl_imported_style.setText(f"Imported: {os.path.basename(path_val)}")
                self.lbl_imported_style.setStyleSheet("color: green;")
            else:
                self.imported_style_path = None
                self.lbl_imported_style.setText("No style imported")
                self.lbl_imported_style.setStyleSheet("color: gray; font-style: italic;")
            applied += 1

        if "write_log" in export:
            self.chk_save_log.setChecked(bool(export["write_log"]))
            applied += 1

        if "bundle_offline" in export:
            self.chk_bundle_offline.setChecked(bool(export["bundle_offline"]))
            applied += 1

        if "extent_layer_name" in export:
            name = export["extent_layer_name"]
            if name:
                idx = self.combo_extent_layer.findText(name)
                if idx >= 0:
                    self.combo_extent_layer.setCurrentIndex(idx)
                else:
                    self._log(
                        f"Extent layer '{name}' from config not found in project — using full extent",
                        "warning",
                    )
            else:
                self.combo_extent_layer.setCurrentIndex(0)  # "Full extent of data"
            applied += 1

        # --- [basemap] section ---
        basemap = config_dict.get("basemap", {})

        if "enabled" in basemap:
            self.basemap_group.setChecked(bool(basemap["enabled"]))
            applied += 1

        if "source_type" in basemap:
            if basemap["source_type"] == "file":
                self.radio_basemap_file.setChecked(True)
            else:
                self.radio_basemap_url.setChecked(True)
            applied += 1

        if "source" in basemap:
            self.txt_basemap_source.setText(basemap["source"])
            applied += 1

        if "style_path" in basemap:
            self.txt_basemap_style.setText(basemap["style_path"])
            applied += 1

        # --- [viewer] section ---
        viewer = config_dict.get("viewer", {})
        viewer_map = {
            "scale_bar": self.chk_viewer_scale_bar,
            "geolocate": self.chk_viewer_geolocate,
            "fullscreen": self.chk_viewer_fullscreen,
            "coords": self.chk_viewer_coords,
            "zoom_display": self.chk_viewer_zoom_display,
            "reset_view": self.chk_viewer_reset_view,
            "north_reset": self.chk_viewer_north_reset,
        }
        for key, widget in viewer_map.items():
            if key in viewer:
                widget.setChecked(bool(viewer[key]))
                applied += 1

        if "label_placement_mode" in viewer:
            idx = 0 if viewer["label_placement_mode"] == "exact" else 1
            self.combo_label_placement.setCurrentIndex(idx)
            applied += 1

        if "advanced_legend" in viewer:
            self.chk_advanced_legend.setChecked(bool(viewer["advanced_legend"]))
            applied += 1

        if "map_width" in viewer:
            self.spin_map_width.setValue(int(viewer["map_width"]))
            applied += 1

        if "map_height" in viewer:
            self.spin_map_height.setValue(int(viewer["map_height"]))
            applied += 1

        self._log(f"Config loaded: {applied} settings applied from {file_path}", "info")

    def closeEvent(self, event):
        """Handle close event."""
        self.closingPlugin.emit()
        event.accept()
