import io
import logging
import os
import subprocess
from tempfile import mkdtemp

import rasterio
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from rasterio.warp import transform

from src.utils import db

logger = logging.getLogger(__name__)


class Tif2Tiles:
    def __init__(self):
        creds, _ = default()
        self.service = build("drive", "v3", credentials=creds)
        self.drive_id = "0AFogaYeoFEjDUk9PVA"

        self.tiff_file_dir = mkdtemp()
        self.tile_file_dir = mkdtemp()
        self.warp_file_dir = mkdtemp()
        self.tiles_storage_bucket = "alerts-storage"
        self.bucket_tile_parent = "tif_2_tiles"

    def download_file(self, file_id, file_name):
        # create drive api client
        download_path = os.path.join(self.tiff_file_dir, file_name)
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)

        with io.FileIO(download_path, "wb") as handler:
            downloader = MediaIoBaseDownload(handler, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Download {int(status.progress() * 100)}%")

        handler.close()

    def main(self):
        try:
            results = (
                self.service.files()
                .list(
                    fields="*",
                    corpora="drive",
                    supportsAllDrives=True,
                    driveId=self.drive_id,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )

            items = results.get("files", [])

            if not items:
                return "No files in drive"
            folders = {}
            for item in items:
                item_parents = item["parents"]
                if item_parents == [self.drive_id] and not folders.get(item["id"]):
                    folders[item["id"]] = item["name"]

            count = 0
            for item in items:
                item_parent = item["parents"][0]
                if folders.get(item_parent):
                    file_name = item["name"]

                    if not file_name.upper().endswith(".TIF") and not file_name.upper().endswith(
                        ".TIFF"
                    ):
                        continue

                    file_id = item["id"]
                    folder_name = folders.get(item_parent)
                    storage_file_path = folder_name + "/" + file_name
                    prev_uploaded_file = db.get_file_upload(storage_file_path)

                    if prev_uploaded_file is None:
                        count += 1
                        status = "new"
                        message = "new"
                        email = "monitor-jobs"
                        user_id = 1  # The DB needs this so stub in a value

                        db.insert_file_upload(
                            storage_file_path,
                            status,
                            message,
                            email,
                            user_id,
                            file_name,
                            folder_name,
                            latitude=None,
                            longitude=None,
                        )

                        self.download_file(file_id, file_name)

                        db.upd_file_upload(storage_file_path, "downloaded", "downloaded")

                        bucket = self.tiles_storage_bucket + folder_name

                        tile_folder_name = file_name[: file_name.index(".")]

                        self.scale_to_8bits(
                            file_name,
                            storage_file_path,
                        )

                        # Convert to tiles
                        self.convert_to_tiles(
                            file_name,
                            tile_folder_name,
                            storage_file_path,
                        )
                        # Upload tiles to storage
                        self.upload_tiles_to_storage(
                            tile_folder_name,
                            bucket,
                            folder_name,
                        )

                        status = "convertedToTiles"
                        message = "success"

                        # Try to get lat/lngs
                        latitude = None
                        longitude = None
                        try:
                            full_path_to_downloaded_file = self.tiff_file_dir + "/" + file_name
                            [latitude, longitude] = self.get_centroid(full_path_to_downloaded_file)

                        except Exception:
                            logger.warning(f"Failed to get centroid for {folder_name}/{file_name}")
                            latitude = "NULL"
                            longitude = "NULL"

                        # Update the database to show success
                        db.upd_file_upload(
                            storage_file_path,
                            status,
                            message,
                            latitude,
                            longitude,
                        )

                if count > 0:
                    return

        except Exception as e:
            logger.error("tiff_2_tiles failed", str(e))
            self.error(storage_file_path, "error", str(e))

    def error(self, storage_file_path, status, message):
        db.upd_file_upload(storage_file_path, status, message)

    def get_centroid(self, full_path_to_downloaded_file):
        with rasterio.open(full_path_to_downloaded_file) as image:
            bounds = image.bounds
            crs = image.crs

            if crs is None:
                file_name_idx = full_path_to_downloaded_file.rfind("/")
                file = full_path_to_downloaded_file[file_name_idx + 1 :]

                logger.exception(f"{file} has no defined CRS")
                raise ValueError("Raster has no CRS defined")

            centroid_x = (bounds.left + bounds.right) / 2
            centroid_y = (bounds.top + bounds.bottom) / 2

            # Reproject centroid to EPSG:4326
            lon, lat = transform(
                crs,
                "EPSG:4326",
                [centroid_x],
                [centroid_y],
            )

            return lat[0], lon[0]

    def scale_to_8bits(self, file_name, storage_file_path):
        """
        Generate a "virtual raster" (VRT) with data converted to 8-bit and values
        scaled between 0-255. This is an intermediate step that speeds up the tile
        generation process
        """
        try:
            input_tif_file = os.path.join(self.tiff_file_dir, file_name)
            output_tif_file = os.path.join(self.warp_file_dir, file_name)

            gdalwarp_cmd = (
                "gdal_translate -of VRT -ot Byte -scale " + input_tif_file + " " + output_tif_file
            )
            os.system(gdalwarp_cmd)
        except Exception as e:
            logger.exception(f"Failed generate 8-bit VRT fro geotiff {str(e)}")
            self.error(storage_file_path, "scale_to_8bits", str(e))
            raise

    def convert_to_tiles(self, file_name, tile_folder_name, storage_file_path):
        try:
            tif_file_name = os.path.join(self.warp_file_dir, file_name)
            output_tileset_folder_path = os.path.join(self.tile_file_dir, tile_folder_name)

            cmd = (
                "gdal2tiles.py --zoom 10-11 --xyz  "
                + tif_file_name
                + " "
                + output_tileset_folder_path
            )
            os.system(cmd)
        except Exception as e:
            logger.exception(f"Failed to convert geotiff to raster tiles {(str(e))}")
            self.error(storage_file_path, "convert_to_tiles", str(e))
            raise

    def upload_tiles_to_storage(self, tile_folder_name, storage_file_path, folder_name):
        try:
            gcs_parent = os.path.join(self.bucket_tile_parent, folder_name)
            gcs_path = os.path.join(gcs_parent, tile_folder_name)
            tile_path = os.path.join(self.tile_file_dir, tile_folder_name)

            cmd = [
                "gcloud",
                "storage",
                "rsync",
                "--recursive",
                "--checksums-only",
                tile_path,
                f"gs://{self.tiles_storage_bucket}/{gcs_path}",
            ]

            subprocess.run(cmd, check=True)

        except Exception as e:
            logger.exception(f"Failed to upload map tiles to GCS {str(e)}")
            self.error(storage_file_path, "upload_tiles_to_storage", str(e))
            raise


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = Tif2Tiles()
    it.main()
