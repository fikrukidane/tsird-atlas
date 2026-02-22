# TSIRD Geospatial Data Inventory

## Raster data (~512 MB total)

| Layer | Purpose | Location | File size | Format / CRS | Status |
|---|---|---:|---:|---|---|
| Ethiopia DEM | Digital Elevation Model 2001 | dem | 136M (UTM) + 40M (RGB) | GeoTIFF, EPSG:20137 | ✓ Live in WMS |
| Ethiopia Slope | Slope derived from DEM | slope | 68M (UTM) + 19M (RGB) | GeoTIFF, EPSG:20137 | ✓ Live in WMS |
| Hillshade 2001 | Shaded relief for visualization | rasters | 101M | GeoTIFF, EPSG:20137 | ✓ Copied |
| CIA Basemap | CIA reference basemap | rasters | 3.6M | GeoTIFF, RGB | ✓ Copied |
| Language Map | Linguistic/ethnic distribution | rasters | 3.2M | GeoTIFF, RGB | ✓ Copied |
| DTM 50m | 50m resolution DEM | rasters | 1.3M | GeoTIFF | ✓ Copied |

### Raster directories

- data/raw/rasters/ — 121M (4 original rasters + sidecars)
- data/gold/rasters_src/ — 382M (all rasters + deployed DEM/Slope + RGB versions, working copies)
- data/gold/dem/ — DEM + RGB versions (WMS live)
- data/gold/slope/ — Slope + RGB versions (WMS live)
- data/gold/rasters_web/ — 49M (6 web-ready EPSG:3857 cloud-optimized versions):

ethiopia_dem_3857.tif (25M, Int16, 4 overviews)

ethiopia_slope_3857.tif (4.5M, Byte, 4 overviews)

ethiopia_hillshade_3857.tif (16M, Int16, 4 overviews)

cia_basemap_3857.tif (2.6M, RGB, 4 overviews)

ethiopia_language_3857.tif (1.9M, RGB, 4 overviews)

## Vector data (~80 MB total)

State: 35 shapefile groups (120+ files) with supporting components: .shp, .shx, .dbf, .prj, .cpg, .sbn, .sbx, .qix, .fix, .shp.xml

#### National / regional layers

admin, basins, bound01, bound02, bound03, contour, ethio_wereda, ethio_wereda_Project, Eth_Zones_New, EthioWoredasNew, Ethio_roads, isoght, lakes, mbasins, msoils, necolog, nforest, nforests, nparks, rain_patrn, rain_stat, rivers, roads, streams, towns, wetlands

#### Tigray regional layers

TigrayContour, TigrayHealth2006, TigrayNewWoredas, TigrayWoredaNew, TigrayRoads2006t, TigrayRoadsIn2006, TigraySchools2006, TigraiTabiasNew, Tigray_Towns

#### Vector directories

- data/raw/vectors/ — 80M (all 35 shapefile groups, 120+ individual files)
- data/gold/vectors_src/ — Empty (prepared for future PostGIS import)

## CRS coverage

- EPSG:20137 (Adindan / UTM Zone 37N) — primary for DEM/Slope/Hillshade rasters

- EPSG:3857 (Web Mercator) — web-ready raster versions

- EPSG:4326 (WGS 84) — vector layers, reference data

Small reference files in dem/slope (4326 variants, ~6.2K each)

## Current status

- ✓ All baseline data copied (rasters + vectors)

- ✓ DEM/Slope deployed and live in MapServer (color-relief RGB rendering)

- ✓ Web-ready EPSG:3857 rasters built (cloud-optimized with overviews)

- ⊘ Vectors not yet loaded into PostgreSQL (deferred to Atlas phase)

- ⊘ Tile server not yet configured

Last updated: 2026-02-17.
