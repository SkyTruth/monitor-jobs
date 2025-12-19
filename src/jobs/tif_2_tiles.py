import io
import os
import subprocess
import sys
from tempfile import mkdtemp

from src.utils import db
import rasterio
import rasterio.warp

from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage

from rasterio.crs import CRS

from src.utils.config import GCP_PROJECT_ID


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

        with io.FileIO(download_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Download {int(status.progress() * 100)}%")

        fh.close()

    def main(self, args):
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

            print("ITEMS", items[0], flush=True)

            if not items:
                print("No files found.")
            else:
                folders = []
                for item in items:
                    print(item["parents"], flush=True)
                    if item["parents"] == [self.drive_id]:
                        folders.insert(0, [item["id"], item["name"]])
                print("folders:", folders, flush=True)

                count = 0
                print("Files:")
                for item in items:
                    for folder in folders:
                        if folder[0] == item["parents"][0]:
                            file_name = item["name"]
                            print(file_name)
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
        dat = rasterio.open(full_path_to_downloaded_file)
        # check the crs of the data
        src_crs = str(dat.crs)[5:]
        print("src_crs:", src_crs, flush=True)

        # check the bounding-box of the data
        print(dat.bounds, flush=True)
        src_bounds = str(dat.bounds)
        # BoundingBox(left=240848.5, bottom=1672362.0, right=243066.0, top=1673347.0)
        left = float(src_bounds[src_bounds.index("left=") + 5 : src_bounds.index(", bottom=")])
        bottom = float(src_bounds[src_bounds.index("bottom=") + 7 : src_bounds.index(", right=")])
        right = float(src_bounds[src_bounds.index("right=") + 6 : src_bounds.index(", top=")])
        top = float(src_bounds[src_bounds.index("top=") + 4 : src_bounds.index(")")])
        longitude = (left + right) / 2
        latitude = (bottom + top) / 2

        # print(83, dat.crs, left, bottom, right, top, latitude, longitude, flush=True)
        if dat.crs == "EPSG:4326":
            return [latitude, longitude]
        else:
            print("attempting to get centroid after converting from", dat.crs, flush=True)
            # In GeoJSON format
            # xmin, ymin, xmax, ymax = -180.0225, -90.0225, 179.9775, 90.0225
            feature = {"type": "Point", "coordinates": [longitude, latitude]}

            # Project the feature to the desired CRS
            feature_proj = rasterio.warp.transform_geom(
                CRS.from_epsg(int(src_crs)), CRS.from_epsg(4326), feature
            )
            longitude = feature_proj["coordinates"][0]
            latitude = feature_proj["coordinates"][1]
            # print(99, feature_proj, longitude, latitude, flush=True)
            return [latitude, longitude]

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
                "gdal2tiles.py --zoom 10 --xyz  " + tif_file_name + " " + output_tileset_folder_path
            )
            os.system(cmd)
        except Exception as e:
            print("convert_to_tiles error:", e, flush=True)
            self.error(storage_file_path, "convert_to_tiles", str(e))

    def upload_tiles_to_storage(self, tile_folder_name, storage_file_path, folder_name):
        try:
            storage_client = storage.Client(project=GCP_PROJECT_ID)
            bucket = storage_client.bucket(self.tiles_storage_bucket)

            gcs_parent = os.path.join(self.bucket_tile_parent, folder_name)
            gcs_path = os.path.join(gcs_parent, tile_folder_name)
            tile_path = os.path.join(self.tile_file_dir, tile_folder_name)

            for root, _, files in os.walk(tile_path):
                for filename in files:
                    if not filename.lower().endswith(".png"):
                        continue

                    local_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(local_path, tile_path).replace(os.sep, "/")

                    object_name = f"{gcs_path}/{relative_path}"

                    blob = bucket.blob(object_name)

                    print(
                        f"Uploading {local_path} → gs://{self.tiles_storage_bucket}/{object_name}"
                    )
                    blob.upload_from_filename(local_path, content_type="image/png")

            # bucket.blob(gcs_path).upload_from_filename(tile_path, timeout=60000)
            print("Uplaoded")

        except subprocess.TimeoutExpired:
            self.error(
                storage_file_path,
                "upload_tiles_to_storage",
                "TimeoutExpired",
            )

        except Exception as e:
            print("Upoload failed!", e)
            self.error(storage_file_path, "upload_tiles_to_storage", str(e))


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = Tif2Tiles()
    it.main(sys.argv[1:])
