import io
import logging
import os
import shutil
import subprocess
from tempfile import mkdtemp

import httplib2
import rasterio
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from rasterio.warp import transform

from src.utils import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProgressLogger:
    """
    Log a text progress bar at fixed percentage steps. Cloud Logging turns
    every line into a separate entry (carriage-return bars like tqdm's don't
    render), so emit one line per `step` percent instead of one per item
    """

    def __init__(self, label, total, step=10, width=20):
        self.label = label
        self.total = total
        self.step = step
        self.width = width
        self.next_pct = 0

    def update(self, current):
        if self.total <= 0:
            return
        pct = min(100, int(current * 100 / self.total))
        if pct < self.next_pct:
            return
        filled = int(self.width * pct / 100)
        bar = "█" * filled + "·" * (self.width - filled)
        logger.info(f"{self.label} |{bar}| {pct}% ({current}/{self.total})")
        self.next_pct = (pct // self.step + 1) * self.step


class Tif2Tiles:
    def __init__(self):
        self.service = self.build_drive_service()
        self.drive_id = "0AFogaYeoFEjDUk9PVA"

        self.tiff_file_dir = mkdtemp()
        self.tile_file_dir = mkdtemp()
        self.warp_file_dir = mkdtemp()
        self.tiles_storage_bucket = "alerts-storage"
        self.bucket_tile_parent = "tif_2_tiles"

        self.min_zoom = int(os.environ.get("TILE_MIN_ZOOM", "10"))
        self.max_zoom = int(os.environ.get("TILE_MAX_ZOOM", "16"))

    def build_drive_service(self):
        creds, _ = default()
        return build("drive", "v3", credentials=creds)

    def download_file(self, file_id, file_name, max_attempts=3):
        """
        Download a file from Drive. next_chunk(num_retries=5) retries
        transient network errors with backoff and resumes mid-file; if a
        whole attempt fails the Drive connection is rebuilt, since hours of
        tiling between downloads leaves the original keep-alive socket dead
        """
        logger.info(f"Downloading {file_name}")

        download_path = os.path.join(self.tiff_file_dir, file_name)

        for attempt in range(1, max_attempts + 1):
            try:
                request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
                progress = ProgressLogger(f"Downloading {file_name}", 100)
                with io.FileIO(download_path, "wb") as handler:
                    downloader = MediaIoBaseDownload(handler, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk(num_retries=5)
                        progress.update(int(status.progress() * 100))
                return
            except (OSError, httplib2.HttpLib2Error, HttpError) as e:
                # Don't retry client errors like 403/404
                if isinstance(e, HttpError) and e.resp.status < 500:
                    raise
                if attempt == max_attempts:
                    raise
                logger.warning(
                    f"Download attempt {attempt} of {max_attempts} for {file_name} "
                    f"failed ({e}); rebuilding Drive connection and retrying"
                )
                self.service = self.build_drive_service()

    def list_drive_files(self):
        """List every file in the shared drive, following pagination."""
        items = []
        page_token = None
        while True:
            results = (
                self.service.files()
                .list(
                    fields="nextPageToken, files(id, name, parents)",
                    corpora="drive",
                    supportsAllDrives=True,
                    driveId=self.drive_id,
                    includeItemsFromAllDrives=True,
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )
            items.extend(results.get("files", []))
            page_token = results.get("nextPageToken")
            if not page_token:
                return items

    def main(self):
        items = self.list_drive_files()

        if not items:
            return "No files in drive"

        folders = {}
        for item in items:
            item_parents = item.get("parents", [])
            if item_parents == [self.drive_id] and not folders.get(item["id"]):
                folders[item["id"]] = item["name"]

        processed = 0
        failed = 0
        for item in items:
            item_parent = item.get("parents", [None])[0]
            folder_name = folders.get(item_parent)
            if not folder_name:
                continue

            file_name = item["name"]
            if not file_name.upper().endswith(".TIF") and not file_name.upper().endswith(".TIFF"):
                continue

            storage_file_path = folder_name + "/" + file_name

            if db.get_file_upload(storage_file_path) is not None:
                continue

            try:
                self.process_file(item["id"], file_name, folder_name, storage_file_path)
                processed += 1
            except Exception as e:
                failed += 1
                logger.exception(f"Failed to process {storage_file_path}")
                self.error(storage_file_path, "error", str(e))

        logger.info(f"tiff_2_tiles finished: {processed} processed, {failed} failed")

    def process_file(self, file_id, file_name, folder_name, storage_file_path):
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

        tile_folder_name = file_name[: file_name.index(".")]

        try:
            self.download_file(file_id, file_name)

            db.upd_file_upload(storage_file_path, "downloaded", "downloaded")

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
                storage_file_path,
                folder_name,
            )

            status = "convertedToTiles"
            message = "success"

            # Try to get lat/lngs
            latitude = None
            longitude = None
            try:
                full_path_to_downloaded_file = os.path.join(self.tiff_file_dir, file_name)
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
        finally:
            # Free local disk/memory before the next file
            self.cleanup_local_files(file_name, tile_folder_name)

    def cleanup_local_files(self, file_name, tile_folder_name):
        """
        Remove the downloaded tiff, the 8-bit VRT and the generated tileset so
        scratch space doesn't accumulate while processing files back to back
        """
        for path in (
            os.path.join(self.tiff_file_dir, file_name),
            os.path.join(self.warp_file_dir, file_name),
            os.path.join(self.tile_file_dir, tile_folder_name),
        ):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    os.remove(path)
            except OSError:
                logger.warning(f"Failed to remove {path}")

    def error(self, storage_file_path, status, message):
        db.upd_file_upload(storage_file_path, status, message)

    def get_centroid(self, full_path_to_downloaded_file):
        file_name_idx = full_path_to_downloaded_file.rfind("/")
        file = full_path_to_downloaded_file[file_name_idx + 1 :]

        logger.info(f"Attempting to find the centroid for {file}")

        with rasterio.open(full_path_to_downloaded_file) as image:
            bounds = image.bounds
            crs = image.crs

            if crs is None:
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
            logger.info(f"Creating VRT for {file_name}")
            input_tif_file = os.path.join(self.tiff_file_dir, file_name)
            output_tif_file = os.path.join(self.warp_file_dir, file_name)

            cmd = [
                "gdal_translate",
                "-of",
                "VRT",
                "-ot",
                "Byte",
                "-scale",
                input_tif_file,
                output_tif_file,
            ]
            subprocess.run(cmd, check=True)
        except Exception as e:
            logger.exception(f"Failed generate 8-bit VRT for geotiff {str(e)}")
            self.error(storage_file_path, "scale_to_8bits", str(e))
            raise

    def convert_to_tiles(self, file_name, tile_folder_name, storage_file_path):
        try:
            logger.info(f"Creating tiles for tiff {file_name}")
            tif_file_name = os.path.join(self.warp_file_dir, file_name)
            output_tileset_folder_path = os.path.join(self.tile_file_dir, tile_folder_name)

            cmd = [
                "gdal2tiles.py",
                f"--zoom={self.min_zoom}-{self.max_zoom}",
                "--xyz",
                f"--processes={os.cpu_count() or 1}",
                tif_file_name,
                output_tileset_folder_path,
            ]
            self.run_gdal2tiles(cmd)
        except Exception as e:
            logger.exception(f"Failed to convert geotiff to raster tiles {(str(e))}")
            self.error(storage_file_path, "convert_to_tiles", str(e))
            raise

    def run_gdal2tiles(self, cmd):
        """
        Run gdal2tiles, re-emitting its dot progress ("0...10...20") as one
        log line per step. gdal2tiles prints those dots without newlines, so
        left alone they arrive in Cloud Logging as a single garbled line
        """
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        stage = "Tiling"
        line = ""
        digits = ""
        while True:
            char = process.stdout.read(1)
            if not char:
                break
            if char.isdigit():
                digits += char
            else:
                if digits:
                    logger.info(f"{stage}: {digits}%")
                    digits = ""
            if char == "\n":
                # Stage headers look like "Generating Base Tiles:"
                if "Generating" in line:
                    stage = line.strip().rstrip(":")
                line = ""
            else:
                line += char

        returncode = process.wait()
        if returncode != 0:
            raise subprocess.CalledProcessError(returncode, cmd)

    def upload_tiles_to_storage(self, tile_folder_name, storage_file_path, folder_name):
        try:
            gcs_parent = os.path.join(self.bucket_tile_parent, folder_name)
            gcs_path = os.path.join(gcs_parent, tile_folder_name)
            tile_path = os.path.join(self.tile_file_dir, tile_folder_name)

            tile_count = sum(len(files) for _, _, files in os.walk(tile_path))
            logger.info(
                f"Uploading {tile_count} tiles to gs://{self.tiles_storage_bucket}/{gcs_path}"
            )

            cmd = [
                "gcloud",
                "storage",
                "rsync",
                "--recursive",
                "--checksums-only",
                tile_path,
                f"gs://{self.tiles_storage_bucket}/{gcs_path}",
            ]

            # rsync logs one "Copying ..." line per tile; swallow those and
            # log a progress bar instead
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            progress = ProgressLogger(f"Uploading {tile_folder_name}", tile_count)
            copied = 0
            for line in process.stdout:
                if line.startswith("Copying"):
                    copied += 1
                    progress.update(copied)

            returncode = process.wait()
            if returncode != 0:
                raise subprocess.CalledProcessError(returncode, cmd)

            logger.info(f"Upload complete: {copied} of {tile_count} tiles copied")

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
