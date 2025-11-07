import io
import os
import subprocess
import sys

# import gdal2tiles
import db
import rasterio
import rasterio.warp
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from oauth2client.service_account import ServiceAccountCredentials
from rasterio.crs import CRS

import utils


class Tif2Tiles:
    # email = None
    scope = ["https://www.googleapis.com/auth/drive.readonly"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        "skytruth-alerts2-e3be1fb35d2b.json", scope
    )
    # https://developers.google.com/drive/api/v3/quickstart/python
    service = build("drive", "v3", credentials=credentials)

    def download_file(self, real_file_id, file_name):
        # create drive api client
        file_id = real_file_id
        request = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO("tif_files/" + file_name, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        # file = io.FileIO()
        # file.name = 'tif_files/' + file_name
        print("downloading", file_name)

        #     fh = io.FileIO('cow.png', mode='wb')
        #   downloader = MediaIoBaseDownload(fh, request, chunksize=1024*1024)
        # downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%")

    def main(self, args):
        try:
            # Call the Drive v3 API
            results = (
                self.service.files()
                .list(
                    fields="*",
                    corpora="drive",
                    supportsAllDrives=True,
                    driveId="",
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            items = results.get("files", [])

            if not items:
                print("No files found.")
            else:
                folders = []
                for item in items:
                    if item["parents"] == [""]:
                        folders.insert(0, [item["id"], item["name"]])
                # print('folders:', folders)

                count = 0
                print("Files:")
                for item in items:
                    for folder in folders:
                        if folder[0] == item["parents"][0]:
                            file_name = item["name"]
                            # print(file_name)
                            if (
                                not file_name.upper().endswith(".TIF")
                                and not file_name.upper().endswith(".TIFF") == None
                            ):
                                continue
                            file_id = item["id"]
                            folder_name = folder[1]
                            # print(u'{0} {1} {2}'.format(folder_name, file_name, file_id))
                            storage_file_path = folder_name + "/" + file_name
                            file_upload = db.get_file_upload(storage_file_path)
                            if file_upload != None:
                                print("file exists:", storage_file_path)
                            else:
                                # if 'x' == 'x':
                                count += 1
                                print("downloading", storage_file_path)
                                status = "new"
                                message = "new"
                                email = "tech@skytruth.org"
                                # if folder_name == "PALMERLAND":
                                #     email = 'theron@palmerland.org'
                                user_id = 1
                                storage_bucket = folder_name
                                # if file_upload == None:
                                db.insert_file_upload(
                                    storage_file_path,
                                    status,
                                    message,
                                    email,
                                    user_id,
                                    file_name,
                                    storage_bucket,
                                    latitude=None,
                                    longitude=None,
                                )
                                self.download_file(file_id, file_name)
                                db.upd_file_upload(storage_file_path, "downloaded", "downloaded")

                                write_tiles_path = "tif_2_tiles/" + storage_bucket
                                tif_folder_path = (
                                    "tif_files"  # Specify path to folder of tif images.
                                )
                                warp_folder_path = "tif_warp_files"
                                # print(file_name.index("."))
                                tile_folder_name = file_name[: file_name.index(".")]
                                output_tileset_folder_path = (
                                    tif_folder_path + "/" + tile_folder_name + "/"
                                )  # Specify the desired output folder path
                                # print("output_tileset_folder_path:", output_tileset_folder_path, flush=True)
                                os.makedirs(output_tileset_folder_path, exist_ok=True)
                                self.scale_to_8bits(
                                    file_name,
                                    tif_folder_path,
                                    warp_folder_path,
                                    storage_bucket,
                                )
                                # Convert to tiles
                                self.convert_to_tiles(
                                    file_name,
                                    output_tileset_folder_path,
                                    warp_folder_path,
                                    storage_bucket,
                                )
                                # Upload tiles to storage
                                self.upload_tiles_to_storage(
                                    output_tileset_folder_path,
                                    tile_folder_name,
                                    write_tiles_path,
                                    storage_bucket,
                                    file_name,
                                )
                                # print('Success')
                                status = "convertedToTiles"
                                message = "success"
                                # Try to get lat/lngs
                                latitude = None
                                longitude = None
                                try:
                                    full_path_to_downloaded_file = (
                                        warp_folder_path + "/" + file_name
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

                                # Email user
                                utils.send_email(
                                    file_name + " converted to tiles",
                                    file_name
                                    + " has been converted to tiles. You can view this by selecting "
                                    + file_name
                                    + " from the 'Uploaded TIFFs' layer in Alerts.",
                                    email,
                                )

                    if count > 0:
                        return

        except Exception as e:
            print(73, str(e), flush=True)
            # self.error(storage_bucket + "/" + file_name, "main", str(e))

    def error(self, storage_file_path, status, message):
        print("108 error:", storage_file_path, status, message, flush=True)
        db.upd_file_upload(storage_file_path, status, message)
        storage_bucket, file_name = storage_file_path.split("/")
        msg = """Could not convert tif file %s to tiles. Uploaded tif files must be geo-coded (GeoTIFF).\n
If you believe this file is a valid GeoTIFF file, contact SkyTruth at info@skytruth.org.\n
The error received is: %s
and happened in the %s function.\n
TIF files should include georeferencing metadata, have a Web Mercator projection, and be in 8-bit format.
            """ % (file_name, message, status)
        utils.send_email("ERROR in uploaded tif file " + file_name, msg, self.email)
        utils.send_email("ERROR in uploaded tif file " + file_name, msg, "tech@skytruth.org")
        sys.exit(0)

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

    def scale_to_8bits(self, file_name, tif_folder_path, warp_folder_path, storage_bucket):
        try:
            print("scale_to_8bits:", file_name, tif_folder_path, flush=True)
            # gdal_translate -of VRT -ot Byte -scale tif_files/mlatlon.tif temp.vrt
            input_tif_file = os.path.join(tif_folder_path, file_name)
            output_tif_file = os.path.join(warp_folder_path, file_name)
            # print('input_tif_file:', input_tif_file, 'output_tif_file:', output_tif_file, flush=True)
            # gdal_translate -of VRT -ot Byte -scale tif_files/SkyFi_2422CO03-1_2024-06-04_1639Z_DAY_HIGH_Colorado-USA.tif temp.vrt
            gdalwarp_cmd = (
                "gdal_translate -of VRT -ot Byte -scale " + input_tif_file + " " + output_tif_file
            )
            os.system(gdalwarp_cmd)
        except Exception as e:
            self.error(storage_bucket + "/" + file_name, "scale_to_8bits", str(e))

    def convert_to_tiles(
        self, file_name, output_tileset_folder_path, tif_folder_path, storage_bucket
    ):
        try:
            tif_file_name = os.path.join(tif_folder_path, file_name)
            # print("convert_to_tiles:", tif_file_name, output_tileset_folder_path)
            print(
                "convert_to_tiles command: gdal2tiles.py --zoom 10-18 --xyz ",
                tif_file_name,
                output_tileset_folder_path,
                flush=True,
            )
            cmd = (
                "gdal2tiles.py --zoom 10-18 --xyz  "
                + tif_file_name
                + " "
                + output_tileset_folder_path
            )
            os.system(cmd)
        except Exception as e:
            print("convert_to_tiles error:", e, flush=True)
            self.error(storage_bucket + "/" + file_name, "convert_to_tiles", str(e))

    def upload_tiles_to_storage(
        self,
        output_tileset_folder_path,
        tile_folder_name,
        write_tiles_path,
        storage_bucket,
        file_name,
    ):
        try:
            gcs_path = "gs://alerts-storage/" + write_tiles_path + "/" + tile_folder_name
            # print("upload_tiles_to_storage", tile_folder_name, gcs_path, flush=True)
            print(
                "gsutil",
                "-m",
                "rsync",
                "-r",
                output_tileset_folder_path,
                gcs_path,
                flush=True,
            )
            proc = subprocess.Popen(
                ["gsutil", "-m", "rsync", "-r", output_tileset_folder_path, gcs_path]
            )
            outs, errs = proc.communicate(timeout=60000)
            # now you can do something with the text in outs and errs
        except subprocess.TimeoutExpired:
            self.error(
                storage_bucket + "/" + file_name,
                "upload_tiles_to_storage",
                "TimeoutExpired",
            )
            proc.kill()
            # outs, errs = proc.communicate()
        except Exception as e:
            self.error(storage_bucket + "/" + file_name, "upload_tiles_to_storage", str(e))


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = Tif2Tiles()
    it.main(sys.argv[1:])
