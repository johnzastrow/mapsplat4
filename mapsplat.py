"""
MapSplat - Main Plugin Class

This module contains the main plugin class that handles QGIS integration,
menu items, toolbar buttons, and the dockable widget.
"""

__version__ = "0.6.16"

import os

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon

# Qt6 compatibility: QAction moved from QtWidgets to QtGui
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from qgis.PyQt.QtWidgets import QDockWidget

from qgis.core import QgsProject

from .mapsplat_dockwidget import MapSplatDockWidget

# Qt6 compatibility: handle scoped enums
try:
    # Qt6 style
    _RightDockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea
except AttributeError:
    # Qt5 style
    _RightDockWidgetArea = Qt.RightDockWidgetArea


class MapSplat:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # Initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'mapsplat_{locale}.qm'
        )

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr('&MapSplat')
        self.toolbar = self.iface.addToolBar('MapSplat')
        self.toolbar.setObjectName('MapSplat')

        # Dockwidget
        self.dockwidget = None
        self.pluginIsActive = False

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        :param message: String for translation.
        :type message: str

        :returns: Translated version of message.
        :rtype: str
        """
        return QCoreApplication.translate('MapSplat', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action.
        :param text: Text that should be shown in menu items for this action.
        :param callback: Function to be called when the action is triggered.
        :param enabled_flag: A flag indicating if the action should be enabled.
        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu.
        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar.
        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.
        :param parent: Parent widget for the new action.
        :returns: The action that was created.
        :rtype: QAction
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(
                self.menu,
                action
            )

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr('MapSplat - Export to Web Map'),
            callback=self.run,
            parent=self.iface.mainWindow(),
            status_tip=self.tr('Export project to static web map')
        )

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed."""
        # Disconnects
        if self.dockwidget:
            self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        self.pluginIsActive = False

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr('&MapSplat'),
                action
            )
            self.iface.removeToolBarIcon(action)

        # Remove the toolbar
        del self.toolbar

        # Remove dockwidget
        if self.dockwidget:
            self.iface.removeDockWidget(self.dockwidget)

    def run(self):
        """Run method that loads and starts the plugin."""
        if not self.pluginIsActive:
            self.pluginIsActive = True

            # Create the dockwidget if it doesn't exist
            if self.dockwidget is None:
                self.dockwidget = MapSplatDockWidget(self.iface)

            # Connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # Show the dockwidget
            self.iface.addDockWidget(_RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
