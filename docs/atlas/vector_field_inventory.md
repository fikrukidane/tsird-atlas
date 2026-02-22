# TSIRD Vector Field Inventory

Comprehensive inventory of all vector layers in the TSIRD system.

## Layers

### Eth_Zones_New

| Property | Value |
|----------|-------|
| File | `Eth_Zones_New.shp` |
| Geometry | Polygon |
| Features | 74 |
| Extent | `(33.001536, 3.398548) - (47.958228, 14.845692)` |
| CRS | `GEOGCRS["WGS 84",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/Eth_Zones_New.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/Eth_Zones_New.shp, this=0x5dcb0ca56b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/Eth_Zones_New.shp, this=0x5dcb0ca56b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/Eth_Zones_New.shp'
Geometry: Polygon
Extent: (33.001536, 3.398548) - (47.958228, 14.845692)
ZONENAME: String (16.0)
```

### EthioWoredasNew

| Property | Value |
|----------|-------|
| File | `EthioWoredasNew.shp` |
| Geometry | Polygon |
| Features | 532 |
| Extent | `(32.999230, 3.400880) - (47.960530, 14.852220)` |
| CRS | `GEOGCRS["WGS 84",` |

**Fields:**

```
Shape: DBF Codepage = UTF-8 for /data/raw/vectors/EthioWoredasNew.shp
Shape: Treating as encoding 'UTF-8'.
GDAL: GDALOpen(/data/raw/vectors/EthioWoredasNew.shp, this=0x58562927ab40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/EthioWoredasNew.shp, this=0x58562927ab40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/EthioWoredasNew.shp'
Geometry: Polygon
Extent: (32.999230, 3.400880) - (47.960530, 14.852220)
OBJECTID: Integer (9.0)
W_NAME: String (50.0)
Z4ID: String (6.0)
EASE_Z4ID: String (4.0)
REGION_R2I: String (2.0)
Area_km2: Real (19.11)
Shape_Leng: Real (19.11)
Shape_Area: Real (19.11)
Pop_04: Integer (9.0)
Pop_Den: Real (19.11)
LINK_ID: Integer (9.0)
Admin_Unit: String (254.0)
W6ID: Real (16.6)
MF_All_All: Real (16.6)
M_All_All_: Real (16.6)
F_All_All_: Real (16.6)
MF_All_0_4: Real (16.6)
M_All_0_4: Real (16.6)
F_All_0_4: Real (16.6)
MF_All_5_9: Real (16.6)
M_All_5_9: Real (16.6)
F_All_5_9: Real (16.6)
MF_All_10_: Real (16.6)
M_All_10_1: Real (16.6)
F_All_10_1: Real (16.6)
MF_All_15_: Real (16.6)
M_All_15_1: Real (16.6)
F_All_15_1: Real (16.6)
MF_All_20_: Real (16.6)
M_All_20_2: Real (16.6)
F_All_20_2: Real (16.6)
MF_All_25_: Real (16.6)
M_All_25_2: Real (16.6)
F_All_25_2: Real (16.6)
MF_All_30_: Real (16.6)
M_All_30_3: Real (16.6)
F_All_30_3: Real (16.6)
MF_All_35_: Real (16.6)
M_All_35_3: Real (16.6)
F_All_35_3: Real (16.6)
MF_All_40_: Real (16.6)
M_All_40_4: Real (16.6)
F_All_40_4: Real (16.6)
MF_All_45_: Real (16.6)
M_All_45_4: Real (16.6)
F_All_45_4: Real (16.6)
MF_All_50_: Real (16.6)
M_All_50_5: Real (16.6)
F_All_50_5: Real (16.6)
MF_All_55_: Real (16.6)
M_All_55_5: Real (16.6)
F_All_55_5: Real (16.6)
MF_All_60_: Real (16.6)
M_All_60_6: Real (16.6)
F_All_60_6: Real (16.6)
MF_All_65_: Real (16.6)
M_All_65_6: Real (16.6)
F_All_65_6: Real (16.6)
MF_All_70_: Real (16.6)
M_All_70_7: Real (16.6)
F_All_70_7: Real (16.6)
```

### Ethio_roads

| Property | Value |
|----------|-------|
| File | `Ethio_roads.shp` |
| Geometry | Line |
| Features | 1786 |
| Extent | `(33.006302, 3.440106) - (47.949379, 14.809500)` |
| CRS | `GEOGCRS["WGS 84",` |
fikru@srv1375603:/opt/tigrayinsights/apps/tsird$ cd /opt/tigrayinsights/apps/tsird
bash scripts/tsird-vector-field-inventory.sh
xargs: unmatched single quote; by default quotes are special to xargs unless you use the -0 option
**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/Ethio_roads.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/Ethio_roads.shp, this=0x64baffaeab40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/Ethio_roads.shp, this=0x64baffaeab40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/Ethio_roads.shp'
Geometry: Line String
Extent: (33.006302, 3.440106) - (47.949379, 14.809500)
FNODE_: Integer64 (11.0)
TNODE_: Integer64 (11.0)
LPOLY_: Integer64 (11.0)
RPOLY_: Integer64 (11.0)
LENGTH: Real (12.3)
RDLINE_: Integer64 (11.0)
RDLINE_ID: Integer64 (11.0)
RDLNTYPE: Integer (2.0)
RDLNTYPETX: String (30.0)
RDLNSTAT: Integer (2.0)
RDLNSTATTX: String (40.0)
```

### TigraiTabiasNew

| Property | Value |
|----------|-------|
| File | `TigraiTabiasNew.shp` |
| Geometry | Polygon |
| Features | 748 |
| Extent | `(213444.750000, 1355035.750000) - (607154.812500, 1654728.875000)` |
| CRS | `PROJCRS["WGS 84 / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = UTF-8 for /data/raw/vectors/TigraiTabiasNew.shp
Shape: Treating as encoding 'UTF-8'.
GDAL: GDALOpen(/data/raw/vectors/TigraiTabiasNew.shp, this=0x5c7f0fea0b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/TigraiTabiasNew.shp, this=0x5c7f0fea0b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/TigraiTabiasNew.shp'
Geometry: Polygon
Extent: (213444.750000, 1355035.750000) - (607154.812500, 1654728.875000)
AREA: Real (19.6)
PERIMETER: Real (13.6)
WEREDA: String (20.0)
TABIA: String (30.0)
T8ID: String (14.0)
SQ_KM: Real (16.2)
HECTARES: Real (10.2)
ZONES: String (12.0)
LENGTH: Real (19.15)
DENSITY: Real (10.2)
```

### TigrayContour

| Property | Value |
|----------|-------|
| File | `TigrayContour.shp` |
| Geometry | Line |
| Features | 805 |
| Extent | `(227239.176557, 1355057.844373) - (595220.125000, 1645334.893633)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = UTF-8 for /data/raw/vectors/TigrayContour.shp
Shape: Treating as encoding 'UTF-8'.
GDAL: GDALOpen(/data/raw/vectors/TigrayContour.shp, this=0x625d77474b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/TigrayContour.shp, this=0x625d77474b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/TigrayContour.shp'
Geometry: Line String
Extent: (227239.176557, 1355057.844373) - (595220.125000, 1645334.893633)
FNODE_: Integer64 (11.0)
TNODE_: Integer64 (11.0)
LPOLY_: Integer64 (11.0)
RPOLY_: Integer64 (11.0)
LENGTH: Real (19.5)
ETTOPOL01C: Integer64 (11.0)
ETTOPOL0_1: Integer64 (11.0)
ELEVATION: Integer64 (11.0)
```

### TigrayHealth2006

| Property | Value |
|----------|-------|
| File | `TigrayHealth2006.shp` |
| Geometry | Point |
| Features | 729 |
| Extent | `(226852.000000, 138155.000000) - (999868.000000, 58324602265790775512818934328062380370204061125905757621900627630504127784873829166706231314797131290131351555290081397079016567616702065739258411806660475789030824119593008819537508515711602030597672321539487027096811201764043838550179840.000000)` |
| CRS | `(unknown)` |

**Fields:**

```
Shape: DBF Codepage = UTF-8 for /data/raw/vectors/TigrayHealth2006.shp
Shape: Treating as encoding 'UTF-8'.
GDAL: GDALOpen(/data/raw/vectors/TigrayHealth2006.shp, this=0x58de4f71cb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/TigrayHealth2006.shp, this=0x58de4f71cb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/TigrayHealth2006.shp'
Geometry: Point
Extent: (226852.000000, 138155.000000) - (999868.000000, 58324602265790775512818934328062380370204061125905757621900627630504127784873829166706231314797131290131351555290081397079016567616702065739258411806660475789030824119593008819537508515711602030597672321539487027096811201764043838550179840.000000)
Object_ID_: Integer (9.0)
geodb_oid: Integer (9.0)
Object_ID: Real (19.11)
Woreda_Nam: String (254.0)
Woreda_ID: String (254.0)
Type_of_in: String (254.0)
Institutio: String (254.0)
X_Coordina: Real (19.11)
Y_Coordina: Real (19.11)
```

### TigrayNewWoredas

| Property | Value |
|----------|-------|
| File | `TigrayNewWoredas.shp` |
| Geometry | Polygon |
| Features | 48 |
| Extent | `(213444.750000, 1355035.750000) - (607154.812500, 1654728.875000)` |
| CRS | `PROJCRS["WGS 84 / UTM zone 37N",` |

**Fields:**

```
GDAL: GDALOpen(/data/raw/vectors/TigrayNewWoredas.shp, this=0x55cf3bf82b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/TigrayNewWoredas.shp, this=0x55cf3bf82b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/TigrayNewWoredas.shp'
Geometry: Polygon
Extent: (213444.750000, 1355035.750000) - (607154.812500, 1654728.875000)
WEREDA: String (20.0)
COUNT: Integer64 (11.0)
SUM_AREA: Real (18.4)
SUM_PERIME: Real (18.4)
SUM_SQ_KM: Real (18.4)
SUM_HECTAR: Real (18.4)
ZONE_NAME: String (16.0)
Wereda__Id: String (12.0)
Tot_Popula: Integer64 (10.0)
wor_name: String (50.0)
LINK_ID: Integer (4.0)
TRHB_2004E: Real (24.15)
TRHB_200_1: Real (24.15)
TRHB_200_2: Real (24.15)
TRHB_200_3: Real (24.15)
TRHB_200_4: Real (24.15)
TRHB_200_5: Real (24.15)
TRHB_200_6: Real (24.15)
TRHB_200_7: Real (24.15)
TRHB_200_8: Real (24.15)
```

### TigrayRoads2006t

| Property | Value |
|----------|-------|
| File | `TigrayRoads2006t.shp` |
| Geometry | Line |
| Features | 547 |
| Extent | `(216990.679530, 1357238.876820) - (590408.126889, 1628485.453266)` |
| CRS | `PROJCRS["WGS 84 / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/TigrayRoads2006t.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/TigrayRoads2006t.shp, this=0x571c7943eb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/TigrayRoads2006t.shp, this=0x571c7943eb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/TigrayRoads2006t.shp'
Geometry: Line String
Extent: (216990.679530, 1357238.876820) - (590408.126889, 1628485.453266)
OBJECTID: Integer (9.0)
OBJECTID_1: Integer (9.0)
LAYER: String (254.0)
NAME: String (43.0)
LENGTH: String (8.0)
OWNER: String (50.0)
ZONE_: String (50.0)
RDID: String (20.0)
SHAPE_LENG: Real (19.11)
Shape_Le_1: Real (19.11)
length_KM: Real (19.11)
```

### TigrayRoadsIn2006

| Property | Value |
|----------|-------|
| File | `TigrayRoadsIn2006.shp` |
| Geometry | Line |
| Features | 97 |
| Extent | `(216984.791281, 1357397.999842) - (594406.833049, 1628341.000158)` |
| CRS | `(unknown)` |

**Fields:**

```
Shape: DBF Codepage = UTF-8 for /data/raw/vectors/TigrayRoadsIn2006.shp
Shape: Treating as encoding 'UTF-8'.
GDAL: GDALOpen(/data/raw/vectors/TigrayRoadsIn2006.shp, this=0x62454cc7eb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/TigrayRoadsIn2006.shp, this=0x62454cc7eb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/TigrayRoadsIn2006.shp'
Geometry: Line String
Extent: (216984.791281, 1357397.999842) - (594406.833049, 1628341.000158)
OBJECTID: Integer (9.0)
OBJECTID_1: Integer (9.0)
LAYER: String (254.0)
NAME: String (43.0)
LENGTH: String (8.0)
OWNER: String (50.0)
ZONE_: String (50.0)
RDID: String (20.0)
SHAPE_LENG: Real (19.11)
SHAPE_LE_1: Real (19.11)
LENGTH_KM: Real (19.11)
TYPE: String (16.0)
NEAR_FID: Integer (9.0)
NEAR_DIST: Real (19.11)
```

### TigraySchools2006

| Property | Value |
|----------|-------|
| File | `TigraySchools2006.shp` |
| Geometry | Point |
| Features | 2121 |
| Extent | `(226914.000000, 1356739.000000) - (594252.000000, 1627780.000000)` |
| CRS | `PROJCRS["WGS 84 / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/TigraySchools2006.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/TigraySchools2006.shp, this=0x5df43f5a6b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/TigraySchools2006.shp, this=0x5df43f5a6b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/TigraySchools2006.shp'
Geometry: Point
Extent: (226914.000000, 1356739.000000) - (594252.000000, 1627780.000000)
No: Real (16.6)
Zone_Name: String (254.0)
Woreda_Nam: String (254.0)
Woreda_ID: Real (16.6)
T_Name: String (254.0)
Name: String (254.0)
Type: String (254.0)
X: Real (16.6)
Y: Real (16.6)
F10: String (254.0)
F11: String (254.0)
F12: String (254.0)
F13: String (254.0)
F14: String (254.0)
F15: String (254.0)
F16: String (254.0)
```

### TigrayWoredaNew

| Property | Value |
|----------|-------|
| File | `TigrayWoredaNew.shp` |
| Geometry | Polygon |
| Features | 47 |
| Extent | `(213444.750000, 1355035.750000) - (607154.812500, 1654728.875000)` |
| CRS | `PROJCRS["WGS 84 / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = UTF-8 for /data/raw/vectors/TigrayWoredaNew.shp
Shape: Treating as encoding 'UTF-8'.
GDAL: GDALOpen(/data/raw/vectors/TigrayWoredaNew.shp, this=0x5c810899eb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/TigrayWoredaNew.shp, this=0x5c810899eb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/TigrayWoredaNew.shp'
Geometry: Polygon
Extent: (213444.750000, 1355035.750000) - (607154.812500, 1654728.875000)
WEREDA: String (20.0)
COUNT: Integer64 (11.0)
SUM_AREA: Real (18.4)
SUM_PERIME: Real (18.4)
SUM_SQ_KM: Real (18.4)
SUM_HECTAR: Real (18.4)
ZONE_NAME: String (16.0)
Wereda__Id: String (12.0)
Tot_Popula: Integer64 (10.0)
wor_name: String (50.0)
```

### Tigray_Towns

| Property | Value |
|----------|-------|
| File | `Tigray_Towns.shp` |
| Geometry | Point |
| Features | 47 |
| Extent | `(240696.875000, 1358289.250000) - (583338.937500, 1606416.875000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = UTF-8 for /data/raw/vectors/Tigray_Towns.shp
Shape: Treating as encoding 'UTF-8'.
GDAL: GDALOpen(/data/raw/vectors/Tigray_Towns.shp, this=0x61f096354b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/Tigray_Towns.shp, this=0x61f096354b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/Tigray_Towns.shp'
Geometry: Point
Extent: (240696.875000, 1358289.250000) - (583338.937500, 1606416.875000)
ETTOWN01CO: Integer64 (11.0)
ETTOWN01_1: Integer64 (11.0)
TOWN_NAME: String (25.0)
POP: Integer (7.0)
WEREDA: String (30.0)
REGION: String (20.0)
ZONES: String (20.0)
POPURB: Real (19.0)
POPRUR: Real (19.0)
POPTOT: Real (19.0)
RAIN: Real (15.3)
K_VALUE: Real (15.3)
SOIL: Real (15.3)
EROSIVITY: Real (15.3)
ELEVATION: Real (15.3)
POP_TXT: String (9.0)
RAIN_TXT: String (24.0)
ELEV_TXT: String (19.0)
```

### admin

| Property | Value |
|----------|-------|
| File | `admin.shp` |
| Geometry | Polygon |
| Features | 699 |
| Extent | `(-163699.776769, 376528.626524) - (1494578.021537, 1645738.557697)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/admin.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/admin.shp, this=0x60fb9d4c4b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/admin.shp, this=0x60fb9d4c4b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/admin.shp'
Geometry: Polygon
Extent: (-163699.776769, 376528.626524) - (1494578.021537, 1645738.557697)
AREA: Real (12.3)
PERIMETER: Real (12.3)
ETH2BDY_: Integer64 (11.0)
ETH2BDY_ID: Integer64 (11.0)
SQKM: Real (8.1)
ADMSQKM: Real (10.1)
CODE: String (3.0)
ADMINID: Integer64 (11.0)
COUNTRY: String (3.0)
NAME1: String (25.0)
NAME2: String (25.0)
NAME3: String (25.0)
DEMOFLAG: Integer (2.0)
P60: Integer64 (11.0)
P70: Integer64 (11.0)
P80: Integer64 (11.0)
P90: Integer64 (11.0)
SR: Real (8.2)
HECTARES: Real (16.3)
```

### basins

| Property | Value |
|----------|-------|
| File | `basins.shp` |
| Geometry | Polygon |
| Features | 658 |
| Extent | `(-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/basins.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/basins.shp, this=0x6372506eeb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/basins.shp, this=0x6372506eeb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/basins.shp'
Geometry: Polygon
Extent: (-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)
AREA: Real (18.5)
PERIMETER: Real (18.5)
ETWSHED01C: Integer64 (11.0)
ETWSHED01C: Integer64 (11.0)
BASIN_NR: Integer (2.0)
BASIN_NAME: String (16.0)
BASIN: Integer (5.0)
SQKM: Integer (8.0)
BASIN_COD: String (11.0)
```

### bound01

| Property | Value |
|----------|-------|
| File | `bound01.shp` |
| Geometry | Polygon |
| Features | 1 |
| Extent | `(-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/bound01.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/bound01.shp, this=0x62474569ab40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/bound01.shp, this=0x62474569ab40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/bound01.shp'
Geometry: Polygon
Extent: (-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)
AREA: Real (18.5)
PERIMETER: Real (18.5)
ETBOUND01C: Integer64 (11.0)
ETBOUND01C: Integer64 (11.0)
```

### bound02

| Property | Value |
|----------|-------|
| File | `bound02.shp` |
| Geometry | Polygon |
| Features | 12 |
| Extent | `(-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/bound02.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/bound02.shp, this=0x55b5a711eb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/bound02.shp, this=0x55b5a711eb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/bound02.shp'
Geometry: Polygon
Extent: (-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)
AREA: Real (18.5)
PERIMETER: Real (18.5)
ETREGIO01C: Integer64 (11.0)
ETREGIO0_1: Integer64 (11.0)
REGION: String (20.0)
```

### bound03

| Property | Value |
|----------|-------|
| File | `bound03.shp` |
| Geometry | Polygon |
| Features | 76 |
| Extent | `(-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/bound03.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/bound03.shp, this=0x56c3ece74b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/bound03.shp, this=0x56c3ece74b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/bound03.shp'
Geometry: Polygon
Extent: (-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)
AREA: Real (18.5)
PERIMETER: Real (18.5)
ETZONES01C: Integer64 (11.0)
ETZONES01C: Integer64 (11.0)
ZONES: String (20.0)
```

### contour

| Property | Value |
|----------|-------|
| File | `contour.shp` |
| Geometry | Line |
| Features | 9125 |
| Extent | `(-38587.152344, 380749.406250) - (1472705.875000, 1645334.893633)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/contour.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/contour.shp, this=0x555fdf62ab40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/contour.shp, this=0x555fdf62ab40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/contour.shp'
Geometry: Line String
Extent: (-38587.152344, 380749.406250) - (1472705.875000, 1645334.893633)
FNODE_: Integer64 (11.0)
TNODE_: Integer64 (11.0)
LPOLY_: Integer64 (11.0)
RPOLY_: Integer64 (11.0)
LENGTH: Real (18.5)
ETTOPOL01C: Integer64 (11.0)
ETTOPOL01C: Integer64 (11.0)
ELEVATION: Integer64 (11.0)
```

### ethio_wereda

| Property | Value |
|----------|-------|
| File | `ethio_wereda.shp` |
| Geometry | Polygon |
| Features | 466 |
| Extent | `(-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)` |
| CRS | `GEOGCRS["WGS 84",` |

**Fields:**

```
GDAL: GDALOpen(/data/raw/vectors/ethio_wereda.shp, this=0x564bd988cb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/ethio_wereda.shp, this=0x564bd988cb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/ethio_wereda.shp'
Geometry: Polygon
Extent: (-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)
```

### ethio_wereda_Project

| Property | Value |
|----------|-------|
| File | `ethio_wereda_Project.shp` |
| Geometry | Polygon |
| Features | 466 |
| Extent | `(-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)` |
| CRS | `GEOGCRS["WGS 84",` |

**Fields:**

```
Shape: Inconsistent record number in .shp (466) and in .dbf (1073741824)
Shape: DBF Codepage = UTF-8 for /data/raw/vectors/ethio_wereda_Project.shp
Shape: Treating as encoding 'UTF-8'.
GDAL: GDALOpen(/data/raw/vectors/ethio_wereda_Project.shp, this=0x62459348ab40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/ethio_wereda_Project.shp, this=0x62459348ab40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/ethio_wereda_Project.shp'
Geometry: Polygon
Extent: (-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)
```

### isoght

| Property | Value |
|----------|-------|
| File | `isoght.shp` |
| Geometry | Line |
| Features | 1778 |
| Extent | `(-127500.000000, 388997.924805) - (1478041.992188, 1645605.398945)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/isoght.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/isoght.shp, this=0x65133c5e6b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/isoght.shp, this=0x65133c5e6b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/isoght.shp'
Geometry: Line String
Extent: (-127500.000000, 388997.924805) - (1478041.992188, 1645605.398945)
FNODE_: Integer64 (11.0)
TNODE_: Integer64 (11.0)
LPOLY_: Integer64 (11.0)
RPOLY_: Integer64 (11.0)
LENGTH: Real (18.5)
ETISOHY01C: Integer64 (11.0)
ETISOHY01C: Integer64 (11.0)
CONTOUR: Integer64 (11.0)
```

### lakes

| Property | Value |
|----------|-------|
| File | `lakes.shp` |
| Geometry | Polygon |
| Features | 23 |
| Extent | `(161931.658614, 492150.121467) - (806796.025989, 1557998.095908)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/lakes.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/lakes.shp, this=0x559e42cc0b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/lakes.shp, this=0x559e42cc0b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/lakes.shp'
Geometry: Polygon
Extent: (161931.658614, 492150.121467) - (806796.025989, 1557998.095908)
AREA: Real (12.3)
PERIMETER: Real (12.3)
RIVERMAJ_: Integer64 (11.0)
RIVERMAJ_I: Integer64 (11.0)
CODE: String (3.0)
WATER: Integer64 (11.0)
ACRES: Real (16.3)
HECTARES: Real (16.3)
```

### mbasins

| Property | Value |
|----------|-------|
| File | `mbasins.shp` |
| Geometry | Polygon |
| Features | 16 |
| Extent | `(-163699.776769, 376528.626524) - (1494578.021537, 1645738.557697)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/mbasins.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/mbasins.shp, this=0x616da2af2b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/mbasins.shp, this=0x616da2af2b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/mbasins.shp'
Geometry: Polygon
Extent: (-163699.776769, 376528.626524) - (1494578.021537, 1645738.557697)
AREA: Real (12.3)
PERIMETER: Real (12.3)
WATERSHD_: Integer64 (11.0)
WATERSHD_I: Integer64 (11.0)
HY_BAS: String (3.0)
HY_SBA: String (2.0)
TYPE: String (1.0)
NAME: String (28.0)
BASIN_MAJO: String (15.0)
BNO: Integer (2.0)
WNO: Integer (3.0)
WATRANK: String (2.0)
WSHD: String (6.0)
ACRES: Real (16.3)
HECTARES: Real (16.3)
BASINNAME: String (50.0)
```

### msoils

| Property | Value |
|----------|-------|
| File | `msoils.shp` |
| Geometry | Polygon |
| Features | 394 |
| Extent | `(-163699.776769, 376528.626524) - (1494578.021537, 1645738.557697)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/msoils.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/msoils.shp, this=0x57bd5bf52b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/msoils.shp, this=0x57bd5bf52b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/msoils.shp'
Geometry: Polygon
Extent: (-163699.776769, 376528.626524) - (1494578.021537, 1645738.557697)
AREA: Real (12.3)
PERIMETER: Real (12.3)
USDASOILET: Integer64 (11.0)
USDASOILET: Integer64 (11.0)
SNUM: Integer (4.0)
FAOSOIL: String (17.0)
TAX: String (4.0)
TAXON: String (3.0)
NAME: String (20.0)
CODE: String (4.0)
CO_DOM: String (6.0)
SYMBOL: Integer (3.0)
GPCD: String (3.0)
SYMBOL1: Integer (3.0)
SYMBOL2: Integer (2.0)
SYMBOL3: Integer (3.0)
QUAL: Integer (2.0)
AWC: String (2.0)
CK: Integer (3.0)
PHASE1: String (2.0)
PHASE2: String (2.0)
MISCLU1: String (1.0)
MISCLU2: String (1.0)
COUNTRY_NU: Integer (3.0)
COUNTRY_NA: String (14.0)
SU_DOM: String (2.0)
SU_DOMCODE: String (1.0)
SU_DOMPERC: Real (5.1)
SU_1: String (2.0)
SU_1_CODE: String (1.0)
SU_1_PERC: Real (5.1)
SU_2: String (2.0)
SU_2_CODE: String (1.0)
SU_2_PERC: Real (5.1)
SU_3: String (2.0)
SU_3_CODE: String (1.0)
SU_3_PERC: Real (5.1)
SU_4: String (2.0)
SU_4_CODE: String (1.0)
SU_4_PERC: Real (5.1)
SU_5: String (2.0)
SU_5_CODE: String (1.0)
SU_5_PERC: Real (5.1)
SU_6: String (2.0)
SU_6_CODE: String (1.0)
SU_6_PERC: Real (5.1)
SU_7: String (2.0)
SU_7_CODE: String (1.0)
SU_7_PERC: Real (5.1)
SU_8: String (2.0)
SU_8_CODE: String (1.0)
SU_8_PERC: Real (5.1)
HECTARES: Real (16.3)
SOILTYPE: String (50.0)
```

### necolog

| Property | Value |
|----------|-------|
| File | `necolog.shp` |
| Geometry | Polygon |
| Features | 113 |
| Extent | `(-162450.353514, 411870.163594) - (1427023.646010, 1548091.541212)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/necolog.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/necolog.shp, this=0x6287d48ecb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/necolog.shp, this=0x6287d48ecb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/necolog.shp'
Geometry: Polygon
Extent: (-162450.353514, 411870.163594) - (1427023.646010, 1548091.541212)
AREA: Real (12.3)
PERIMETER: Real (12.3)
LCPOLY_: Integer64 (11.0)
LCPOLY_ID: Integer64 (11.0)
LCPYTYPE: Integer (2.0)
LCPYTYPETX: String (25.0)
HECTARES: Real (16.3)
```

### nforest

| Property | Value |
|----------|-------|
| File | `nforest.shp` |
| Geometry | Polygon |
| Features | 71 |
| Extent | `(33.816299, 4.446621) - (41.809891, 14.098610)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/nforest.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/nforest.shp, this=0x641675cd6b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/nforest.shp, this=0x641675cd6b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/nforest.shp'
Geometry: Polygon
Extent: (33.816299, 4.446621) - (41.809891, 14.098610)
AREA: Real (12.3)
PERIMETER: Real (12.3)
FOREST_: Integer64 (11.0)
FOREST_ID: Integer64 (11.0)
VEGN: Integer (3.0)
VEGNTX: String (50.0)
```

### nforests

| Property | Value |
|----------|-------|
| File | `nforests.shp` |
| Geometry | Polygon |
| Features | 71 |
| Extent | `(-71536.726192, 492150.121467) - (806817.888528, 1559055.159611)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/nforests.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/nforests.shp, this=0x59fda00dcb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/nforests.shp, this=0x59fda00dcb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/nforests.shp'
Geometry: Polygon
Extent: (-71536.726192, 492150.121467) - (806817.888528, 1559055.159611)
AREA: Real (12.3)
PERIMETER: Real (12.3)
FOREST_: Integer64 (11.0)
FOREST_ID: Integer64 (11.0)
VEGN: Integer (3.0)
VEGNTX: String (50.0)
HECTARES: Real (16.3)
```

### nparks

| Property | Value |
|----------|-------|
| File | `nparks.shp` |
| Geometry | Polygon |
| Features | 37 |
| Extent | `(-100632.162839, 376090.628553) - (1007968.972419, 1574906.618646)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/nparks.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/nparks.shp, this=0x5a6015218b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/nparks.shp, this=0x5a6015218b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/nparks.shp'
Geometry: Polygon
Extent: (-100632.162839, 376090.628553) - (1007968.972419, 1574906.618646)
AREA: Real (12.3)
PERIMETER: Real (12.3)
PARKPY_: Integer64 (11.0)
PARKPY_ID: Integer64 (11.0)
SITE_CODE: Integer (8.0)
AREANAME: String (50.0)
ISO3: String (3.0)
SIZE: Integer64 (11.0)
YEAR: String (4.0)
IUCNCAT: String (4.0)
LON: Real (9.4)
LAT: Real (9.4)
CNTRYNAME: String (50.0)
DESIGNATE: String (50.0)
HECTARES: Real (16.3)
```

### rain_patrn

| Property | Value |
|----------|-------|
| File | `rain_patrn.shp` |
| Geometry | Polygon |
| Features | 20 |
| Extent | `(-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/rain_patrn.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/rain_patrn.shp, this=0x58ba7a7d6b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/rain_patrn.shp, this=0x58ba7a7d6b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/rain_patrn.shp'
Geometry: Polygon
Extent: (-161882.562500, 376388.125000) - (1495282.875000, 1645935.625000)
AREA: Real (18.5)
PERIMETER: Real (18.5)
ETRAIPA01C: Integer64 (11.0)
ETRAIPA01C: Integer64 (11.0)
PATTER: Integer (3.0)
PATTERN_G: Integer (3.0)
```

### rain_stat

| Property | Value |
|----------|-------|
| File | `rain_stat.shp` |
| Geometry | Point |
| Features | 146 |
| Extent | `(-22353.398438, 392184.718750) - (1083995.000000, 1578401.500000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/rain_stat.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/rain_stat.shp, this=0x5dea2148cb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/rain_stat.shp, this=0x5dea2148cb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/rain_stat.shp'
Geometry: Point
Extent: (-22353.398438, 392184.718750) - (1083995.000000, 1578401.500000)
AREA: Real (18.5)
PERIMETER: Real (18.5)
ETRAIST01C: Integer64 (11.0)
ETRAIST01C: Integer64 (11.0)
TOWN_NAME: String (25.0)
STATION_CO: Integer64 (11.0)
JAN: Real (11.1)
FEB: Real (11.1)
MARCH: Real (11.1)
MAY: Real (11.1)
JUN: Real (11.1)
JULY: Real (11.1)
AUG: Real (11.1)
SEPT: Real (11.1)
OCT: Real (11.1)
NOV: Real (11.1)
DEZ: Real (11.1)
RAIN_SUM: Real (11.1)
N_YEARS: String (11.0)
MAIN_TOWN: String (20.0)
SPOT: Integer (5.0)
PATTER: Integer (3.0)
APRIL: Real (11.1)
RAIN_MODEL: Real (12.3)
```

### rivers

| Property | Value |
|----------|-------|
| File | `rivers.shp` |
| Geometry | Line |
| Features | 5496 |
| Extent | `(-161882.562500, 393758.625000) - (1439188.625000, 1645935.625000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/rivers.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/rivers.shp, this=0x62c8a091cb40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/rivers.shp, this=0x62c8a091cb40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/rivers.shp'
Geometry: Line String
Extent: (-161882.562500, 393758.625000) - (1439188.625000, 1645935.625000)
FNODE_: Integer64 (11.0)
TNODE_: Integer64 (11.0)
LPOLY_: Integer64 (11.0)
RPOLY_: Integer64 (11.0)
LENGTH: Real (18.5)
ETRIVER01C: Integer64 (11.0)
ETRIVER01C: Integer64 (11.0)
RIV_NAME: String (25.0)
TYPE: String (25.0)
CLASS: Integer (4.0)
RIV_ORDER: Integer64 (16.0)
```

### roads

| Property | Value |
|----------|-------|
| File | `roads.shp` |
| Geometry | Line |
| Features | 2268 |
| Extent | `(-80509.867188, 390045.093750) - (1382796.500000, 1639481.250000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/roads.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/roads.shp, this=0x5fdc45066b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/roads.shp, this=0x5fdc45066b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/roads.shp'
Geometry: Line String
Extent: (-80509.867188, 390045.093750) - (1382796.500000, 1639481.250000)
FNODE_: Integer64 (11.0)
TNODE_: Integer64 (11.0)
LPOLY_: Integer64 (11.0)
RPOLY_: Integer64 (11.0)
LENGTH: Real (12.3)
ETROAD01CO: Integer64 (11.0)
ETROAD01CO: Integer64 (11.0)
TYPE: String (40.0)
CLASS: Integer64 (12.0)
ROAD_TYPE: String (50.0)
```

### streams

| Property | Value |
|----------|-------|
| File | `streams.shp` |
| Geometry | Line |
| Features | 4845 |
| Extent | `(-162480.472616, 390045.598579) - (1440060.835333, 1641864.098237)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/streams.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/streams.shp, this=0x601b9df36b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/streams.shp, this=0x601b9df36b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/streams.shp'
Geometry: Line String
Extent: (-162480.472616, 390045.598579) - (1440060.835333, 1641864.098237)
FNODE_: Integer64 (11.0)
TNODE_: Integer64 (11.0)
LPOLY_: Integer64 (11.0)
RPOLY_: Integer64 (11.0)
LENGTH: Real (12.3)
HYDDNETALL: Integer64 (11.0)
HYDDNETALL: Integer64 (11.0)
```

### towns

| Property | Value |
|----------|-------|
| File | `towns.shp` |
| Geometry | Point |
| Features | 935 |
| Extent | `(-155308.609375, 392184.718750) - (1369387.250000, 1606416.875000)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/towns.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/towns.shp, this=0x5c629aaf8b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/towns.shp, this=0x5c629aaf8b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/towns.shp'
Geometry: Point
Extent: (-155308.609375, 392184.718750) - (1369387.250000, 1606416.875000)
ETTOWN01CO: Integer64 (11.0)
ETTOWN01CO: Integer64 (11.0)
TOWN_NAME: String (25.0)
POP: Integer (7.0)
WEREDA: String (30.0)
REGION: String (20.0)
ZONES: String (20.0)
POPURB: Real (20.0)
POPRUR: Real (20.0)
POPTOT: Real (20.0)
RAIN: Real (12.3)
K_VALUE: Real (12.3)
SOIL: Real (12.3)
EROSIVITY: Real (12.3)
ELEVATION: Real (12.3)
POP_TXT: String (9.0)
RAIN_TXT: String (24.0)
ELEV_TXT: String (19.0)
```

### wetlands

| Property | Value |
|----------|-------|
| File | `wetlands.shp` |
| Geometry | Polygon |
| Features | 76 |
| Extent | `(-162480.485587, 491317.090089) - (1174375.546619, 1593601.242725)` |
| CRS | `PROJCRS["Adindan / UTM zone 37N",` |

**Fields:**

```
Shape: DBF Codepage = LDID/87 for /data/raw/vectors/wetlands.shp
Shape: Treating as encoding 'ISO-8859-1'.
GDAL: GDALOpen(/data/raw/vectors/wetlands.shp, this=0x5fb9acfc0b40) succeeds as ESRI Shapefile.
GDAL: GDALClose(/data/raw/vectors/wetlands.shp, this=0x5fb9acfc0b40)
GDAL: In GDALDestroy - unloading GDAL shared library.
INFO: Open of `/data/raw/vectors/wetlands.shp'
Geometry: Polygon
Extent: (-162480.485587, 491317.090089) - (1174375.546619, 1593601.242725)
AREA: Real (12.3)
PERIMETER: Real (12.3)
WETLANDS_: Integer64 (11.0)
WETLANDS_I: Integer64 (11.0)
CLASS: String (3.0)
CLASSTX: String (50.0)
NAME: String (121.0)
DESCRIP: String (251.0)
HECTARES: Real (16.3)
LOCATION: String (50.0)
```

---
_Inventory generated on 2026-02-18 21:04:15_
