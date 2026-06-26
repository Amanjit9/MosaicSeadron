import os
import glob
import rasterio
import flirimageextractor

# Configure your directories (Update these paths to match your local machine)
input_dir = r"D:\Path\To\Your\main\images"
output_dir = r"D:\Path\To\Your\bands\output"

# Initialize the pure FLIR extractor (Bypasses DJI SDK completely)
flir = flirimageextractor.FlirImageExtractor() 

# Find all JPGs in the main folder
jpegs = glob.glob(os.path.join(input_dir, "*.JPG"))
print(f"Found {len(jpegs)} images to process...")

for img_path in jpegs:
    filename = os.path.basename(img_path)
    tif_name = filename.replace(".JPG", ".tif").replace(".jpg", ".tif")
    output_path = os.path.join(output_dir, tif_name)

    try:
        # Extract the FLIR thermal array natively
        flir.process_image(img_path)
        thermal_array = flir.get_thermal_np()

        # Save as a 16-bit/32-bit Floating Point TIFF for photogrammetry
        height, width = thermal_array.shape
        with rasterio.open(
            output_path,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=thermal_array.dtype,
            crs=None,
            transform=None
        ) as dst:
            dst.write(thermal_array, 1)

        print(f"Success: Extracted {tif_name}")

    except Exception as e:
        print(f"Error processing {filename}: {e}")

print("Extraction complete. Your bands folder is ready for photogrammetry.")