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

field_map_df = pd.DataFrame(FIELD_MAP)


def correct_hemisphere(lat, lon, LOCATION_STATE):
    if LOCATION_STATE in TERRITORIES.keys() and (lat < 0 or lon > 0):
        print("corrected hemisphere for ", lat, lon)
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


def computer_min_spill_volume(sheen_width_ft, sheen_length_ft):
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


def get_last_posted_reportnum(db_cursor):
    query = """SELECT source_item_id from feedentry where source_id=1 AND source_item_id>0 AND status='published' 
        order by source_item_id DESC LIMIT 1"""
    db_cursor.execute(query)
    return db_cursor.fetchone()


def get_field_value(nrc_dfs, field_map_df, reportnum, db_field):
    """
    Given a db_field and reportnum, return the corresponding value from the relevant sheet using the field mapping.

    Parameters:
        nrc_dfs (dict): dictionary of pandas DataFrames keyed by sheet name
        field_map_df (pd.DataFrame): the field mapping DataFrame
        reportnum (int/str): the unique identifier to query (maps to SEQNOS in sheets)
        db_field (str): the target database field to look up

    Returns:
        value of the field for the given reportnum, or None if not found
    """
    # Look up mapping for this db_field
    mapping = field_map_df[field_map_df["db_field"] == db_field]

    if mapping.empty:
        return None  # db_field not found in mapping

    # There should be only one row in mapping per db_field
    mapping_row = mapping.iloc[0]
    sheet_name = mapping_row["sheet_name"]
    column_name = mapping_row["column"]

    # Query the sheet
    if sheet_name not in nrc_dfs:
        return None  # Sheet not loaded

    df = nrc_dfs[sheet_name]
    row = df[df["SEQNOS"] == reportnum]

    if row.empty:
        return None  # reportnum not found

    # Choose the last listed material, mimicking the existing scraper functionality
    item = row.iloc[-1][column_name]

    if pd.isna(item):
        return None
    else:
        return item


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
            raise ValueError("ERROR: Illegal value: %s" % iv)

    if quadrant.lower() not in ("n", "e", "s", "w"):
        raise ValueError("ERROR: Invalid quadrant: %s" % quadrant)
    # 9/21/2020
    # Round to 6 decimals
    output = round(int(degrees) + int(minutes) / 60 + int(seconds) / 3600, 6)

    if quadrant.lower() in ("s", "w"):
        output *= -1

    return output


def process_geoinformation(nrc_dfs, reportnum):
    # Pull data from merged_data
    task_id = get_field_value(nrc_dfs, field_map_df, reportnum, "task_id")
    areaid = None  # get_field_value(nrc_dfs, field_map_df, reportnum, "areaid")
    blockid = None  # get_field_value(nrc_dfs, field_map_df, reportnum, "blockid")
    lat = None  # get_field_value(nrc_dfs, field_map_df, reportnum, "latitude")
    lng = None  # get_field_value(nrc_dfs, field_map_df, reportnum, "longitude")
    zip_code = get_field_value(nrc_dfs, field_map_df, reportnum, "zip")
    city = get_field_value(nrc_dfs, field_map_df, reportnum, "nearestcity")
    state = get_field_value(nrc_dfs, field_map_df, reportnum, "state")
    location = get_field_value(nrc_dfs, field_map_df, reportnum, "location")
    incidentlocation = get_field_value(nrc_dfs, field_map_df, reportnum, "incidentlocation")
    locationstreet1 = get_field_value(nrc_dfs, field_map_df, reportnum, "locationstreet1")
    locationstreet2 = get_field_value(nrc_dfs, field_map_df, reportnum, "locationstreet2")

    # Pull latitude DMS/quadrant fields
    lat_deg = get_field_value(nrc_dfs, field_map_df, reportnum, "lat_degrees")
    lat_min = get_field_value(nrc_dfs, field_map_df, reportnum, "lat_minutes")
    lat_sec = get_field_value(nrc_dfs, field_map_df, reportnum, "lat_seconds")
    lat_quad = get_field_value(nrc_dfs, field_map_df, reportnum, "lat_quadrant")

    # Pull longitude DMS/quadrant fields
    lon_deg = get_field_value(nrc_dfs, field_map_df, reportnum, "lon_degrees")
    lon_min = get_field_value(nrc_dfs, field_map_df, reportnum, "lon_minutes")
    lon_sec = get_field_value(nrc_dfs, field_map_df, reportnum, "lon_seconds")
    lon_quad = get_field_value(nrc_dfs, field_map_df, reportnum, "lon_quadrant")

    # Compute decimal coordinates if all components exist

    if None not in (lat_deg, lat_min, lat_sec, lat_quad):
        lat = dms2dd(lat_deg, lat_min, lat_sec, lat_quad)
    else:
        lat = None
    if None not in (lon_deg, lon_min, lon_sec, lon_quad):
        lng = dms2dd(lon_deg, lon_min, lon_sec, lon_quad)
    else:
        lng = None

    address = None
    geo_results = None
    precision = "Explicit"

    incidenttype = get_field_value(nrc_dfs, field_map_df, reportnum, "incidenttype")

    # Correct hemisphere placeholder
    if lat or lng:
        lat, lng = correct_hemisphere(lat, lng, state)
    # Placeholder for block centroid geocode

    if lat and lng:
        pass
    elif location and city and state:
        address = f"{location} {city}, {state} {zip_code or ''}"
        geo_results = geocodeAddress(address, "street_address", task_id, state)
        precision = "street_address"
    elif incidentlocation and city and state:
        address = f"{incidentlocation} {city}, {state} {zip_code or ''}"
        geo_results = geocodeAddress(address, "street_address", task_id, state)
        precision = "street_address"
    elif zip_code or (city and state):
        if zip_code:
            if len(zip_code) == 9:
                zip_code = f"{zip_code[:5]}-{zip_code[5:]}"
            geo_results = geocodeAddress(zip_code, "ZIP", task_id, state)
            precision = "ZIP"
        elif city and state:
            address = f"{city}, {state}"
            geo_results = geocodeAddress(address, "CITY_STATE", task_id, state)
            precision = "CITY_STATE"
    else:
        # print("Not enough info to find a geo code, reportnum=", task_id)
        return 0.0, 0.0, "Unknown", None
    if lat is None or lng is None:
        # print(f"No lat/lng, getting from {precision} geocode for reportnum=", task_id)
        try:
            lat, lng = geo_results["results"][0]["geometry"]["location"].values()
            lat = float(lat)
            lng = float(lng)
        except Exception as e:
            print("Geocoding failed for reportnum=", task_id, " error=", e)
            return 0.0, 0.0, "Unknown", geo_results
    else:
        pass
        # print(f"Returning explicit lat/lng from DMS for reportnum=", task_id)
    return lat, lng, precision, geo_results


def geocodeAddress(address, source, task_id, state):
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json?%s" % urllib.parse.urlencode(
        {
            "address": address,
            "sensor": "false",
            "key": config.GEOCODING_API_KEY,  # Secret removed, lets move this to config file later
        }
    )

    results = requests.get(geocode_url)
    # Results will be in JSON format - convert to dict using requests functionality
    results = results.json()
    return results


def build_nrc_post(nrc_dfs, reportnum):
    task_id = get_field_value(nrc_dfs, field_map_df, reportnum, "task_id")
    description = get_field_value(nrc_dfs, field_map_df, reportnum, "description")
    incident_datetime = timestamp2datetime(
        get_field_value(nrc_dfs, field_map_df, reportnum, "incident_datetime")
    )
    incidenttype = get_field_value(nrc_dfs, field_map_df, reportnum, "incidenttype")
    location = get_field_value(nrc_dfs, field_map_df, reportnum, "location")
    state = get_field_value(nrc_dfs, field_map_df, reportnum, "state")
    nearestcity = get_field_value(nrc_dfs, field_map_df, reportnum, "nearestcity")
    suspected_responsible_company = get_field_value(
        nrc_dfs, field_map_df, reportnum, "suspected_responsible_company"
    )
    medium_affected = get_field_value(nrc_dfs, field_map_df, reportnum, "medium_affected")
    material_name = get_field_value(nrc_dfs, field_map_df, reportnum, "material_name")
    full_report_url = "http://nrc.uscg.mil/	"
    incident_location = get_field_value(nrc_dfs, field_map_df, reportnum, "incidentlocation")
    reported_spill_volume = get_field_value(nrc_dfs, field_map_df, reportnum, "amount")
    reported_spill_unit = get_field_value(nrc_dfs, field_map_df, reportnum, "unit")

    reported_spill_volume, reported_spill_unit = (
        normalize_unit(reported_spill_unit, float(reported_spill_volume))
        if reported_spill_volume
        else (None, None)
    )

    lat, lng, precision, geo_results = process_geoinformation(nrc_dfs, reportnum)
    if precision == "Explicit":
        source = "Explicit"
    else:
        source = "Approximated from " + geo_results["results"][0]["types"][0]
    sheen_length = get_field_value(nrc_dfs, field_map_df, reportnum, "sheen_size_length")
    sheen_width = get_field_value(nrc_dfs, field_map_df, reportnum, "sheen_size_width")
    sheen_length_unit = get_field_value(nrc_dfs, field_map_df, reportnum, "sheen_size_length_unit")
    sheen_width_unit = get_field_value(nrc_dfs, field_map_df, reportnum, "sheen_size_width_unit")

    sheen_width_ft = (
        normalize_unit(sheen_width_unit, float(sheen_width))[0] if sheen_width else None
    )
    sheen_length_ft = (
        normalize_unit(sheen_length_unit, float(sheen_length))[0] if sheen_length else None
    )

    release_type = RELEASE_TYPE_DICT.get(material_name, None)

    min_spill_volume = computer_min_spill_volume(sheen_width_ft, sheen_length_ft)

    tags = []
    severity = ""

    tags.append("NRC")
    if reported_spill_volume is None:
        reported_spill_volume = 0
    if release_type is not None:
        tags.append(release_type)
    if (reported_spill_volume > 100) and reported_spill_unit == "GALLON":
        tags.append("BigSpill")
    if incidenttype == "RAILROAD NON-RELEASE" or medium_affected in (
        "NON-RELEASE (N/A)",
        "RAIL REPORT (N/A)",
    ):
        tags.append("non-release")
        severity = "non-release"
    if (
        reported_spill_volume < 42
        and min_spill_volume < 42
        and re.match("HYDRAULIC", material_name or "")
        or material_name in ("REFRIGERANT GASES", "OIL, FUEL: NO. 1-D", "OIL, FUEL: NO. 2-D")
    ):
        tags.append("minor")
        severity = "minor"
    if incidenttype == "UNKNOWN SHEEN" and reported_spill_volume < 1 and min_spill_volume < 10:
        tags.append("minor")
    if reported_spill_volume > 100 or min_spill_volume > 100:
        tags.append("major")

    if state == "LA" and severity != "minor" and severity != "non-release":
        tags.append("LABB")

    tags.append("release")

    if material_name == None:
        material_name = ""

    title = "NRC Report: " + material_name.title()
    if nearestcity and state:
        title += " near " + nearestcity.title() + ", " + state
    link = full_report_url
    summary = "Incident Type: " + incidenttype + " - NRC Report ID: " + str(task_id)
    if medium_affected:
        summary += " - Medium Affected: " + medium_affected
    summary += " - Suspected Responsible Party: "
    if suspected_responsible_company:
        summary += suspected_responsible_company
    content = (
        '<b>Report Details</b><br/>NRC Report ID: <a href="https://nrc.uscg.mil/" target="_blank">'
        + str(task_id)
    )
    if incident_datetime:
        content += "</a><br/>Incident Time: " + str(incident_datetime)
    if nearestcity or state:
        content += "<br/>Nearest City: "
        if nearestcity:
            content += nearestcity.title() + ", "
        if state:
            content += state
    if location:
        content += "<br/>Location: " + location
    if incident_location:
        content += "<br/>Location2: " + incident_location
    if incidenttype:
        content += "<br/>Incident Type: " + incidenttype
    if material_name:
        content += "<br/>Material: " + material_name
    if medium_affected:
        content += "<br/>Medium Affected: " + medium_affected
    if suspected_responsible_company:
        content += "<br/>Suspected Responsible Party: " + suspected_responsible_company

    content += (
        "<br/><b>SkyTruth Analysis</b><br/>"
        + "Lat/Long: "
        + str(round(lat, 6))
        + ", "
        + str(round(lng, 6))
        + " ("
        + source
        + ") "
        + '<a href="https://skytruth.org/section/alerts-geocoding/" target="_blank">'
        + '<img src="/images/icons8-info-20.png" align="center" /></a>'
    )
    if sheen_width_ft and sheen_length_ft:
        content += (
            "<br/>"
            + "Reported Sheen Size: "
            + format_value_extent(sheen_width_ft)
            + " by "
            + format_value_extent(sheen_length_ft)
            + " (area "
            + format_value_area(sheen_width_ft * sheen_length_ft)
            + ")"
        )
    if reported_spill_volume:
        content += (
            "<br/>"
            + "Reported Spill Volume: "
            + str(int(reported_spill_volume))
            + " "
            + reported_spill_unit.lower()
        )
    if min_spill_volume:
        content += "<br/>" + "SkyTruth Minimum Estimate: " + format_value_volume(min_spill_volume)
    content += "<br/>" + "<b>Report Description</b>" + description

    id = hashlib.md5((summary + str(incident_datetime) + str(lat) + str(lng)).encode()).hexdigest()
    id = "-".join((id[:8], id[8:12], id[12:16], id[16:20], id[20:32]))
    post_fields = {
        "id": id,
        "title": title,
        "link": link,
        "summary": summary,
        "content": content,
        "lat": lat,
        "lng": lng,
        "source_id": 1,
        "kml_url": "",
        "incident_datetime": incident_datetime,
        "source_item_id": task_id,
        "tags": tags,
        "status": "published",
        "bot_reportnum_done": task_id,
    }
    return post_fields


def main(excel_save_location=None, limit_incident_count=None):
    current_year = datetime.strftime(datetime.now(), "%y")
    if excel_save_location is None:  # Use docker /tmp directory
        excel_save_location = "/tmp"
    file_name = f"CY{current_year}.xlsx"
    download_url = f"https://nrc.uscg.mil/FOIAFiles/CY{current_year}.xlsx"
    print("Downloading NRC data from", download_url, "to", excel_save_location)
    download(download_url, excel_save_location, file_name)
    nrc_sheets = [
        "CALLS",
        "INCIDENT_COMMONS",
        "INCIDENT_DETAILS",
        "MATERIAL_INVOLVED",
    ]
    db_conn = psycopg2.connect(config.DB_CONNECTION_STRING)
    db_conn.autocommit = True
    db_cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    last_posted_reportnum = get_last_posted_reportnum(db_cursor)[0]
    nrc_dfs = pd.read_excel(excel_save_location + "/" + file_name, sheet_name=nrc_sheets)
    INCIDENT_COMMONS = nrc_dfs["INCIDENT_COMMONS"]
    most_recent_reportnum = INCIDENT_COMMONS["SEQNOS"].max()
    print("Last posted reportnum:", last_posted_reportnum)
    print("Most recent reportnum in NRC data:", most_recent_reportnum)
    total_to_process = (
        INCIDENT_COMMONS[INCIDENT_COMMONS["SEQNOS"] > last_posted_reportnum]["SEQNOS"]
        .unique()
        .tolist()
    )
    if limit_incident_count is not None:
        total_to_process = total_to_process[:limit_incident_count]
    print(f"Processing {len(total_to_process)} new NRC reports...")
    for reportnum in total_to_process:
        print("Processing reportnum:", reportnum)
        post_fields = build_nrc_post(nrc_dfs, reportnum)
        if post_fields:
            print(f"Inserted incident: {post_fields['title']} into feedentry.")
        else:
            print(f"Failed to build post for reportnum {reportnum}.")
