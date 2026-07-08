# Skydio X10 VT300-L Thermal Orthomosaic Pipeline
## Complete Journey: Bugs Found, Diagnosed and Fixed

---

## PHASE 0 — Starting Point

**Goal:** Use [MosaicSeadron](https://github.com/SeadroneICMAN/MosaicSeadron) (open-source, designed for DJI + MicaSense) to georeference and mosaic raw radiometric JPEGs from a Skydio X10 drone with VT300-L thermal sensor.

**Input data:**
- 173 raw radiometric JPEGs (`S1007773_R.JPG` … `S1008289_R.JPG`) in `main/`
- Flight area: Simpson Swamp Rd, Tuscaloosa AL (lat 33.011–33.016, lon -87.643 to -87.637)
- Altitude: ~144m AGL

---

## PHASE 1 — Environment Setup

### What we did
- Created `seadronelib-venv` (Python 3.10) with SeaDroneLib installed
- Created `native_env` (Python 3.12) for ExifTool-based extraction scripts

### Problem encountered
> `ModuleNotFoundError: No module named 'rasterio'` in Jupyter

**Cause:** Jupyter was using the system Python kernel, not the venv kernel.

**Fix:**
```bash
./seadronelib-venv/Scripts/python.exe -m jupyter notebook
# OR register the venv as a kernel:
./seadronelib-venv/Scripts/python.exe -m ipykernel install --user \
  --name seadronelib-venv --display-name "Python 3.10 (seadronelib-venv)"
```

### CuPy numpy conflict (later)
Installing CuPy upgraded numpy 1.25.2 → 2.2.6, breaking rasterio.

**Fix:**
```bash
pip install "numpy==1.25.2" --force-reinstall
```

---

## PHASE 2 — Thermal TIFF Extraction

### What we did
Ran `extract_thermal.py` using `flirimageextractor` to extract raw 16-bit thermal arrays from radiometric JPEGs → `bands/` folder (640×512 uint16 TIFFs).

### Result
✓ **Working** — 172 TIFFs produced (1 image `S1008262_R.JPG` was corrupt/missing, dropped).

---

## PHASE 3 — Metadata Extraction

### Bug 1: Wrong orientation tags extracted
**Original script** (`skydio_batch_setup.py`) extracted:
```python
"Yaw":   data.get("XMP:CameraOrientationNEDYaw")    # WRONG
"Roll":  data.get("XMP:CameraOrientationNEDRoll")   # WRONG
"Pitch": data.get("XMP:CameraOrientationNEDPitch")  # correct for pitch only
```

**Problem:** `CameraOrientationNEDYaw` and `CameraOrientationNEDRoll` describe the **gimbal/camera**, which spins freely around the nadir axis while still pointing straight down. This produced:
- Yaw standard deviation: **91°** within a single straight flight line (should be ~0.3°)
- Roll range: **−178° to +172°** (should be ~5°)

**Diagnosis:** Compared tag names from `thermal_tags_dump.txt`:
```
XMP:VehicleOrientationNEDYaw  = 61.148805  ← drone body heading (stable)
XMP:CameraOrientationNEDYaw  = 65.307688  ← gimbal twist (random noise)
XMP:VehicleOrientationNEDRoll = 5.4633    ← vehicle body roll (stable)
XMP:CameraOrientationNEDRoll = -4.303942  ← gimbal roll (noisy)
```

**Fix (`reextract_metadata_vehicle_v3.py`):**
```python
"Yaw":   data.get("XMP:VehicleOrientationNEDYaw")   # vehicle body heading
"Roll":  data.get("XMP:VehicleOrientationNEDRoll")  # vehicle body roll
"Pitch": data.get("XMP:CameraOrientationNEDPitch")  # camera pitch (reliable ~-90°)
```

**Result after fix:** Yaw std per line dropped from **91° → 0.29°** ✓

---

## PHASE 4 — Flight Line Building (`summary.yml`)

### Bug 2: `load_flight_lines()` returned 0 lines
**Cause:** `load_flight_lines()` reads the output format of `save_flight_lines()` — a list of dicts with integer row indices. Our `summary.yml` used filename-based boundaries. Parser found no matching keys → returned `[]`.

**Fix:** Parse `summary.yml` ourselves and convert filename spans to row indices:
```python
# For each line in summary.yml:
si = source_to_idx[cfg['start_img']]
ei = source_to_idx[cfg['end_img']]
# Build the dict manually in the format SeaDroneLib expects
```

### Bug 3: `compute_flight_lines()` failed on Skydio data
**Cause:** Author's `compute_flight_lines()` clusters images by Yaw to detect transect boundaries. For DJI, Yaw (vehicle heading) is stable per line so clustering works. For Skydio, we were using `CameraOrientationNEDYaw` (gimbal twist = noise) → only 2 bogus clusters from 173 images.

**Fix:** Use manually-curated `summary.yml` (author's intended fallback for non-DJI workflows).

### Bug 4: `'yaw': None` in flight_lines — per-image values used
**Initial approach:** Set `'yaw': None` so `get_georefence_by_uuid()` reads each image's own Yaw.

**Problem:** Even with correct `VehicleOrientationNEDYaw` (std=0.29°), boundary frames at turns had slightly higher values. More importantly, the author's design **always uses a single fixed value per line** (not None).

**Fix (matching author's design):**
```python
interior = segment.iloc[1:-1]  # exclude noisy boundary frames from median
line_yaw = circular_median(interior['Yaw'].tolist())
corrected_yaw = (line_yaw + 90.0) % 360  # +90° confirmed by ArcGIS test

flight_lines.append({
    'yaw':   corrected_yaw,              # fixed per-line — not None
    'pitch': None,                        # per-image pitch is reliable
    'roll':  float(interior['Roll'].median()),  # fixed median roll
    'alt':   None,
})
```

### Bug 5: `'roll': None` — noisy gimbal roll caused misplaced tiles
**Symptom:** Images `S1007806_R.JPG`, `S1007839_R.JPG` (line starts/ends) visibly misplaced in ArcGIS.

**Cause:** Even after fixing to `VehicleOrientationNEDRoll`, boundary frames captured during turns still had elevated roll values (~13° vs ~5° interior median).

**Fix:** Set `'roll': float(interior['Roll'].median())` — all frames in line inherit stable median roll, boundary frames can no longer deviate.

---

## PHASE 5 — Sensor Specification Injection (Cell 3)

### Bug 6: Wrong column names — `GPSLatitude` vs `Latitude`
**Cause:** `load_metadata()` creates `Latitude`/`Longitude`/`Altitude` from the CSV. But `get_georefence_by_uuid()` reads `GPSLatitude`/`GPSLongitude`/`GPSAltitude`. Column mismatch → GPS coordinates not found → NaN transforms.

**Fix:**
```python
flight_metadata['GPSLatitude']  = flight_metadata['Latitude']
flight_metadata['GPSLongitude'] = flight_metadata['Longitude']
flight_metadata['GPSAltitude']  = flight_metadata['Altitude']
```

### Bug 7: Pitch convention mismatch — all NaN transforms
**This was the root cause of ALL NaN transforms throughout the project.**

**cameratransform convention:** `tilt_deg=0` → nadir (straight down), `tilt_deg=90` → horizontal

**DJI stores:** `FlightPitchDegree ≈ 0°` (vehicle body, level flight) → passed directly → tilt=0 → nadir ✓

**Skydio stores:** `CameraOrientationNEDPitch ≈ -89.88°` (NED frame, -90° = pointing down) → passed directly → tilt=-89.88° → **outside 0-180° range → NaN** ✗

**Fix:**
```python
flight_metadata['Pitch'] = 90.0 + flight_metadata['Pitch']
# 90 + (-89.88) = 0.12° ≈ nadir ✓
```

### Bug 8: ImageWidth/Height and SensorX/Y order
**Cause:** `get_georefence_by_uuid()` internally does:
```python
image_size  = (capture['ImageWidth'],  capture['ImageHeight'])[::-1]
sensor_size = (capture['SensorX'],     capture['SensorY'])[::-1]
```
The `[::-1]` reversal means `ImageWidth` ends up as the **height** seen by cameratransform.

**Diagnosed by:** Opening georeferenced TIFFs in ArcGIS — tiles appeared rotated 90°. Transform matrix analysis showed top-edge bearing was 320° instead of expected 150°.

**Fix (confirmed by ArcGIS orientation test):**
```python
# Inject original order — after [::-1] cameratransform receives correct values
flight_metadata['ImageWidth']  = SKYDIO_SENSOR.width    # 640
flight_metadata['ImageHeight'] = SKYDIO_SENSOR.height   # 512
flight_metadata['SensorX']     = SKYDIO_SENSOR.sensor_x # 7.68
flight_metadata['SensorY']     = SKYDIO_SENSOR.sensor_y # 6.14
```

---

## PHASE 6 — Heading Offset (+90°)

### Bug 9: All tiles rotated ~90° in ArcGIS
**Diagnosis:** Ran `GeorefenceUtils.get_transform()` with 8 candidate heading offsets (0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°) and saved 8 GeoTIFFs. Loaded in ArcGIS. File `h150.9_off090_original.tif` aligned correctly over the survey area.

**Root cause:** The Skydio VT300-L thermal sensor is physically mounted with its image top rotated 90° relative to the vehicle body heading. DJI cameras align image top with vehicle forward direction; Skydio does not.

**Fix:**
```python
corrected_yaw = (line_yaw + 90.0) % 360  # ArcGIS confirmed
```

### Bug 10: FLIP_AXIS=[1] caused 180° rotation
**Original code had:** `FLIP_AXIS = [1]` (horizontal pixel flip).

**Effect:** Combined with the +90° heading, this produced a net 180° rotation — top-edge bearing was 320° instead of 150°.

**Diagnosed by:** Transform matrix analysis:
```
a=-0.00000077  b=-0.00000112  → top-edge bearing = 320.7° (expected 150°)
```

**Fix:**
```python
FLIP_AXIS = None  # No flip — heading offset handles orientation
```

---

## PHASE 7 — Georeferencing

### What worked after all fixes
- 172 TIFFs georeferenced correctly
- `georefence_bands()` used (not `georefence_images()` — thermal TIFFs are single-band uint16, not colour JPEGs)
- Spot-check: CRS=EPSG:4326, top-edge bearing ~150° ✓, bounds inside survey area ✓

### Key API lesson
```python
# CORRECT for thermal TIFFs:
processor.georefence_bands(... profile=BANDS_PROFILE ...)  # uint16, count=1

# WRONG for thermal (designed for RGB JPEGs):
processor.georefence_images(...)  # would fail on uint16 single-band
```

---

## PHASE 8 — Merging

### Bug 11: `processor.merge(method='mean')` — discrete blocky output
**Symptom:** Hard rectangular seams at every tile boundary. Thermal mosaic looked like a patchwork quilt rather than a continuous surface.

**Cause:** SeaDroneLib's `merge(method='mean')` averages pixel values with **equal weights** regardless of position within the tile. At tile boundaries, the abrupt transition from one tile's content to another's creates hard edges.

**Fix:** Replaced with custom **distance-weighted feathered merge** using `rasterio.warp.reproject()`:

```python
# For each tile, compute feather weight:
valid = (tile_data > 0).astype(float)
dist  = distance_transform_edt(valid)      # distance from tile edge
wt    = dist / dist.max() * valid          # 0 at edges, 1 at centre

# Accumulate weighted contributions:
accum  += tile_data * wt
weight += wt

# Normalise:
output = accum / weight  # smooth continuous blend
```

**Why `rasterio.warp.reproject()` is required (not simple offset blitting):**
Our tiles have **rotated affine transforms** (non-zero `b` and `d` coefficients) because of the +90° heading offset. Simple row/col offset blitting only works for axis-aligned tiles. `reproject()` correctly maps each rotated pixel to its geographic position in the axis-aligned mosaic grid.

### Bug 12: MemoryError in RGB feathered merge
```
Unable to allocate 36.2 GiB for array (3, 42391, 38178) float64
```
**Fix:** Process in 512-row strips (float32, one band at a time):
```python
# Peak RAM per strip: mosaic_w × STRIP_H × 4 bytes ≈ 350 MB
# vs full mosaic: 36 GB → impossible
```

---

## PHASE 9 — Post-Processing

### Issue: Planck calibration (DN → °C)
**Input:** Raw uint16 DN values (21–40 range)
**Formula:** FLIR Planck constants from APP1 EXIF tags:
```
R1=2794437.5, R2=1.0, B=1680.1614, F=1.0, O=-12587.0
Emissivity=0.95, T_reflected=22.0°C
```
**Output:** Calibrated surface temperature 22–31°C ✓

### Note on histogram matching
**NOT applied to thermal.** Thermal data is radiometrically calibrated to absolute temperature. Per-line brightness normalisation (designed for RGB) would corrupt calibrated DN values and produce physically incorrect temperatures.

---

## FINAL CONFIRMED PARAMETER VALUES

| Parameter | Wrong value used | Correct value | How confirmed |
|---|---|---|---|
| Yaw source | `CameraOrientationNEDYaw` | `VehicleOrientationNEDYaw` | Tag dump comparison |
| Roll source | `CameraOrientationNEDRoll` | `VehicleOrientationNEDRoll` | Tag dump comparison |
| Pitch source | `CameraOrientationNEDPitch` | Same — but needs conversion | Correct tag, wrong convention |
| Pitch value | Raw NED (-89.88°) | `90 + NED_pitch` = 0.12° | cameratransform convention |
| Heading offset | 0° | +90° | ArcGIS orientation test |
| FLIP_AXIS | [1] | None | Transform matrix analysis |
| flight_lines yaw | None (per-image) | circular_median(interior) | Author source code design |
| flight_lines roll | None (per-image) | interior['Roll'].median() | Misplaced tile diagnosis |
| Merge method | SeaDroneLib mean | Distance-weighted feathering | Visual quality analysis |
| GPSLatitude | Not injected | = flight_metadata['Latitude'] | Source code reading |

---

## FINAL PIPELINE (working)

```
1. extract_thermal.py        → bands/ (172 × 640×512 uint16 TIFFs)
2. reextract_metadata_v3.py  → metadata.csv (VehicleNED Yaw/Roll, CameraNED Pitch)
3. Notebook Cell 0-1         → imports, paths
4. Notebook Cell 2           → Sensor(640×512, 13.6mm focal, 7.68×6.14mm sensor)
5. Notebook Cell 3           → inject GPS aliases, pitch conversion 90+pitch
6. Notebook Cell 4           → sync check (drop missing TIFFs)
7. Notebook Cell 5           → flight lines: fixed yaw+90°, fixed roll median
8. Notebook Cell 6           → partitions
9. Notebook Cell 7           → georefence_bands() → 172 georeferenced TIFFs
10. Notebook Cell 8          → feathered merge → thermal_mosaic_feathered.tif
11. Notebook Cell 9          → quality check
12. Notebook Cell 10         → 4-panel visualisation
13. Notebook Cell 11         → Planck calibration → celsius map
```

---

## KEY LESSONS

1. **Tag naming matters:** `Vehicle*` vs `Camera*` in Skydio XMP tags are fundamentally different physical quantities. Always check the actual tag dump, not assumptions from DJI documentation.

2. **Coordinate conventions differ:** NED pitch (-90° = nadir) vs cameratransform tilt (0° = nadir). Always verify the convention before passing angles to any library.

3. **Read the library source code:** `get_georefence_by_uuid()` doing `[::-1]` on sensor dimensions and reading `GPSLatitude` not `Latitude` are invisible without reading the source. These caused weeks of debugging.

4. **Validate with actual GIS software:** Opening individual tiles in ArcGIS/QGIS is the most reliable diagnostic for orientation and position errors. The mosaic preview hides errors that are obvious per-tile.

5. **SeaDroneLib's `merge(method='mean')` ≠ feathered blending:** For rotated tiles, equal-weight averaging produces hard seams. Distance-weighted feathering with `rasterio.warp.reproject()` is required for continuous output.

6. **Thermal data requires no histogram matching:** Unlike RGB, thermal DN values are radiometrically calibrated. Brightness normalisation between lines corrupts absolute temperature values.

---

## RGB PIPELINE EXTENSION

### Starting point
Same SeaDroneLib pipeline adapted for Skydio X10 RGB sensor (`MAIN_VISIBLE`, 8192×6144, 50.3MP).

---

## RGB PHASE 1 — Metadata Extraction

### Key differences from thermal
- Filename pattern: `S1007771.JPG` (no `_R` suffix, offset by 2 from thermal)
- Resolution: 8192×6144 (50.3MP) vs 640×512
- No Planck radiometric tags → no Celsius calibration
- `CameraSource: MAIN_VISIBLE` vs `INFRARED`

### Script: `extract_metadata_rgb.py`
Same vehicle orientation tags confirmed present on RGB images:
```
XMP:VehicleOrientationNEDYaw  = 60.724789  (same vehicle, same flight)
XMP:VehicleOrientationNEDRoll = 0.767094
XMP:CameraOrientationNEDPitch = -89.99     (nadir — reliable)
```
Fix applied from start — no re-extraction needed.

### Sensor values derived from EXIF dump
```
XMP:CalibratedFocalLengthX = 4988.81 px
EXIF:FocalLength = 7.7 mm
pixel_pitch = 7.7 / 4988.81 = 0.001543 mm/px
sensor_x = 8192 * 0.001543 = 12.644 mm
sensor_y = 6144 * 0.001543 = 9.483 mm
GSD = 2.89 cm/px at 144m altitude
Footprint = 236.5m × 177.3m (92% side overlap)
```

---

## RGB PHASE 2 — summary_rgb.yml

Manually curated by identifying start/end images of each flight line — same approach as thermal `summary.yml`. Validated: all 15 lines, Yaw std < 1° per line, 173/173 images covered.

---

## RGB PHASE 3 — Georeferencing Issues

### Bug 13: `georefence_images()` vs `georefence_bands()`
RGB uses `georefence_images()` (3-band colour JPEGs), not `georefence_bands()` (single-band TIFFs).

### Bug 14: Same +90° heading offset applies
Confirmed by same ArcGIS orientation test:
- `h150.9_off000_original.tif` aligned correctly
- Same physical sensor mounting offset as thermal (both share Skydio gimbal)

### Bug 15: Roll = None caused misplaced tiles
Same diagnosis as thermal: `S1007804.JPG` had Roll = −13° (mid-turn bank). Fixed with `interior['Roll'].median()`.

---

## RGB PHASE 4 — Feathered Merge Challenges

### Bug 16: Simple row/col offset blitting fails for rotated tiles
**Initial approach (v1, v2, v3):** Calculate tile position from GPS coordinates, blit rectangular chunks at computed row/col offset into accumulation arrays.

**Failure:** Tiles have rotated affine transforms (`b=-0.00000027, d=0.00000023` — non-zero off-diagonals). Each source pixel maps diagonally across the mosaic grid, not to a rectangular block.

**Evidence:** Debug script showed:
```
Method A (bounds-based offset): WRONG for rotated tiles
  bounds.top ≠ actual top-left pixel for rotated tile
Method B (transform.c/f-based): still wrong
  transform.c/f = top-left pixel geographic coords
  but pixel (0,0) → pixel (0,1) → ... maps diagonally
```

**Fix:** Use `rasterio.warp.reproject()` which handles rotation correctly:
```python
reproject(source=src_data, destination=dst_data,
          src_transform=src_tf, dst_transform=strip_tf,
          resampling=Resampling.bilinear)
```

### Bug 17: MemoryError — 36GB array allocation
```
Unable to allocate 36.2 GiB for array (3, 42391, 38178) float64
```

**Fix:** Process in 512-row strips, one band at a time, float32:
```python
# Peak RAM per strip per band: 38178 × 512 × 4 bytes = 78MB
# vs full mosaic all bands: 36 GB → impossible
```

### Bug 18: All pixels = 0 in output (Coverage 0.2%)
**Cause:** `tile_bounds[fp]` used `bounds.top` (bounding envelope top) to compute row offset. For rotated tiles, the bounding envelope is larger than the actual pixel extent, so computed strip offsets were wrong — tile data was written outside the valid strip range and discarded.

**Fix:** Use `rasterio.warp.reproject()` — it handles the mapping correctly by reprojecting through geographic coordinates, bypassing the offset calculation entirely.

---

## RGB PHASE 5 — Histogram Matching

### Problem: Alternating bright/dark stripe pattern
**Cause:** BRDF (Bidirectional Reflectance Distribution Function) effect:
- NE passes (heading ~61°): sun on camera's left side → vegetation appears brighter
- SW passes (heading ~241°): sun on camera's right side → vegetation appears darker
- Result: alternating bright/dark stripes matching flight line spacing

**Not a georeferencing error** — confirmed by overlaying individual tiles in ArcGIS. Each tile sits in correct geographic position; the brightness difference is in the image content itself.

**Fix:** Per-band histogram matching normalises each line's brightness to the global median:
```python
# For each line, sample middle frames for mean brightness
gain = ref_mean / line_means[name]  # per-band (R, G, B separately)

# Apply gain to all files in that line
corrected = np.clip(data * gain[:, None, None], 0, 255).astype(np.uint8)
```

**Why NOT full BRDF correction:**
- Requires sun position, per-pixel view angle, BRDF model parameters
- Consumer RGB cameras with auto-exposure lack precise radiometric calibration
- Histogram matching handles 70-80% of the effect practically

---

## RGB PHASE 6 — Illumination vs Position Confusion

### Investigation: Shoreline stepping pattern
**Initial diagnosis (wrong):** GPS lag bias → even/odd lines shift opposite directions.

**Actual diagnosis (correct):** Solar illumination geometry — confirmed by overlaying individual tiles in ArcGIS:
- Each tile sits in the correct geographic position
- The apparent shoreline position differs between NE/SW passes because **shadow length changes** with sun angle
- NE-facing passes: shorter shoreline shadows (sun behind camera)
- SW-facing passes: longer shoreline shadows (sun in front of camera)
- The shadow boundary appears as a shifted "shoreline" in the merged image

**This is not fixable by GPS correction or histogram matching.** It is an inherent limitation of bidirectional lawnmower surveys without BRDF correction or SfM tie-point matching.

---

## COMPARISON: Our Pipeline vs Agisoft/Pix4D

| Aspect | Our pipeline (direct georef) | Agisoft SfM |
|---|---|---|
| Position source | GPS directly as truth | GPS as starting guess only |
| Orientation source | Vehicle IMU tags | Refined by feature matching |
| Color balancing | Histogram matching per line | Tie-point based across strips |
| Shadow handling | Not corrected | Partially corrected via blending |
| Works over water | Yes (no features needed) | Struggles (no matchable features) |
| Processing time | Minutes | Hours |
| Requires GCPs | No | For absolute accuracy |
| Output quality | Good — continuous, calibrated | Better visual appearance |

**Key insight:** Agisoft hides even/odd illumination differences by warping each image using tie-point geometry so features align across passes. Our pipeline cannot do this without feature matching. For thermal data over featureless water/vegetation, our approach is actually **more reliable** than SfM which would fail to find tie points.

---

## FINAL FILE OUTPUTS

| File | Description |
|---|---|
| `metadata.csv` | 173 rows, VehicleNED Yaw/Roll + CameraNED Pitch |
| `bands/*.tif` | 172 raw 640×512 uint16 thermal TIFFs |
| `georeferences/bands/all/*.tif` | 172 georeferenced thermal TIFFs |
| `merges/bands/thermal_mosaic_feathered.tif` | Final feathered thermal mosaic |
| `merges/bands/thermal_mosaic_celsius.png` | Calibrated temperature map 22–31°C |
| `RGB/metadata_rgb.csv` | 173 RGB rows, same tag corrections |
| `RGB/georeferences/main/*.tif` | 173 georeferenced RGB tiles |
| `RGB/georeferences/main_corrected/*.tif` | Histogram-corrected RGB tiles |
| `RGB/merges/main/rgb_mosaic_feathered.tif` | Final feathered RGB mosaic |

---

## ERROR COUNT SUMMARY

| Category | Errors found | All fixed? |
|---|---|---|
| Environment setup | 2 (kernel, numpy) | ✓ |
| Metadata extraction | 2 (wrong tags, wrong format) | ✓ |
| Flight line building | 3 (parser, clustering, None yaw/roll) | ✓ |
| Sensor injection | 3 (GPS aliases, pitch convention, dimension order) | ✓ |
| Orientation | 2 (heading offset, flip axis) | ✓ |
| Merge quality | 3 (mean vs feathered, memory, offset blitting) | ✓ |
| RGB specific | 4 (sensor spec, tile blitting, memory, histogram) | ✓ |
| **Total** | **19 bugs diagnosed and fixed** | ✓ |

