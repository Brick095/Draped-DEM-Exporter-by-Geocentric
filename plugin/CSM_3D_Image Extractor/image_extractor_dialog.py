import os
from pathlib import Path
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QPolygonF  
from qgis.PyQt.QtCore import QSize, QPointF, Qt                  
from qgis.core import (
    QgsProject,
    QgsMapSettings,
    QgsMapRendererParallelJob,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsRectangle,
    QgsMapLayerProxyModel,
    QgsRasterLayer,
    QgsVectorLayer,
)
from qgis.utils import iface
import processing


UI_PATH = os.path.join(os.path.dirname(__file__), 'Image Extractor UI.ui')
FORM_CLASS, _ = uic.loadUiType(UI_PATH)



def get_aoi_bounds_in_crs(clipping_layer, target_crs_epsg, transform_context):
    src_crs     = clipping_layer.crs()
    dest_crs    = QgsCoordinateReferenceSystem(target_crs_epsg)
    coord_xform = QgsCoordinateTransform(src_crs, dest_crs, transform_context)
    combined_extent = QgsRectangle()
    for feat in clipping_layer.getFeatures():
        geom = QgsGeometry(feat.geometry())
        geom.transform(coord_xform)
        if combined_extent.isNull():
            combined_extent = geom.boundingBox()
        else:
            combined_extent.combineExtentWith(geom.boundingBox())
    return combined_extent


def render_imagery_to_extent(visible_layers, extent, output_size, dest_crs_epsg):
    map_settings = QgsMapSettings()
    map_settings.setLayers(visible_layers)
    map_settings.setExtent(extent)
    map_settings.setOutputSize(output_size)
    map_settings.setDestinationCrs(QgsCoordinateReferenceSystem(dest_crs_epsg))
    job = QgsMapRendererParallelJob(map_settings)
    job.start()
    job.waitForFinished()
    return job.renderedImage(), job.mapSettings()


def create_aoi_mask(clipping_layer, image_size, map_settings, clipping_crs_epsg):
    width, height = image_size.width(), image_size.height()
    mask = QImage(width, height, QImage.Format.Format_ARGB32)   
    mask.fill(0)
    painter = QPainter(mask)
    painter.setPen(Qt.PenStyle.NoPen)                           
    painter.setBrush(Qt.GlobalColor.white)                      
    transform_context = QgsProject.instance().transformContext()
    src_crs     = clipping_layer.crs()
    dest_crs    = map_settings.destinationCrs()
    coord_xform = QgsCoordinateTransform(src_crs, dest_crs, transform_context)
    pixel_xform = map_settings.mapToPixel()
    for feat in clipping_layer.getFeatures():
        geom = QgsGeometry(feat.geometry())
        geom.transform(coord_xform)
        all_polys = geom.asMultiPolygon() if geom.isMultipart() else [geom.asPolygon()]
        for poly in all_polys:
            for ring in poly:
                qpoints = [pixel_xform.transform(pt) for pt in ring]
                qp = QPolygonF([QPointF(pt.x(), pt.y()) for pt in qpoints])
                painter.drawPolygon(qp)
    painter.end()
    return mask


def apply_mask_to_image(image, mask):
    for x in range(image.width()):
        for y in range(image.height()):
            if mask.pixelColor(x, y).alpha() == 0:
                image.setPixelColor(x, y, QColor(0, 0, 0, 0))
    return image


def get_opaque_bounds(image):
    width, height = image.width(), image.height()
    min_x, min_y  = width, height
    max_x = max_y = 0
    for x in range(width):
        for y in range(height):
            if image.pixelColor(x, y).alpha() != 0:
                min_x = min(min_x, x); min_y = min(min_y, y)
                max_x = max(max_x, x); max_y = max(max_y, y)
    return (min_x, min_y, max_x, max_y) if min_x <= max_x and min_y <= max_y else None


def pixel_bounds_to_geo_extent(pixel_bounds, map_settings):
    min_x, min_y, max_x, max_y = pixel_bounds
    pixel_xform  = map_settings.mapToPixel()
    top_left     = pixel_xform.toMapCoordinates(min_x, min_y)
    bottom_right = pixel_xform.toMapCoordinates(max_x + 1, max_y + 1)
    return QgsRectangle(top_left.x(), bottom_right.y(), bottom_right.x(), top_left.y())


def clip_dem_to_extent(dem_layer, extent, output_path, output_crs_epsg,
                       render_crs_epsg, output_size=None):
    transform_context = QgsProject.instance().transformContext()
    src_crs       = QgsCoordinateReferenceSystem(render_crs_epsg)
    dest_crs      = QgsCoordinateReferenceSystem(output_crs_epsg)
    coord_xform   = QgsCoordinateTransform(src_crs, dest_crs, transform_context)
    output_extent = coord_xform.transformBoundingBox(extent)
    extent_str = (f"{output_extent.xMinimum()},{output_extent.xMaximum()},"
                  f"{output_extent.yMinimum()},{output_extent.yMaximum()}")
    params = {
        'INPUT': dem_layer,
        'SOURCE_CRS': dem_layer.crs(),
        'TARGET_CRS': QgsCoordinateReferenceSystem(output_crs_epsg),
        'RESAMPLING': 0, 'NODATA': -9999, 'TARGET_RESOLUTION': None,
        'OPTIONS': '', 'DATA_TYPE': 0,
        'TARGET_EXTENT': extent_str,
        'TARGET_EXTENT_CRS': QgsCoordinateReferenceSystem(output_crs_epsg),
        'MULTITHREADING': True, 'OUTPUT': output_path
    }
    if output_size is not None:
        x_res = (output_extent.xMaximum() - output_extent.xMinimum()) / output_size.width()
        y_res = (output_extent.yMaximum() - output_extent.yMinimum()) / output_size.height()
        params['TARGET_RESOLUTION'] = min(x_res, y_res)
    result = processing.run("gdal:warpreproject", params)
    return result['OUTPUT'], output_extent



class ImageExtractorDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # ── Filter dropdowns to correct layer types ───────────────────────────
        self.mMapLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)    # Basemap
        self.mMapLayerComboBox_3.setFilters(QgsMapLayerProxyModel.RasterLayer)  # DEM
        self.mMapLayerComboBox_2.setFilters(QgsMapLayerProxyModel.VectorLayer)  # Cropping Extent

        # ── Initialise progress bar ───────────────────────────────────────────
        self.progressBar.setValue(0)

        # ── Wire buttons ─────────────────────────────────────────────────────
        self.buttonBox.accepted.connect(self.run)
        self.buttonBox.rejected.connect(self.close)

    def _set_progress(self, value, label=None):
        self.progressBar.setValue(value)
        QtWidgets.QApplication.processEvents() 
        if label:
            print(label)

    def _get_params(self):
        """
        ──────────────────────────────────────────────────────────────────────
        mMapLayerComboBox               (Basemap)            → imagery_layer
        mMapLayerComboBox_3             (DEM)                → dem_layer
        mMapLayerComboBox_2             (Cropping Extent)    → clipping_layer
        mQgsFileWidget_2                (Output Folder)      → output_folder
        lineEdit                        (Output Name)        → output_name
        mQgsProjectionSelectionWidget   (Output CRS)         → output_crs_epsg
        mQgsProjectionSelectionWidget_2 (Cropping layer CRS) → clipping_crs_epsg
        mQgsProjectionSelectionWidget_3 (Basemap CRS)        → render_crs_epsg
        """
        return {
            "imagery_layer":     self.mMapLayerComboBox.currentLayer(),
            "dem_layer":         self.mMapLayerComboBox_3.currentLayer(),
            "clipping_layer":    self.mMapLayerComboBox_2.currentLayer(),
            "output_folder":     self.mQgsFileWidget_2.filePath(),
            "output_name":       self.lineEdit.text().strip() or "TIFF",
            "output_crs_epsg":   self.mQgsProjectionSelectionWidget.crs().postgisSrid(),
            "clipping_crs_epsg": self.mQgsProjectionSelectionWidget_2.crs().postgisSrid(),
            "render_crs_epsg":   self.mQgsProjectionSelectionWidget_3.crs().postgisSrid(),
        }

    def run(self):
        try:
            p = self._get_params()

            # ── Validation ────────────────────────────────────────────────────
            if p["imagery_layer"] is None:
                QMessageBox.warning(self, "Missing input", "Please select a Basemap layer."); return
            if not isinstance(p["imagery_layer"], QgsRasterLayer):
                QMessageBox.warning(self, "Wrong layer type", "Basemap must be a raster layer."); return

            if p["dem_layer"] is None:
                QMessageBox.warning(self, "Missing input", "Please select a DEM layer."); return
            if not isinstance(p["dem_layer"], QgsRasterLayer):
                QMessageBox.warning(self, "Wrong layer type", "DEM must be a raster layer."); return

            if p["clipping_layer"] is None:
                QMessageBox.warning(self, "Missing input", "Please select a Cropping Extent layer."); return
            if not isinstance(p["clipping_layer"], QgsVectorLayer):
                QMessageBox.warning(self, "Wrong layer type", "Cropping Extent must be a vector layer."); return

            if not p["output_folder"]:
                QMessageBox.warning(self, "Missing input", "Please select an Output Folder."); return

            imagery_layer      = p["imagery_layer"]
            dem_layer          = p["dem_layer"]
            clipping_layer     = p["clipping_layer"]
            output_folder      = p["output_folder"]
            output_name        = p["output_name"]
            render_crs_epsg    = p["render_crs_epsg"]
            clipping_crs_epsg  = p["clipping_crs_epsg"]
            output_crs_epsg    = p["output_crs_epsg"]
            imagery_resolution = QSize(2000, 2000)

            print("=" * 70)
            print("CLIP IMAGERY AND DEM TO AOI")
            print("=" * 70)

            # [1/6] Output folders ────────────────────────────────────────────
            self._set_progress(5, "\n[1/6] Setting up output folders...")
            output_path     = Path(output_folder)
            textures_folder = output_path / "TIFF_Textures"
            textures_folder.mkdir(parents=True, exist_ok=True)
            dem_output_path     = output_path / f"{output_name}.tif"
            imagery_output_path = textures_folder / "Tile__0__0.png"
            print(f"  ✓ DEM output:     {dem_output_path}")
            print(f"  ✓ Imagery output: {imagery_output_path}")

            # [2/6] AOI extent ────────────────────────────────────────────────
            self._set_progress(15, "\n[2/6] Calculating AOI extent...")
            transform_context = QgsProject.instance().transformContext()
            aoi_extent = get_aoi_bounds_in_crs(clipping_layer, render_crs_epsg, transform_context)
            buf_x = aoi_extent.width()  * 0.05
            buf_y = aoi_extent.height() * 0.05
            render_extent = QgsRectangle(
                aoi_extent.xMinimum() - buf_x, aoi_extent.yMinimum() - buf_y,
                aoi_extent.xMaximum() + buf_x, aoi_extent.yMaximum() + buf_y,
            )
            print(f"  ✓ AOI extent (EPSG:{render_crs_epsg}): {aoi_extent}")

            # [3/6] Render imagery ────────────────────────────────────────────
            self._set_progress(30, "\n[3/6] Rendering imagery...")
            visible_layers = iface.mapCanvas().layers()
            image, map_settings = render_imagery_to_extent(
                visible_layers, render_extent, imagery_resolution, render_crs_epsg
            )
            print(f"  ✓ Rendered: {image.width()} x {image.height()} px")

            # [4/6] Apply AOI mask ────────────────────────────────────────────
            self._set_progress(55, "\n[4/6] Applying AOI mask...")
            mask         = create_aoi_mask(clipping_layer, imagery_resolution, map_settings, clipping_crs_epsg)
            masked_image = apply_mask_to_image(image, mask)
            print("  ✓ Mask applied")

            # [5/6] Auto-crop ─────────────────────────────────────────────────
            self._set_progress(70, "\n[5/6] Auto-cropping...")
            pixel_bounds = get_opaque_bounds(masked_image)
            if pixel_bounds is None:
                QMessageBox.critical(self, "Error", "No opaque pixels found after masking!"); return
            min_x, min_y, max_x, max_y = pixel_bounds
            crop_w = max_x - min_x + 1
            crop_h = max_y - min_y + 1
            final_extent  = pixel_bounds_to_geo_extent(pixel_bounds, map_settings)
            cropped_image = masked_image.copy(min_x, min_y, crop_w, crop_h)
            cropped_image.save(str(imagery_output_path), "PNG")
            print(f"  ✓ Cropped to {crop_w} x {crop_h} px → {imagery_output_path}")

            # [6/6] Clip DEM ──────────────────────────────────────────────────
            self._set_progress(85, "\n[6/6] Clipping DEM...")
            dem_out_size = QSize(crop_w, crop_h)
            dem_result, dem_extent = clip_dem_to_extent(
                dem_layer, final_extent, str(dem_output_path),
                output_crs_epsg, render_crs_epsg, dem_out_size
            )
            print(f"  ✓ DEM saved: {dem_result}")

            # ── Done ──────────────────────────────────────────────────────────
            self._set_progress(100)
            print("\n" + "=" * 70)
            print("EXPORT COMPLETE")
            print(f"  • {output_name}.tif  ({dem_out_size.width()}x{dem_out_size.height()} px)")
            print(f"  • TIFF_Textures/Tile__0__0.png  ({crop_w}x{crop_h} px)")
            print(f"  W:{dem_extent.xMinimum():.8f}  E:{dem_extent.xMaximum():.8f}")
            print(f"  S:{dem_extent.yMinimum():.8f}  N:{dem_extent.yMaximum():.8f}")
            print("✓ Ready for texture draping!")

            QMessageBox.information(self, "Done", f"Export complete!\n\nSaved to:\n{output_folder}\n\nYou can close this window or run another export.")
           
        except Exception as e:
            self.progressBar.setValue(0)
            QMessageBox.critical(self, "Error", str(e))
            raise  # full traceback in QGIS Python console