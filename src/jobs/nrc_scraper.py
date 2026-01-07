import hashlib
import re
import requests
import urllib
import urllib.request
from datetime import datetime
import pandas as pd
import psycopg2
from psycopg2 import extras
from src.utils.utils import (
    FIELD_MAP,
    TERRITORIES,
    RELEASE_TYPE_DICT,
    UNIT_CONVERSIONS,
)
import os
import locale
from src.utils import config
import logging
from src.utils.db import NrcDatabase

logging.basicConfig(level=logging.INFO)


def correct_hemisphere(lat, lon, LOCATION_STATE):
    if LOCATION_STATE in TERRITORIES.keys() and (lat < 0 or lon > 0):
        logging.info(f"corrected hemisphere for {lat}, {lon}")
        lat = abs(lat)
        lon = -abs(lon)
    return lat, lon


def timestamp2datetime(value, formatter="%Y-%m-%d %H:%M:%S"):
    """
    Convert an Excel cell value to a formatted string for Postgres timestamp.
    Supports openpyxl datetime objects or Excel float dates.

    :param value: cell value from openpyxl (datetime or float)
    :param formatter: output format
    :return: formatted timestamp string
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        # assume Excel float date, 1900-based system
        dt = datetime(1899, 12, 30) + datetime.timedelta(days=value)
    elif isinstance(value, str):
        # try parsing common string format
        dt = datetime.strptime(value, "%m/%d/%Y %H:%M")
    else:
        raise TypeError(f"Unsupported type for timestamp conversion: {type(value)}")

    return dt.strftime(formatter)


def normalize_unit(raw_unit, value):
    for pattern, (std_unit, factor) in UNIT_CONVERSIONS.items():
        if re.search(pattern, raw_unit, re.IGNORECASE):
            return value * factor, std_unit
    return value, raw_unit  # fallback


def format_value_area(value):
    if not value:
        return ""

    # (threshold_in_sqft, divisor, unit)
    conversions = [
        (640 * 43560, 640 * 43560, "sq. miles"),
        (43560, 43560, "acres"),
        (0, 1, "sq. ft."),
    ]

    for threshold, divisor, unit in conversions:
        if value >= threshold:
            value = value / divisor
            return f"{locale.format_string('%.12g', round(value, 2), False)} {unit}"


def format_value_extent(value):
    if not value:
        return ""

    if value >= 5280:
        value /= 5280
        unit = "miles"
    else:
        unit = "feet"

    return f"{locale.format_string('%.12g', round(value, 2), False)} {unit}"


def format_value_volume(value, units="gallons"):
    if not value:
        return ""

    units = units.lower()
    formatted_value = locale.format_string("%.2f", value, False).rstrip("0").rstrip(".")

    return f"{formatted_value} {units}"


def compute_min_spill_volume(sheen_width_ft, sheen_length_ft):
    """
    Compute minimum spill volume based on sheen dimensions.
    Assumes a thickness of 1 micron for the sheen.

    :param sheen_width_ft: width of the sheen in feet
    :param sheen_length_ft: length of the sheen in feet
    :return: minimum spill volume in gallons
    """
    if sheen_width_ft is None or sheen_length_ft is None:
        return 0.0  # return 0.0 min_volume
    # or 1000L per km2
    # or 264.172052 gal per 10763910.4 ft2 = 0.000024542386752 gal per ft2
    thickness_ft = 0.000024542386752
    volume_gallons = sheen_width_ft * sheen_length_ft * thickness_ft
    return volume_gallons


def download(url, destination_folder, filename):
    """
    Download a file
    """
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder, exist_ok=True)

    # Properly join folder and filename
    destination_path = os.path.join(destination_folder, filename)

    # Download the file
    response = urllib.request.urlopen(url)
    with open(destination_path, "wb") as f:
        f.write(response.read())

    return destination_path


def dms2dd(degrees, minutes, seconds, quadrant):
    """
    Convert degrees, minutes, seconds, quadrant to decimal degrees

    :param degrees: coordinate degrees
    :type degrees: int
    :param minutes: coordinate minutes
    :type minutes: int
    :param seconds: coordinate seconds
    :type seconds: int
    :param quadrant: coordinate quadrant (N, E, S, W)
    :type quadrant: str|unicode

    :return: decimal degrees
    :rtype: float
    """

    illegal_vals = (None, "", "")
    for iv in illegal_vals:
        if iv in (degrees, minutes, seconds, quadrant):
            logging.error("ERROR: Illegal value: %s" % iv)
            raise ValueError("ERROR: Illegal value: %s" % iv)

    if quadrant.lower() not in ("n", "e", "s", "w"):
        logging.error("ERROR: Invalid quadrant: %s" % quadrant)
        raise ValueError("ERROR: Invalid quadrant: %s" % quadrant)
    # Round to 6 decimals
    output = round(int(degrees) + int(minutes) / 60 + int(seconds) / 3600, 6)

    if quadrant.lower() in ("s", "w"):
        output *= -1

    return output


def geocodeAddress(address):
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json?{}".format(
        urllib.parse.urlencode(
            {
                "address": address,
                "sensor": "false",
                "key": config.GEOCODING_API_KEY,
            }
        )
    )

    results = requests.get(geocode_url)
    # Results will be in JSON format - convert to dict using requests functionality
    results = results.json()
    return results


class NrcIncident:
    """
    Represents a single NRC incident report, with methods to extract fields and build a post.
    """

    def __init__(self, reportnum, nrc_dfs):
        # ---------------------------------------------------
        # Important data structures and constants
        # ---------------------------------------------------

        self.reportnum = reportnum
        self.nrc_dfs = nrc_dfs
        self.field_map = FIELD_MAP
        self.full_report_url = "http://nrc.uscg.mil/"
        self.lat = None
        self.lng = None

        # ---------------------------------------------------
        # Incident commons information
        # ---------------------------------------------------

        self.task_id = self.get_field_value("task_id")
        self.description = self.get_field_value("description")
        self.incident_datetime = timestamp2datetime(self.get_field_value("incident_datetime"))
        self.suspected_responsible_company = self.get_field_value("suspected_responsible_company")
        self.incidenttype = self.get_field_value("incidenttype")

        # ---------------------------------------------------
        # Geolocation information
        # ---------------------------------------------------

        self.nearestcity = self.get_field_value("nearestcity")
        self.incident_location = self.get_field_value("incidentlocation")
        self.zip_code = self.get_field_value("zip")
        self.city = self.get_field_value("nearestcity")
        self.state = self.get_field_value("state")
        self.location = self.get_field_value("location")
        self.incidentlocation = self.get_field_value("incidentlocation")

        # Pull latitude DMS/quadrant fields
        self.lat_deg = self.get_field_value("lat_degrees")
        self.lat_min = self.get_field_value("lat_minutes")
        self.lat_sec = self.get_field_value("lat_seconds")
        self.lat_quad = self.get_field_value("lat_quadrant")

        # Pull longitude DMS/quadrant fields
        self.lon_deg = self.get_field_value("lon_degrees")
        self.lon_min = self.get_field_value("lon_minutes")
        self.lon_sec = self.get_field_value("lon_seconds")
        self.lon_quad = self.get_field_value("lon_quadrant")

        # ---------------------------------------------------
        # Spill and Material Details
        # ---------------------------------------------------

        self.medium_affected = self.get_field_value("medium_affected")
        self.material_name = self.get_field_value("material_name")
        self.sheen_length = self.get_field_value("sheen_size_length")
        self.sheen_width = self.get_field_value("sheen_size_width")
        self.sheen_length_unit = self.get_field_value("sheen_size_length_unit")
        self.sheen_width_unit = self.get_field_value("sheen_size_width_unit")

        self.sheen_width_ft = (
            normalize_unit(self.sheen_width_unit, float(self.sheen_width))[0]
            if self.sheen_width
            else None
        )
        self.sheen_length_ft = (
            normalize_unit(self.sheen_length_unit, float(self.sheen_length))[0]
            if self.sheen_length
            else None
        )
        self.release_type = RELEASE_TYPE_DICT.get(self.material_name, None)
        self.min_spill_volume = compute_min_spill_volume(self.sheen_width_ft, self.sheen_length_ft)

        self.reported_spill_volume = self.get_field_value("amount")
        self.reported_spill_unit = self.get_field_value("unit")
        self.reported_spill_volume, self.reported_spill_unit = (
            normalize_unit(self.reported_spill_unit, float(self.reported_spill_volume))
            if self.reported_spill_volume
            else (None, None)
        )
        self.process_geoinformation()

    def get_field_value(self, field):
        """
        Given a field name, return the corresponding value from the relevant sheet
        using the compact FIELD_MAP dictionary.
        """
        # Look up mapping
        mapping = self.field_map.get(field)
        if not mapping:
            return None  # field not found

        sheet_name = mapping["sheet_name"]
        column_name = mapping["column"]

        # Sheet not loaded
        df = self.nrc_dfs.get(sheet_name)
        if df is None:
            return None

        # Filter rows by reportnum (SEQNOS)
        rows = df[df["SEQNOS"] == self.reportnum]
        if rows.empty:
            return None

        # Mimic existing behavior: use the last matching row
        if column_name is None:
            return None

        item = rows.iloc[-1][column_name]

        if pd.isna(item):
            return None

        return item

    def process_geoinformation(self):
        """
        Process geoinformation for the incident, including converting DMS to decimal degrees and geocoding if necessary.
        """

        if None not in (self.lat_deg, self.lat_min, self.lat_sec, self.lat_quad):
            self.lat = dms2dd(self.lat_deg, self.lat_min, self.lat_sec, self.lat_quad)
        else:
            self.lat = None
        if None not in (self.lon_deg, self.lon_min, self.lon_sec, self.lon_quad):
            self.lng = dms2dd(self.lon_deg, self.lon_min, self.lon_sec, self.lon_quad)
        else:
            self.lng = None

        self.address = None
        self.geo_results = None
        self.precision = "Explicit"

        # Correct hemisphere placeholder
        if self.lat or self.lng:
            self.lat, self.lng = correct_hemisphere(self.lat, self.lng, self.state)
        # Placeholder for block centroid geocode

        if self.lat and self.lng:
            pass
        elif self.location and self.city and self.state:
            self.address = f"{self.location}, {self.city}, {self.state} {self.zip_code or ''}"
            self.geo_results = geocodeAddress(self.address)
            self.precision = "street_address"
        elif self.incidentlocation and self.city and self.state:
            self.address = (
                f"{self.incidentlocation} {self.city}, {self.state} {self.zip_code or ''}"
            )
            self.geo_results = geocodeAddress(self.address)
            self.precision = "street_address"
        elif self.zip_code:
            self.zip_code = str(int(self.zip_code))
            if len(self.zip_code) == 9:
                self.zip_code = f"{self.zip_code[:5]}-{self.zip_code[5:]}"

            self.geo_results = geocodeAddress(self.zip_code)
            self.precision = "ZIP"
        elif self.city and self.state:
            self.address = f"{self.city}, {self.state}"
            self.geo_results = geocodeAddress(self.address)
            self.precision = "CITY_STATE"
        if self.lat is None or self.lng is None:
            if len(self.geo_results["results"]) > 0:
                self.lat, self.lng = self.geo_results["results"][0]["geometry"]["location"].values()
                self.lat = float(self.lat)
                self.lng = float(self.lng)
            else:
                logging.error("No geocode results=", self.task_id)
                raise ValueError("No geocode results=" + str(self.task_id))

        if self.precision == "Explicit":
            self.source = "Explicit"
        elif self.geo_results is not None:
            self.source = "Approximated from " + self.geo_results["results"][0]["types"][0]
        else:
            self.source = "Unknown"

    def build_nrc_post(self):
        """
        Compile NRC information into a post_fields object to be posted to monitor feedentry
        """
        tags = []
        severity = ""

        tags.append("NRC")
        if self.reported_spill_volume is None:
            self.reported_spill_volume = 0
        if self.release_type is not None:
            tags.append(self.release_type)
        if (self.reported_spill_volume > 100) and self.reported_spill_unit == "GALLON":
            tags.append("BigSpill")
        if self.incidenttype == "RAILROAD NON-RELEASE" or self.medium_affected in (
            "NON-RELEASE (N/A)",
            "RAIL REPORT (N/A)",
        ):
            tags.append("non-release")
            severity = "non-release"
        if (
            self.reported_spill_volume < 42
            and self.min_spill_volume < 42
            and re.match("HYDRAULIC", self.material_name or "")
            or self.material_name
            in ("REFRIGERANT GASES", "OIL, FUEL: NO. 1-D", "OIL, FUEL: NO. 2-D")
        ):
            tags.append("minor")
            severity = "minor"
        if (
            self.incidenttype == "UNKNOWN SHEEN"
            and self.reported_spill_volume < 1
            and self.min_spill_volume < 10
        ):
            tags.append("minor")
        if self.reported_spill_volume > 100 or self.min_spill_volume > 100:
            tags.append("major")

        if self.state == "LA" and severity != "minor" and severity != "non-release":
            tags.append("LABB")

        tags.append("release")

        if self.material_name == None:
            self.material_name = ""

        title = "NRC Report: " + self.material_name.title()
        if self.nearestcity and self.state:
            title += " near " + self.nearestcity.title() + ", " + self.state
        link = self.full_report_url
        summary = "Incident Type: " + self.incidenttype + " - NRC Report ID: " + str(self.task_id)
        if self.medium_affected:
            summary += " - Medium Affected: " + self.medium_affected
        summary += " - Suspected Responsible Party: "
        if self.suspected_responsible_company:
            summary += self.suspected_responsible_company
        content = (
            '<b>Report Details</b><br/>NRC Report ID: <a href="https://nrc.uscg.mil/" target="_blank">'
            + str(self.task_id)
        )
        if self.incident_datetime:
            content += "</a><br/>Incident Time: " + str(self.incident_datetime)
        if self.nearestcity or self.state:
            content += "<br/>Nearest City: "
            if self.nearestcity:
                content += self.nearestcity.title() + ", "
            if self.state:
                content += self.state
        if self.location:
            content += "<br/>Location: " + self.location
        if self.incident_location:
            content += "<br/>Location2: " + self.incident_location
        if self.incidenttype:
            content += "<br/>Incident Type: " + self.incidenttype
        if self.material_name:
            content += "<br/>Material: " + self.material_name
        if self.medium_affected:
            content += "<br/>Medium Affected: " + self.medium_affected
        if self.suspected_responsible_company:
            content += "<br/>Suspected Responsible Party: " + self.suspected_responsible_company

        content += (
            "<br/><b>SkyTruth Analysis</b><br/>"
            + "Lat/Long: "
            + str(round(self.lat, 6))
            + ", "
            + str(round(self.lng, 6))
            + " ("
            + self.source
            + ") "
            + '<a href="https://skytruth.org/section/alerts-geocoding/" target="_blank">'
            + '<img src="/images/icons8-info-20.png" align="center" /></a>'
        )
        if self.sheen_width_ft and self.sheen_length_ft:
            content += (
                "<br/>"
                + "Reported Sheen Size: "
                + format_value_extent(self.sheen_width_ft)
                + " by "
                + format_value_extent(self.sheen_length_ft)
                + " (area "
                + format_value_area(self.sheen_width_ft * self.sheen_length_ft)
                + ")"
            )
        if self.reported_spill_volume:
            content += (
                "<br/>"
                + "Reported Spill Volume: "
                + str(int(self.reported_spill_volume))
                + " "
                + self.reported_spill_unit.lower()
            )
        if self.min_spill_volume:
            content += (
                "<br/>" + "SkyTruth Minimum Estimate: " + format_value_volume(self.min_spill_volume)
            )
        content += "<br/>" + "<b>Report Description</b>" + self.description

        id = hashlib.md5(
            (summary + str(self.incident_datetime) + str(self.lat) + str(self.lng)).encode()
        ).hexdigest()
        id = "-".join((id[:8], id[8:12], id[12:16], id[16:20], id[20:32]))
        post_fields = {
            "id": id,
            "title": title,
            "link": link,
            "summary": summary,
            "content": content,
            "lat": self.lat,
            "lng": self.lng,
            "source_id": 1,
            "kml_url": "",
            "incident_datetime": self.incident_datetime,
            "source_item_id": self.task_id,
            "tags": tags,
            "status": "published",
            "bot_reportnum_done": self.task_id,
        }
        return post_fields


def main(excel_save_location=None, limit_incident_count=None):
    current_year = datetime.strftime(datetime.now(), "%y")
    previous_year = datetime.strftime(datetime.now().replace(year=datetime.now().year - 1), "%y")
    if excel_save_location is None:  # Use docker /tmp directory
        excel_save_location = "/tmp"
    file_name = f"CY{current_year}.xlsx"
    download_url = f"https://nrc.uscg.mil/FOIAFiles/CY{current_year}.xlsx"
    logging.info(f"Downloading NRC data from {download_url} to {excel_save_location}")
    download(download_url, excel_save_location, file_name)
    nrc_sheets = [
        "CALLS",
        "INCIDENT_COMMONS",
        "INCIDENT_DETAILS",
        "MATERIAL_INVOLVED",
    ]
    xls = pd.ExcelFile(excel_save_location + "/" + file_name)
    # check to see if all required sheets are present in the xls file
    if not set(nrc_sheets).issubset(xls.sheet_names):
        logging.error("No NRC data found in downloaded spreadsheet. Reverting to previous year.")

        previous_file_name = f"CY{previous_year}.xlsx"
        previous_download_url = f"https://nrc.uscg.mil/FOIAFiles/{previous_file_name}"

        download(previous_download_url, excel_save_location, previous_file_name)

        excel_path = os.path.join(excel_save_location, previous_file_name)
    else:
        excel_path = os.path.join(excel_save_location, file_name)
    nrc_dfs = pd.read_excel(excel_path, sheet_name=nrc_sheets)
    incident_commons = nrc_dfs["INCIDENT_COMMONS"]
    most_recent_reportnum = incident_commons["SEQNOS"].max()

    db = NrcDatabase()
    last_posted_reportnum = db.get_last_posted_reportnum()[0]
    logging.info(
        f"Last posted reportnum: {last_posted_reportnum}",
    )
    logging.info(
        f"Most recent reportnum in NRC data: {most_recent_reportnum}",
    )
    total_to_process = (
        incident_commons[incident_commons["SEQNOS"] > last_posted_reportnum]["SEQNOS"]
        .unique()
        .tolist()
    )
    if limit_incident_count is not None:
        total_to_process = total_to_process[:limit_incident_count]
    if len(total_to_process) == 0:
        logging.warning("No new incidents to process in NRC spreadsheet.")
    logging.info(f"Processing {len(total_to_process)} new NRC reports...")
    for reportnum in total_to_process:
        try:
            nrc_incident = NrcIncident(reportnum=reportnum, nrc_dfs=nrc_dfs)
            post_fields = nrc_incident.build_nrc_post()
            if post_fields:
                logging.info(
                    f"Inserted incident {reportnum}: {post_fields['title']} into feedentry."
                )
                url = config.API_POST_FEEDENTRY
                response = requests.post(url, data=post_fields)
                logging.info(f"Post to feedentry status: {response.content}")

            else:
                logging.info(f"Failed to build post for reportnum {reportnum}.")
        except Exception as e:
            logging.error(f"Error processing reportnum {reportnum}: {e}")
            continue


if __name__ == "__main__":
    main()
