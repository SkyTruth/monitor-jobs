#!/usr/bin/env python


# This document is part of scraper
# https://github.com/SkyTruth/scraper


# =================================================================================== #
#
#  The MIT License (MIT)
#
#  Copyright (c) 2014 SkyTruth
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.
#
# =================================================================================== #


"""
Scraper for the "temporary" NRC incident spreadsheet

Sample command:
    ./bin/nrcSpreadsheetScraper.py --db-name test_skytruth --db-user `whoami` --db-host localhost
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re
from datetime import datetime
import os
from os.path import *
import sys
import urllib
import psycopg2
import xlrd
import urllib
import requests
from items import NrcTag, BotTaskError, FeedEntryTag
from database import NrcDatabase
import utils
from scrapy.loader import ItemLoader
from scrapy.selector import Selector

territories = {
    "AL": "Alabama",
    "KY": "Kentucky",
    "OH": "Ohio",
    "AK": "Alaska",
    "LA": "Louisiana",
    "OK": "Oklahoma",
    "AZ": "Arizona",
    "ME": "Maine",
    "OR": "Oregon",
    "AR": "Arkansas",
    "MD": "Maryland",
    "PA": "Pennsylvania",
    "AS": "American Samoa",
    "MA": "Massachusetts",
    "PR": "Puerto Rico",
    "CA": "California",
    "MI": "Michigan",
    "RI": "Rhode Island",
    "CO": "Colorado",
    "MN": "Minnesota",
    "SC": "South Carolina",
    "CT": "Connecticut",
    "MS": "Mississippi",
    "SD": "South Dakota",
    "DE": "Delaware",
    "MO": "Missouri",
    "TN": "Tennessee",
    "DC": "District of Columbia",
    "MT": "Montana",
    "TX": "Texas",
    "FL": "Florida",
    "NE": "Nebraska",
    "TT": "Trust Territories",
    "GA": "Georgia",
    "NV": "Nevada",
    "UT": "Utah",
    "GU": "Guam",
    "NH": "New Hampshire",
    "VT": "Vermont",
    "HI": "Hawaii",
    "NJ": "New Jersey",
    "VA": "Virginia",
    "ID": "Idaho",
    "NM": "New Mexico",
    "VI": "Virgin Islands",
    "IL": "Illinois",
    "NY": "New York",
    "WA": "Washington",
    "IN": "Indiana",
    "NC": "North Carolina",
    "WV": "West Virginia",
    "IA": "Iowa",
    "ND": "North Dakota",
    "WI": "Wisconsin",
    "KS": "Kansas",
    "MP": "Northern Mariana Islands",
    "WY": "Wyoming",
}
outlier_territories = ["AS", "GU", "MP", "TT"]
extra_locations = {
    "CN": "Canada",
    "MX": "Mexico",
    "PN": "Panama",
    "PI": "Pacific Island Territories",
    "BF": "The Bahamas",
    "NI": "Saipan Island",
}

all_territories = {**territories, **extra_locations}


def debug_format(text):
    text = str(text)
    space = 30
    padding = space - len(text)
    return text + padding * " "


# Maybe change the if to look at vessels where they are legit. But check to see that the following works first.
# if LOCATION_STATE in territories.keys() or (LOCATION_STATE in outlier_territories and TYPE_OF_INCIDENT != 'VESSEL'):


def correct_hemisphere(lat, lon, LOCATION_STATE, TYPE_OF_INCIDENT):
    if LOCATION_STATE in territories.keys():
        if lat < 0 or lon > 0:
            print("corrected hemisphere for ", lat, lon)
            lat = abs(lat)
            lon = -abs(lon)
    return lat, lon


# /* ======================================================================= */#
# /*     Python setup
# /* ======================================================================= */#

if sys.version[0] == 2:
    range = xrange


# /* ======================================================================= */#
# /*     Build information
# /* ======================================================================= */#

__version__ = "0.1-dev"
__release__ = "August 8, 2014"
__author__ = "Kevin D. Wurster"
__source__ = "https://github.com/SkyTruth/scraper"
__docname__ = basename(__file__)
__license__ = """
The MIT License (MIT)

Copyright (c) 2014 SkyTruth

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""


# /* ======================================================================= */#
# /*     Define print_usage() function
# /* ======================================================================= */#


def print_usage():
    """
    Command line usage information

    :return: 1 for exit code purposes
    :rtype: int
    """

    print(
        """
Usage:

    {0} [--help-info] [options] [--no-download] [--download-url URL]
    {1} [--db-connection-string] [--db-host hostname] [--db-user username]
    {1} [--db-pass password] [--no-print-progress] [--print-queries]
    {1} [--no-execute-queries] [--overwrite]

Options:

    --db-connection-string  Explicitly define a Postgres supported connection
                            string.  All other --db-* options are ignored.
    --db-host               Hostname for the target database
                            [default: localhost]
    --db-user               Username used for database connection
                            [default: current user]
    --db-name               Name of target database
                            [default: skytruth]
    --db-pass               Password for database user
                            [default: '']

    --download-url          URL from which to download the input file
    --no-download           Don't download the input file
    --overwrite-download    If the --file-to-process already exists and --no-download
                            has not been specified, blindly overwrite the file.
                            Unless the user is specifying a specific target for
                            the download, this flag is not needed due the default
                            file name containing datetime down to the second.

    --file-to-process       Specify where the input file will be downloaded to
                            If used in conjunction with --no-download it is
                            assumed that the specified file already exists and
                            should be used for processing
                            [default: Current_<CURRENT_DATETIME>.xlsx]
    --no-print-progress     Don't print the progress indicator
    --print-queries         Print queries immediately before execution
                            Automatically turns off the progress indicator
    --no-execute-queries    Don't execute queries

""".format(__docname__, " " * len(__docname__))
    )
    return 1


# /* ======================================================================= */#
# /*     Define print_license() function
# /* ======================================================================= */#


def print_license():
    """
    Print out license information

    :return: 1 for exit code purposes
    :rtype: int
    """

    print(__license__)

    return 1


# /* ======================================================================= */#
# /*     Define print_help() function
# /* ======================================================================= */#


def print_help():
    """
    Detailed help information

    :return: 1 for exit code purposes
    :rtype: int
    """

    print(
        """
Help: {0}
------{1}
{2}
    """.format(__docname__, "-" * len(__docname__), main.__doc__)
    )

    return 1


# /* ======================================================================= */#
# /*     Define print_help_info() function
# /* ======================================================================= */#


def print_help_info():
    """
    Print a list of help related flags

    :return: 1 for exit code purposes
    :rtype: int
    """

    print("""
Help flags:
    --help      More detailed description of this utility
    --usage     Arguments, parameters, flags, options, etc.
    --version   Version and ownership information
    --license   License information
    """)

    return 1


# /* ======================================================================= */#
# /*     Define print_version() function
# /* ======================================================================= */#


def print_version():
    """
    Print script version information

    :return: 1 for exit code purposes
    :rtype: int
    """

    print(
        """
%s version %s - released %s
    """
        % (__docname__, __version__, __release__)
    )

    return 1


# /* ======================================================================= */#
# /*     Define dms2dd() function
# /* ======================================================================= */#


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


# /* ======================================================================= */#
# /*     Define column_names() function
# /* ======================================================================= */#


def column_names(sheet, formatter=str):
    """
    Get the ordered column names from an XLRD sheet object

    :param sheet: XLRD sheet object
    :type sheet: xlrd.Sheet
    :param formatter:
    :type formatter: type|function

    :return: list of column names
    :rtype: list
    """

    return [formatter(cell.value) for cell in sheet.row(0)]


# /* ======================================================================= */#
# /*     Define sheet2dict() function
# /* ======================================================================= */#


def sheet2dict(sheet):
    """
    Convert an XLRD sheet object into a list of rows, each structured as a dictionary


    Example Input:

        "Column1","Column2","Column3"
        "Row 1 Val","Another Row 1 Val","Even More Row 1 Values"
        "Row 2 Val","Another Row 2 Val","Even More Row 2 Values"
        "Row 3 Val","Another Row 3 Val","Even More Row 3 Values"


    Example Output:

        [
            {
                'Column1': 'Row 1 Val',
                'Column2': 'Another Row 1 Val',
                'Column3': 'Even More Row 1 Values'
            },
            {
                'Column1': 'Row 2 Val',
                'Column2': 'Another Row 2 Val',
                'Column3': 'Even more Row 2 Values'
            }
            {
                'Column1': 'Row 3 Val',
                'Column2': 'Another Row 3 Val',
                'Column3': 'Even more Row 3 Values'
            }
        ]

    :param sheet: XLRD sheet object from xlrd.open_workbook('workbook').sheet_by_name('name')
    :type sheet: xlrd.Sheet

    :return: list of elements, each containing one row of the sheet as a dictionary
    :rtype: dict
    """

    output = []
    columns = column_names(sheet)
    for r in range(1, sheet.nrows):  # Skip first row since it contains the header
        output.append(dict((columns[c], sheet.cell_value(r, c)) for c in range(sheet.ncols)))

    return output


def report_already_posted(db_cursor, reportnum):
    # reportnum = kwargs['reportnum']
    cursor = db_cursor
    cursor.execute("""SELECT * FROM feedentry WHERE source_item_id=%s""" % (reportnum))
    return len(cursor.fetchall()) > 0


# /* ======================================================================= */#
# /*     Define report_exists() function
# /* ======================================================================= */#


def report_exists(**kwargs):
    """
    Check to see if a report has already been submitted to a table

    :param seqnos: reportnum
    :type seqnos: int|float
    :param field:
    :type field:

    :return:
    :rtype: bool
    """

    reportnum = kwargs["reportnum"]
    cursor = kwargs["db_cursor"]
    table = kwargs["table"]
    field = kwargs.get("field", "reportnum")
    schema = kwargs["schema"]

    # TODO: replace this hack with something better.
    # Perhpas have a report_exists method on each of the field map classes so we don't have to
    # have the same existance test for all tables

    if table == '"BotTaskStatus"':
        cursor.execute(
            """SELECT * FROM %s.%s WHERE bot='NrcExtractor' AND task_id = %s"""
            % (schema, table, reportnum)
        )
    else:
        cursor.execute("""SELECT * FROM %s.%s WHERE %s = %s""" % (schema, table, field, reportnum))
    return len(cursor.fetchall()) > 0


# /* ======================================================================= */#
# /*     Define timestamp2datetime() function
# /* ======================================================================= */#


def timestamp2datetime(stamp, workbook_datemode, formatter="%Y-%m-%d %I:%M:%S"):
    """
    Convert a float formatted date a Postgres supported timestamp

    :param stamp: timestamp from XLRD reading a date encoded field
    :type stamp: float
    :param workbook_datemode: from xlrd.Workbook.datemode
    :type workbook_datemode: int

    :return: date capable of being inserted into Postgres timestamp field
    :rtype: str|unicode
    """

    dt = datetime(*xlrd.xldate_as_tuple(stamp, workbook_datemode))

    return dt.strftime(formatter)


# /* ======================================================================= */#
# /*     Define get_current_spreadsheet() function
# /* ======================================================================= */#


def download(url, destination, overwrite=False):
    """
    Download a file

    :param url: URL to download from
    :type url: str|unicode
    :param destination: target path and filename for downloaded file
    :type destination: str|unicode
    :param overwrite: specify whether or not an existing destination should be overwritten
    :type overwrite: bool

    :return: path to downloaded file
    :rtype: str|unicode
    """

    # Validate arguments
    if not overwrite and isfile(destination):
        raise ValueError("ERROR: Overwrite=%s and outfile exists: %s" % (overwrite, destination))

    # Download
    response = urllib.request.urlopen(url)
    # with open(destination, 'wb') as f:
    with open(destination, "wb") as f:
        f.write(response.read())

    return destination


# /* ======================================================================= */#
# /*     Define name_current_file() function
# /* ======================================================================= */#


def name_current_file(input_name):
    """
    Generate the output Current.xlsx name for permanent archival

    :param input_name: input file name (e.g. Current.xlsx)
    :type input_name: str|unicode

    :return: output formatted name
    :rtype: str|unicode
    """

    dt = datetime.now()
    dt = dt.strftime("_%Y-%m-%d_%I:%M:%S")
    input_split = input_name.split(".")
    input_split[0] += dt

    return ".".join(input_split)


# /* ======================================================================= */#
# /*     Define db_row_count() function
# /* ======================================================================= */#


def db_row_count(cursor, schema_table):
    """

    :param cursor: Postgres formatted database connection string
    :type cursor: psycopg2.cursor
    :param schema_table: schema.table
    :type schema_table: str|unicode

    :return: number of rows in the specified schema.table
    :rtype: int
    """

    query = """SELECT COUNT(1) FROM %s;""" % schema_table
    cursor.execute(query)
    result = cursor.fetchall()

    return int(result[0][0])


# /* ======================================================================= */#
# /*     Define process_field_map() function
# /* ======================================================================= */#


def process_field_map(**kwargs):
    db_cursor = kwargs["db_cursor"]
    uid = kwargs["uid"]
    workbook = kwargs["workbook"]
    row = kwargs["row"]
    db_null_value = kwargs["db_null_value"]
    map_def = kwargs["map_def"]
    sheet = kwargs["sheet"]
    all_field_maps = kwargs["all_field_maps"]
    sheet_seqnos_field = kwargs["sheet_seqnos_field"]
    db_write_mode = kwargs["db_write_mode"]
    print_queries = kwargs["print_queries"]
    execute_queries = kwargs["execute_queries"]
    raw_sheet_cache = kwargs["raw_sheet_cache"]
    db_seqnos_field = kwargs["db_seqnos_field"]

    if map_def["processing"] is None:
        try:
            value = row[map_def["column"]]
        except KeyError:
            # UID doesn't appear in the specified sheet - populate a NULL value
            value = db_null_value

    # Pass all necessary information to the processing function in order to get a result
    else:
        value = map_def["processing"]["function"](
            db_cursor=db_cursor,
            uid=uid,
            workbook=workbook,
            row=row,
            db_null_value=db_null_value,
            map_def=map_def,
            sheet=sheet,
            all_field_maps=all_field_maps,
            sheet_seqnos_field=sheet_seqnos_field,
            db_write_mode=db_write_mode,
            print_queries=print_queries,
            execute_queries=execute_queries,
            raw_sheet_cache=raw_sheet_cache,
            db_seqnos_field=db_seqnos_field,
        )

    return value


# def error_condition(error, details, task_id=0, exc_info=None):
#     print("error:", error)
#     print("details:", details)
#     if task_id != 0:
#         print("task_id:", str(task_id))
#     if exc_info:
#         exc_type, exc_obj, exc_tb = exc_info
#         fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
#         print(str(exc_type) + ":" + str(fname) + ":" + str(exc_tb.tb_lineno))
#         print(exc_info)
#         # exc_type, exc_obj, exc_tb = exc_info()
#         # fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
#         # print(exc_type, fname, exc_tb.tb_lineno)
#     utils.send_alert("nrcSpreadsheetScraper " + error, str(task_id), details, exc_info)


# /* ======================================================================= */#
# /*     Define NrcScrapedReportField() class
# /* ======================================================================= */#


class NrcScrapedReportFields(object):
    """
    Some fields in the NRC spreadsheet do not map directly to a column in the
    database.  These fields require an additional processing step that is
    highly specific and cannot be re-used.  The field map definition contains
    all of the additional arguments and information necessary to execute one
    of these processing functions.

    A class is used as a namespace to provide better organization and to
    prevent having to name functions something like:
    'get_NrcScrapedReport_material_name_field'
    """

    # /* ----------------------------------------------------------------------- */#
    # /*     Define material_name() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def material_name(**kwargs):
        # Parse arguments
        map_def = kwargs["map_def"]
        print_queries = kwargs["print_queries"]
        execute_queries = kwargs["execute_queries"]
        extras_field_maps = map_def["processing"]["args"]["extras_field_maps"]
        db_write_mode = kwargs["db_write_mode"]
        uid = kwargs["uid"]
        sheet_seqnos_field = kwargs["sheet_seqnos_field"]
        db_cursor = kwargs["db_cursor"]
        raw_sheet_cache = kwargs["raw_sheet_cache"]
        db_seqnos_field = kwargs["db_seqnos_field"]
        db_null_value = kwargs["db_null_value"]
        sheet_cache = kwargs["sheet_cache"]

        # TODO: This currently only reads rows from the sheet specified in the field map and NOT the extra field maps
        #   specified in the processing args.  Currently not a problem since

        # Build query
        initial_value_to_be_returned = None
        for row in raw_sheet_cache[map_def["sheet_name"]]:
            extra_query_fields = []
            extra_query_values = []

            # Found a matching row
            if row[sheet_seqnos_field] == uid:
                # print(uid, row)
                # The first instance goes into the table specified in the field map
                # This query must be handled by the parent process so this value is
                # returned at the very end
                if initial_value_to_be_returned == None:
                    initial_value_to_be_returned = row[map_def["column"]]
                    # print(uid, ' initial_value_to_be_returned:', initial_value_to_be_returned)

                # ALL occurrences are sent to a different table - specified in the field map arguments
                for e_db_map in extras_field_maps:
                    for e_map_def in extras_field_maps[e_db_map]:
                        value = process_field_map(
                            db_cursor=db_cursor,
                            uid=uid,
                            workbook=kwargs["workbook"],
                            row=row,
                            db_null_value=db_null_value,
                            map_def=e_map_def,
                            sheet=sheet_cache[e_map_def["sheet_name"]],
                            all_field_maps=kwargs["all_field_maps"],
                            sheet_seqnos_field=sheet_seqnos_field,
                            db_write_mode=db_write_mode,
                            print_queries=print_queries,
                            execute_queries=execute_queries,
                            raw_sheet_cache=raw_sheet_cache,
                            db_seqnos_field=db_seqnos_field,
                        )

                        # Make sure the value is properly quoted
                        if value not in (None, "", "", db_null_value):
                            # if isinstance(value, str) or isinstance(value, unicode):
                            if isinstance(value, bytes) or isinstance(value, str):
                                value = value.replace(
                                    "'", '"'
                                )  # Single quotes cause problems on insert
                                try:
                                    if e_map_def["db_field_width"]:
                                        value = value[: e_map_def["db_field_width"]]
                                except KeyError:
                                    pass
                                extra_query_values.append("'%s'" % value)  # String value
                            else:
                                extra_query_values.append("%s" % value)  # int|float value
                            extra_query_fields.append(e_map_def["db_field"])

                    # Do something with the query
                    query = """%s %s.%s (%s) VALUES (%s);""" % (
                        db_write_mode,
                        e_map_def["db_schema"],
                        e_map_def["db_table"],
                        ", ".join(extra_query_fields),
                        ", ".join(extra_query_values),
                    )
                    if print_queries:
                        print("")
                        print(query)
                    if execute_queries:
                        db_cursor.execute(query)

        # This processing function handled ALL inserts - tell parent process there's nothing left to do
        return initial_value_to_be_returned

    # /* ----------------------------------------------------------------------- */#
    # /*     Define full_report_url() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def full_report_url(**kwargs):
        """
        Default value
        """

        return "http://nrc.uscg.mil/"

    # /* ----------------------------------------------------------------------- */#
    # /*     Define materials_url() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def materials_url(**kwargs):
        """
        Default value
        """

        return NrcScrapedReportFields.full_report_url()

    # /* ----------------------------------------------------------------------- */#
    # /*     Define time_stamp() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def time_stamp(**kwargs):
        """
        Required to insert a NULL value
        """

        return kwargs.get("db_null_value", None)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define ft_id() function
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def ft_id(**kwargs):
        """
        Required to insert a NULL value
        """

        return kwargs.get("db_null_value", None)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define _datetime_caller() function
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def _datetime_caller(**kwargs):
        """
        Several methods require converting a timestamp to a Postgres supported
        timestamp format.  This method eliminates repitition

        :param workbook:
        :type workbook:
        :param row:
        :type row:
        :param map_def:
        :type map_def:

        :rtype:
        :return:
        """

        # TODO: Use 24 hour time

        workbook = kwargs["workbook"]
        row = kwargs["row"]
        map_def = kwargs["map_def"]

        return timestamp2datetime(row[map_def["column"]], workbook.datemode)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define recieved_time() function
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def recieved_datetime(**kwargs):
        """
        See documentation for function called in the return statement
        """

        return NrcScrapedReportFields._datetime_caller(**kwargs)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define incident_datetime() function
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def incident_datetime(**kwargs):
        """
        See documentation for function called in the return statement
        """

        return NrcScrapedReportFields._datetime_caller(**kwargs)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define incident_datetime() function
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def calltype(**kwargs):
        """
        Database is expecting
        """

        map_def = kwargs["map_def"]
        row = kwargs["row"]

        value = row[map_def["column"]]
        if value == "INC":
            value = "INCIDENT"

        return value


# /* ======================================================================= */#
# /*     Define NrcParsedReportFields() class
# /* ======================================================================= */#


class NrcParsedReportFields(object):
    """
    Some fields in the NRC spreadsheet do not map directly to a column in the
    database.  These fields require an additional processing step that is
    highly specific and cannot be re-used.  The field map definition contains
    all of the additional arguments and information necessary to execute one
    of these processing functions.

    A class is used as a namespace to provide better organization and to
    prevent having to name functions something like:
    'get_NrcScrapedReport_material_name_field'
    """

    # /* ----------------------------------------------------------------------- */#
    # /*     Define areaid() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def areaid(**kwargs):
        # TODO: Implement - currently returning NULL
        return kwargs.get("db_null_value", None)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define blockid() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def blockid(**kwargs):
        # TODO: Implement - currently returning NULL
        return kwargs.get("db_null_value", None)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define platform_letter() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def platform_letter(**kwargs):
        # TODO: Implement - currently returning NULL
        return kwargs.get("db_null_value", None)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define _sheen_handler() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def _sheen_handler(**kwargs):
        """
        Several converters require
        """

        # print('inside _sheen_hanler')
        row = kwargs["row"]
        map_def = kwargs["map_def"]
        db_null_value = kwargs["db_null_value"]

        value = row[map_def["column"]]
        unit = row[map_def["processing"]["args"]["unit_field"]]

        # If the value is not a float, change it to nothing so the next test fails
        try:
            value = float(value)
        except ValueError:
            value = ""

        # No sheen size - nothing to do
        if value == "" or unit == "":
            return db_null_value

        # Found a sheen size and unit - perform conversion
        else:
            multipliers = {
                "F": 1,
                "FE": 1,
                "FEET": 1,
                "IN": 0.0833333,
                "INCHES": 0.0833333,
                "KILOMETERS": 3280.84,
                "METER": 3.28084,
                "METERS": 3.28084,
                "MI": 5280,
                "MIL": 5280,
                "MILES": 5280,
                "NI": 5280,  # Assumed mistyping of 'MI'
                "UN": 0.0833333,  # Assumed mistyping of 'IN'
                "YARDS": 3,
            }

            # Database is expecting to handle the normalization by reading from a field containing "1.23 METERS"
            # This function takes care of that but must still supply the expected post-normalization format
            if unit.upper() not in multipliers:
                return db_null_value

            # print('900:', multipliers[unit.upper()], value, multipliers[unit.upper()] * value, round(multipliers[unit.upper()] * value))
            # return unicode(multipliers[unit.upper()] * value) + ' FEET'
            # 9/21/2020
            # Round number of feet to exclude decimals
            # python3 was extending to 12 or so decimal places
            return str(round(multipliers[unit.upper()] * value)) + " FEET"

    # /* ----------------------------------------------------------------------- */#
    # /*     Define sheen_size_length() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def sheen_size_length(**kwargs):
        """
        See called function documentation
        """

        return NrcParsedReportFields._sheen_handler(**kwargs)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define sheen_size_width() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def sheen_size_width(**kwargs):
        """
        See called function documentation
        """

        return NrcParsedReportFields._sheen_handler(**kwargs)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define affected_area() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def affected_area(**kwargs):
        return kwargs.get("db_null_value", None)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define time_stamp() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def time_stamp(**kwargs):
        """
        Required to insert a NULL value
        """

        return kwargs.get("db_null_value", None)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define ft_id() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def ft_id(**kwargs):
        """
        Required to insert a NULL value
        """

        return kwargs.get("db_null_value", None)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define _coord_formatter() protected static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def _coord_formatter(**kwargs):
        """
        The latitude() and longitude() methods require the same general
        logic.
        """
        # print('_coord_formatter:', **kwargs)

        try:
            row = kwargs["row"]
            col_deg = kwargs["map_def"]["processing"]["args"]["col_degrees"]
            col_min = kwargs["map_def"]["processing"]["args"]["col_minutes"]
            col_sec = kwargs["map_def"]["processing"]["args"]["col_seconds"]
            col_quad = kwargs["map_def"]["processing"]["args"]["col_quadrant"]
            output = dms2dd(row[col_deg], row[col_min], row[col_sec], row[col_quad])
        except (ValueError, KeyError):
            output = kwargs["db_null_value"]

        return output

    # /* ----------------------------------------------------------------------- */#
    # /*     Define latitude() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def latitude(**kwargs):
        # print('latitude:', **kwargs)

        """
        Convert coordinates from DMS to DD
        """

        return NrcParsedReportFields._coord_formatter(**kwargs)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define longitude() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def longitude(**kwargs):
        # print('longitude:', **kwargs)

        """
        Convert coordinates from DMS to DD
        """

        return NrcParsedReportFields._coord_formatter(**kwargs)


# /* ======================================================================= */#
# /*     Define NrcScrapedMaterialFields() class
# /* ======================================================================= */#


class NrcScrapedMaterialFields(object):
    """
    Some fields in the NRC spreadsheet do not map directly to a column in the
    database.  These fields require an additional processing step that is
    highly specific and cannot be re-used.  The field map definition contains
    all of the additional arguments and information necessary to execute one
    of these processing functions.

    A class is used as a namespace to provide better organization and to
    prevent having to name functions something like:
    'get_NrcScrapedReport_material_name_field'
    """

    # /* ----------------------------------------------------------------------- */#
    # /*     Define ft_id() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def ft_id(**kwargs):
        return kwargs.get("db_null_value", None)

    # /* ----------------------------------------------------------------------- */#
    # /*     Define st_id() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def st_id(**kwargs):
        return kwargs.get("db_null_value", None)


# /* ======================================================================= */#
# /*     Define BotTaskStatusFields() class
# /* ======================================================================= */#


class BotTaskStatusFields(object):
    """
    Some fields in the NRC spreadsheet do not map directly to a column in the
    database.  These fields require an additional processing step that is
    highly specific and cannot be re-used.  The field map definition contains
    all of the additional arguments and information necessary to execute one
    of these processing functions.

    A class is used as a namespace to provide better organization and to
    prevent having to name functions something like:
    'get_NrcScrapedReport_material_name_field'
    """

    # /* ----------------------------------------------------------------------- */#
    # /*     Define status() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def status(**kwargs):
        # return 'DONE'
        return "ALERTS2"

    # /* ----------------------------------------------------------------------- */#
    # /*     Define bot() static method
    # /* ----------------------------------------------------------------------- */#

    @staticmethod
    def bot(**kwargs):
        return "NrcExtractor"


class NrcAnalyzer:
    name = "NrcAnalyzer"
    allowed_domains = ["skytruth.org"]
    task_conditions = {"NrcGeocoder": "*"}
    units_map = None
    materials_map = None
    job_item_limit = 10000  # maximum total items to process in one job execution
    db = None
    db_cursor = None
    area_code_map = None
    geocode_cache = {}
    geocode_precision = {
        "Explicit": 1,
        "street_address": 0.95,
        "premise": 0.9,
        "subpremise": 0.9,
        "intersection": 0.8,
        "route": 0.75,
        "BlockCentroid": 0.6,
        "ZIP": 0.5,
        "CITY_STATE": 0.2,
        "IGNORE": 0,
    }
    us_territories = ["AS", "FM", "GU", "MH", "MP", "PW", "PR", "UM", "VI"]
    # street_address indicates a precise street address.
    # route indicates a named route (such as "US 101").
    # intersection indicates a major intersection, usually of two major roads.
    # political indicates a political entity. Usually, this type indicates a polygon of some civil administration.
    # country indicates the national political entity, and is typically the highest order type returned by the Geocoder.
    # administrative_area_level_1 indicates a first-order civil entity below the country level. Within the United States, these administrative levels are states. Not all nations exhibit these administrative levels. In most cases, administrative_area_level_1 short names will closely match ISO 3166-2 subdivisions and other widely circulated lists; however this is not guaranteed as our geocoding results are based on a variety of signals and location data.
    # administrative_area_level_2 indicates a second-order civil entity below the country level. Within the United States, these administrative levels are counties. Not all nations exhibit these administrative levels.
    # administrative_area_level_3 indicates a third-order civil entity below the country level. This type indicates a minor civil division. Not all nations exhibit these administrative levels.
    # administrative_area_level_4 indicates a fourth-order civil entity below the country level. This type indicates a minor civil division. Not all nations exhibit these administrative levels.
    # administrative_area_level_5 indicates a fifth-order civil entity below the country level. This type indicates a minor civil division. Not all nations exhibit these administrative levels.
    # colloquial_area indicates a commonly-used alternative name for the entity.
    # locality indicates an incorporated city or town political entity.
    # ward indicates a specific type of Japanese locality, to facilitate distinction between multiple locality components within a Japanese address.
    # sublocality indicates a first-order civil entity below a locality. For some locations may receive one of the additional types: sublocality_level_1 to sublocality_level_5. Each sublocality level is a civil entity. Larger numbers indicate a smaller geographic area.
    # neighborhood indicates a named neighborhood
    # premise indicates a named location, usually a building or collection of buildings with a common name
    # subpremise indicates a first-order entity below a named location, usually a singular building within a collection of buildings with a common name
    # postal_code indicates a postal code as used to address postal mail within the country.
    # natural_feature indicates a prominent natural feature.
    # airport indicates an airport.
    # park indicates a named park.
    # point_of_interest indicates a named point of interest. Typically, these "POI"s are prominent local entities that don't easily fit in another category, such as "Empire State Building" or "Statue of Liberty."

    def process_item(self, task_id, db_cursor):
        try:
            print("")
            print("NrcGeocoder process_item", str(task_id))
            self.db = NrcDatabase()
            self.db.connect()
            self.db_cursor = db_cursor

            parsed_report = self.db.loadParsedReport(task_id)
            if parsed_report is None:
                return
            scraped_report = self.db.loadScrapedReport(task_id)
            if scraped_report is None:
                return
            if scraped_report["calltype"] == "DRILL":
                # self.item_dropped(task_id)
                return

            areaid = parsed_report["areaid"]
            blockid = parsed_report["blockid"]
            lat = parsed_report["latitude"]
            lng = parsed_report["longitude"]
            zip = parsed_report["zip"]
            city = scraped_report["nearestcity"]
            state = scraped_report["state"]
            location = scraped_report["location"]
            incidentlocation = scraped_report["incidentlocation"]
            locationstreet1 = scraped_report["locationstreet1"]
            locationstreet2 = scraped_report["locationstreet2"]
            block_geocode = None
            address = None

            print(
                "locationstreet1:",
                locationstreet1,
                " locationstreet2:",
                locationstreet2,
            )
            # print('areaid:', areaid, ' blockid:', blockid)
            if areaid and blockid:
                block_geocode = self.geocode_area_id(task_id, areaid, blockid)
            # print('block_geocode:', block_geocode)
            # print('zip:', zip, ' city:', city, ' state:', state)
            # print('lat:', lat, ' lng:', lng)
            geo_results = None
            precision = "Explicit"
            geo_cached = False

            incidenttype = scraped_report["incidenttype"]
            if lat or lng:
                lat, lng = correct_hemisphere(lat, lng, state, incidenttype)

            if lat and lng:
                # we have an explicit lat/lng.  If we also have a block_geocode, then this is a chance to check
                # the area id mapping
                #
                # Dan: Comment out for now. The idea is to not keep calling the geocode API, so this defeats that.
                # if block_geocode:
                #     lat_diff = abs(block_geocode['lat'] - lat)
                #     lng_diff = abs(block_geocode['lng'] - lng)
                #     # if lat_diff + lng_diff > 2:
                #     #     msg = 'Lat/Lng mismatch for report %s. Centroid: %s Report: %s' % (task_id, block_geocode, parsed_report)
                #     #     self.send_alert (msg)
                #     #     yield self.make_tag(task_id, 'GeocodeMismatch', msg)
                self.createGeocode(task_id, "Explicit", lat, lng)
                # self.item_completed(task_id)
                # else:
                #     print('lat/lng not there')
            elif block_geocode:
                print("1199")
                # yield \
                self.createGeocode(
                    task_id, "BlockCentroid", block_geocode["lat"], block_geocode["lng"]
                )
                # self.item_completed(task_id)

            elif location and city and state:
                print("1205")
                address = "%s %s, %s %s" % (location, city, state, zip or "")
                # print('address:', address)
                geo_results = self.geocodeAddress(address, "street_address", task_id, state)
                precision = "street_address"

            # Dan: Aded 7/30/19
            # If no match on location, try incidentlocation before going on to zip
            elif incidentlocation and city and state:
                address = "%s %s, %s %s" % (incidentlocation, city, state, zip or "")
                print("1215 address:", address)
                geo_results = self.geocodeAddress(address, "street_address", task_id, state)
                precision = "street_address"

            elif zip or (city and state):
                print("1220 zip or city and state")
                # mark this item as "no data" in case none of the google geocode requests return something we can use
                # status_processing = 'PROCESSING'
                # status_done = 'DONE'
                # status_dropped = 'SKIPPED'
                # status_new = 'NEW'
                # status_no_data = 'NODATA'
                # status_updated = 'UPDATED'

                # self.set_item_status(task_id, self.status_no_data)

                if zip:
                    if len(zip) == 9:
                        zip = "%s-%s" % (zip[:5], zip[5:])
                    # print('zip:', zip)
                    cache_entry = self.db.getGeocodeCache(zip)
                    if cache_entry:
                        print(task_id, "zip cached:", zip)
                        self.createGeocode(task_id, "ZIP", cache_entry["lat"], cache_entry["lng"])
                        geo_cached = True
                    else:
                        geo_results = self.geocodeAddress(zip, "ZIP", task_id, state)
                        precision = "ZIP"
                    # for item in self.geocodeAddress (zip, 'ZIP', task_id, state):
                    #     print('item:', item)

                elif city and state:
                    address = "%s, %s" % (city, state)
                    print("1248 ", str(task_id), " checking address:", address)
                    cache_entry = self.db.getGeocodeCache(address)
                    if cache_entry:
                        print(task_id, " city-state cached:", address)
                        self.createGeocode(
                            task_id,
                            "CITY_STATE",
                            cache_entry["lat"],
                            cache_entry["lng"],
                        )
                        geo_cached = True
                    else:
                        geo_results = self.geocodeAddress(address, "CITY_STATE", task_id, state)
                        precision = "CITY_STATE"
                    # for item in self.geocodeAddress (address, 'CITY_STATE', task_id, state):
                    #     print('item:', item)

            else:
                # Not enough info to find a geo code
                print("Not enough info to find a geo code, reportnum=", task_id)
                # utils.send_alert("Not enough info to find a geo code", task_id)
                return

            if geo_results:
                # print('1300 geo_results:', geo_results)
                if geo_results["status"] == "OK":
                    try:
                        # print('1303')
                        if (
                            not precision == "ZIP" and not precision == "CITY_STATE"
                        ):  # == 'street_address':
                            # print('1303b ', str(task_id), geo_results)
                            try:
                                it = geo_results["results"][0]["types"][0]
                                # print('1308 it=', it)
                                if it != "street_address":
                                    # print(task_id, it)
                                    # print(task_id, geo_results)
                                    precision = it  #'premise'
                            except:
                                pass
                        lat = geo_results["results"][0]["geometry"]["location"]["lat"]
                        lng = geo_results["results"][0]["geometry"]["location"]["lng"]
                        # print('1317 here:', task_id, precision, lat, lng, address)
                        self.createGeocode(task_id, precision, lat, lng)
                        if (precision == "CITY_STATE" or precision == "ZIP") and address:
                            if geo_cached == False:
                                self.db.putGeocodeCache(address, lat, lng)
                                # print(task_id, 'geocache updated', lat, lng)
                    except IndexError as error:
                        print("IndexError on geocoding result", str(error), task_id)
                        # error_condition("IndexError", str(error), task_id, sys.exc_info())
                else:
                    if geo_results["status"] == "ZERO_RESULTS":
                        print("No geocoding results, reportnum=", task_id)
                        # utils.send_alert("No geocoding results", task_id)
                    else:
                        print("geocoding error")
                        # error_condition(
                        #     "geocoding error",
                        #     "geocoding returned status:" + geo_results["status"],
                        #     task_id,
                        # )
                        # print(task_id, ' geocoding returned status:', geo_results['status'])

            # print('NrcAnalyzer process_item', task_id)
            # self.db = NrcDatabase()
            # self.db.connect()
            parsed_report = self.db.loadParsedReport(task_id)
            # print('NrcAnalyzer process_item 3', parsed_report)
            if parsed_report is None:
                # utils.send_alert("No parsed_report", task_id)
                return

            scraped_report = self.db.loadScrapedReport(task_id)
            if scraped_report is None:
                # utils.send_alert("No scraped_report", task_id)
                return
            # print('NrcAnalyzer process_item scraped_report:', scraped_report)

            geocode = self.db.loadBestGeocode(task_id)

            sheen_width = self.normalize_value(parsed_report["sheen_size_width"], "UNKNOWN")
            sheen_length = self.normalize_value(parsed_report["sheen_size_length"], "UNKNOWN")

            # print('sheen_size_width:', parsed_report['sheen_size_width'], ' sheen_length:', parsed_report['sheen_size_length'],
            #      ' sheen_width:', sheen_width, ' sheen_length:', sheen_length)
            if (
                sheen_width
                and sheen_width[1] == "UNKNOWN"
                and sheen_length
                and sheen_length[1] != "UNKNOWN"
            ):
                sheen_width = self.normalize_value(
                    parsed_report["sheen_size_width"], sheen_length[1]
                )

            if (
                sheen_length
                and sheen_length[1] == "UNKNOWN"
                and sheen_width
                and sheen_width[1] != "UNKNOWN"
            ):
                sheen_length = self.normalize_value(
                    parsed_report["sheen_size_length"], sheen_width[1]
                )

            scraped_materials = self.db.loadScrapedMaterial(task_id)

            reported_volume = 0.0
            reported_unit = "GALLON"
            for m in scraped_materials:
                # print('scraped_materials m:', m)
                if m["amount"]:
                    v = self.normalize_value((m["amount"], m["unit"]))
                    if v and v[1] in ("GALLON", "CUBIC FT"):
                        reported_volume += v[0]
                        reported_unit = v[1]

            min_volume = 0.0
            db_sheen_width = None
            db_sheen_length = None
            if sheen_width and sheen_length:
                # assume 1 micron thick,
                # or 1000L per km2
                # or 264.172052 gal per 10763910.4 ft2 = 0.000024542386752 gal per ft2
                min_volume = sheen_width[0] * sheen_length[0] * 0.000024542386752
                # l.add_value ('min_spill_volume', min_volume)
                db_sheen_width = sheen_width[0]
                db_sheen_length = sheen_length[0]
            calltype = scraped_report["calltype"]
            # Check for "ATON BATTERY RELEASE" in the description - ignore these, not exactly sure what they are...
            if re.match(".*ATON BATTERY", scraped_report["description"] or ""):
                calltype = "ATON"
            if calltype == "INCIDENT" and re.match(
                "DRILL[^\w]", scraped_report["description"] or ""
            ):
                calltype = "DRILL"
            severity = self.get_release_severity(scraped_report, reported_volume, min_volume)
            release_type = self.get_release_type(scraped_report)
            # print('reportnum:', task_id, ' release_type:', release_type)
            region = self.get_region(scraped_report, parsed_report, geocode)
            # print('new NrcAnalysis:', task_id, reported_volume, reported_unit, calltype)
            sql = """INSERT INTO "NrcAnalysis" (reportnum, sheen_length, sheen_width, reported_spill_volume,
                min_spill_volume, calltype, severity, region, release_type, reported_spill_unit)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"""
            try:
                # execute the INSERT statement
                self.db_cursor.execute(
                    sql,
                    (
                        task_id,
                        db_sheen_length,
                        db_sheen_width,
                        reported_volume,
                        min_volume,
                        calltype,
                        severity,
                        region,
                        release_type,
                        reported_unit,
                    ),
                )
            except (Exception, psycopg2.DatabaseError) as error:
                print(error)
                # utils.send_alert("Error on NrcAnalysis insert", str(error), task_id, sys.exc_info())
                # pass
            # l.load_item()

            # self.item_completed(task_id)
        # except ValueError as error:
        #     error_condition("ValueError found", str(error), task_id, sys.exc_info())
        # except psycopg2.DatabaseError as error:
        #     error_condition("psycopg2.DatabaseError", str(error), task_id, sys.exc_info())
        # except psycopg2.OperationalError as error:
        #     error_condition("psycopg2.OperationalError", str(error), task_id, sys.exc_info())
        # except psycopg2.Error as error:
        #     error_condition(
        #         "psycopg2.Error:",
        #     )
        # except RuntimeError as error:
        #     error_condition("RuntimeError found", str(error), task_id, sys.exc_info())
        # except TypeError as error:
        #     error_condition("TypeError found", str(error), task_id, sys.exc_info())
        # except NameError as error:
        #     error_condition("NameError found", str(error), task_id, sys.exc_info())
        # except:
        #     error_condition("An error occured.", "An error occured", task_id, sys.exc_info())
        except:
            pass

    def createGeocode(self, task_id, source, lat, lng):
        # print(str(task_id), ' new NrcGeocode source:', source)
        precision = self.geocode_precision.get(source, 0)
        if source != "Explicit":
            source = "Approximated from " + source
        if not source:
            return None

        sql = """INSERT INTO "NrcGeocode" (reportnum, source, lat, lng, precision)
            VALUES (%s, %s, %s, %s, %s);"""
        try:
            # execute the INSERT statement
            self.db_cursor.execute(sql, (task_id, source, lat, lng, precision))
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)

    def geocodeAddress(self, address, source, task_id, state):
        print("geocodeAddress", address, source, task_id, state)
        geocode_url = (
            "https://maps.googleapis.com/maps/api/geocode/json?%s"
            % urllib.parse.urlencode(
                {
                    "address": address,
                    "sensor": "false",
                    "key": "",  # Secret removed, lets move this to config file later
                }
            )
        )

        results = requests.get(geocode_url)
        # Results will be in JSON format - convert to dict using requests functionality
        results = results.json()
        # print('results:', results)
        return results

    def error_callback(self, err):
        print("error_callback:", err)
        log.ERROR("HTTP request failed %s" % (err.getErrorMessage()))

    def parse_google_geocode(self, response, task_id, source):
        # print('parse_google_geocode:', response, task_id, source)
        log.INFO("Parsing response from google geocoder\n%s" % (response))
        # response = json.loads(response)
        #
        xxs = Selector(response=response)
        reportnum = response.request.meta["reportnum"]
        source = response.request.meta["source"]
        state = response.request.meta["state"]
        geocode_cache_key = response.request.meta.get("cache_key", None)

        status = xxs.select("//status/text()").extract()
        if status:
            status = status[0]
        if status == "OK":
            # print('1653')
            result_type = xxs.select("//result/type[1]/text()").extract()
            if result_type:
                result_type = result_type[0]

            location = xxs.select("//geometry/location")
            lat = location.select("lat/text()").extract()[0]
            lng = location.select("lng/text()").extract()[0]

            geocode_state = xxs.select(
                '//address_component[type="administrative_area_level_1"]/short_name/text()'
            )
            if geocode_state:
                geocode_state = geocode_state.extract()[0]
            else:
                # print('1665')
                geocode_state = xxs.select('//address_component[type="country"]/short_name/text()')
                if geocode_state:
                    geocode_state = geocode_state.extract()[0]
                    if not geocode_state in self.us_territories:
                        geocode_state = None

            if source == "ADDRESS":
                if result_type:
                    source = result_type
                else:
                    source = "IGNORE"

            if source == "ZIP" and result_type != "postal_code":
                self.log("Bad zip code %s" % (geocode_cache_key), log.WARNING)

                source = "IGNORE"

            if geocode_state:
                if geocode_state.lower() != state.lower():
                    self.log(
                        "Geocode state mismatch: expected %s, actual %s" % (state, geocode_state),
                        log.WARNING,
                    )
                    source = "IGNORE"
            else:
                self.log("Geocode returned with no state code", log.WARNING)
                source = "IGNORE"

            try:
                item = self.createGeocode(reportnum, source, lat, lng)
            except Exception as e:
                self.log(
                    "GeocodeError:%s\n\torig source %s, source %s, loc %s, %s"
                    % (e, response.request.meta["source"], source, lat, lng),
                    log.ERROR,
                )
                raise
            # if item:
            #     if geocode_cache_key:
            #         self.db.putGeocodeCache(geocode_cache_key, lat, lng)
            #     yield item
            #     self.item_completed(reportnum)
            # else:
            #     self.log('Dropping geocoder response with result type: %s' % (result_type), log.INFO)

        elif status == "OVER_QUERY_LIMIT":
            self.log(
                "Geocode failed for task id %s \n%s\n%s"
                % (reportnum, response.request, response.body),
                log.WARNING,
            )

            # Do not mark the task as done, we will pick it up again on the next run
            self.item_processing(reportnum)

            pass
        else:
            msg = "Google Geocode operation failed for task id %s : %s \n%s" % (
                reportnum,
                response.request,
                response.body,
            )
            # print('1717:', msg)
            try:
                pass
                # self.send_alert(msg, reportnum)
            except Exception:
                self.log(msg, log.ERROR)
                raise

    def geocode_area_id(self, task_id, areaid, blockid):
        # print('geocode_area_id:', task_id, areaid, blockid)
        # load area id patterns if necessary
        if not self.area_code_map:
            self.area_code_map = self.db.getAreaCodeMap()
            for m in self.area_code_map:
                m["pattern"] = re.compile(m["pattern"], re.IGNORECASE)

        area_codes = []
        # see if there is an area id match
        for m in self.area_code_map:
            p = m["pattern"]
            if p.match(areaid):
                area_codes.append(m["area_code"])

        if len(area_codes) > 1:
            # self.send_alert(
            #     "WARNING: Multiple pattern matches in %s for AreaID: %s -- %s"
            #     % (task_id, areaid, area_codes)
            # )
            return None

        # clean up block ID to get rid of extraneous characters
        match = re.search("(A?[\d]+)", blockid)
        if not match:
            return None
        blockid = match.group()

        # got a numeric blockid, now make sure we have an area code
        if len(area_codes) == 0:
            # send warning and bail out
            # self.send_alert(
            #     "WARNING: No pattern matches in %s for AreaID: %s"
            #     % (
            #         task_id,
            #         areaid,
            #     )
            # )
            return None

        # we have a single area code and a block ID, so look them up in the table to get lat/lng
        # see if there is a match in the BlockCentroid table
        block = self.db.getBlockCentroid(area_codes[0], blockid)
        if not block:
            # try prepending 'A' - sometimes this is missing in the report
            block = self.db.getBlockCentroid(area_codes[0], "A%s" % blockid)
        if not block:
            # self.send_alert(
            #     "WARNING: No matching lease block block found. report %s for areaid=%s blockid=%s"
            #     % (task_id, area_codes[0], blockid)
            # )
            return None
        # print('geocode_area_id block lat lng:', task_id, block)
        return {"lat": block["lat"], "lng": block["lng"]}

    def normalize_value(self, value, default_unit="UNKNOWN"):
        # print('normalize_value:', value, type(value))

        # if type (value) in (str, unicode):
        if type(value) in (bytes, str):
            value = self.parse_value(value, default_unit)
        # print('after normalize_value:', value)

        if not value:
            return None

        if type(value) is tuple:
            amount = value[0]
            unit = value[1]
        else:
            raise TypeError(value)

        # normalize unit
        normalized_unit = self.normalize_unit(unit)
        if not normalized_unit:
            return None

        return (
            amount * normalized_unit["conversion_factor"],
            normalized_unit["standardized_unit"],
        )

    def parse_value(self, value, default_unit="UNKNOWN"):
        # print('parse_value:', value)
        m = re.match("([\d\s/.]+)([^\d]+)", value)
        if m:
            v = m.group(1).strip()
            u = m.group(2).strip()
        else:
            # check to see if this is a value with no unit
            m = re.match("([\d\s/.]+)", value)
            if m:
                v = m.group(1).strip()
                u = default_unit
            else:
                # Check to see if value matches an UNIT pattern.  Should encapsuate that test...
                # unit with no value - do not send warning, just ignore
                normalized_unit = self.normalize_unit(unit=value, send_warning=0)
                if not normalized_unit:
                    # utils.send_alert("WARNING: failed to parse value: '%s' " % (value,))
                return None

        # Check to see if the value part is in the form "1 1/2" or "1/8"
        m = re.match("([\d]*)[\s]*([\d])/([\d])", v)
        try:
            if m:
                base = float(m.group(1) or 0)
                num = float(m.group(2) or 0)
                denom = float(m.group(3) or 0)
                v = base
                if num and denom:
                    v += num / denom
            else:
                v = float(v)
        except ValueError:
            # utils.send_alert("WARNING: failed to parse amount: '%s' " % (v,))
            return None

        return (v, u)

    def normalize_unit(self, unit, send_warning=1):
        if not self.units_map:
            self.units_map = self.db.getNrcUnits()
            for m in self.units_map:
                m["pattern"] = re.compile(m["pattern"], re.IGNORECASE)

        if not unit:
            return None

        matched = []
        for u in self.units_map:
            p = u["pattern"]
            if unit and p.match(unit):
                matched.append(u)

        if len(matched) == 0:
            if send_warning:
                pass
                # utils.send_alert("WARNING: no pattern matches for unit: %s" % (unit,))
            return None

        if len(matched) > 1:
            if send_warning:
                pass
                # utils.send_alert(
                #     "WARNING: Multiple pattern matches for unit: %s -- %s" % (unit, matched)
                # )
            return None

        return matched[0]

    def get_release_severity(self, scraped_report, reported_volume, min_volume):
        if (scraped_report["incidenttype"] == "RAILROAD NON-RELEASE") or (
            scraped_report["medium_affected"] in ("NON-RELEASE (N/A)", "RAIL REPORT (N/A)")
        ):
            return "non-release"

        if (
            reported_volume < 42
            and min_volume < 42
            and (
                re.match("HYDRAULIC", scraped_report["material_name"] or "")
                or scraped_report["material_name"]
                in ("REFRIGERANT GASES", "OIL, FUEL: NO. 1-D", "OIL, FUEL: NO. 2-D")
            )
        ):
            return "minor"

        if (
            scraped_report["incidenttype"] == "UNKNOWN SHEEN"
            and reported_volume < 1
            and min_volume < 10
        ):
            return "minor"

        if reported_volume > 100 or min_volume > 100:
            return "major"

        return "release"

    def get_release_type(self, scraped_report):
        if not self.materials_map:
            self.materials_map = self.db.getNrcMaterials()
            for m in self.materials_map:
                m["pattern"] = re.compile(m["pattern"], re.IGNORECASE)

        matched = []
        material_name = scraped_report["material_name"]
        # print('material_name:', material_name)
        for item in self.materials_map:
            p = item["pattern"]
            if material_name and p.match(material_name):
                matched.append(item)
                # print('matched:', item);

        if len(matched) == 0:
            return "other"

        if len(matched) > 1:
            pass
            # utils.send_alert(
            #     "WARNING: Multiple pattern matches for material: %s -- %s"
            #     % (material_name, matched)
            # )
            return None

        return matched[0]["group_label"]

    def get_region(self, scraped_report, parsed_report, geocode):
        region_rects = [
            {"name": "gulf", "lat": (23, 30.41), "lng": (-97.36, -82.66)},
            {"name": "gulf", "lat": (23, 27.4), "lng": (-82.66, -81.7)},
            {"name": "gulf", "lat": (23, 25.92), "lng": (-81.7, -80.72)},
        ]

        if parsed_report["affected_area"] == "GULF OF MEXICO":
            return "gulf"

        if geocode:
            for r in region_rects:
                if (
                    geocode["lat"] >= min(r["lat"])
                    and geocode["lat"] <= max(r["lat"])
                    and geocode["lng"] >= min(r["lng"])
                    and geocode["lng"] <= max(r["lng"])
                ):
                    return r["name"]

        return "unknown"

    def make_tag(self, task_id, tag, comment=None):
        # print('make_tag:', task_id, tag)
        t = ItemLoader(NrcTag())
        t.add_value("reportnum", task_id)
        t.add_value("tag", tag)
        t.add_value("comment", comment)
        return t.load_item()

    # used for FeedEntry Tags
    def create_tag(self, feed_entry_id, tag, comment=""):
        l = ItemLoader(FeedEntryTag())
        l.add_value("feed_entry_id", feed_entry_id)
        l.add_value("tag", tag)
        l.add_value("comment", comment)
        return l.load_item()

    def make_bot_task_error(self, task_id, code, message=""):
        t = ItemLoader(BotTaskError())
        t.message_in = lambda slist: [s[:1023] for s in slist]
        t.add_value("task_id", task_id)
        t.add_value("bot", self.name)
        t.add_value("code", code)
        t.add_value("message", message)
        return t.load_item()


class NrcSpreadsheetScraper:
    # /* ======================================================================= */#
    # /*     Define main() function
    # /* ======================================================================= */#

    def main(self, args):
        """
        Main routine to parse, transform, and insert Current.xlsx into the tables
        used by the Alerts system.

        http://nrc.uscg.mil/FOIAFiles/Current.xlsx

        Before doing any transformations, a set of SEQNOS/reportnum's are gathered
        from one of the workbook's sheets.  The default column in 'CALLS' but can be
        specified by the user.  This set of ID's are treated as primary keys and drive
        processing.

        Rather than process the input document sheet by sheet and row by row, a set
        of field map definitions are declared to describe which fields in which
        sheets should be inserted into which table in which schema.  Each field map
        is applied against each ID which means that if ID number 1234 is being
        processed, the bare minimum field map example below states that whatever
        value is in sheet 'CALLS' and column 'RESPONSIBLE_COMPANY' can be sent to
        public."NrcScrapedReport".suspected_responsible_company  The more complicated
        field map states that a specific function must do more of the heavy lifting.

        Field maps are grouped by table and center around the target field.  There
        should be one map for every field in a table.  The structure for field maps
        is roughly as follows:

            All field maps = {
                'table_name': [
                    {
                        'db_table': Name of target table,
                        'db_field': Name of target field,
                        'db_field_width': Maximum width for this field - used in string slicing
                        'db_schema': Name of target schema,
                        'sheet_name': Name of source sheet in input file,
                        'column': Name of source column in sheet_name,
                        'processing': {  # Optional - should be set to None if not used
                            'function': Callable object responsible for additional sub-processing
                            'args': {  # Essentially kwargs
                                'Arg1': parameter,
                                'Arg2': ...
                            }
                        }
                    },
                    {
                        'db_table': Name of target table,
                        'db_field': Name of target field,
                        'db_schema': Name of target schema,
                        'sheet_name': Name of source sheet in input file,
                        'column': Name of source column in sheet_name,
                        'processing': {  # Optional - should be set to None if not used
                            'function': Callable object responsible for additional sub-processing
                            'args': {  # Essentially kwargs
                                'Arg1': parameter,
                                'Arg2': ...
                            }
                        }
                    },
                ],
                'TABLE_NAME': [
                    {
                        'db_table': Name of target table,
                        'db_field': Name of target field,
                        'db_schema': Name of target schema,
                        'sheet_name': Name of source sheet in input file,
                        'column': Name of source column in sheet_name,
                        'processing': {  # Optional - should be set to None if not used
                            'function': Callable object responsible for additional sub-processing
                            'args': {  # Essentially kwargs
                                'Arg1': parameter,
                                'Arg2': ...
                            }
                        }
                    }
                ],
            }


        The order of operations for a given ID is as follows:

            1. Get an ID
            2. Get a set of field maps for one target table
            3. Process all field maps and assemble an insert query
            4. Execute the insert statement
            5. Repeat steps 2-4 until all tables have been processed


        Example bare minimum field map:

            The field map below shows that the value in the 'RESPONSIBLE_COMPANY'
            column in the 'CALLS' sheet can be sent directly to
            public."NrcScrapedReport".suspected_responsible_company without any
            additional processing.  Note the quotes around the table name.

            {
                'db_table': '"NrcScrapedReport"',
                'db_field': 'suspected_responsible_company',
                'db_field_width': 32,
                'db_schema': 'public',
                'sheet_name': 'CALLS',
                'column': 'RESPONSIBLE_COMPANY',
                'processing': None
            },


        Example field map with all options:

            This field map shows that no specific column contains the value required
            for public."NrcParsedReport".longitude  Instead, some information must be
            passed to the NrcParsedReportFields.longitude() function where the actual
            processing happens.  Field maps using additional processing always receive
            the following kwargs:

                all_field_maps      All field maps with keys set to schema.table
                db_cursor           The cursor to be used for all queries
                db_null_value       Value to use for NULL
                db_seqnos_field     The reportnum field in the database
                db_write_mode       The first part of the SQL statement for writes
                                    (e.g. INSERT INTO)
                execute_queries     Specifies whether or not queries should actually
                                    be executed
                map_def             Current map definition being processed (example
                                    below)
                print_queries       Specifies whether or not queries should be printed
                                    as they are executed
                raw_sheet_cache     Structured similar to the normal sheet cache,
                                    but with a list of rows instead of a dictionary
                                    containing reportnums as keys and rows as values
                row                 The current row being processed - structured
                                    just like a csv.DictReader row
                sheet               The entire sheet from which the row was extracted
                                    as described in the field map
                sheet_seqnos_field  The field in all sheets containing the reportnum
                uid                 The current SEQNOS/reportnum being processed
                workbook            XLRD workbook object

            The callable object specified in map_def['processing']['function'] is
            responsible for ALL queries.  The processing functions are intended
            to return a final value to be inserted into the target field described
            in the field map but this behavior is not required.  If the function
            itself handles all queries internally it can return '__NO_QUERY__' in
            order to be excluded from the insert statement for that table.

            {
                'db_table': '"NrcParsedReport"',
                'db_field': 'longitude',
                'db_schema': 'public',
                'sheet_name': 'INCIDENT_COMMONS',
                'column': None,
                'processing': {
                    'function': NrcParsedReportFields.longitude,
                    'args': {
                        'col_degrees': 'LONG_DEG',
                        'col_minutes': 'LONG_MIN',
                        'col_seconds': 'LONG_SEC',
                        'col_quadrant': 'LONG_QUAD'
                    }
                }
            },


        :param args: arguments from the commandline (sys.argv[1:] in order to drop the script name)
        :type args: list

        :return: 0 on success and 1 on error
        :rtype: int
        """

        # /* ----------------------------------------------------------------------- */#
        # /*     Define Field Maps
        # /* ----------------------------------------------------------------------- */#

        field_map_order = [
            'public."NrcScrapedReport"',
            'public."NrcParsedReport"',
            'public."BotTaskStatus"',
        ]
        field_map = {
            'public."NrcScrapedReport"': [
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "reportnum",
                    "db_schema": "public",
                    "sheet_name": "CALLS",
                    "column": "SEQNOS",
                    "processing": None,
                },
                # Dan C. 1/19/2019 -- Commented out the DATE_TIME_RECEIVED field
                # because blank values were being returned in the spreadsheet. Doesn't
                # look like it's used anywhere.
                # {
                #     'db_table': '"NrcScrapedReport"',
                #     'db_field': 'recieved_datetime',
                #     'db_schema': 'public',
                #     'sheet_name': 'CALLS',
                #     'column': 'DATE_TIME_RECEIVED',
                #     'processing': {
                #         'function': NrcScrapedReportFields.recieved_datetime
                #     }
                # },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "calltype",
                    "db_schema": "public",
                    "sheet_name": "CALLS",
                    "column": "CALLTYPE",
                    "processing": {"function": NrcScrapedReportFields.calltype},
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "suspected_responsible_company",
                    "db_schema": "public",
                    "sheet_name": "CALLS",
                    "column": "RESPONSIBLE_COMPANY",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "description",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "DESCRIPTION_OF_INCIDENT",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "incident_datetime",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "INCIDENT_DATE_TIME",
                    "processing": None,
                    # 03/05/2019 Dan C.
                    # Removed NrcScrapedReportFields.incident_datetime processing.for
                    # It was erroring out with:
                    # ValueError invalid literal for int() with base 10: '02/17/2019 16:20'
                    # NRC looks like changed the FORMAT from 'Date' to 'Number'
                    # Just having 'processing': None works
                    #
                    # Looks like a recurring issue.
                    # When you get the msg "...invalid literal for int() with base 10: ..."
                    # change to:
                    # 'processing': None
                    #
                    # The following is what you need to use when you get this error:
                    # nrcSpreadsheetScraper psycopg2.DatabaseError reportnum=(<class 'psycopg2.errors.DatatypeMismatch'>,
                    # DatatypeMismatch('column "incident_datetime" is of type timestamp without time zone but expression is of type numeric\nLINE 1: ...
                    # 'processing': {
                    #     'function': NrcScrapedReportFields.incident_datetime
                    # }
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "incidenttype",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "TYPE_OF_INCIDENT",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "cause",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "INCIDENT_CAUSE",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "incidentlocation",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "INCIDENT_LOCATION",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "location",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "LOCATION_ADDRESS",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "locationstreet1",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "LOCATION_STREET1",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "locationstreet2",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "LOCATION_STREET2",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "state",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "LOCATION_STATE",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "nearestcity",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "LOCATION_NEAREST_CITY",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "county",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "LOCATION_COUNTY",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "medium_affected",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_DETAILS",
                    "column": "MEDIUM_DESC",
                    "processing": None,
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "material_name",
                    "db_schema": "public",
                    "sheet_name": "MATERIAL_INVOLVED",
                    "column": "NAME_OF_MATERIAL",
                    "processing": {
                        "function": NrcScrapedReportFields.material_name,
                        "args": {
                            "extras_table": '"NrcScrapedMaterial"',
                            "extras_schema": "public",
                            "extras_field_maps": {
                                'public."NrcScrapedReport"': [
                                    {
                                        "db_table": "NrcScrapedMaterial",
                                        "db_field": "reportnum",
                                        "db_schema": "public",
                                        "sheet_name": "MATERIAL_INVOLVED",
                                        "column": "SEQNOS",
                                        "processing": None,
                                    },
                                    {
                                        "db_table": '"NrcScrapedMaterial"',
                                        "db_field": "name",
                                        "db_field_width": 128,
                                        "db_schema": "public",
                                        "sheet_name": "MATERIAL_INVOLVED",
                                        "column": "NAME_OF_MATERIAL",
                                        "processing": None,
                                    },
                                    {
                                        "db_table": "NrcScrapedMaterial",
                                        "db_field": "reached_water",
                                        "db_schema": "public",
                                        "sheet_name": "MATERIAL_INVOLVED",
                                        "column": "IF_REACHED_WATER",
                                        "processing": None,
                                    },
                                    {
                                        "db_table": '"NrcScrapedMaterial"',
                                        "db_field": "amt_in_water",
                                        "db_schema": "public",
                                        "sheet_name": "MATERIAL_INVOLVED",
                                        "column": "AMOUNT_IN_WATER",
                                        "processing": None,
                                    },
                                    {
                                        "db_table": '"NrcScrapedMaterial"',
                                        "db_field": "amt_in_water_unit",
                                        "db_schema": "public",
                                        "sheet_name": "MATERIAL_INVOLVED",
                                        "column": "UNIT_OF_MEASURE_REACH_WATER",
                                        "processing": None,
                                    },
                                    {
                                        "db_table": '"NrcScrapedMaterial"',
                                        "db_field": "chris_code",
                                        "db_schema": "public",
                                        "sheet_name": "MATERIAL_INVOLVED",
                                        "column": "CHRIS_CODE",
                                        "processing": None,
                                    },
                                    {  # TODO: Not populated
                                        "db_table": '"NrcScrapedMaterial"',
                                        "db_field": "amount",
                                        "db_schema": "public",
                                        "sheet_name": "MATERIAL_INVOLVED",
                                        "column": "AMOUNT_OF_MATERIAL",
                                        "processing": None,
                                    },
                                    {  # TODO: Not populated
                                        "db_table": '"NrcScrapedMaterial"',
                                        "db_field": "unit",
                                        "db_schema": "public",
                                        "sheet_name": "MATERIAL_INVOLVED",
                                        "column": "UNIT_OF_MEASURE",
                                        "processing": None,
                                    },
                                    {
                                        "db_table": '"NrcScrapedMaterial"',
                                        "db_field": "ft_id",
                                        "db_schema": "public",
                                        "sheet_name": "CALLS",
                                        "column": None,
                                        "processing": {"function": NrcScrapedMaterialFields.ft_id},
                                    },
                                    {
                                        "db_table": '"NrcScrapedMaterial"',
                                        "db_field": "st_id",
                                        "db_schema": "public",
                                        "sheet_name": "CALLS",
                                        "column": None,
                                        "processing": {"function": NrcScrapedMaterialFields.st_id},
                                    },
                                ]
                            },
                        },
                    },
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "full_report_url",
                    "db_schema": "public",
                    "sheet_name": "CALLS",
                    "column": None,
                    "processing": {"function": NrcScrapedReportFields.full_report_url},
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "materials_url",
                    "db_schema": "public",
                    "sheet_name": "CALLS",
                    "column": None,
                    "processing": {"function": NrcScrapedReportFields.materials_url},
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "time_stamp",
                    "db_schema": "public",
                    "sheet_name": "CALLS",
                    "column": None,
                    "processing": {"function": NrcScrapedReportFields.time_stamp},
                },
                {
                    "db_table": '"NrcScrapedReport"',
                    "db_field": "ft_id",
                    "db_schema": "public",
                    "sheet_name": "CALLS",
                    "column": None,
                    "processing": {"function": NrcScrapedReportFields.ft_id},
                },
            ],
            'public."NrcParsedReport"': [
                {
                    "db_table": '"NrcParsedReport"',
                    "db_field": "reportnum",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "SEQNOS",
                    "processing": None,
                },
                {
                    "db_table": '"NrcParsedReport"',
                    "db_field": "latitude",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": None,
                    "processing": {
                        "function": NrcParsedReportFields.latitude,
                        "args": {
                            "col_degrees": "LAT_DEG",
                            "col_minutes": "LAT_MIN",
                            "col_seconds": "LAT_SEC",
                            "col_quadrant": "LAT_QUAD",
                        },
                    },
                },
                {
                    "db_table": '"NrcParsedReport"',
                    "db_field": "longitude",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": None,
                    "processing": {
                        "function": NrcParsedReportFields.longitude,
                        "args": {
                            "col_degrees": "LONG_DEG",
                            "col_minutes": "LONG_MIN",
                            "col_seconds": "LONG_SEC",
                            "col_quadrant": "LONG_QUAD",
                        },
                    },
                },
                {  # TODO: Implement - check notes about which column to use
                    "db_table": '"NrcParsedReport"',
                    "db_field": "areaid",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": None,
                    "processing": {"function": NrcParsedReportFields.areaid},
                },
                {  # TODO: Implement - check notes about which column to use
                    "db_table": '"NrcParsedReport"',
                    "db_field": "blockid",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": None,
                    "processing": {"function": NrcParsedReportFields.blockid},
                },
                {
                    "db_table": '"NrcParsedReport"',
                    "db_field": "zip",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "LOCATION_ZIP",
                    "processing": None,
                },
                {  # TODO: Implement - check notes about which column to use
                    "db_table": '"NrcParsedReport"',
                    "db_field": "platform_letter",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": None,
                    "processing": {"function": NrcParsedReportFields.platform_letter},
                },
                {
                    "db_table": '"NrcParsedReport"',
                    "db_field": "sheen_size_length",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_DETAILS",
                    "column": "SHEEN_SIZE_LENGTH",
                    "processing": {
                        "function": NrcParsedReportFields.sheen_size_length,
                        "args": {"unit_field": "SHEEN_SIZE_LENGTH_UNITS"},
                    },
                },
                {
                    "db_table": '"NrcParsedReport"',
                    "db_field": "sheen_size_width",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_DETAILS",
                    "column": "SHEEN_SIZE_WIDTH",
                    "processing": {
                        "function": NrcParsedReportFields.sheen_size_width,
                        "args": {"unit_field": "SHEEN_SIZE_WIDTH_UNITS"},
                    },
                },
                {  # TODO: Implement
                    "db_table": '"NrcParsedReport"',
                    "db_field": "affected_area",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": None,
                    "processing": {
                        "function": NrcParsedReportFields.affected_area,
                    },
                },
                {
                    "db_table": '"NrcParsedReport"',
                    "db_field": "county",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "LOCATION_COUNTY",
                    "processing": None,
                },
                {
                    "db_table": '"NrcParsedReport"',
                    "db_field": "time_stamp",
                    "db_schema": "public",
                    "sheet_name": "CALLS",
                    "column": None,
                    "processing": {
                        "function": NrcParsedReportFields.time_stamp,
                    },
                },
                {
                    "db_table": '"NrcParsedReport"',
                    "db_field": "ft_id",
                    "db_schema": "public",
                    "sheet_name": "CALLS",
                    "column": None,
                    "processing": {
                        "function": NrcParsedReportFields.ft_id,
                    },
                },
            ],
            'public."BotTaskStatus"': [
                {
                    "db_table": '"BotTaskStatus"',
                    "db_field": "task_id",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": "SEQNOS",
                    "processing": None,
                },
                {
                    "db_table": '"BotTaskStatus"',
                    "db_field": "status",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": None,
                    "processing": {
                        "function": BotTaskStatusFields.status,
                    },
                },
                {
                    "db_table": '"BotTaskStatus"',
                    "db_field": "bot",
                    "db_schema": "public",
                    "sheet_name": "INCIDENT_COMMONS",
                    "column": None,
                    "processing": {
                        "function": BotTaskStatusFields.bot,
                    },
                },
            ],
        }

        # /* ----------------------------------------------------------------------- */#
        # /*     Define Defaults
        # /* ----------------------------------------------------------------------- */#

        # Database
        db_connection_string = None
        db_host = settings.DB_HOST  # 'localhost'
        db_name = settings.DB_DATABASE  # 'skytruth'
        db_user = settings.DB_USER  # getpass.getuser()
        db_pass = settings.DB_PASS  # ''
        db_write_mode = "INSERT INTO"
        db_seqnos_field = "reportnum"
        db_null_value = "NULL"
        sheet_seqnos_field = "SEQNOS"

        # testing_limit in effect if > 0
        testing_limit = 0

        # NRC file I/O
        now = datetime.now()
        current_year = datetime.strftime(now, "%y")
        download_url = f"https://nrc.uscg.mil/FOIAFiles/CY{current_year}.xlsx"
        file_to_process = os.getcwd() + sep + name_current_file(basename(download_url))
        overwrite_downloaded_file = False
        download_file = True
        process_subsample = None
        process_subsample_min = 0

        # User feedback settings
        print_progress = True
        print_queries = False
        execute_queries = True
        final_table_counts = [
            'public."NrcParsedReport"',
            'public."NrcScrapedMaterial"',
            'public."NrcScrapedReport"',
        ]

        # SELECT source_item_id from feedentry where source_id=1 AND source_item_id>0 order by source_item_id DESC LIMIT 1
        def get_last_posted_reportnum(db_cursor):
            query = """SELECT source_item_id from feedentry where source_id=1 AND source_item_id>0 AND status='published' 
                order by source_item_id DESC LIMIT 1"""
            # print('query:', query)
            db_cursor.execute(query)
            return db_cursor.fetchone()

        def load_curr_feedentry_reportnums(db_cursor, start_reportnum):
            query = (
                """SELECT source_item_id from feedentry WHERE source_id=1 AND source_item_id>=%s"""
                % start_reportnum
            )
            # print('query:', query)
            db_cursor.execute(query)
            return [item[0] for item in db_cursor.fetchall()]

        def remove_old_table_entries(db_cursor):
            task_id = None
            print("remove_old_table_entries:")
            try:
                query = """DELETE FROM "NrcScrapedReport";
                    DELETE FROM "NrcScrapedMaterial";
                    DELETE FROM "NrcParsedReport";
                    DELETE FROM "BotTaskStatus";
                    DELETE FROM "NrcGeocode";
                    DELETE FROM "NrcAnalysis";"""
                # print('query:', query)
                db_cursor.execute(query)
            # except ValueError as error:
            #     error_condition("ValueError found", str(error), task_id, sys.exc_info())
            # except psycopg2.DatabaseError as error:
            #     error_condition("psycopg2.DatabaseError", str(error), task_id, sys.exc_info())
            # except psycopg2.OperationalError as error:
            #     error_condition("psycopg2.OperationalError", str(error), task_id, sys.exc_info())
            # except psycopg2.Error as error:
            #     error_condition(
            #         "psycopg2.Error:",
            #     )
            # except RuntimeError as error:
            #     error_condition("RuntimeError found", str(error), task_id, sys.exc_info())
            # except TypeError as error:
            #     error_condition("TypeError found", str(error), task_id, sys.exc_info())
            # except NameError as error:
            #     error_condition("NameError found:" + str(error))
            # except:
            #     error_condition("An error occured.", "An error occured", task_id, sys.exc_info())
            except:
                pass

        # /* ----------------------------------------------------------------------- */#
        # /*     Parse arguments
        # /* ----------------------------------------------------------------------- */#

        i = 0
        arg_error = False
        while i < len(args):
            try:
                arg = args[i]

                # Help arguments
                if arg in ("--help-info", "-help-info", "--helpinfo", "-help-info"):
                    return print_help_info()
                elif arg in ("--help", "-help", "--h", "-h"):
                    return print_help()
                elif arg in ("--usage", "-usage"):
                    return print_usage()
                elif arg in ("--version", "-version"):
                    return print_version()
                elif arg in ("--license", "-usage"):
                    return print_license()

                # Spreadsheet I/O
                elif arg == "--no-download":
                    i += 1
                    download_file = False
                elif arg == "--download-url":
                    i += 2
                    download_url = args[i - 1]
                elif arg == "--file-to-process":
                    i += 2
                    file_to_process = abspath(args[i - 1])
                    print("file to process:", file_to_process)

                # Database connection
                elif arg == "--db-connection-string":
                    i += 2
                    db_connection_string = args[i - 1]
                elif arg == "--db-host":
                    i += 2
                    db_host = args[i - 1]
                elif arg == "--db-user":
                    i += 2
                    db_user = args[i - 1]
                elif arg == "--db-name":
                    i += 2
                    db_name = args[i - 1]
                elif arg == "--db-pass":
                    i += 2
                    db_pass = args[i - 1]

                # Commandline print-outs
                elif arg == "--no-print-progress":
                    i += 1
                    print_progress = False
                elif arg == "--print-queries":
                    i += 1
                    print_queries = True
                    print_progress = False
                elif arg == "--no-execute-queries":
                    i += 1
                    execute_queries = False

                # Additional options
                elif arg == "--overwrite-download":
                    i += 1
                    overwrite_downloaded_file = True
                elif arg == "--subsample":
                    i += 2
                    process_subsample = args[i - 1]
                elif arg == "--subsample-min":
                    i += 2
                    process_subsample_min = args[i - 1]

                # Positional arguments and errors
                else:
                    # Invalid argument
                    i += 1
                    arg_error = True
                    # error_condition("ERROR: Invalid argument: %s" % arg)

            # This catches three conditions:
            #   1. The last argument is a flag that requires parameters but the user did not supply the parameter
            #   2. The arg parser did not properly consume all parameters for an argument
            #   3. The arg parser did not properly iterate the 'i' variable
            except IndexError:
                i += 1
                arg_error = True
                # error_condition("ERROR: An argument has invalid parameters")

        # /* ----------------------------------------------------------------------- */#
        # /*     Adjust options
        # /* ----------------------------------------------------------------------- */#

        # Database - must be done here in order to allow the user to overwrite the default credentials and settings
        if db_connection_string is None:
            db_connection_string = "host='%s' dbname='%s' user='%s' password='%s'" % (
                db_host,
                db_name,
                db_user,
                db_pass,
            )

        # /* ----------------------------------------------------------------------- */#
        # /*     Validate parameters
        # /* ----------------------------------------------------------------------- */#

        bail = False

        # Make sure arguments were properly parse
        if arg_error:
            bail = True
            # error_condition("ERROR: Did not successfully parse arguments")

        # Make sure the downloaded file is not going to be accidentally deleted
        if download_file and not overwrite_downloaded_file and isfile(file_to_process):
            bail = True
            # error_condition(
            #     "ERROR: Overwrite=%s and download target exists: %s"
            #     % (overwrite_downloaded_file, file_to_process)
            # )

        # Make sure the user has write permission to the target directory
        if not os.access(dirname(file_to_process), os.W_OK):
            bail = True
            # error_condition(
            #     "ERROR: Need write permission for download directory: %s" % dirname(file_to_process)
            # )

        # Handle subsample
        if process_subsample is not None:
            try:
                process_subsample = int(process_subsample)
                process_subsample_min = int(process_subsample_min)
            except ValueError:
                bail = True
                # error_condition(
                #     "ERROR: Invalid subsample or subsample min - must be an int: %s"
                #     % process_subsample
                # )

        # Exit if any problems were encountered
        if bail:
            return 1

        # /* ----------------------------------------------------------------------- */#
        # /*     Prep DB connection and XLRD workbook for processing
        # /* ----------------------------------------------------------------------- */#

        # Test connection
        # print("Connecting to DB: %s" % db_connection_string)
        try:
            connection = psycopg2.connect(db_connection_string)
            connection.close()
        except psycopg2.OperationalError as e:
            error = "ERROR: Could not connect to database. See settings connection_string: %s" % (e)
            # error_condition(error)
            return 1

        # /* ----------------------------------------------------------------------- */#
        # /*     Download the spreadsheet
        # /* ----------------------------------------------------------------------- */#

        if download_file:
            print("Downloading: %s" % download_url)
            print("Target: %s" % file_to_process)
            try:
                download(download_url, file_to_process)
            except urllib.error.HTTPError as e:
                # error_condition("ERROR: Could not download from URL: %s, %s" % (download_url, e))
                return 1

        # Prep workbook
        try:
            print("Opening workbook: %s" % file_to_process)
            with xlrd.open_workbook(file_to_process, "r") as workbook:
                # Establish a DB connection  and turn on dict reading
                db_conn = psycopg2.connect(db_connection_string)
                db_conn.autocommit = True
                db_cursor = db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

                # /* ----------------------------------------------------------------------- */#
                # /*     Validate field map definitions
                # /* ----------------------------------------------------------------------- */#

                validate_field_map_error = False

                print("Validating field mapping ...")
                for db_map in field_map_order:
                    # Check each field definition in the set of mappings
                    for map_def in field_map[db_map]:
                        # print('map_def:', map_def)
                        # Attempt to get the sheet to test
                        if map_def["sheet_name"] is not None and map_def["column"] is not None:
                            try:
                                sheet = workbook.sheet_by_name(map_def["sheet_name"])
                                if map_def["column"] not in column_names(sheet):
                                    validate_field_map_error = True
                                    # error_condition(
                                    #     "ERROR: Can't find source: %s -> %s.%s"
                                    #     % (
                                    #         file_to_process,
                                    #         map_def["sheet_name"],
                                    #         map_def["column"],
                                    #     )
                                    # )

                            # Could not get the sheet to test
                            except xlrd.XLRDError:
                                validate_field_map_error = True
                                # error_condition(
                                #     "ERROR: Sheet does not exist: %s" % map_def["sheet_name"]
                                # )

                        # Make sure schema and table exist in the DB
                        query = (
                            "SELECT * FROM information_schema.columns WHERE table_schema = '%s' AND table_name = '%s' AND column_name = '%s';"
                            % (
                                map_def["db_schema"],
                                map_def["db_table"].replace('"', ""),
                                map_def["db_field"],
                            )
                        )
                        db_cursor.execute(query)
                        results = db_cursor.fetchall()
                        if not results:
                            validate_field_map_error = True
                            # error_condition(
                            #     "ERROR: Invalid DB target: %s.%s.%s.%s.%s"
                            #     % (
                            #         db_host,
                            #         db_name,
                            #         map_def["db_schema"],
                            #         map_def["db_table"],
                            #         map_def["db_field"],
                            #     )
                            # )

                # Encountered an error validating the field map
                if validate_field_map_error:
                    db_cursor.close()
                    db_conn.close()
                    return 1

                # /* ----------------------------------------------------------------------- */#
                # /*     Cache initial DB row counts for final stat printing
                # /* ----------------------------------------------------------------------- */#

                initial_db_row_counts = {
                    ts: db_row_count(db_cursor, ts) for ts in final_table_counts
                }

                # /* ----------------------------------------------------------------------- */#
                # /*     Additional prep
                # /* ----------------------------------------------------------------------- */#

                # Cache all sheets needed by the field definitions as dictionaries
                print("Caching sheets ...")
                sheet_cache = {}
                raw_sheet_cache = {}
                for sname in workbook.sheet_names():
                    if sname not in sheet_cache:
                        try:
                            sheet_dict = sheet2dict(workbook.sheet_by_name(sname))
                            raw_sheet_cache[sname] = sheet_dict
                            sheet_cache[sname] = {
                                row[sheet_seqnos_field]: row for row in sheet_dict
                            }
                        except IndexError:
                            # Sheet was empty
                            pass

                remove_old_table_entries(db_cursor)
                start_reportnum = get_last_posted_reportnum(db_cursor)[0]  # 1282490
                # start_reportnum = 1356520 # 1359880
                print("start_reportnum:", start_reportnum)
                # curr_feedentry_reportnums = load_curr_feedentry_reportnums(db_cursor, start_reportnum)
                # Get a list of unique report id's
                unique_report_ids = []
                for s_name, s_rows in sheet_cache.items():
                    for reportnum in s_rows.keys():
                        try:
                            float(reportnum)
                        except:
                            print("reportnum not a number:", reportnum)
                            continue
                        if (
                            reportnum > start_reportnum
                        ):  # not in curr_feedentry_reportnums: and reportnum < 1286030
                            # print('reportnum=', reportnum)
                            unique_report_ids.append(reportnum)
                unique_report_ids = list(set(unique_report_ids))
                unique_report_ids.sort()
                print("unique_report_ids loaded")
                # Grab a subsample if necessary
                if process_subsample is not None and process_subsample < len(unique_report_ids):
                    # TODO: Delete constraining line - needed to verify everything was wroking
                    unique_report_ids = [i for i in unique_report_ids if i > 1221346]

                    unique_report_ids.sort()
                    unique_report_ids = unique_report_ids[
                        process_subsample_min : process_subsample_min + process_subsample
                    ]

                # /* ----------------------------------------------------------------------- */#
                # /*     Process data
                # /* ----------------------------------------------------------------------- */#

                # Loops:
                # Get a report number to process
                #   Get a set of field maps for a single table to process
                #       Get a field map to process

                print("Processing workbook ...")
                num_ids = len(unique_report_ids)
                print("num_ids:", num_ids)
                uid_i = 0
                testing_count = 0
                # Loop through the primary keys
                for uid in unique_report_ids:
                    print("")
                    print("processing reportnum:", uid, uid > 0)
                    # Use this to only process one report
                    # if uid != 1286689.0:
                    #     continue

                    # Use this to skip over a report
                    if uid == 1387614.0 or uid == 1387855.0 or uid == 1387909.0 or uid == 1387920.0:
                        print("skipping 1264683.0")
                        continue

                    testing_count += 1
                    if testing_limit > 0 and testing_count == testing_limit:
                        break
                    #
                    # Update user
                    uid_i += 1
                    if print_progress:
                        sys.stdout.write("\r\x1b[K" + "  %s/%s" % (uid_i, num_ids))
                        sys.stdout.flush()

                    # Get field maps for one table
                    for db_map in field_map_order:
                        # print('db_map:', db_map, uid)
                        query_fields = []
                        query_values = []
                        # If the report already exists, in the target table, skip everything else
                        _schema, _table = db_map.split(".")
                        if not report_exists(
                            db_cursor=db_cursor,
                            reportnum=uid,
                            schema=_schema,
                            table=_table,
                        ):
                            # if not report_already_posted(db_cursor=db_cursor, reportnum=uid):
                            #   print(uid, 'does not exist')

                            # Get a single field map to process
                            for map_def in field_map[db_map]:
                                # Don't need to process the reportnum information since it was added to the initial query above
                                if map_def["db_field"] == db_seqnos_field:
                                    query_fields = [db_seqnos_field]
                                    query_values = [str(uid)]
                                else:
                                    # Get the row for this sheet
                                    try:
                                        row = sheet_cache[map_def["sheet_name"]][uid]
                                    except KeyError:
                                        row = None
                                    # If no additional processing is required, simply grab the value from the sheet and add to the query
                                    if row is not None:
                                        # /* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */#
                                        # /*     Value goes from input file straight into DB
                                        # /* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */#
                                        if map_def["processing"] is None:
                                            try:
                                                value = row[map_def["column"]]
                                            except KeyError:
                                                # UID doesn't appear in the specified sheet - populate a NULL value
                                                value = db_null_value
                                        # /* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */#
                                        # /*     Value with additional processing
                                        # /* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */#

                                        # Pass all necessary information to the processing function in order to get a result
                                        else:
                                            value = map_def["processing"]["function"](
                                                db_cursor=db_cursor,
                                                uid=uid,
                                                workbook=workbook,
                                                row=row,
                                                db_null_value=db_null_value,
                                                map_def=map_def,
                                                sheet=sheet_cache[map_def["sheet_name"]],
                                                all_field_maps=field_map,
                                                sheet_seqnos_field=sheet_seqnos_field,
                                                db_write_mode=db_write_mode,
                                                print_queries=print_queries,
                                                execute_queries=execute_queries,
                                                raw_sheet_cache=raw_sheet_cache,
                                                db_seqnos_field=db_seqnos_field,
                                                sheet_cache=sheet_cache,
                                            )

                                        # /* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */#
                                        # /*     Add this field map to the insert statement
                                        # /* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */#

                                        # Handle NULL values - these should be handled elsewhere so this is more of a safety net
                                        if value is None or not value:
                                            value = db_null_value

                                        # Assemble query
                                        if value not in ("__NO_QUERY__", db_null_value):
                                            # print('field:', map_def['db_field'], ' value:', value)
                                            query_fields.append(map_def["db_field"])
                                            # Only put quotes around specific values
                                            # if isinstance(value, str) or isinstance(value, unicode):
                                            if isinstance(value, bytes) or isinstance(value, str):
                                                # Having single quotes in the string causes problems on insert because the entire
                                                # value is single quoted
                                                value = value.replace("'", '"')
                                                query_values.append("'%s'" % value)
                                            else:
                                                query_values.append("%s" % value)

                            # /* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */#
                            # /*     Execute query
                            # /* ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ */#

                            # Execute query, but not if the report already exists
                            query = """%s %s (%s) VALUES (%s);""" % (
                                db_write_mode,
                                db_map,
                                ", ".join(query_fields),
                                ", ".join(query_values),
                            )
                            # print('query:', query)
                            if print_queries:
                                # print("")
                                try:
                                    print(query)
                                except Exception as e:
                                    print("Error printing SQL query to console (unicode weirdness?")
                                    # error_condition(e.message)
                            if execute_queries:
                                print(query, flush=True)
                                db_cursor.execute(query)
                # Done processing - update user
                if print_progress:
                    print(" - Done")
        # except ValueError as error:
        #     error_condition("ValueError found", str(error), uid, sys.exc_info())
        #     return 1
        # except psycopg2.DatabaseError as error:
        #     error_condition("psycopg2.DatabaseError", str(error), sys.exc_info())
        #     return 1
        # except psycopg2.OperationalError as error:
        #     error_condition("psycopg2.OperationalError", str(error), sys.exc_info())
        #     return 1
        # except psycopg2.Error as error:
        #     error_condition("psycopg2.Error", str(error), sys.exc_info())
        #     return 1
        # except RuntimeError as error:
        #     error_condition("RuntimeError found", str(error), sys.exc_info())
        #     return 1
        # except TypeError as error:
        #     error_condition("TypeError found", str(error), sys.exc_info())
        #     return 1
        # except NameError as error:
        #     error_condition("NameError found on reportnum " + str(uid), str(error), sys.exc_info())
        #     return 1
        # except:
        #     # (error, details, task_id=0, exc_info=None):
        #     error_condition(
        #         "ERROR: processing spreadsheet ", "except error", uid, sys.exc_info()
        #     )  # % file_to_process)
        #     return 1
        except:
            return 1

        # /* ----------------------------------------------------------------------- */#
        # /*     Cleanup and final return
        # /* ----------------------------------------------------------------------- */#

        # Update user
        padding = max([len(i) for i in field_map.keys()])
        indent = " " * 2
        print("Initial row counts:")
        for schema_table, count in initial_db_row_counts.items():
            print(
                "%s%s%s"
                % (
                    indent,
                    schema_table + " " * (padding - len(schema_table) + 4),
                    count,
                )
            )
        print("Final row counts:")
        final_db_row_counts = {ts: db_row_count(db_cursor, ts) for ts in final_table_counts}
        for schema_table, count in final_db_row_counts.items():
            print(
                "%s%s%s"
                % (
                    indent,
                    schema_table + " " * (padding - len(schema_table) + 4),
                    count,
                )
            )
        print("New rows:")
        for schema_table, count in final_db_row_counts.items():
            print(
                "%s%s%s"
                % (
                    indent,
                    schema_table + " " * (padding - len(schema_table) + 4),
                    final_db_row_counts[schema_table] - initial_db_row_counts[schema_table],
                )
            )

        # /* ----------------------------------------------------------------------- */#
        # /*     Build "NrcAnalysis"
        # /* ----------------------------------------------------------------------- */#
        query = """SELECT task_id FROM "%s" WHERE bot='NrcExtractor' AND status='ALERTS2'""" % (
            "BotTaskStatus"
        )
        print(query)
        db_cursor.execute(query)
        result = db_cursor.fetchall()
        for alert2 in result:
            task_id = alert2[0]
            # print('task_id:', task_id)
            # db = NrcAnalyzer2()
            # geocoder = NrcGeocoder()
            # geocoder.process_item(task_id, db_cursor)
            analyzer = NrcAnalyzer()
            analyzer.process_item(task_id, db_cursor)

        query = """SELECT * FROM "BotTaskStatus" bt, "NrcScrapedReport" scr, "NrcParsedReport" par, "NrcGeocode" geo, "NrcAnalysis" anl
            WHERE bt.bot='NrcExtractor' AND bt.status='ALERTS2' 
            AND bt.task_Id=scr.reportnum 
            AND bt.task_id=par.reportnum 
            AND bt.task_id=geo.reportnum
            AND bt.task_id=anl.reportnum"""

        # print('query:', query)
        db_cursor.execute(query)
        result = db_cursor.fetchall()
        testing_count = 0
        total_new_feedentry = 0
        print("number of potential new entries:", str(len(result)))
        # return
        # alert2: [1220613, u'NrcExtractor', u'ALERTS2', datetime.datetime(2018, 9, 4, 14, 35, 15, 314414), 1220613,
        #          u'INCIDENT', datetime.datetime(2018, 8, 5, 6, 21, 15),
        #          u'THE CALLER IS REPORTING A SHEEN FROM AN UNKNOWN SOURCE.', datetime.datetime(2018, 8, 5, 6, 0),
        #          u'UNKNOWN SHEEN', u'UNKNOWN', u'10 CRAWFORD PARKWAY', u'VA', u'PORTSMOUTH', u'PORTSMOUTH', None, u'WATER',
        #          u'UNKNOWN OIL', u'http://nrc.uscg.mil/', u'http://nrc.uscg.mil/',
        #          datetime.datetime(2018, 9, 4, 14, 35, 15, 205053), None, 1220613, None, None, None, None, u'23704', None,
        #          u'10.0 FEET', u'3.0 FEET', None, u'PORTSMOUTH', datetime.datetime(2018, 9, 4, 14, 35, 15, 259248), None,
        #          1220613, u'OUN', u'UNKNOWN OIL', 0.0, u'UNKNOWN AMOUNT', u'YES', 0.0, u'UNKNOWN AMOUNT', None, 2049,
        #          1220613, u'ZIP', 36.8274757, -76.3116235, Decimal('1')]

        # task_id = None
        try:
            for alert2 in result:
                # print('alert2:', alert2)
                task_id = alert2[0]
                print("inside alert2 in result, task_id=", str(task_id))
                calltype = alert2[5]
                received = alert2[6]
                description = alert2[7]
                incident_datetime = alert2[8]
                incidenttype = alert2[9]
                cause = alert2[10]
                location = alert2[11]
                state = alert2[12]
                nearestcity = alert2[13]
                county1 = alert2[14]
                suspected_responsible_company = alert2[15]
                medium_affected = alert2[16]
                material_name = alert2[17]
                full_report_url = alert2[18]
                materials_url = alert2[19]
                ft_id = alert2[21]
                incident_location = alert2[22]
                locationstreet1 = alert2[23]
                locationstreet2 = alert2[24]
                lat1 = alert2[26]
                lng1 = alert2[27]
                areaid = alert2[28]
                blockid = alert2[29]
                zip = alert2[30]
                platform_letter = alert2[31]
                sheen_size_length = alert2[32]
                sheen_size_width = alert2[33]
                affected_area = alert2[34]
                county2 = alert2[35]
                # These are for NrcScrapedMaterial, which is not used here.
                # chris_code = alert2[36] # starts NrcScrapedMaterial
                # name = alert2[37]
                # amount = alert2[38]
                # unit = alert2[39]
                # reached_water = alert2[40]
                # amt_in_water = alert2[41]
                # amt_in_water_unit = alert2[42]
                # st_id = alert2[44] # ends NrcScrapedMaterial
                source = alert2[39]
                lat = alert2[40]
                lng = alert2[41]
                precision = alert2[42]
                sheen_length = alert2[44]
                sheen_width = alert2[45]
                reported_spill_volume = alert2[46]
                min_spill_volume = alert2[47]
                # print(str(task_id), reported_spill_volume, min_spill_volume, flush=True)
                calltype = alert2[48]
                severity = alert2[49]
                region = alert2[50]
                release_type = alert2[51]
                reported_spill_unit = alert2[52]

                # print('lat:', lat, ' lat1:', lat1, ' lng:', lng, ' lng1:', lng1)
                # print('release_type:', release_type)
                tags = []
                severity = ""

                tags.append("NRC")
                tags.append(release_type)
                # if(str(task_id)) == "1385713":
                #     print(33890, reported_spill_volume, min_spill_volume, flush=True)
                #     continue
                if (
                    reported_spill_volume > 100 or min_spill_volume > 100
                ) and reported_spill_unit == "GALLON":
                    tags.append("BigSpill")
                    # yield self.make_tag(task_id, 'BigSpill')
                if reported_spill_volume and min_spill_volume / reported_spill_volume >= 2:
                    tags.append("SheenSizeMismatch")
                    # yield self.make_tag(task_id, 'SheenSizeMismatch')
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
                    or material_name
                    in ("REFRIGERANT GASES", "OIL, FUEL: NO. 1-D", "OIL, FUEL: NO. 2-D")
                ):
                    tags.append("minor")
                    severity = "minor"
                if (
                    incidenttype == "UNKNOWN SHEEN"
                    and reported_spill_volume < 1
                    and min_spill_volume < 10
                ):
                    tags.append("minor")
                if reported_spill_volume > 100 or min_spill_volume > 100:
                    tags.append("major")

                if state == "LA" and severity != "minor" and severity != "non-release":
                    tags.append("LABB")

                tags.append("release")

                if material_name == None:
                    material_name = ""
                # print('material_name:', material_name)

                title = "NRC Report: " + material_name.title()
                if nearestcity and state:
                    title += " near " + nearestcity.title() + ", " + state
                # print('lat:', lat, ' lng:', lng,'title:', title)
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

                # THIS IS MISSING AFTER Suspected Responsible Party:
                # Suspected Responsible Party: <br/><b>SkyTruth Analysis</b>
                # <br/>Lat/Long: 47.571999, -122.346412 (Approximated from premise)
                # <br/>Reported Sheen Size: 20 feet by 30 feet (area 600 sq. ft.)
                # <br/>SkyTruth Minimum Estimate: 0.01 gallons
                # <br/><b>Report Description</b>
                # <br/>CALLER IS REPORTING THE DISCOVERY OF A MYSTERY SHEEN FROM AN UNKNOWN SOURCE IN THE DUWAMISH WATERWAY EAST.  CALLER OBSERVED THE SHEEN IN APPROXIMATELY THREE PATCHES OF THE LISTED SIZE.

                # < b > SkyTruth
                # Analysis < / b > < br / > Lat / Long: 43.023056, -75.112222(Explicit)

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
                # https://developers.google.com/maps/documentation/geocoding/intro#Types
                # def capitalize(x):
                #     i = sliceindex(x)
                #     return x[:i].upper() + x[i:]

                # assumes value in gallons
                def format_value_volume(value, units=None):
                    # print('format_value_volume:', value)
                    if not value:
                        return ""
                    if units is None:
                        units = "gallons"
                    else:
                        units = units.lower()
                    return "%s %s" % (
                        locale.format("%.12g", round(value, 2), False),
                        units,
                    )

                # assumes value is in sq. feet
                def format_value_area(value):
                    # print('format_value_area:', value)
                    if not value:
                        return ""
                    units = "sq. ft."
                    if value >= 10000:
                        value = value / 43560
                        units = "acres"
                        if value >= 640:
                            value = value / 640
                            units = "sq. miles"
                    return "%s %s" % (
                        locale.format("%.12g", round(value, 2), False),
                        units,
                    )

                # assumes value is in feet
                def format_value_extent(value):
                    if not value:
                        return ""
                    units = "feet"
                    if value >= 1000:
                        value = value / 5280
                        units = "miles"
                    return "%s %s" % (
                        locale.format("%.12g", round(value, 2), False),
                        units,
                    )

                if sheen_length and sheen_width:
                    # print('sheen_width:', str(sheen_width), ' sheen_length:', str(sheen_length))
                    content += (
                        "<br/>"
                        + "Reported Sheen Size: "
                        + format_value_extent(sheen_width)
                        + " by "
                        + format_value_extent(sheen_length)
                        + " (area "
                        + format_value_area(sheen_width * sheen_length)
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
                    content += (
                        "<br/>"
                        + "SkyTruth Minimum Estimate: "
                        + format_value_volume(min_spill_volume)
                    )
                    # str(min_spill_volume)
                content += "<br/>" + "<b>Report Description</b>" + description

                id = hashlib.md5(
                    (summary + str(incident_datetime) + str(lat) + str(lng)).encode()
                ).hexdigest()
                id = "-".join((id[:8], id[8:12], id[12:16], id[16:20], id[20:32]))
                post_fields = {
                    "id": id,
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "content": content,
                    "lat": lat,  # str(round(lat, 6)),
                    "lng": lng,  # str(round(lng, 6)),
                    "source_id": 1,
                    "kml_url": "",
                    "incident_datetime": incident_datetime,
                    "source_item_id": task_id,
                    "tags": tags,
                    "status": "published",
                    "bot_reportnum_done": task_id,
                }
                print(post_fields, flush=True)
                url = settings.API_POST_FEEDENTRY
                # comment out post routine until date bug fixed
                response = requests.post(url, data=post_fields)
                response_status = str(response.content, "utf-8")
                print(
                    str(task_id),
                    str(round(lat, 6)),
                    str(round(lng, 6)),
                    "API_POST_FEEDENTRY returned " + response_status,
                )
                if response_status == "Success":
                    total_new_feedentry = total_new_feedentry + 1
                else:
                    if response_status != "Already in feedentry":
                        print(response.content)

        # except ValueError as error:
        #     error_condition("ValueError found", str(error), task_id, sys.exc_info())
        # except psycopg2.DatabaseError as error:
        #     error_condition("psycopg2.DatabaseError", str(error), task_id, sys.exc_info())
        # except psycopg2.OperationalError as error:
        #     error_condition("psycopg2.OperationalError", str(error), task_id, sys.exc_info())
        # except psycopg2.Error as error:
        #     error_condition("psycopg2.Error", str(error), task_id, sys.exc_info())
        # except RuntimeError as error:
        #     error_condition("RuntimeError found", str(error), task_id, sys.exc_info())
        # except TypeError as error:
        #     error_condition("TypeError found", str(error), task_id, sys.exc_info())
        # except NameError as error:
        #     error_condition("NameError found", str(error), task_id, sys.exc_info())
        # except:
        #     error_condition("An error occured.", "An error occured", task_id, sys.exc_info())
        except:
            pass
        # Success - commit inserts and destroy DB connections
        # db_conn.commit()  # connection is now set to autocommit
        db_cursor.close()
        db_conn.close()

        # utils.send_email(
        #     "nrcSpreadsheetScraper finished (" + str(total_new_feedentry) + ")",
        #     "nrcSpreadsheetScraper finished (" + str(total_new_feedentry) + ")",
        # )

        return 0


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    objName = NrcSpreadsheetScraper()
    sys.exit(objName.main(sys.argv[1:]))
