import csv
import os
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject

def create_hls_folders(out_dir, file_path):
    # Splitting the file name and extracting the relevant subfolders
    subfolders = os.path.basename(file_path).split(".")[1:4]

    # Set the current path to the output directory
    current_path = out_dir

    # Iterate through each subfolder
    for subfolder in subfolders:
        # Append the current subfolder to the current path
        current_path = os.path.join(current_path, subfolder)

        # Create the subfolder if it doesn't exist
        os.makedirs(current_path, exist_ok=True)

    # Create the new file path by joining the current path and the original file name
    new_file_path = os.path.join(current_path, os.path.basename(file_path))

    # Move the file to the new file path
    os.rename(file_path, new_file_path)

def find_subfolders(directory):
    # Initialize an empty list to store the subfolder paths
    subfolders = []

    # Traverse the directory tree rooted at the given directory
    for root, dirs, files in os.walk(directory):
        # Check if there are no subdirectories in the current iteration
        if not dirs:
            # Append the current root directory (subfolder) to the subfolders list
            subfolders.append(root)

    # Return the list of subfolders
    return subfolders

def composite_bands(input_files, output_file, band_names):
    # Open the first input file to get the metadata
    with rasterio.open(input_files[0]) as src:
        profile = src.profile

    # Update the metadata for the output file
    profile.update(count=len(input_files))

    # Create the output file
    with rasterio.open(output_file, "w", **profile) as dst:
        for i, (file, band_name) in enumerate(zip(input_files, band_names), start=1):
            with rasterio.open(file) as src:
                dst.write(src.read(1), i)
                dst.set_band_description(i, band_name)
    print(f"\tOutput file '{os.path.basename(output_file)}' created successfully.")

def hls_xml_csv(xml_file):
    # Parse XML File
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Extract itmes from the XML and write to the CSV
    ur = root.find("GranuleUR").text
    ur_split = ur.split(".")
    sensor = ur_split[1]  # Sensor
    tile = ur_split[2]  # Tile ID
    data_granule = root.find("DataGranule")
    production_date = data_granule.find("ProductionDateTime").text  # Production Date
    temporal = root.find("Temporal")
    date_range = temporal.find("RangeDateTime")
    begin_date = date_range.find("BeginningDateTime").text  # Sensing Start Time
    end_date = date_range.find("EndingDateTime").text  # Sensing End Time
    attributes = root.find("AdditionalAttributes")
    for attribute in attributes.findall("AdditionalAttribute"):
        if attribute.find("Name").text == "CLOUD_COVERAGE":
            cc_values = attribute.find("Values")
            cc_value = cc_values.find("Value").text  # Cloud Coverage
        if attribute.find("Name").text == "SPATIAL_RESAMPLING_ALG":
            resampling_values = attribute.find("Values")
            resampling_value = resampling_values.find("Value").text  # Resampling Method
        if attribute.find("Name").text == "HORIZONTAL_CS_NAME":
            cs_values = attribute.find("Values")
            cs_value = cs_values.findall("Value")
            cs_value = cs_value[0].text
            utm = cs_value.replace(",", "")  # UTM Zone
        if attribute.find("Name").text == "REF_SCALE_FACTOR":
            sf_values = attribute.find("Values")
            sf_value = sf_values.find("Value").text  # Reference Scale Factor
        if attribute.find("Name").text == "MEAN_SUN_AZIMUTH_ANGLE":
            sa_values = attribute.find("Values")
            sa_value = sa_values.find("Value").text  # Sun Azimuth
        if attribute.find("Name").text == "MEAN_SUN_ZENITH_ANGLE":
            sz_values = attribute.find("Values")
            sz_value = sz_values.find("Value").text  # Sun Zenith

    # Open CSV File for writing
    csv_file = os.path.join(os.path.dirname(xml_file), ur + ".csv")
    with open(csv_file, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)

        # Write the header row
        writer.writerow(
            [
                "File Name",
                "Sensor",
                "Tile",
                "Production Date",
                "Sensing Begin",
                "Sensing End",
                "Cloud Cover",
                "Resampling Algorithim",
                "UTM",
                "Ref Scale Factor",
                "Mean Sun Azimuth",
                "Mean Sun Zenith",
            ]
        )  # get relevant information
        writer.writerow(
            [
                ur,
                sensor,
                tile,
                production_date,
                begin_date,
                end_date,
                cc_value,
                resampling_value,
                utm,
                sf_value,
                sa_value,
                sz_value,
            ]
        )

def merge_csvs(csv_files, output_file):
    # Create an empty DataFrame to store the merged data
    df = pd.DataFrame()

    # Iterate over each CSV file in the provided list
    for file in csv_files:
        # Read the CSV file into a DataFrame
        csv = pd.read_csv(file)

        # Concatenate the current CSV data with the existing DataFrame
        df = pd.concat([df, csv])

    # Write the merged DataFrame to a new CSV file without including the index
    df.to_csv(output_file, index=False)

    # Return the merged DataFrame
    return df

def delete_files(file_paths):
    for file in file_paths:
        try:
            os.remove(file)  # Remove file
        except OSError as e:
            print(f"Error deleting file: {file}")

def move_xml(xml_file, out_dir):
    # Parse the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Extract information from the XML
    ur = root.find("GranuleUR").text
    ur_split = ur.split(".")
    sensor = ur_split[1]  # Extract sensor name
    tile = ur_split[2]  # Extract tile name
    date = ur_split[3]  # Extract date
    out_folder = os.path.join(
        out_dir, sensor, tile, date, os.path.basename(xml_file)
    )  # Define the destination folder
    os.rename(xml_file, out_folder)  # Move the XML file to the destination folder

def print_color(text, color):
    # ANSI escape sequences for different colors
    color_codes = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "reset": "\033[0m",
    }
    if color in color_codes:
        color_code = color_codes[color]
        reset_code = color_codes["reset"]
        print(color_code + text + reset_code)
    else:
        print(text)

def reproject_rasters(input_rasters, output_dir, target_crs):
    for raster_path in input_rasters:
        with rasterio.open(raster_path) as src:
            # Get the source CRS and transform
            src_crs = src.crs
            src_transform = src.transform

            # Calculate the transform to the target CRS
            dst_crs = target_crs
            width = src.width
            height = src.height
            dst_transform, dst_width, dst_height = calculate_default_transform(
                src_crs, dst_crs, width, height, *src.bounds
            )

            # Update the destination transform to match the desired resolution
            dst_transform, dst_width, dst_height = calculate_default_transform(
                src_crs,
                dst_crs,
                width,
                height,
                *src.bounds,
                dst_width=src.width,
                dst_height=src.height,
            )

            # Create the output path using the input raster name
            output_path = f"{output_dir}/{os.path.basename(raster_path)}"

            # Reproject the raster
            with rasterio.open(
                output_path,
                "w",
                driver="GTiff",
                crs=dst_crs,
                transform=dst_transform,
                width=dst_width,
                height=dst_height,
                count=src.count,
                dtype=src.dtypes[0],
            ) as dst:
                for band_idx in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, band_idx),
                        destination=rasterio.band(dst, band_idx),
                        src_transform=src_transform,
                        src_crs=src_crs,
                        dst_transform=dst_transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.bilinear,
                    )

def mosaic_rasters(raster_list, output_path, resampling=Resampling.bilinear):
    out_folder = os.path.dirname(output_path)
    os.makedirs(out_folder, exist_ok=True)
    temp_folder = os.path.join(out_folder, "temp")
    os.makedirs(temp_folder, exist_ok=True)
    # Reproject Files
    with rasterio.open(raster_list[0]) as src:
        crs = src.crs
        transform = src.transform
    reproject_rasters(raster_list, temp_folder, crs)

    temp_raster_list = [
        os.path.join(temp_folder, file)
        for file in os.listdir(temp_folder)
        if file.endswith(".tif")
    ]

    # Open all input rasters
    src_files = []
    for raster_file in temp_raster_list:
        src = rasterio.open(raster_file)
        src_files.append(src)

    # Merge the rasters with defined interpolation
    mosaic, out_trans = merge(src_files, resampling=resampling)

    # Create the output raster file
    out_meta = src_files[0].meta.copy()
    out_meta.update(
        {"height": mosaic.shape[1], "width": mosaic.shape[2], "transform": out_trans}
    )

    with MemoryFile() as memfile:
        with memfile.open(**out_meta) as dataset:
            dataset.write(mosaic)

            # Save the mosaic to the output path
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(dataset.read())

    # Close all the source rasters
    for src in src_files:
        src.close()

    delete_files(temp_raster_list)
    print(f"{output_path} generated successfully.")

def merge_rasters(input_files, output_file, method="min"):
    out_folder = os.path.dirname(output_file)
    os.makedirs(out_folder, exist_ok=True)
    # Open the input files
    src_files = [rasterio.open(file) for file in input_files]

    # Merge the rasters
    if method == "min":
        merged, out_trans = merge(src_files, method="min")
    elif method == "max":
        merged, out_trans = merge(src_files, method="max")

    # Create the output raster file
    out_meta = src_files[0].meta.copy()
    out_meta.update(
        {"height": merged.shape[1], "width": merged.shape[2], "transform": out_trans}
    )

    with MemoryFile() as memfile:
        with memfile.open(**out_meta) as dataset:
            dataset.write(merged)

            # Save the mosaic to the output path
            with rasterio.open(output_file, "w", **out_meta) as dest:
                dest.write(dataset.read())

                
# Organize Data and Create Metadata CSV
directory = r"D:\MurrayBrent\projects\paper2\data\raw\RMF_HLS"
seasons = ["fall", "spring", "summer", "winter"]
for season in seasons:
    folder = os.path.join(directory, season)

    # Create folder structure and move files
    input_files = [
        os.path.join(folder, file)
        for file in os.listdir(folder)
        if file.endswith((".tif", ".jpg"))
    ]  # Find .tif and .jpg files

    for file in input_files:
        create_hls_folders(folder, file)  # Create folder structure and move files

    # Create Meta Data CSV from XML Files
    input_files = [
        os.path.join(folder, file)
        for file in os.listdir(folder)
        if file.endswith(".xml")
    ]  # Find .xml Files

    for file in input_files:
        hls_xml_csv(file)  # Create CSV from XML
        move_xls(file, folder)  # Move XML

    if os.path.exists(os.path.join(folder, "hls_images.csv")):
        os.remove(os.path.join(folder, "hls_images.csv"))  # Delete csv if exists

    input_files = [
        os.path.join(folder, file)
        for file in os.listdir(folder)
        if file.endswith(".csv")
    ]  # Find all .csv files

    df = merge_csvs(
        input_files, os.path.join(folder, "hls_images.csv")
    )  # Merge all .csv files
    delete_files(input_files)  # Delete old files


# Create Individual Image Composites
directory = r"D:\MurrayBrent\projects\paper2\data\raw\RMF_HLS"
sensors = ["L30", "S30"]
seasons = ["fall", "spring", "summer", "winter"]
for season in seasons:
    for sensor in sensors:
        folder = os.path.join(directory, season, sensor)
        if os.path.exists(os.path.join(folder, "composites")):
            os.remove(os.path.join(folder, "composites"))  # Remove Folder if it exists
        print(f"Processing Images in: {folder}")
        subfolders = find_subfolders(folder)  # Find all of the folders where images are
        if sensor == "L30":
            bands = [
                "B02",
                "B03",
                "B04",
                "B05",
                "B06",
                "B07",
            ]  # Landsat Bands of Interest
        else:
            bands = [
                "B02",
                "B03",
                "B04",
                "B05",
                "B06",
                "B07",
                "B08",
                "B8A",
                "B11",
                "B12",
            ]  # Sentinel2 Bands of Interest
        out_dir = os.path.join(folder, "composites")
        os.makedirs(out_dir, exist_ok=True)  # Create Folder
        for subfolder in subfolders:
            try:
                input_files = [
                    os.path.join(subfolder, file)
                    for file in os.listdir(subfolder)
                    if file.endswith(".tif")
                    and any(
                        value in os.path.basename(file).split(".") for value in bands
                    )
                ]  # find .tif files of bands of interest
                band_names = [
                    os.path.basename(file).split(".")[-3] for file in input_files
                ]  # get band names
                tile = os.path.basename(input_files[1]).split(".")[2]  # Get Tile
                date = os.path.basename(input_files[1]).split(".")[3]  # Get Date
                output_file = os.path.join(
                    out_dir, (tile + "_" + date + ".tif")
                )  # Define Ouput File
                composite_bands(
                    input_files, output_file, band_names
                )  # Create Composites
            except Exception as e:
                print_color(f"Error Processing {subfolder}", "red")



# Create Tile Composites and Mosaic Images
directory = r"D:\MurrayBrent\projects\paper2\data\raw\RMF_HLS"
seasons = ["fall", "spring", "summer", "winter"]
sensors = ["L30", "S30"]
for season in seasons:
    df = pd.read_csv(
        os.path.join(directory, season, "hls_images.csv")
    )  # Read seasons images csv
    # df["Cloud Cover"] = df["Cloud Cover"].astype(int)
    for sensor in sensors:
        try:
            print(f"{season} {sensor}")
            current_folder = os.path.join(
                directory, season, sensor
            )  # get current folder path
            comp_folder = os.path.join(
                current_folder, "composites"
            )  # get composites folder
            df_sub = df[df["Sensor"] == sensor]  # subset df to sensor
            tiles = list(df_sub["Tile"].unique())  # Find unique tiles
            for tile in tiles:
                print(f"Generating Tile Composite for {tile}")
                df_tile = df_sub[df_sub["Tile"] == tile]  # subset df to tile
                files = list(df_tile["File Name"].unique())  # list files
                files = [
                    os.path.join(
                        comp_folder,
                        (file.split(".")[2] + "_" + file.split(".")[3] + ".tif"),
                    )
                    for file in files
                ]  # create file paths

                merge_rasters(
                    files, os.path.join(comp_folder, "tile_composites", tile + ".tif")
                )
                print(" ")

            files = [
                os.path.join(comp_folder, "tile_composites", file)
                for file in os.listdir(os.path.join(comp_folder, "tile_composites"))
                if file.endswith(".tif")
            ]  # list files

            print(f"Creating {season} {sensor} mosaic")
            mosaic_rasters(
                files, os.path.join(current_folder, "mosaic", "mosaic.tif")
            )  # generate mosaic
        except Exception as e:
            print_color(f"{str(e)}", "red")