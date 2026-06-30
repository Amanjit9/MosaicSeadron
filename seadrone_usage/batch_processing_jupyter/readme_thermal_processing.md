# open the git bash
git clone https://github.com/SeadroneICMAN/MosaicSeadron
# Set the directory
cd D:\Thermal_Mosaic

cd MosaicSeadron
# install the requirements and libraries 
python -m pip install -r requirements.txt

python -m pip install dependencies/GDAL-3.4.3-cp310-cp310-win_amd64.whl

python -B scripts/package_manager_generator.py -e droneOS -p micasense,seadrone -i 1 -ri 1

bash scripts/install.sh

# activate the environment
source seadronelib-venv/Scripts/activate
# check the tag parser and see the list of file name 
cd D:\Thermal_Mosaic

ls RGB/main | head -5

./exiftool.exe -G -j "RGB/main/S1007780.JPG" > rgb_tags_dump.txt

cat rgb_tags_dump.txt

# Install the packages in an activated environment
python -m pip install "numpy<1.26.0"

python -m pip install rasterio

jupyter notebook
