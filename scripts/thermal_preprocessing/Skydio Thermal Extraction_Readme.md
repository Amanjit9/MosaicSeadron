Skydio Thermal Extraction & SeaDroneLib Pipeline

This repository contains the complete environment setup and workflow to process thermal imagery from a Skydio drone (VT300-L sensor) over water surfaces.

Because standard photogrammetry (like Pix4D or Agisoft) fails over moving water due to shifting tie-points, this pipeline utilizes SeaDroneLib (MosaicSeadron) to stitch the orthomosaic using Direct Georeferencing (relying on exact GPS and gimbal pitch/roll/yaw metadata instead of visual tie-points).

To achieve this without dependency conflicts, the workflow is split into two isolated Python virtual environments:

Phase 1 (Python 3.12): Extracts raw 16-bit thermal TIFFs from proprietary Skydio R-JPEGs.
Phase 2 (Python 3.10): Stitches the extracted data into an orthomosaic.
🛑 General PrerequisitesOS: Windows 10/11Terminal: Git Bash (Highly Recommended)No Conda: Do not use Anaconda/Miniconda, as mixing pip and Conda with spatial libraries like GDAL will cause C-library corruptions.
🛠️ Phase 1: Thermal TIFF Extraction (Python 3.12)Because modern FLIR libraries default to a DJI-specific SDK (which rejects Skydio), and legacy FLIR libraries demand outdated dependencies, we must use a "Dependency Smuggle" method.
ExifTool Configuration
2. Download the Windows Executable .zip from exiftool.org.
3. Extract the .zip file.
4. Move BOTH of these into your project folder:The exiftool(-k).exe launcher (Rename exactly to exiftool.exe).The exiftool_files folder (Contains the required Perl engine).
Environment SetupInstall Python 3.12 from python.org (ensure "Add to PATH" is checked). 
Open Git Bash in your project folder and run:
# Create and activate the environment
python -m venv native_env
source native_env/Scripts/activate

# 1. Install modern spatial/math foundations
python -m pip install matplotlib numpy rasterio

# 2. Force-install the pre-DJI legacy FLIR extractor (Bypass dependency rules)
python -m pip install "flirimageextractor==1.4.1" --no-deps

# 3. Manually patch the skipped helper libraries
python -m pip install loguru requests opencv-python logzero tqdm

3. ExecutionRun your extraction script (python extract_thermal.py).Output: This will leave your original Skydio JPEGs in a main/ folder and output raw 16-bit TIFFs into a bands/ folder.
4.🌍 Phase 2: SeaDroneLib / MosaicSeadron Setup (Python 3.10)SeaDroneLib strictly requires Python 3.10 and a specific pre-compiled GDAL wheel to function on Windows.
# Python 3.10 Installation
2. Download the Python 3.10.x Windows Installer.
3. Choose Customize Installation.Check "Add Python to environment variables".
4. Leave "Associate files with Python" unchecked to keep 3.12 as your system default. Install.
# Environment Setup
Open a fresh Git Bash window and run:
# Clone the populated repository and enter it
git clone [https://github.com/SeadroneICMAN/MosaicSeadron](https://github.com/SeadroneICMAN/MosaicSeadron)
cd MosaicSeadron

# Create a 3.10-specific environment using the py launcher and activate it
py -3.10 -m venv seadronelib-venv
source seadronelib-venv/Scripts/activate

# Install requirements
python -m pip install -r requirements.txt

# Install the exact GDAL wheel for Python 3.10
python -m pip install dependencies/GDAL-3.4.3-cp310-cp310-win_amd64.whl

# Install missing spatial tools
python -m pip install rasterio jupyter geopandas

# Generate and run the SeaDroneLib installation scripts
python -B scripts/package_manager_generator.py -e seadronelib-venv -p micasense,seadrone -i 1 -ri 1
bash scripts/install.sh

🚀 Phase 3: Processing the OrthomosaicTo trick SeaDroneLib into processing Skydio imagery, we process it as a "DJI dataset".1. Data StructureEnsure your working folder looks exactly like this:/Your_Project_Folder
  ├── /main             (Contains Skydio R-JPEGs)
  ├── /bands            (Contains extracted TIFFs)
  └── summary.yml       (Flight metadata configuration)
2. The summary.yml File
SeaDroneLib requires you to isolate the straight flight lines and exclude photos taken while the drone was turning, banking, or rotating. Create a summary.yml file formatted like this:flight_info:
  sensor: "dji"  
  # MUST remain 'dji' to trigger the RGB/Thermal dual-folder pipeline
  flight_name: "Skydio_Thermal_Survey_01"
  altitude_m: 120

lines:
  line_1:
    start_img: "S1007773_R.JPG"
    end_img: "S1007803_R.JPG"
  # (Skip the turning photos)
  line_2:
    start_img: "S1007806_R.JPG"
    end_img: "S1007836_R.JPG"
  # Repeat for all transects...
3. Launching the SoftwareWhenever you want to process a new flight, open Git Bash in your MosaicSeadron folder and run:
source seadronelib-venv/Scripts/activate
jupyter notebook
Navigate in your browser to /seadrone_usage/batch_processing_jupyter/dji.ipynb.
Update the paths in the notebook to point to your data folder, run the cells, and export your radiometrically accurate thermal orthomosaic!
