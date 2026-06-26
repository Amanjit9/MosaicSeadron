Phase 1: Environment Setup (No Conda)
Anaconda must be completely disabled for this specific extraction step to prevent background sandbox corruption.
PowerShell
# 1. Deactivate conda completely until (base) disappears from your terminal prompt
conda deactivate

# 2. Create a native Windows Python virtual environment
python -m venv native_env

# 3. Activate the environment
.\native_env\Scripts\activate

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

