Phase 1: Environment Setup (No Conda)
Anaconda must be completely disabled for this specific extraction step to prevent background sandbox corruption.
# if you dont have python follow this instruction 
Install a Clean Python 3.12
Go directly to the official download link: python.org/downloads

Click the yellow Download Python 3.12.x button (or 3.11/3.13).

Open the downloaded .exe installer file.

⚠️ CRITICAL STEP: At the very bottom of the first installation window, check the box that says "Add python.exe to PATH". If you miss this box, Windows will continue to say "Python was not found."

Click Install Now.
Open Git bash OR if it is Powershell
# 1. Deactivate conda completely until (base) disappears from your terminal prompt
conda deactivate
# 2. Create a native Windows Python virtual environment
python -m venv native_env

# 3. Activate the environment
if it is Powershell
.\native_env\Scripts\activate
 or Git Bash
source native_env/Scripts/activate

Phase 2: The Dependency Smuggle
We must install modern libraries first, then force-install the legacy FLIR library while explicitly commanding it to ignore its own broken dependency rules.

# 1. Install modern, stable packages that Python 3.12 supports
python -m pip install matplotlib numpy rasterio

# 2. Force-install the pre-DJI version of the extractor, strictly bypassing dependencies
python -m pip install "flirimageextractor==1.4.1" --no-deps

Phase 3: ExifTool Configuration
ExifTool does the heavy lifting to read the proprietary FLIR tags.

Download the Windows Executable from exiftool.org.

Extract the .zip file and rename exiftool(-k).exe to exactly exiftool.exe.

Place exiftool.exe directly into your master project folder alongside your Python scripts.

Troubleshooting Note: If the script throws a perl5*.dll error during execution, delete the hidden exiftool_files folder in your project directory and run the script again to force a clean unpack.

Phase 4: The Extraction Script
Create extract_thermal.py in your master folder. This script strictly uses the native FLIR extractor and avoids DJI parsing logic.
Phase 5: Execution
With your (native_env) active and your Skydio R-JPEGs in the configured input folder, run the script:python extract_thermal.py
Once the script completes, you can deactivate the native Python environment and return to your primary photogrammetry environment to stitch the resulting TIFFs.
# The Autopsy: What Failed & Why
Setting this up requires navigating a perfect storm of deprecated libraries, corrupted binaries, and proprietary SDKs. If you deviate from the installation path, you will likely hit one of these fatal errors:

Conda + Pip Mixing (pyexpat.dll load failure): Anaconda environments are notorious for C-library conflicts. Mixing pip and conda installs forcefully downgraded NumPy, which cascaded and corrupted the core Windows XML parser, effectively bricking the geospatial environment.

FLIR Desktop Software (Paywall): FLIR Thermal Studio Starter was tested as a no-code bypass, but FLIR recently locked the "Batch Export" feature behind a paid Pro license, making it useless for drone mapping mosaics.

The DJI SDK Hijack (Unsupported camera type: VT300-L_40IR): Newer versions of the open-source library (flirimageextractor > 1.5.0) integrated the proprietary DJI Thermal SDK. The DJI C++ code intercepts all images, realizes the Skydio sensor isn't a DJI camera, and instantly throws a fatal error before ExifTool can do its job.

Python 3.12 vs. Legacy Build Tools (ModuleNotFoundError: No module named 'distutils'): Rolling back to version 1.4.1 (the pre-DJI version) failed initially because Python 3.12 permanently deleted distutils. Furthermore, 1.4.1 is hard-coded to demand matplotlib==3.5.3, which cannot compile on modern Python architecture.

Corrupted ExifTool (Could not find ... perl5*.dll): Even with a perfect Python environment, ExifTool can fail to unpack its temporary .dll files due to Windows Defender or corrupted downloads, requiring a manual replacement of the executable.
