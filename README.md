# CSM 3D Image Extractor — QGIS Plugin v1.0

Developed by **Geocentric Environmental Inc.** to streamline the export of draped DEMs and basemap imagery for use in **CSM 3D Vis**.

---

# Download/install

**Do not use the green "Code → Download ZIP" button to install this plugin.**

**Download the install-ready zip from the [Releases](link) page instead. To download click on the placeholder.**

---

## What it does

Image Extractor automates the process of clipping a basemap (e.g. Google Satellite) and a DEM raster to a user-defined AOI polygon, producing two georeferenced outputs that share an identical spatial extent. The files are ready to be imported as a draped terrain in CSM 3D Vis with no manual alignment needed.

The tool:
- Renders the visible QGIS map canvas to a high-resolution image
- Applies a precise vector mask from the selected AOI layer
- Auto-crops to the opaque pixel boundary
- Clips the DEM to the exact same geographic extent

Both outputs are pixel-aligned, eliminating skirt artifacts in 3D visualization.

### Outputs
- `TIFF_Textures/Tile__0__0.png` — masked and cropped basemap image
- `[Output Name].tif` — DEM clipped to matching extent (GeoTIFF)

---

## Important notes

1. **Use only square or rectangular Cropping Extents.** CSM 3D Vis only supports these shapes — irregular polygons will produce skirt artifacts along the edges.
2. **Turn off unwanted layers** before running the plugin. Everything visible on the QGIS canvas will be captured in the output image.
3. **Zoom to the full extent of your Cropping Extent layer** before running. This ensures the basemap is rendered at the highest resolution possible.

---

## Installation (without QGIS Plugin Repository)

1. Download the latest `CSM_3D_Image_Extractor.zip` from the [Releases](placeholder) page 
2. Open QGIS and go to **Plugins → Manage and Install Plugins**
3. Select the **Install from ZIP** tab
4. Browse to the downloaded `.zip` file and click **Install Plugin**
5. Once installed, enable it under the **Installed** tab
6. The plugin will appear as a button in your toolbar and under **Plugins → Image Extractor**

### Requirements
- **QGIS 3.16 or later (including QGIS 4.x)**
- No additional Python packages required — all dependencies are bundled with QGIS

---

## Usage

1. Load your Basemap, DEM, and Cropping Extent layers in QGIS
2. Zoom to the full extent of your Cropping Extent layer
3. Turn off any layers you don't want in the basemap output
4. Open the plugin and fill in the dialog:
   - Select your Basemap, DEM, and Cropping Extent layers
   - Choose an output folder and file name
   - Set the CRS values (Output CRS: EPSG:4326, Basemap CRS: EPSG:3857 for Google imagery)
5. Click **OK** and monitor the progress bar
6. Import the outputs into CSM 3D Vis through the "Import Terrain" function

---

## Contact

Please submit a form at: [geocentric-env.com](https://geocentric-env.com/contact/)

or drop be an email to: gamicarelli@geocentric-env.com

We'll reply as soon as possible
