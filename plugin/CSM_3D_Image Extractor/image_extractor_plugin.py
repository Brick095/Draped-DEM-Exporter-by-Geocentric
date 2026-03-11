import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

class ImageExtractorPlugin:
    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), 'icon.png'))
        self.action = QAction(icon, "Image Extractor", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("Image Extractor", self.action)

    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("Image Extractor", self.action)

    def run(self):
        from .image_extractor_dialog import ImageExtractorDialog
        dlg = ImageExtractorDialog()
        dlg.exec()