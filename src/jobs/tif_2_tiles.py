import io
import os
import subprocess
from tempfile import mkdtemp

from src.utils import db
import rasterio
from rasterio.warp import transform

from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import logging

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

            if items:
                folders = []
                for item in items:
                    if item["parents"] == [self.drive_id]:
                        folders.insert(0, [item["id"], item["name"]])

                count = 0
                for item in items:
                    for folder in folders:
                        if folder[0] == item["parents"][0]:
                            file_name = item["name"]
                            if (
                                not file_name.upper().endswith(".TIF")
                                and not file_name.upper().endswith(".TIFF") == None
                            ):
                                continue
                            file_id = item["id"]
                            folder_name = folder[1]
                            storage_file_path = folder_name + "/" + file_name
                            prev_uploaded_file = db.get_file_upload(storage_file_path)
                            if prev_uploaded_file is None:
                                print("file name for processing", file_name)
                                count += 1
                                print("downloading", storage_file_path)
                                status = "new"
                                message = "new"
                                email = "monitor-jobs"
                                user_id = 1

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

                                print("Updated as new in DB", storage_file_path, status)
                                self.download_file(file_id, file_name)
                                print("downloading", file_name)
                                print(
                                    "Downlaod Directory",
                                    self.tiff_file_dir,
                                    os.system(f"ls {self.tiff_file_dir}"),
                                    flush=True,
                                )
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
                                # print('Success')
                                status = "convertedToTiles"
                                message = "success"
                                # Try to get lat/lngs
                                latitude = None
                                longitude = None
                                try:
                                    full_path_to_downloaded_file = (
                                        self.warp_file_dir + "/" + file_name
                                    )
                                    coords = self.get_centroid(full_path_to_downloaded_file)
                                    latitude = coords[0]
                                    longitude = coords[1]
                                    print(latitude, longitude, flush=True)
                                except Exception:
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
            print("ERROR", e)
            self.error(storage_file_path, "error", str(e))

    def error(self, storage_file_path, status, message):
        db.upd_file_upload(storage_file_path, status, message)

    def get_centroid(self, full_path_to_downloaded_file):
        with rasterio.open(full_path_to_downloaded_file) as image:
            # Get bounds in source CRS
            bounds = image.bounds
            crs = image.crs

            if crs is None:
                raise ValueError("Raster has no CRS defined")

            # Compute centroid in source CRS
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
        try:
            print("scale_to_8bits:", file_name, flush=True)

            input_tif_file = os.path.join(self.tiff_file_dir, file_name)
            output_tif_file = os.path.join(self.warp_file_dir, file_name)

            gdalwarp_cmd = (
                "gdal_translate -of VRT -ot Byte -scale " + input_tif_file + " " + output_tif_file
            )
            os.system(gdalwarp_cmd)
            print("WARP FILE", output_tif_file, flush=True)
            print(os.system(f"ls {self.warp_file_dir}"))
        except Exception as e:
            self.error(storage_file_path, "scale_to_8bits", str(e))

    def convert_to_tiles(self, file_name, tile_folder_name, storage_file_path):
        try:
            tif_file_name = os.path.join(self.warp_file_dir, file_name)
            output_tileset_folder_path = os.path.join(self.tile_file_dir, tile_folder_name)
            print("writing tiles to", output_tileset_folder_path, flush=True)

            cmd = (
                "gdal2tiles.py --zoom 10-11 --xyz  "
                + tif_file_name
                + " "
                + output_tileset_folder_path
            )
            os.system(cmd)
        except Exception as e:
            print("convert_to_tiles error:", e, flush=True)
            self.error(storage_file_path, "convert_to_tiles", str(e))

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
            print("Upoload failed!", e)
            self.error(storage_file_path, "upload_tiles_to_storage", str(e))


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = Tif2Tiles()
    it.main()
