"""
MapSplat - Dockable Widget

This module contains the dockable widget that provides the main UI
for layer selection, export options, and triggering exports.
"""

__version__ = "0.19.0"

import os

try:
    from .log_utils import format_log_line
except ImportError:
    from log_utils import format_log_line  # test environment (no package)

try:
    from . import config_manager
except ImportError:
    import config_manager  # test environment (no package)

from qgis.PyQt.QtCore import pyqtSignal, Qt, QUrl, QTimer, QStandardPaths
from qgis.PyQt.QtGui import QDesktopServices
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
    QToolButton,
    QApplication,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QStyle,
)

from qgis.PyQt.QtWidgets import QAbstractItemView

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsSettings,
)

from .exporter import MapSplatExporter

_ItemIsEnabled = Qt.ItemFlag.ItemIsEnabled
_UserRole = Qt.ItemDataRole.UserRole
_MultiSelection = QAbstractItemView.SelectionMode.MultiSelection


class MapSplatDockWidget(QDockWidget):
    """Dockable widget for MapSplat plugin."""

    closingPlugin = pyqtSignal()

    # (label, width, height) — width=0/height=0 means responsive
    _DIMENSION_PRESETS = [
        ("Full window (responsive)", 0, 0),
        ("800 × 600", 800, 600),
        ("800 × 900", 800, 900),
        ("1024 × 768", 1024, 768),
        ("1920 × 1080", 1920, 1080),
        ("Custom", None, None),
    ]

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

        # Connect to project layer changes via a DEBOUNCED scheduler. A project load
        # fires a burst of add/remove signals while layers are still being built;
        # coalescing them into one refresh that runs after the load settles avoids
        # reading layers mid-teardown (which crashed QGIS).
        QgsProject.instance().layersAdded.connect(self._schedule_layer_refresh)
        QgsProject.instance().layersRemoved.connect(self._schedule_layer_refresh)

        # Initial population, restore persisted settings, then seed still-empty
        # required fields from the open project (zero-config start).
        self.refresh_layer_list()
        self._restore_settings()
        self._prefill_defaults()
        self._update_readiness()

    def _schedule_layer_refresh(self, *args):
        """Coalesce a burst of layersAdded/Removed signals into a single refresh that
        runs once the event loop is idle (i.e. after a project load has settled)."""
        if getattr(self, "_refresh_pending", False):
            return
        self._refresh_pending = True
        QTimer.singleShot(250, self._run_scheduled_refresh)

    def _run_scheduled_refresh(self):
        self._refresh_pending = False
        self.refresh_layer_list()

    def _open_user_guide(self):
        """Open the bundled PDF user guide (fall back to the online docs)."""
        pdf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "help", "MapSplat_User_Guide.pdf")
        if os.path.isfile(pdf):
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf))
        else:
            QDesktopServices.openUrl(QUrl("https://github.com/johnzastrow/mapsplat4"))

    def _plugin_version(self):
        """Read the shipped version from metadata.txt (what QGIS installs), so the
        stamp reflects the actual loaded build; fall back to the module constant."""
        try:
            meta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.txt")
            with open(meta, encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("version="):
                        return line.split("=", 1)[1].strip()
        except Exception:
            pass
        return __version__

    def _setup_ui(self):
        """Set up the user interface."""
        # ==================== Header: intro + Help menu ====================
        header_row = QHBoxLayout()
        lbl_intro = QLabel(
            "Turn selected QGIS layers into a self-contained web map (PMTiles + MapLibre)."
        )
        lbl_intro.setWordWrap(True)
        lbl_intro.setStyleSheet("color: gray; font-size: 11px;")
        header_row.addWidget(lbl_intro, 1)

        self.btn_help = QToolButton()
        self.btn_help.setText("Help")
        self.btn_help.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        help_menu = QMenu(self.btn_help)
        help_menu.addAction("Open User Guide (PDF)", self._open_user_guide)
        help_menu.addAction(
            "Online docs / source",
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/johnzastrow/mapsplat4")),
        )
        self.btn_help.setMenu(help_menu)
        header_row.addWidget(self.btn_help)
        self.main_layout.addLayout(header_row)

        # ==================== Tab Widget ====================
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # ================================================================
        # --- Tab 0: Inputs (layers, advanced options, config, export) ---
        # ================================================================
        inputs_tab = QWidget()
        inputs_layout = QVBoxLayout(inputs_tab)
        inputs_layout.setContentsMargins(8, 8, 8, 8)
        inputs_layout.setSpacing(8)

        # ==================== Layer Selection ====================
        layer_group = QGroupBox("Layers to Export")
        layer_layout = QVBoxLayout(layer_group)
        lbl_layers_help = QLabel(
            "<b>Required.</b> Pick the vector layers to publish — their QGIS styles "
            "and labels are read automatically."
        )
        lbl_layers_help.setWordWrap(True)
        lbl_layers_help.setStyleSheet("color: gray; font-size: 11px;")
        layer_layout.addWidget(lbl_layers_help)

        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(_MultiSelection)
        self.layer_list.setToolTip("Select the layers to include in the export.\nCtrl+click or Shift+click to select multiple layers.")
        self.layer_list.itemSelectionChanged.connect(self._update_layer_count)
        self.layer_list.itemSelectionChanged.connect(self._update_tile_estimate)
        self.layer_list.itemSelectionChanged.connect(self._update_readiness)
        layer_layout.addWidget(self.layer_list)

        # Select all / none / refresh buttons
        btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setToolTip("Select all layers in the list.")
        self.btn_select_none = QPushButton("Select None")
        self.btn_select_none.setToolTip("Deselect all layers.")
        self.btn_refresh_layers = QPushButton("Refresh")
        self.btn_refresh_layers.setToolTip(
            "Re-read the layers from the current map/project.\n"
            "Use after renaming, reordering, adding or restyling layers.\n"
            "Your current selection is kept for layers that still exist."
        )
        self.btn_select_all.clicked.connect(self._select_all_layers)
        self.btn_select_none.clicked.connect(self._select_no_layers)
        self.btn_refresh_layers.clicked.connect(self.refresh_layer_list)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_select_none)
        btn_layout.addWidget(self.btn_refresh_layers)
        layer_layout.addLayout(btn_layout)

        # Layer count summary label
        self.lbl_layer_count = QLabel("0 of 0 layers selected")
        self.lbl_layer_count.setStyleSheet("color: gray; font-style: italic;")
        layer_layout.addWidget(self.lbl_layer_count)

        inputs_layout.addWidget(layer_group, 1)  # stretch=1 so it fills space

        # ============ Output (required) — beside Layers + Export so a whole run
        # can be configured on ONE tab, no jumping to the Options tab. ============
        output_group = QGroupBox("Output")
        output_group.setToolTip("Where the web map is written. Both fields are required.")
        output_group_layout = QVBoxLayout(output_group)
        output_group_layout.setSpacing(6)
        lbl_output_help = QLabel(
            "<b>Required.</b> A <code>&lt;project name&gt;_webmap/</code> folder is "
            "created inside the output folder."
        )
        lbl_output_help.setWordWrap(True)
        lbl_output_help.setStyleSheet("color: gray; font-size: 11px;")
        output_group_layout.addWidget(lbl_output_help)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Project name:"))
        self.txt_project_name = QLineEdit()
        self.txt_project_name.setPlaceholderText("my_webmap")
        self.txt_project_name.setToolTip(
            "Name for the output subdirectory.\n"
            "The export is written to <output folder>/<project name>_webmap/."
        )
        self.txt_project_name.textChanged.connect(self._update_readiness)
        name_layout.addWidget(self.txt_project_name)
        output_group_layout.addLayout(name_layout)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Output folder:"))
        self.txt_output_folder = QLineEdit()
        self.txt_output_folder.setPlaceholderText("Select output folder...")
        self.txt_output_folder.setToolTip("Parent directory where the export subdirectory is created.")
        self.txt_output_folder.textChanged.connect(self._save_settings)
        self.txt_output_folder.textChanged.connect(self._update_readiness)
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_output_folder)
        folder_layout.addWidget(self.txt_output_folder, 1)
        folder_layout.addWidget(self.btn_browse)
        output_group_layout.addLayout(folder_layout)

        inputs_layout.addWidget(output_group)

        # ================================================================
        # --- Tab 1: Options (export settings, basemap, output) ---
        # ================================================================
        options_tab = QWidget()
        options_tab_layout = QVBoxLayout(options_tab)
        options_tab_layout.setContentsMargins(8, 8, 8, 8)
        options_tab_layout.setSpacing(8)

        # Scroll area wraps all option groups
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setMinimumHeight(80)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(8)

        # ==================== Export Options (collapsible) ====================
        self._opt_toggle = QToolButton()
        self._opt_toggle.setText(" Export Options")
        self._opt_toggle.setCheckable(True)
        self._opt_toggle.setChecked(True)
        self._opt_toggle.setArrowType(Qt.ArrowType.DownArrow)
        self._opt_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._opt_toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        scroll_layout.addWidget(self._opt_toggle)

        opt_container = QWidget()
        options_layout = QVBoxLayout(opt_container)
        options_layout.setContentsMargins(16, 0, 0, 4)
        options_layout.setSpacing(6)

        # Export mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("PMTiles mode:"))
        self.combo_export_mode = QComboBox()
        self.combo_export_mode.addItems([
            "Single file (all layers)",
            "Separate files per layer"
        ])
        self.combo_export_mode.setToolTip(
            "Single file: all layers merged into one .pmtiles archive.\n"
            "Separate files: one .pmtiles per layer, loaded independently in the viewer."
        )
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

        self.lbl_tile_estimate = QLabel("Select layers to see tile estimate")
        self.lbl_tile_estimate.setStyleSheet("color: #666; font-size: 11px;")
        self.lbl_tile_estimate.setToolTip(
            "Rough tile count and file size estimate for the selected vector layers.\n"
            "Assumes ~4 KB per tile. Does not include basemap tiles — those depend\n"
            "on the external PMTiles source density and can add significant extra size."
        )
        options_layout.addWidget(self.lbl_tile_estimate)
        self.spin_max_zoom.valueChanged.connect(self._update_tile_estimate)

        # Style options
        self.chk_export_style = QCheckBox("Export separate style.json")
        self.chk_export_style.setChecked(True)
        self.chk_export_style.setToolTip(
            "Write a standalone style.json alongside the viewer.\n"
            "Useful if you want to load the style separately or customise it by hand."
        )
        options_layout.addWidget(self.chk_export_style)

        # Export extent layer
        extent_layout = QHBoxLayout()
        extent_layout.addWidget(QLabel("Export extent:"))
        self.combo_extent_layer = QComboBox()
        self.combo_extent_layer.addItem("Full extent of data", None)
        self.combo_extent_layer.setToolTip(
            "Sets the bounding box used when extracting basemap tiles.\n"
            "Choose a layer to clip the basemap to that layer's extent\n"
            "instead of the combined extent of all exported layers."
        )
        extent_layout.addWidget(self.combo_extent_layer, 1)
        options_layout.addLayout(extent_layout)

        # Import style button
        style_import_layout = QHBoxLayout()
        self.btn_import_style = QPushButton("Import style.json...")
        self.btn_import_style.setToolTip(
            "Merge an existing style.json into the generated output.\n"
            "Layers and sources from the imported file are added alongside the exported layers."
        )
        self.btn_import_style.clicked.connect(self._import_style)
        self.lbl_imported_style = QLabel("No style imported")
        self.lbl_imported_style.setStyleSheet("color: gray; font-style: italic;")
        style_import_layout.addWidget(self.btn_import_style)
        style_import_layout.addWidget(self.lbl_imported_style, 1)
        options_layout.addLayout(style_import_layout)

        scroll_layout.addWidget(opt_container)

        self._opt_toggle.toggled.connect(lambda checked: (
            opt_container.setVisible(checked),
            self._opt_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow),
        ))

        # ==================== Basemap Overlay (collapsible) ====================
        self._bm_toggle = QToolButton()
        self._bm_toggle.setText(" Basemap Overlay")
        self._bm_toggle.setCheckable(True)
        self._bm_toggle.setChecked(False)
        self._bm_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._bm_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._bm_toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._bm_toggle.setToolTip(
            "Add a Protomaps basemap (streets, terrain, etc.) beneath your layers.\n"
            "Expand to configure the basemap source and style."
        )
        scroll_layout.addWidget(self._bm_toggle)

        self.basemap_group = QGroupBox("Enable basemap")
        self.basemap_group.setCheckable(True)
        self.basemap_group.setChecked(False)
        self.basemap_group.setToolTip(
            "Check to add a Protomaps basemap (streets, terrain, etc.) beneath your layers.\n"
            "The basemap tiles are extracted to the output folder so the map works offline."
        )
        basemap_layout = QVBoxLayout(self.basemap_group)

        # Mode: stream from a URL (no install) vs download + clip for offline (needs CLI)
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.radio_basemap_stream = QRadioButton("Stream from URL")
        self.radio_basemap_stream.setToolTip(
            "No install needed. The published map loads the basemap live from the remote URL\n"
            "when viewed (the browser fetches only the visible tiles). Needs internet to view."
        )
        self.radio_basemap_bundle = QRadioButton("Download && clip offline")
        self.radio_basemap_bundle.setToolTip(
            "Clips the basemap to your data extent and embeds it in the export so the map works\n"
            "with no internet. Requires the 'pmtiles' command-line tool on your PATH."
        )
        self.radio_basemap_stream.setChecked(True)
        self._basemap_mode_group = QButtonGroup()
        self._basemap_mode_group.addButton(self.radio_basemap_stream)
        self._basemap_mode_group.addButton(self.radio_basemap_bundle)
        mode_layout.addWidget(self.radio_basemap_stream)
        mode_layout.addWidget(self.radio_basemap_bundle)
        mode_layout.addStretch()
        basemap_layout.addLayout(mode_layout)

        # Source type (bundle mode only): URL vs local file
        self._basemap_srctype_widget = QWidget()
        source_type_layout = QHBoxLayout(self._basemap_srctype_widget)
        source_type_layout.setContentsMargins(0, 0, 0, 0)
        source_type_layout.addWidget(QLabel("Source:"))
        self.radio_basemap_url = QRadioButton("Remote URL")
        self.radio_basemap_url.setToolTip("Fetch the basemap from a remote URL (e.g. build.protomaps.com). Requires internet during export.")
        self.radio_basemap_file = QRadioButton("Local file")
        self.radio_basemap_file.setToolTip("Use a locally downloaded .pmtiles file as the basemap source.")
        self.radio_basemap_url.setChecked(True)
        self._basemap_source_group = QButtonGroup()
        self._basemap_source_group.addButton(self.radio_basemap_url)
        self._basemap_source_group.addButton(self.radio_basemap_file)
        source_type_layout.addWidget(self.radio_basemap_url)
        source_type_layout.addWidget(self.radio_basemap_file)
        source_type_layout.addStretch()
        self._basemap_srctype_widget.setVisible(False)  # stream is the default
        basemap_layout.addWidget(self._basemap_srctype_widget)

        # Source URL / file path row
        basemap_src_layout = QHBoxLayout()
        self.txt_basemap_source = QLineEdit()
        self.txt_basemap_source.setPlaceholderText(
            "https://build.protomaps.com/20260217.pmtiles"
        )
        self.txt_basemap_source.setToolTip(
            "URL or local path to a Protomaps .pmtiles archive.\n"
            "Tiles within the export bounding box will be extracted\n"
            "to data/basemap.pmtiles in the output folder."
        )
        self.btn_basemap_test = QPushButton("Test")
        self.btn_basemap_test.setMaximumWidth(48)
        self.btn_basemap_test.setToolTip(
            "Check that the basemap source is reachable (URL) or exists (local file)\n"
            "before you export."
        )
        self.btn_basemap_test.clicked.connect(self._test_basemap_source)
        self.btn_basemap_browse = QPushButton("Browse...")
        self.btn_basemap_browse.setVisible(False)
        self.btn_basemap_browse.clicked.connect(self._browse_basemap_file)
        basemap_src_layout.addWidget(self.txt_basemap_source, 1)
        basemap_src_layout.addWidget(self.btn_basemap_test)
        basemap_src_layout.addWidget(self.btn_basemap_browse)
        basemap_layout.addLayout(basemap_src_layout)

        self.lbl_basemap_source_error = QLabel()
        self.lbl_basemap_source_error.setStyleSheet("color: red; font-size: 11px;")
        self.lbl_basemap_source_error.setVisible(False)
        self.lbl_basemap_source_error.setWordWrap(True)
        basemap_layout.addWidget(self.lbl_basemap_source_error)

        # Basemap style.json row
        basemap_style_layout = QHBoxLayout()
        basemap_style_layout.addWidget(QLabel("Basemap style:"))
        self.txt_basemap_style = QLineEdit()
        self.txt_basemap_style.setPlaceholderText("path/to/basemap_style.json")
        self.txt_basemap_style.setToolTip(
            "Path to a Protomaps-compatible MapLibre style.json.\n"
            "The basemap layers from this file are used as the base;\n"
            "your exported layers are overlaid on top."
        )
        self.btn_basemap_style_browse = QPushButton("Browse...")
        self.btn_basemap_style_browse.clicked.connect(self._browse_basemap_style)
        basemap_style_layout.addWidget(self.txt_basemap_style, 1)
        basemap_style_layout.addWidget(self.btn_basemap_style_browse)
        basemap_layout.addLayout(basemap_style_layout)

        bm_container = QWidget()
        bm_container.setVisible(False)
        bm_outer_layout = QVBoxLayout(bm_container)
        bm_outer_layout.setContentsMargins(16, 0, 0, 4)
        bm_outer_layout.setSpacing(0)
        bm_outer_layout.addWidget(self.basemap_group)
        scroll_layout.addWidget(bm_container)

        self._bm_toggle.toggled.connect(lambda checked: (
            bm_container.setVisible(checked),
            self._bm_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow),
        ))

        # Connect radio buttons to show/hide browse button
        self.radio_basemap_url.toggled.connect(self._on_basemap_source_type_changed)
        self.radio_basemap_file.toggled.connect(self._on_basemap_source_type_changed)
        self.radio_basemap_stream.toggled.connect(self._on_basemap_mode_changed)
        self.radio_basemap_bundle.toggled.connect(self._on_basemap_mode_changed)
        self.basemap_group.toggled.connect(self._update_tile_estimate)

        # (Output — project name + folder — now lives on the Inputs tab, beside
        # Layers and Export, so the whole required setup is on one screen.)

        # Finish scroll area → goes into Options tab
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        options_tab_layout.addWidget(scroll_area)

        # ==================== Advanced Options on Inputs tab (collapsible) ====================
        adv_separator = QFrame()
        adv_separator.setFrameShape(QFrame.Shape.HLine)
        adv_separator.setFrameShadow(QFrame.Shadow.Sunken)
        inputs_layout.addWidget(adv_separator)

        self._adv_toggle = QToolButton()
        self._adv_toggle.setText(" Advanced Options")
        self._adv_toggle.setCheckable(True)
        self._adv_toggle.setChecked(False)
        self._adv_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._adv_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._adv_toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        inputs_layout.addWidget(self._adv_toggle)

        adv_container = QWidget()
        adv_container.setVisible(False)
        adv_layout = QVBoxLayout(adv_container)
        adv_layout.setContentsMargins(16, 0, 0, 4)
        adv_layout.setSpacing(4)

        self.chk_style_only = QCheckBox("Style only (skip data export)")
        self.chk_style_only.setToolTip(
            "Export only style.json and HTML viewer without converting data.\n"
            "Use when data already exists or for quick style iteration."
        )
        adv_layout.addWidget(self.chk_style_only)

        self.chk_save_log = QCheckBox("Save export log to file (export.log)")
        self.chk_save_log.setChecked(False)
        self.chk_save_log.setToolTip("Write the full export log to export.log in the output folder for later review.")
        adv_layout.addWidget(self.chk_save_log)

        inputs_layout.addWidget(adv_container)

        self._adv_toggle.toggled.connect(lambda checked: (
            adv_container.setVisible(checked),
            self._adv_toggle.setArrowType(
                Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
            ),
        ))

        # ==================== Config Save/Load (Inputs tab, pinned) ====================
        cfg_separator = QFrame()
        cfg_separator.setFrameShape(QFrame.Shape.HLine)
        cfg_separator.setFrameShadow(QFrame.Shadow.Sunken)
        inputs_layout.addWidget(cfg_separator)

        config_btn_layout = QHBoxLayout()
        self.btn_save_config = QPushButton("Save Config...")
        self.btn_save_config.setToolTip("Save all current settings to a .toml config file for reuse.")
        self.btn_load_config = QPushButton("Load Config...")
        self.btn_load_config.setToolTip("Load settings from a previously saved .toml config file.")
        self.btn_save_config.clicked.connect(self._save_config)
        self.btn_load_config.clicked.connect(self._load_config)
        config_btn_layout.addWidget(self.btn_save_config)
        config_btn_layout.addWidget(self.btn_load_config)
        inputs_layout.addLayout(config_btn_layout)

        # ============ Readiness + Export (Inputs tab, pinned) ============
        # Live checklist so the user sees what's still missing BEFORE clicking
        # (the modal warnings in _validate_export remain as a backstop).
        self.lbl_readiness = QLabel("")
        self.lbl_readiness.setWordWrap(True)
        self.lbl_readiness.setStyleSheet("color: #1565c0; font-size: 11px;")
        inputs_layout.addWidget(self.lbl_readiness)

        export_btn_row = QHBoxLayout()

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
        export_btn_row.addWidget(self.btn_export, 1)

        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_open_folder.setMinimumHeight(40)
        self.btn_open_folder.setVisible(False)
        self.btn_open_folder.setToolTip("Open the last export output folder in the system file manager.")
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        export_btn_row.addWidget(self.btn_open_folder)

        inputs_layout.addLayout(export_btn_row)

        # --- Viewer tab ---
        viewer_tab = QWidget()
        viewer_layout = QVBoxLayout(viewer_tab)
        viewer_layout.setContentsMargins(8, 8, 8, 8)
        viewer_layout.setSpacing(6)

        viewer_group = QGroupBox("Map Controls")
        viewer_group_layout = QVBoxLayout(viewer_group)

        self.chk_viewer_scale_bar = QCheckBox("Scale bar")
        self.chk_viewer_scale_bar.setChecked(True)
        self.chk_viewer_scale_bar.setToolTip("Shows a distance scale bar in the bottom-left of the map.")
        viewer_group_layout.addWidget(self.chk_viewer_scale_bar)

        self.chk_viewer_geolocate = QCheckBox("Geolocate (show my location)")
        self.chk_viewer_geolocate.setChecked(True)
        self.chk_viewer_geolocate.setToolTip(
            "Adds a button to locate and follow the viewer's current GPS position.\n"
            "Requires browser location permission."
        )
        viewer_group_layout.addWidget(self.chk_viewer_geolocate)

        self.chk_viewer_fullscreen = QCheckBox("Fullscreen button")
        self.chk_viewer_fullscreen.setChecked(True)
        self.chk_viewer_fullscreen.setToolTip("Adds a button to toggle the map to full-screen mode.")
        viewer_group_layout.addWidget(self.chk_viewer_fullscreen)

        self.chk_viewer_coords = QCheckBox("Coordinate display (mouse position)")
        self.chk_viewer_coords.setChecked(True)
        self.chk_viewer_coords.setToolTip("Shows the longitude/latitude of the cursor position in the map corner.")
        viewer_group_layout.addWidget(self.chk_viewer_coords)

        self.chk_viewer_zoom_display = QCheckBox("Zoom level display")
        self.chk_viewer_zoom_display.setChecked(True)
        self.chk_viewer_zoom_display.setToolTip("Shows the current MapLibre zoom level in the map corner.")
        viewer_group_layout.addWidget(self.chk_viewer_zoom_display)

        self.chk_viewer_reset_view = QCheckBox("Reset view button (fit to data)")
        self.chk_viewer_reset_view.setChecked(True)
        self.chk_viewer_reset_view.setToolTip("Adds a button that resets the map view to fit all exported data.")
        viewer_group_layout.addWidget(self.chk_viewer_reset_view)

        self.chk_viewer_north_reset = QCheckBox("North-up / reset rotation button")
        self.chk_viewer_north_reset.setChecked(True)
        self.chk_viewer_north_reset.setToolTip("Adds a compass button that snaps the map back to north-up orientation.")
        viewer_group_layout.addWidget(self.chk_viewer_north_reset)

        # Label placement mode
        placement_row = QHBoxLayout()
        placement_row.addWidget(QLabel("Label placement:"))
        self.combo_label_placement = QComboBox()
        self.combo_label_placement.addItems([
            "Match QGIS (exact positions)",
            "Auto-place (avoid overlaps)",
        ])
        self.combo_label_placement.setToolTip(
            "Match QGIS: labels are placed at fixed coordinates matching QGIS output.\n"
            "Auto-place: MapLibre repositions labels dynamically to avoid overlaps at any zoom."
        )
        placement_row.addWidget(self.combo_label_placement)
        viewer_group_layout.addLayout(placement_row)

        self.chk_advanced_legend = QCheckBox("Advanced Legend (show categories and class breaks)")
        self.chk_advanced_legend.setChecked(False)
        self.chk_advanced_legend.setToolTip(
            "Show individual category swatches and class-break labels in the map legend.\n"
            "When unchecked, only the layer name is shown."
        )
        viewer_group_layout.addWidget(self.chk_advanced_legend)

        self.chk_viewer_measure = QCheckBox("Measure tool (distance & area)")
        self.chk_viewer_measure.setChecked(False)
        self.chk_viewer_measure.setToolTip(
            "Adds a ruler button to the map. Click to add points and measure distance;\n"
            "double-click to close a shape and measure area. Shows metric and imperial units."
        )
        viewer_group_layout.addWidget(self.chk_viewer_measure)

        # Attribution text
        attribution_row = QHBoxLayout()
        attribution_row.addWidget(QLabel("Attribution:"))
        self.txt_viewer_attribution = QLineEdit()
        self.txt_viewer_attribution.setPlaceholderText("© Your Organization")
        self.txt_viewer_attribution.setToolTip(
            "Custom attribution text shown in the map's attribution control.\n"
            "Leave blank to use the default MapLibre attribution."
        )
        attribution_row.addWidget(self.txt_viewer_attribution, 1)
        viewer_group_layout.addLayout(attribution_row)

        background_row = QHBoxLayout()
        background_row.addWidget(QLabel("Background:"))
        self.txt_viewer_background = QLineEdit()
        self.txt_viewer_background.setPlaceholderText("#ffffff (blank = no change)")
        self.txt_viewer_background.setToolTip(
            "Optional map background colour, as a hex value (e.g. #ffffff).\n"
            "Leave blank to keep the basemap's own background (or the default) unchanged."
        )
        background_row.addWidget(self.txt_viewer_background, 1)
        viewer_group_layout.addLayout(background_row)

        viewer_layout.addWidget(viewer_group)

        # Map Dimensions group
        dim_group = QGroupBox("Map Dimensions")
        dim_group_layout = QVBoxLayout(dim_group)

        # Preset dropdown
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.combo_dim_preset = QComboBox()
        for label, _w, _h in self._DIMENSION_PRESETS:
            self.combo_dim_preset.addItem(label)
        self.combo_dim_preset.setToolTip(
            "Select a preset to set the map's pixel dimensions.\n"
            "'Full window' makes the map fill the browser window responsively.\n"
            "Choose 'Custom' or edit the spinboxes directly for any other size."
        )
        self.combo_dim_preset.currentIndexChanged.connect(self._on_dimension_preset_changed)
        preset_row.addWidget(self.combo_dim_preset, 1)
        dim_group_layout.addLayout(preset_row)

        # Width / Height spinboxes
        dim_layout = QHBoxLayout()
        dim_layout.addWidget(QLabel("Width:"))
        self.spin_map_width = QSpinBox()
        self.spin_map_width.setRange(0, 9999)
        self.spin_map_width.setValue(0)
        self.spin_map_width.setSpecialValueText("responsive")
        self.spin_map_width.setSuffix(" px")
        self.spin_map_width.setToolTip("Map width in pixels. Set to 0 (responsive) to fill the browser window.")
        self.spin_map_width.valueChanged.connect(self._on_dimension_spinbox_changed)
        dim_layout.addWidget(self.spin_map_width)
        dim_layout.addSpacing(12)
        dim_layout.addWidget(QLabel("Height:"))
        self.spin_map_height = QSpinBox()
        self.spin_map_height.setRange(0, 9999)
        self.spin_map_height.setValue(0)
        self.spin_map_height.setSpecialValueText("responsive")
        self.spin_map_height.setSuffix(" px")
        self.spin_map_height.setToolTip("Map height in pixels. Set to 0 (responsive) to fill the browser window.")
        self.spin_map_height.valueChanged.connect(self._on_dimension_spinbox_changed)
        dim_layout.addWidget(self.spin_map_height)
        dim_layout.addStretch()
        dim_group_layout.addLayout(dim_layout)

        viewer_layout.addWidget(dim_group)
        viewer_layout.addStretch()

        # --- Log tab (progress + status at top, log text below) ---
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.setSpacing(4)

        # ==================== Progress (shown during export) ====================
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setToolTip("Cancel the running export. Any files already written will remain.")
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
        log_layout.addLayout(progress_layout)

        self.lbl_export_status = QLabel("")
        self.lbl_export_status.setVisible(False)
        self.lbl_export_status.setStyleSheet("color: gray; font-style: italic;")
        self.lbl_export_status.setWordWrap(True)
        log_layout.addWidget(self.lbl_export_status)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("font-family: monospace; font-size: 11px;")
        log_layout.addWidget(self.txt_log)

        # Version stamp — confirms at a glance which build QGIS actually loaded.
        self.lbl_version = QLabel(f"MapSplat v{self._plugin_version()}")
        self.lbl_version.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_version.setStyleSheet("color: gray; font-size: 10px;")
        log_layout.addWidget(self.lbl_version)

        # --- Offline tab ---
        offline_tab = QWidget()
        offline_layout = QVBoxLayout(offline_tab)
        offline_layout.setContentsMargins(8, 8, 8, 8)
        offline_layout.setSpacing(6)

        offline_group = QGroupBox("Offline Asset Bundling")
        offline_group_layout = QVBoxLayout(offline_group)

        self.chk_bundle_offline = QCheckBox("Bundle JS/CSS for offline viewing")
        self.chk_bundle_offline.setChecked(False)
        self.chk_bundle_offline.setToolTip(
            "Download MapLibre GL JS, its CSS, and PMTiles JS from unpkg.com at export time\n"
            "and save them to lib/ so the viewer works without an internet connection.\n"
            "If the download fails, CDN links are used instead."
        )
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

        # Register tabs: Inputs(0), Options(1), Viewer(2), Offline(3), Log(4)
        self.tabs.addTab(inputs_tab, "Inputs")
        self.tabs.addTab(options_tab, "Options")
        self.tabs.addTab(viewer_tab, "Viewer")
        self.tabs.addTab(offline_tab, "Offline")
        self.tabs.addTab(log_tab, "Log")

        # Connect all persistent-settings signals (all tabs — placed here after all widgets exist)
        for w in (
            self.chk_export_style, self.chk_save_log, self.chk_bundle_offline,
            self.chk_viewer_scale_bar, self.chk_viewer_geolocate,
            self.chk_viewer_fullscreen, self.chk_viewer_coords,
            self.chk_viewer_zoom_display, self.chk_viewer_reset_view,
            self.chk_viewer_north_reset, self.chk_advanced_legend,
            self.chk_viewer_measure,
        ):
            w.toggled.connect(self._save_settings)
        self.combo_export_mode.currentIndexChanged.connect(self._save_settings)
        self.combo_label_placement.currentIndexChanged.connect(self._save_settings)
        self.spin_map_width.valueChanged.connect(self._save_settings)
        self.spin_map_height.valueChanged.connect(self._save_settings)
        self.txt_viewer_attribution.editingFinished.connect(self._save_settings)
        self.txt_viewer_background.editingFinished.connect(self._save_settings)
        self.basemap_group.toggled.connect(self._save_settings)
        self.txt_basemap_source.editingFinished.connect(self._save_settings)
        self.txt_basemap_source.editingFinished.connect(self._validate_basemap_source)
        self.txt_basemap_style.editingFinished.connect(self._save_settings)
        self.radio_basemap_url.toggled.connect(self._save_settings)
        self.radio_basemap_file.toggled.connect(self._save_settings)
        self.basemap_group.toggled.connect(self._on_basemap_group_toggled)

        # Store imported style path
        self.imported_style_path = None

        # Log file handle (opened at export start, closed at finish)
        self._log_file = None

        # Remember last config directory for file dialogs
        self._last_config_dir = ""

        # Popup field visibility: {layer_id: [visible_field_names]} (empty list = show all)
        self._popup_fields = {}

        # Right-click context menu on the layer list for popup field configuration
        self.layer_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.layer_list.customContextMenuRequested.connect(self._on_layer_list_context_menu)

        # Restore all persisted settings (called after full UI setup and initial layer refresh)
        self._restoring = False

    def refresh_layer_list(self):
        """Refresh the layer list and extent combo from the current project.

        Signals are BLOCKED during the clear/rebuild: clearing a list that has a live
        selection emits itemSelectionChanged mid-mutation, whose slots read half-deleted
        items -> crash. Dependent UI is updated once afterwards, on a consistent state.
        Layers come from mapLayers() (layerOrder() is empty for gpkg-stored projects).
        """
        # Preserve the current selection (by layer id) so a manual Refresh keeps it.
        previously_selected = {
            self.layer_list.item(i).data(_UserRole)
            for i in range(self.layer_list.count())
            if self.layer_list.item(i).isSelected()
        }
        project = QgsProject.instance()
        blocked = self.layer_list.blockSignals(True)
        try:
            self.layer_list.clear()

            current_extent_id = self.combo_extent_layer.currentData()
            self.combo_extent_layer.clear()
            self.combo_extent_layer.addItem("Full extent of data", None)
            self.combo_extent_layer.addItem("Current map view", "__map_view__")

            for layer in list(project.mapLayers().values()):
                if layer is None or not layer.isValid():
                    continue
                name = layer.name()
                item = QListWidgetItem()

                # Layer type prefix (geometryType() is an enum on QGIS 4, int on QGIS 3)
                if isinstance(layer, QgsVectorLayer):
                    geom_type = int(layer.geometryType())
                    prefix = {0: "[Point]", 1: "[Line]", 2: "[Polygon]"}.get(geom_type, "[Vector]")
                elif isinstance(layer, QgsRasterLayer):
                    prefix = "[Raster]"
                else:
                    prefix = "[Other]"
                    item.setFlags(item.flags() & ~_ItemIsEnabled)

                item.setText(f"{prefix} {name}")
                item.setData(_UserRole, layer.id())

                warning = self._get_symbology_warning(layer)
                if warning:
                    warn_icon, warn_tip = warning
                    item.setIcon(warn_icon)
                    item.setToolTip(warn_tip)

                self.layer_list.addItem(item)
                self.combo_extent_layer.addItem(name, layer.id())

            # Restore previously selected extent layer; default to "Current map view"
            if current_extent_id is not None:
                idx = self.combo_extent_layer.findData(current_extent_id)
                if idx >= 0:
                    self.combo_extent_layer.setCurrentIndex(idx)
            else:
                self.combo_extent_layer.setCurrentIndex(
                    self.combo_extent_layer.findData("__map_view__")
                )

            # Restore prior selection for layers that still exist.
            if previously_selected:
                for i in range(self.layer_list.count()):
                    it = self.layer_list.item(i)
                    if it.flags() & _ItemIsEnabled and it.data(_UserRole) in previously_selected:
                        it.setSelected(True)

            # Zero-config: on the FIRST population with nothing carried over, preselect
            # the layers checked (visible) in the Layers panel, else the active layer.
            if not getattr(self, "_initial_selection_done", False):
                if not self.layer_list.selectedItems():
                    self._preselect_default_layers(project)
                self._initial_selection_done = True
        finally:
            self.layer_list.blockSignals(blocked)

        # Auto-populate project name from QGIS project
        project_name = project.baseName()
        if project_name and not self.txt_project_name.text():
            clean_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
            self.txt_project_name.setText(clean_name)

        # Dependent UI, updated once on the now-consistent state.
        self._update_layer_count()
        self._update_readiness()
        self._update_tile_estimate()

    def _preselect_default_layers(self, project):
        """Select the checked/visible layers (or the active layer) in the list."""
        preferred = {lyr.id() for lyr in project.layerTreeRoot().checkedLayers()}
        if not preferred:
            active = self.iface.activeLayer()
            if active is not None:
                preferred = {active.id()}
        if not preferred:
            return
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            if item.flags() & _ItemIsEnabled and item.data(_UserRole) in preferred:
                item.setSelected(True)

    def _prefill_defaults(self):
        """Seed still-empty required fields so the dock opens export-ready (runs once,
        after _restore_settings, and only fills a field that is still blank)."""
        if not self.txt_output_folder.text().strip():
            default_dir = QgsProject.instance().homePath()
            if not default_dir or not os.path.isdir(default_dir):
                default_dir = QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.DocumentsLocation
                )
            if default_dir and os.path.isdir(default_dir):
                self.txt_output_folder.setText(default_dir)

    def _run_readiness(self):
        """Return (is_ready, [missing]) mirroring the hard checks in _validate_export."""
        missing = []
        if not self.layer_list.selectedItems():
            missing.append("select a layer")
        if not self.txt_project_name.text().strip():
            missing.append("name the project")
        folder = self.txt_output_folder.text().strip()
        if not folder or not os.path.isdir(folder):
            missing.append("set an output folder")
        return (not missing, missing)

    def _update_readiness(self):
        """Refresh the readiness label + Export button enabled state."""
        if not hasattr(self, "lbl_readiness"):
            return
        ready, missing = self._run_readiness()
        self.btn_export.setEnabled(ready)
        if ready:
            self.lbl_readiness.setText("Ready to export")
            self.lbl_readiness.setStyleSheet("color: #2e7d32; font-size: 11px;")
        else:
            self.lbl_readiness.setText("To export: " + ", ".join(missing))
            self.lbl_readiness.setStyleSheet(
                "color: #1565c0; background-color: #e3f2fd;"
                "padding: 3px 6px; border-radius: 3px; font-size: 11px;"
            )

    def _get_symbology_warning(self, layer):
        """Return (icon, tooltip_text) if the layer uses symbology that won't translate well, else None."""
        if not isinstance(layer, QgsVectorLayer):
            return None
        renderer = layer.renderer()
        if renderer is None:
            return None

        r_type = renderer.type()
        warn_icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)

        if r_type == "heatmapRenderer":
            return (warn_icon, "Heatmap renderer: will export as circle markers, not a smooth heatmap")
        if r_type == "pointDisplacement":
            return (warn_icon, "Point displacement renderer: displaced positions are not preserved in PMTiles")
        if r_type == "pointCluster":
            return (warn_icon, "Point cluster renderer: clustering is not supported; all points will render at their original positions")

        # Collect CLONES of the symbols. cat.symbol()/rng.symbol()/rule.symbol() return
        # pointers OWNED by the temporary category/range/rule from the renderer; once
        # that temporary container is garbage-collected, those pointers dangle and
        # calling .symbolLayers() on one is a use-after-free that SEGFAULTS QGIS (hit on
        # a categorizedSymbol polygon layer). clone() gives Python-owned copies that stay
        # valid for the rest of this function.
        symbols = []
        if r_type == "singleSymbol":
            s = renderer.symbol()
            if s is not None:
                symbols.append(s.clone())
        elif r_type == "categorizedSymbol":
            for cat in renderer.categories():
                s = cat.symbol()
                if s is not None:
                    symbols.append(s.clone())
        elif r_type == "graduatedSymbol":
            for rng in renderer.ranges():
                s = rng.symbol()
                if s is not None:
                    symbols.append(s.clone())
        elif r_type == "RuleRenderer":
            for rule in renderer.rootRule().descendants():
                s = rule.symbol()
                if s is not None:
                    symbols.append(s.clone())

        for sym in symbols:
            for sym_layer in sym.symbolLayers():
                if sym_layer.layerType() == "FontMarker":
                    return (warn_icon, "Font marker: will render as a plain circle in the exported map")

        return None

    def _update_tile_estimate(self):
        """Update the live tile count and size estimate label."""
        selected = self.layer_list.selectedItems()
        if not selected:
            self.lbl_tile_estimate.setText("Select layers to see tile estimate")
            return

        project = QgsProject.instance()
        crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
        combined_bbox = None

        for item in selected:
            layer_id = item.data(_UserRole)
            layer = project.mapLayer(layer_id)
            if layer is None or layer.extent().isNull():
                continue
            try:
                xform = QgsCoordinateTransform(layer.crs(), crs_4326, project)
                bbox = xform.transformBoundingBox(layer.extent())
            except Exception:
                continue
            if combined_bbox is None:
                combined_bbox = bbox
            else:
                combined_bbox.combineExtentWith(bbox)

        if combined_bbox is None or combined_bbox.isEmpty():
            self.lbl_tile_estimate.setText("Cannot compute extent")
            return

        # Fraction of world area covered (Web Mercator world: 360° × 170.1°)
        world_area = 360.0 * 170.1
        bbox_w = max(0.0, min(combined_bbox.xMaximum(), 180) - max(combined_bbox.xMinimum(), -180))
        bbox_h = max(0.0, min(combined_bbox.yMaximum(), 85.05) - max(combined_bbox.yMinimum(), -85.05))
        fraction = min((bbox_w * bbox_h) / world_area, 1.0)

        max_zoom = self.spin_max_zoom.value()
        total_tiles = sum(max(1, round(fraction * (4 ** z))) for z in range(max_zoom + 1))

        # ~4 KB per tile (conservative midpoint estimate)
        est_bytes = total_tiles * 4096
        if est_bytes < 1024 * 1024:
            size_str = f"{est_bytes / 1024:.0f} KB"
        elif est_bytes < 1024 ** 3:
            size_str = f"{est_bytes / (1024 ** 2):.0f} MB"
        else:
            size_str = f"{est_bytes / (1024 ** 3):.1f} GB"

        if total_tiles < 1000:
            count_str = str(total_tiles)
        elif total_tiles < 1_000_000:
            count_str = f"{total_tiles / 1000:.0f}K"
        else:
            count_str = f"{total_tiles / 1_000_000:.1f}M"

        basemap_note = " + basemap (size unknown)" if self.basemap_group.isChecked() else ""
        self.lbl_tile_estimate.setText(f"~{count_str} tiles · est. {size_str}{basemap_note}")

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
        """Update the 'X of Y layers selected' label (with an empty-state hint)."""
        total = self.layer_list.count()
        selected = len(self.layer_list.selectedItems())
        if total == 0:
            self.lbl_layer_count.setText("No layers in this project — add one in QGIS, then click Refresh.")
        else:
            self.lbl_layer_count.setText(f"{selected} of {total} layers selected")

    def _capture_canvas_bounds(self):
        """Return current map canvas extent as [W, S, E, N] in EPSG:4326.

        Must be called on the main thread (iface/canvas are not thread-safe).
        """
        canvas = self.iface.mapCanvas()
        canvas_extent = canvas.extent()
        canvas_crs = canvas.mapSettings().destinationCrs()
        crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
        if canvas_crs != crs_4326:
            transform = QgsCoordinateTransform(canvas_crs, crs_4326, QgsProject.instance())
            extent_4326 = transform.transformBoundingBox(canvas_extent)
        else:
            extent_4326 = canvas_extent
        return [
            extent_4326.xMinimum(),
            extent_4326.yMinimum(),
            extent_4326.xMaximum(),
            extent_4326.yMaximum(),
        ]

    def _save_settings(self, *_):
        """Persist all UI state to QgsSettings (profile-scoped)."""
        if self._restoring:
            return
        s = QgsSettings()
        s.beginGroup("MapSplat")
        s.setValue("output_folder", self.txt_output_folder.text().strip())
        s.setValue("last_config_dir", self._last_config_dir)
        s.setValue("export_mode", self.combo_export_mode.currentIndex())
        s.setValue("max_zoom", self.spin_max_zoom.value())
        s.setValue("export_style_json", self.chk_export_style.isChecked())
        s.setValue("save_log", self.chk_save_log.isChecked())
        s.setValue("bundle_offline", self.chk_bundle_offline.isChecked())
        s.setValue("label_placement", self.combo_label_placement.currentIndex())
        s.setValue("advanced_legend", self.chk_advanced_legend.isChecked())
        s.setValue("map_width", self.spin_map_width.value())
        s.setValue("map_height", self.spin_map_height.value())
        s.setValue("viewer_scale_bar", self.chk_viewer_scale_bar.isChecked())
        s.setValue("viewer_geolocate", self.chk_viewer_geolocate.isChecked())
        s.setValue("viewer_fullscreen", self.chk_viewer_fullscreen.isChecked())
        s.setValue("viewer_coords", self.chk_viewer_coords.isChecked())
        s.setValue("viewer_zoom_display", self.chk_viewer_zoom_display.isChecked())
        s.setValue("viewer_reset_view", self.chk_viewer_reset_view.isChecked())
        s.setValue("viewer_north_reset", self.chk_viewer_north_reset.isChecked())
        s.setValue("viewer_measure", self.chk_viewer_measure.isChecked())
        s.setValue("viewer_attribution", self.txt_viewer_attribution.text())
        s.setValue("viewer_background_color", self.txt_viewer_background.text())
        s.setValue("basemap_enabled", self.basemap_group.isChecked())
        s.setValue("basemap_mode", "stream" if self.radio_basemap_stream.isChecked() else "bundle")
        s.setValue("basemap_source_type", "file" if self.radio_basemap_file.isChecked() else "url")
        s.setValue("basemap_source", self.txt_basemap_source.text().strip())
        s.setValue("basemap_style_path", self.txt_basemap_style.text().strip())
        s.endGroup()

    def _restore_settings(self):
        """Restore UI state from QgsSettings. Called once after UI is fully built."""
        self._restoring = True
        try:
            s = QgsSettings()
            s.beginGroup("MapSplat")

            folder = s.value("output_folder", "")
            if folder and os.path.isdir(folder):
                self.txt_output_folder.setText(folder)

            self._last_config_dir = s.value("last_config_dir", "")

            mode = s.value("export_mode", None)
            if mode is not None:
                self.combo_export_mode.setCurrentIndex(int(mode))

            zoom = s.value("max_zoom", None)
            if zoom is not None:
                self.spin_max_zoom.setValue(int(zoom))

            # Boolean checkboxes
            bool_widgets = [
                ("export_style_json", self.chk_export_style),
                ("save_log", self.chk_save_log),
                ("bundle_offline", self.chk_bundle_offline),
                ("advanced_legend", self.chk_advanced_legend),
                ("viewer_scale_bar", self.chk_viewer_scale_bar),
                ("viewer_geolocate", self.chk_viewer_geolocate),
                ("viewer_fullscreen", self.chk_viewer_fullscreen),
                ("viewer_coords", self.chk_viewer_coords),
                ("viewer_zoom_display", self.chk_viewer_zoom_display),
                ("viewer_reset_view", self.chk_viewer_reset_view),
                ("viewer_north_reset", self.chk_viewer_north_reset),
                ("viewer_measure", self.chk_viewer_measure),
            ]
            for key, widget in bool_widgets:
                val = s.value(key, None)
                if val is not None:
                    widget.setChecked(val is True or val == "true")

            placement = s.value("label_placement", None)
            if placement is not None:
                self.combo_label_placement.setCurrentIndex(int(placement))

            width = s.value("map_width", None)
            if width is not None:
                self.spin_map_width.setValue(int(width))

            height = s.value("map_height", None)
            if height is not None:
                self.spin_map_height.setValue(int(height))

            basemap_enabled = s.value("basemap_enabled", None)
            if basemap_enabled is not None:
                enabled = basemap_enabled is True or basemap_enabled == "true"
                self.basemap_group.setChecked(enabled)
                if enabled:
                    self._bm_toggle.setChecked(True)

            src_type = s.value("basemap_source_type", None)
            if src_type == "file":
                self.radio_basemap_file.setChecked(True)
            elif src_type == "url":
                self.radio_basemap_url.setChecked(True)

            basemap_mode = s.value("basemap_mode", None)
            if basemap_mode == "bundle":
                self.radio_basemap_bundle.setChecked(True)
            else:
                self.radio_basemap_stream.setChecked(True)
            self._on_basemap_mode_changed()

            src = s.value("basemap_source", "")
            if src:
                self.txt_basemap_source.setText(src)

            style_path = s.value("basemap_style_path", "")
            if style_path:
                self.txt_basemap_style.setText(style_path)

            attribution = s.value("viewer_attribution", "")
            if attribution:
                self.txt_viewer_attribution.setText(attribution)

            background_color = s.value("viewer_background_color", "")
            if background_color:
                self.txt_viewer_background.setText(background_color)

            s.endGroup()
        finally:
            self._restoring = False

    def _check_pmtiles_cli(self):
        """Check pmtiles CLI is on PATH; show install dialog if missing. Returns True if OK."""
        import shutil
        if shutil.which("pmtiles") is not None:
            return True
        QMessageBox.warning(
            self,
            "pmtiles CLI Not Found",
            "<b>The <code>pmtiles</code> command-line tool was not found on PATH.</b><br><br>"
            "It is required for Basemap Overlay extraction. Download and install it from:<br>"
            "<a href='https://github.com/protomaps/go-pmtiles/releases'>"
            "github.com/protomaps/go-pmtiles/releases</a><br><br>"
            "After installing, restart QGIS so the updated PATH is visible to the plugin."
        )
        return False

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

    def _on_dimension_preset_changed(self, index):
        """Apply the selected dimension preset to the width/height spinboxes."""
        _label, w, h = self._DIMENSION_PRESETS[index]
        if w is None:
            return  # Custom — leave spinboxes untouched
        self._applying_preset = True
        self.spin_map_width.setValue(w)
        self.spin_map_height.setValue(h)
        self._applying_preset = False

    def _on_dimension_spinbox_changed(self):
        """Switch combo to Custom when the user edits a spinbox directly."""
        if getattr(self, '_applying_preset', False):
            return
        custom_index = len(self._DIMENSION_PRESETS) - 1
        if self.combo_dim_preset.currentIndex() != custom_index:
            self.combo_dim_preset.setCurrentIndex(custom_index)

    def _on_basemap_source_type_changed(self):
        """Show/hide browse button based on source type selection."""
        is_file = self.radio_basemap_file.isChecked()
        self.btn_basemap_browse.setVisible(is_file)
        if is_file:
            self.txt_basemap_source.setPlaceholderText("path/to/basemap.pmtiles")
        else:
            self.txt_basemap_source.setPlaceholderText(
                "https://build.protomaps.com/20260401.pmtiles"
            )

    def _on_basemap_mode_changed(self):
        """Stream mode is URL-only (no CLI); bundle mode exposes the URL/file choice."""
        if not hasattr(self, "_basemap_srctype_widget"):
            return
        stream = self.radio_basemap_stream.isChecked()
        self._basemap_srctype_widget.setVisible(not stream)
        if stream:
            self.radio_basemap_url.setChecked(True)  # streaming always reads a URL
        self._on_basemap_source_type_changed()
        if not self._restoring:
            self._save_settings()

    def _test_basemap_source(self):
        """Check the basemap source is reachable (URL) or exists (file); report inline."""
        source = self.txt_basemap_source.text().strip()
        if not source:
            self._show_basemap_test("Enter a basemap URL or file path first.", ok=False)
            return
        if source.startswith(("http://", "https://")):
            import urllib.request
            try:
                req = urllib.request.Request(source, method="HEAD")
                with urllib.request.urlopen(req, timeout=6):  # nosec B310 - scheme checked above
                    pass
                self._show_basemap_test("Reachable — the URL responds.", ok=True)
            except Exception as exc:
                self._show_basemap_test(f"Not reachable: {exc}", ok=False)
        elif os.path.isfile(source):
            self._show_basemap_test("File found.", ok=True)
        else:
            self._show_basemap_test("File not found.", ok=False)

    def _show_basemap_test(self, msg, ok):
        """Show a basemap source test result (green ok / red problem)."""
        colour = "#2e7d32" if ok else "#c62828"
        self.lbl_basemap_source_error.setText(msg)
        self.lbl_basemap_source_error.setStyleSheet(f"color: {colour}; font-size: 11px;")
        self.lbl_basemap_source_error.setVisible(True)

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

    def _plugin_version(self):
        """Read the plugin version from metadata.txt (best-effort)."""
        try:
            meta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.txt")
            with open(meta, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("version="):
                        return line.split("=", 1)[1].strip()
        except Exception:
            pass
        return "unknown"

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

            if self.radio_basemap_stream.isChecked():
                # Stream mode: the viewer reads the URL live, so it must be a web URL.
                if not basemap_source.startswith(("http://", "https://")):
                    QMessageBox.warning(self, "Basemap URL Required",
                                        "Stream mode needs a basemap URL (http/https).\n"
                                        "Use 'Download & clip offline' mode for a local file.")
                    return False
            elif self.radio_basemap_file.isChecked() and not os.path.isfile(basemap_source):
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
                    f"\n--- Export run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                    f"(MapSplat {self._plugin_version()}) ---\n"
                )
            except OSError as e:
                self._log_file = None
                self._log(f"Warning: could not open log file: {e}", "warning")

        self._log(f"MapSplat version {self._plugin_version()}", "info")
        self._log("Starting export...", "info")
        self.tabs.setCurrentIndex(4)  # Log tab

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
            "basemap_mode": "stream" if self.radio_basemap_stream.isChecked() else "bundle",
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
            "viewer_measure": self.chk_viewer_measure.isChecked(),
            "bundle_offline": self.chk_bundle_offline.isChecked(),
            "label_placement_mode": (
                "exact" if self.combo_label_placement.currentIndex() == 0 else "auto"
            ),
            "advanced_legend": self.chk_advanced_legend.isChecked(),
            "map_width": self.spin_map_width.value(),
            "map_height": self.spin_map_height.value(),
            "attribution": self.txt_viewer_attribution.text().strip(),
            "background_color": self.txt_viewer_background.text().strip(),
            "popup_fields": self._popup_fields_by_name(),
            "extent_layer_id": (
                None if self.combo_extent_layer.currentData() == "__map_view__"
                else self.combo_extent_layer.currentData()
            ),
        }

        # Capture canvas extent on main thread before handing off to worker
        if self.combo_extent_layer.currentData() == "__map_view__":
            settings["extent_bounds"] = self._capture_canvas_bounds()

        # Check pmtiles CLI early on main thread so we can show a dialog
        if self.basemap_group.isChecked() and not self.chk_style_only.isChecked():
            if not self._check_pmtiles_cli():
                return

        # Show progress and cancel button; hide Open Folder from previous run
        self.btn_open_folder.setVisible(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_export.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.lbl_export_status.setText("Starting export...")
        self.lbl_export_status.setVisible(True)

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
        # Show top-level info messages (not indented sub-step lines) as status text
        if level == "info" and not message.startswith("  "):
            self.lbl_export_status.setText(message)

    def _on_export_finished(self, success, output_path):
        """Handle export completion."""
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)  # Re-enable for next export
        self.btn_export.setEnabled(True)
        self.lbl_export_status.setVisible(False)

        if success:
            self._last_output_path = output_path
            self.btn_open_folder.setVisible(True)
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

    def _open_output_folder(self):
        """Open the last export output folder in the system file manager."""
        if hasattr(self, '_last_output_path') and self._last_output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_output_path))

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
        self._save_settings()

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
                "mode": "stream" if self.radio_basemap_stream.isChecked() else "bundle",
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
                "measure": self.chk_viewer_measure.isChecked(),
                "label_placement_mode": (
                    "exact" if self.combo_label_placement.currentIndex() == 0 else "auto"
                ),
                "advanced_legend": self.chk_advanced_legend.isChecked(),
                "map_width": self.spin_map_width.value(),
                "map_height": self.spin_map_height.value(),
                "attribution": self.txt_viewer_attribution.text().strip(),
                "background_color": self.txt_viewer_background.text().strip(),
            },
            "popup": self._popup_fields_for_config(),
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
        self._save_settings()

        try:
            config_dict = config_manager.read_config(file_path)
        except (FileNotFoundError, ValueError) as e:
            self._log(f"Failed to load config: {e}", "error")
            return

        # Ensure layer list reflects current project state before applying config
        self.refresh_layer_list()

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
            matched_names = set()
            project = QgsProject.instance()
            for i in range(self.layer_list.count()):
                item = self.layer_list.item(i)
                layer_id = item.data(_UserRole)
                layer = project.mapLayer(layer_id)
                if layer and layer.name() in saved_names:
                    item.setSelected(True)
                    matched_names.add(layer.name())
                else:
                    item.setSelected(False)
            missing = saved_names - matched_names
            if missing:
                missing_list = "\n".join(f"  • {n}" for n in sorted(missing))
                QMessageBox.warning(
                    self,
                    "Missing Layers",
                    f"The following layers from the config were not found in the current project "
                    f"and could not be selected:\n\n{missing_list}",
                )
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

        if "mode" in basemap:
            if basemap["mode"] == "bundle":
                self.radio_basemap_bundle.setChecked(True)
            else:
                self.radio_basemap_stream.setChecked(True)
            self._on_basemap_mode_changed()
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
            "measure": self.chk_viewer_measure,
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

        if "attribution" in viewer:
            self.txt_viewer_attribution.setText(viewer["attribution"])
            applied += 1

        if "background_color" in viewer:
            self.txt_viewer_background.setText(viewer["background_color"])
            applied += 1

        # --- [popup] section ---
        popup = config_dict.get("popup", {})
        if popup:
            project = QgsProject.instance()
            self._popup_fields = {}
            for layer_name, fields in popup.items():
                for lyr in project.mapLayersByName(layer_name):
                    self._popup_fields[lyr.id()] = list(fields)
                    break  # use first match
            applied += 1

        self._log(f"Config loaded: {applied} settings applied from {file_path}", "info")
        # Persist config values so they survive the next session
        self._save_settings()

    # ------------------------------------------------------------------
    # Basemap source validation (Feature 3)
    # ------------------------------------------------------------------

    def _on_basemap_group_toggled(self, checked):
        """Hide validation error when basemap is disabled."""
        if not checked:
            self.lbl_basemap_source_error.setVisible(False)

    def _validate_basemap_source(self):
        """Validate the basemap source URL or file path on focus-out."""
        if not self.basemap_group.isChecked():
            self.lbl_basemap_source_error.setVisible(False)
            return

        source = self.txt_basemap_source.text().strip()
        if not source:
            self.lbl_basemap_source_error.setVisible(False)
            return

        is_url = source.startswith("http://") or source.startswith("https://")
        if is_url:
            import urllib.request
            try:
                req = urllib.request.Request(source, method="HEAD")
                with urllib.request.urlopen(req, timeout=3):  # nosec B310 - scheme restricted to http/https above
                    pass
                self.lbl_basemap_source_error.setVisible(False)
            except Exception as exc:
                self.lbl_basemap_source_error.setText(f"URL unreachable: {exc}")
                self.lbl_basemap_source_error.setVisible(True)
        else:
            if os.path.isfile(source):
                self.lbl_basemap_source_error.setVisible(False)
            else:
                self.lbl_basemap_source_error.setText("File not found.")
                self.lbl_basemap_source_error.setVisible(True)

    # ------------------------------------------------------------------
    # Popup field customization (Feature 4)
    # ------------------------------------------------------------------

    def _on_layer_list_context_menu(self, pos):
        """Show context menu on right-click in the layer list."""
        item = self.layer_list.itemAt(pos)
        if item is None:
            return

        layer_id = item.data(_UserRole)
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)
        if not isinstance(layer, QgsVectorLayer):
            return

        menu = QMenu(self)
        action = menu.addAction(f"Configure popup fields for '{layer.name()}'...")
        if menu.exec(self.layer_list.viewport().mapToGlobal(pos)) == action:
            self._configure_popup_fields(layer_id)

    def _configure_popup_fields(self, layer_id):
        """Open a dialog to choose which fields appear in the click popup."""
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)
        if not isinstance(layer, QgsVectorLayer):
            return

        all_fields = [f.name() for f in layer.fields()]
        current = self._popup_fields.get(layer_id, all_fields)
        visible = set(current)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Popup Fields - {layer.name()}")
        dlg.resize(320, 360)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Select fields to show in the feature popup:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(2)

        checkboxes = {}
        for fname in all_fields:
            cb = QCheckBox(fname)
            cb.setChecked(fname in visible)
            inner_layout.addWidget(cb)
            checkboxes[fname] = cb

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        # Select all / None buttons
        btn_row = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_none = QPushButton("Select None")
        btn_all.clicked.connect(lambda: [cb.setChecked(True) for cb in checkboxes.values()])
        btn_none.clicked.connect(lambda: [cb.setChecked(False) for cb in checkboxes.values()])
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = [fname for fname, cb in checkboxes.items() if cb.isChecked()]
            if set(selected) == set(all_fields):
                # All fields selected means no filtering; remove entry to keep dict clean
                self._popup_fields.pop(layer_id, None)
            else:
                self._popup_fields[layer_id] = selected

    def _popup_fields_by_name(self):
        """Return popup_fields keyed by sanitized source-layer name for the exporter."""
        result = {}
        project = QgsProject.instance()
        for layer_id, fields in self._popup_fields.items():
            layer = project.mapLayer(layer_id)
            if layer:
                sanitized = "".join(
                    c if c.isalnum() or c == "_" else "_" for c in layer.name()
                )
                while "__" in sanitized:
                    sanitized = sanitized.replace("__", "_")
                sanitized = sanitized.strip("_")
                result[sanitized] = fields
        return result

    def _popup_fields_for_config(self):
        """Return popup_fields keyed by original layer name for config file storage."""
        result = {}
        project = QgsProject.instance()
        for layer_id, fields in self._popup_fields.items():
            layer = project.mapLayer(layer_id)
            if layer:
                result[layer.name()] = fields
        return result

    def closeEvent(self, event):
        """Handle close event."""
        self.closingPlugin.emit()
        event.accept()
