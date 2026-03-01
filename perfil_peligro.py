import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from .perfil_peligro_dialog import PerfilPeligroDialog

class PerfilPeligro:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.icon_path = os.path.join(self.plugin_dir, "icono2.png")
        self.dlg = None # Referencia persistente para evitar errores de Python

    def initGui(self):
        self.action = QAction(
            QIcon(self.icon_path),
            "Perfil Topográfico con Peligro",
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Perfil Peligro", self.action)

    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("&Perfil Peligro", self.action)

    def run(self):
        # Evita que se abran múltiples instancias y previene el error de ejecución
        if self.dlg is None:
            self.dlg = PerfilPeligroDialog(self.iface.mainWindow())
        
        if self.dlg.isVisible():
            self.dlg.activateWindow()
            self.dlg.raise_()
        else:
            self.dlg.show()