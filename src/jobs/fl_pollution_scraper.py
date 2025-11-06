from __future__ import absolute_import
from datetime import datetime
import hashlib
import requests
import os
import sys
from os.path import *
import urllib
import xlrd

sys.path.insert(0, "../")
import settings
from database import NrcDatabase


class FlPollution:
    db = NrcDatabase()
    db.connect()
    target_url = None
    source_id = 2001
    name = "pollution"
    now = datetime.now()
    year = datetime.strftime(now, "%Y")

    def main(self, args):
        before_count = self.db.get_feedentry_count(self.source_id)["count"]
        # download_url = 'http://prodenv.dep.state.fl.us/DepPNP/reports/exportIncidents'
        download_url = "https://prodenv.dep.state.fl.us/DepPNP/export-incidents"
        file_to_process = (
            os.getcwd() + sep + "rawdata/export.xls"
        )  # + self.name_current_file(basename(download_url))
        overwrite_downloaded_file = True
        download_file = True

        # /* ----------------------------------------------------------------------- */#
        # /*     Download the spreadsheet
        # /* ----------------------------------------------------------------------- */#

        if download_file:
            print("Downloading: %s" % download_url)
            print("Target: %s" % file_to_process)
            try:
                self.download(download_url, file_to_process, overwrite_downloaded_file)
            except urllib.error.HTTPError as e:
                print("ERROR: Could not download from URL: %s" % download_url)
                print("       URLLIB Error: %s" % e)
                return 1

        print("Opening workbook: %s" % file_to_process)
        with xlrd.open_workbook(file_to_process, "r") as workbook:
            # sheet = workbook.sheet_by_name(map_def['Incident Report List'])
            sheet_names = workbook.sheet_names()
            print("Sheet Names", sheet_names)
            incidents = workbook.sheet_by_name(sheet_names[0])
            num_cols = incidents.ncols  # Number of columns
            for row_idx in range(0, incidents.nrows):  # Iterate through rows
                # print('Row: %s' % row_idx)  # Print row number
                if row_idx > 0:  # and row_idx < 5:
                    Incident_Name = incidents.cell(row_idx, 0).value
                    SWO_Incident_Number = incidents.cell(row_idx, 1).value
                    Incident_Report = incidents.cell(row_idx, 2).value
                    Report_Date_Time = incidents.cell(row_idx, 3).value
                    Facility_Name = incidents.cell(row_idx, 4).value
                    Facility_Address = incidents.cell(row_idx, 5).value
                    Facility_Directions = incidents.cell(row_idx, 6).value
                    Reporter_Name = incidents.cell(row_idx, 7).value
                    Reporter_Title = incidents.cell(row_idx, 8).value
                    Reporter_Email = incidents.cell(row_idx, 9).value
                    Reporter_Phone = incidents.cell(row_idx, 10).value
                    Reporter_Phone_Extension = incidents.cell(row_idx, 11).value
                    Reporter_Role = incidents.cell(row_idx, 12).value
                    Contact_Phone = incidents.cell(row_idx, 14).value
                    Contact_Phone_Extension = incidents.cell(row_idx, 15).value
                    Contact_Email = incidents.cell(row_idx, 16).value
                    Release_Start_Date_Time = incidents.cell(row_idx, 17).value
                    Release_End_Date_Time = incidents.cell(row_idx, 18).value
                    Affected_Counties = incidents.cell(row_idx, 19).value
                    Migrated_Counties = incidents.cell(row_idx, 20).value
                    Migrated_Offsite = incidents.cell(row_idx, 21).value
                    latitude = incidents.cell(row_idx, 22).value
                    longitude = incidents.cell(row_idx, 23).value
                    Map_Direct_Link = incidents.cell(row_idx, 24).value
                    # print('year:', self.year, str(SWO_Incident_Number), str(SWO_Incident_Number)[0:4] == self.year, flush=True )
                    # The max value for an integer in Postgres is 2147483647
                    if str(SWO_Incident_Number)[0:4] == self.year:
                        # print(str(SWO_Incident_Number), latitude, longitude, flush=True)
                        try:
                            if (
                                self.db.getSourceItemIdCount(self.source_id, SWO_Incident_Number)
                                > 0
                            ):
                                # print(str(SWO_Incident_Number), 'already on file')
                                pass
                            elif str(latitude) > "" and str(longitude) > "":
                                print(
                                    str(SWO_Incident_Number),
                                    str(latitude),
                                    str(longitude),
                                    Incident_Name,
                                    Facility_Name,
                                )
                                id = hashlib.md5(
                                    (
                                        str(SWO_Incident_Number)
                                        + Incident_Name
                                        + Facility_Name
                                        + str(latitude)
                                        + str(longitude)
                                    ).encode()
                                ).hexdigest()
                                id = "-".join(
                                    (
                                        id[:8],
                                        id[8:12],
                                        id[12:16],
                                        id[16:20],
                                        id[20:24],
                                        id[24:36],
                                    )
                                )

                                content = (
                                    "<b>Report Details</b>"
                                    + "<table>"
                                    + "<tr><th valign='top'>Facility Name:</th><td>"
                                    + Facility_Name
                                    + "</td></tr>"
                                    + "<tr><th valign='top'>Address:</th><td>"
                                    + Facility_Address
                                    + "</td></tr>"
                                    + "<tr><th valign='top'>Release Date:</th><td>"
                                    + Release_Start_Date_Time
                                    + "</td></tr>"
                                    + "<tr><th valign='top'>Counties:</th><td>"
                                    + Affected_Counties
                                    + "</td></tr>"
                                    + "<tr><th valign='top'>Report:</th><td>"
                                    + Incident_Report
                                    + "</td></tr>"
                                    + "</table>"
                                )

                                post_fields = {
                                    "id": id,
                                    "title": "Fl Pollution Rpt: " + Incident_Name,
                                    "link": Map_Direct_Link,
                                    "summary": Incident_Name + "::" + Facility_Name,
                                    "content": content,
                                    "lat": latitude,
                                    "lng": longitude,
                                    "source_id": self.source_id,
                                    "source_item_id": SWO_Incident_Number,
                                    "kml_url": "",
                                    "incident_datetime": Report_Date_Time,
                                    "status": "published",
                                    "tags": ["Florida", "Pollution"],
                                }
                                url = settings.API_POST_FEEDENTRY
                                response = requests.post(url, data=post_fields)
                                print(response.content)
                        except Exception as e:
                            print("Error processing incident:", e)

        after_count = self.db.get_feedentry_count(self.source_id)["count"]
        print("before:", before_count)
        print("after:", after_count)
        print("total added:", (before_count - after_count))

    # /* ======================================================================= */#
    # /*     Define name_current_file() function
    # /* ======================================================================= */#

    def name_current_file(self, input_name):
        """
        Generate the output Current.xlsx name for permanent archival

        :param input_name: input file name (e.g. Current.xlsx)
        :type input_name: str|unicode

        :return: output formatted name
        :rtype: str|unicode
        """

        dt = datetime.now()
        dt = dt.strftime("_%Y-%m-%d")
        input_split = input_name.split(".")
        input_split[0] += dt

        return ".".join(input_split) + ".xls"

    # /* ======================================================================= */#
    # /*     Define get_current_spreadsheet() function
    # /* ======================================================================= */#

    def download(self, url, destination, overwrite=False):
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
            raise ValueError(
                "ERROR: Overwrite=%s and outfile exists: %s" % (overwrite, destination)
            )

        # Download
        response = urllib.request.urlopen(url)
        with open(destination, "wb") as f:
            f.write(response.read())

        return destination


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = FlPollution()
    it.main(sys.argv[1:])
