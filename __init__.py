def classFactory(iface):
    from .image_extractor_plugin import ImageExtractorPlugin
    return ImageExtractorPlugin(iface)