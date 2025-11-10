import os
import sys
import uuid
from datetime import datetime, timedelta
from os.path import *

import requests

sys.path.insert(0, "../")
import csv

import settings
from database import NrcDatabase
from pyvirtualdisplay.display import Display
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as cond
from selenium.webdriver.support.ui import Select, WebDriverWait


class PAPermits:
    db = NrcDatabase()
    db.connect()
    target_url = None
    source_ids = [9]
    source_types = ["PA DEP Violation"]
    before_counts = [00]
    after_counts = [0]
    name = "PA DEP Violation"
    process_number_of_days = 10
    today = datetime.today()
    # Uncomment the next 2 line to look at specific dates
    # war_start = '2021-01-07'
    # today = datetime.strptime(war_start, '%Y-%m-%d')
    today_string = today.strftime("%m/%d/%Y")
    start_date = today - timedelta(days=int(process_number_of_days))
    start_date_string = start_date.strftime("%m/%d/%Y")
    num_reads = 0

    def main(self, args):
        try:
            for num, source_id in enumerate(self.source_ids, start=0):
                self.before_counts[num] = self.db.get_feedentry_count(source_id)["count"]

            try:
                display = Display(visible=0, size=(800, 600))
                display.start()
                # Initialize a Firefox webdriver
                profile = webdriver.FirefoxProfile()
                profile.set_preference("browser.download.folderList", 2)  # custom location
                profile.set_preference("browser.download.manager.showWhenStarting", False)
                # profile.set_preference('browser.download.dir', '~/Documents/SkyTruth/alerts2scrapers/pa-scraper/rawdata')
                cwd = os.getcwd()
                print(cwd)
                profile.set_preference("browser.download.dir", os.getcwd() + "/rawdata")
                profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv")

                # browser = webdriver.Firefox(profile)
                driver = webdriver.Firefox(profile)

                file_name = cwd + "/rawdata/OilGasCompliance.csv"
                if os.path.exists(file_name):
                    rename_file = (
                        cwd
                        + "/rawdata/OilGasCompliance"
                        + str(datetime.now(tz=None)).replace(" ", "_").replace(":", "_")
                        + ".csv"
                    )
                    os.rename(file_name, rename_file)

                # driver.implicitly_wait(30)  # seconds
                print("getting driver")
                # Grab the web page
                # driver.get("https://www.depgreenport.state.pa.us/ReportExtracts/OG/OilComplianceReport")
                # New URL as of July, 2023
                driver.get("https://greenport.pa.gov/ReportExtracts/OG/OilComplianceReport")
                print("dates:", self.start_date_string, self.today_string)
                from_date = driver.find_element_by_id("InspDtfrm")
                driver.execute_script(
                    "arguments[0].setAttribute('value', '" + self.start_date_string + "')",
                    from_date,
                )
                to_date = driver.find_element_by_id("InspDtto")
                driver.execute_script(
                    "arguments[0].setAttribute('value', '" + self.today_string + "')",
                    to_date,
                )
                violations_only = Select(driver.find_element_by_id("Res_Vio_Only"))
                violations_only.select_by_value("Y")

                search_form = driver.find_element_by_id("btnReport")
                search_form.click()
                print("submit", datetime.now(tz=None))
                # Wait as long as required, or maximum of 30 sec for alert to appear
                WebDriverWait(driver, 30).until(
                    cond.invisibility_of_element_located((By.ID, "pleaseWaitModal"))
                    # cond.presence_of_element_located((By.ID, "btnReport"))
                )
                print("after", datetime.now(tz=None))

                # return

                with open(file_name) as csv_file:
                    csv_reader = csv.reader(csv_file, delimiter=",")
                    line_count = 0
                    for row in csv_reader:
                        if line_count == 0:
                            print(f"Column names are {', '.join(row)}")
                            line_count += 1
                        else:
                            self.examine_row(row)
                            line_count += 1
                    print(f"Processed {line_count} lines.")

            except (NoAlertPresentException, TimeoutException) as py_ex:
                print("TimeoutException")
                print(py_ex)
                print(py_ex.args)
            finally:
                driver.quit()
                display.stop()

        except Exception as e:
            print("Main PA DEP Violation Exception:", e)

        # Finish up
        for num, source_id in enumerate(self.source_ids, start=0):
            self.after_counts[num] = self.db.get_feedentry_count(source_id)["count"]
        email_subj = "PA DEP Violation finished ("
        for num, source_id in enumerate(self.source_ids, start=0):
            print(
                source_id,
                " before:",
                int(self.before_counts[num]),
                " after:",
                int(self.after_counts[num]),
                " total added:",
                int(self.after_counts[num] - self.before_counts[num]),
            )
            email_subj += (
                repr(source_id)
                + " "
                + repr(int(self.after_counts[num] - self.before_counts[num]))
                + " "
            )
        email_subj += ")"

    # @staticmethod
    def uuid3_str(self, namespace=uuid.NAMESPACE_URL, name=None):
        return self.uuid_str(uuid.uuid3(namespace, name))

    # @staticmethod
    def uuid_str(self, uuid_obj):
        s = uuid_obj.hex
        return "-".join([s[0:8], s[8:12], s[12:16], s[16:20], s[20:]])

    def get_field(self, trans, field):
        try:
            val = trans[field]
        except:
            val = ""
        return val

    def examine_row(self, row):  # inspection_trans, violation_trans):
        try:
            INSPECTION_CLIENT_NAME = row[0]  # row[10] inspection_trans, 'INSPECTION CLIENT NAME')
            INSPECTION_ID = row[1]
            INSPECTION_DATE = row[2]
            INSPECTION_TYPE = row[3]
            API_PERMIT = row[4]
            FARM_NAME = row[5]
            UNCONVENTIONAL = row[6]
            SITE = row[7]
            if SITE > "":
                SITE = SITE.split(" - ")
            SITE_ID = ""
            SITE_NAME = ""
            if len(SITE) == 2:
                SITE_ID = SITE[7]
                SITE_NAME = SITE[8]
            FACILITY_TYPE = row[9]
            INSPECTION_CATEGORY = row[10]
            REGION = row[11]
            COUNTY = row[12]
            MUNICIPALITY = row[13]
            INSPECTOR = row[14]
            INSPECTION_SOURCE = row[15]
            INSPECTION_RESULT_DESCRIPTION = row[16]
            INSPECTION_COMMENT = row[17]
            VIOLATION_ID = row[18]
            VIOLATION_DATE = row[19]
            VIOLATION_CODE = row[
                20
            ]  # violation_trans, 'VIOLATION CODE & DESCRIPTION').replace('–','-').replace('§', ' ')
            VIOLATION_TYPE = row[21]
            VIOLATION_COMMENT = row[22]

            if VIOLATION_ID:
                print("VIOLATION_ID:", VIOLATION_ID)
            else:
                return

            if API_PERMIT == None or API_PERMIT == "":
                print("No API_PERMIT found")
                return

            pa_permit = self.db.getPaPermit(API_PERMIT)
            if pa_permit == None:
                print("api_permit:", API_PERMIT, " original permit not found")
                return

            print("")
            print("")
            print("row:", row)
            print("")

            latitude = pa_permit["lat"]
            longitude = pa_permit["lng"]
            print("api_permit:", API_PERMIT, " found ", latitude, longitude)

            incident_datetime = INSPECTION_DATE
            if not INSPECTION_CLIENT_NAME:
                INSPECTION_CLIENT_NAME = ""
            if not VIOLATION_TYPE:
                VIOLATION_TYPE = ""
            if not VIOLATION_DATE:
                VIOLATION_DATE = ""
            if not VIOLATION_CODE:
                VIOLATION_CODE = ""
            if not VIOLATION_ID:
                VIOLATION_ID = ""
            if not UNCONVENTIONAL:
                UNCONVENTIONAL = ""
            if not COUNTY:
                COUNTY = ""
            if not MUNICIPALITY:
                MUNICIPALITY = ""
            if not INSPECTION_TYPE:
                INSPECTION_TYPE = ""
            if not INSPECTION_DATE:
                INSPECTION_DATE = ""
            if not INSPECTION_COMMENT:
                INSPECTION_COMMENT = ""

            title = (
                "PA Permit Violation Issued to "
                + INSPECTION_CLIENT_NAME
                + " in "
                + MUNICIPALITY
                + ", "
                + COUNTY
                + " County"
            )
            try:
                summary = (
                    str(VIOLATION_TYPE)
                    + " violation issued on "
                    + str(INSPECTION_DATE)[:10]
                    + " to "
                    + str(INSPECTION_CLIENT_NAME)
                    + " in "
                    + str(MUNICIPALITY)
                    + ", "
                    + str(COUNTY)
                    + " county. "
                    + str(VIOLATION_CODE)
                )
            except:
                print("VIOLATION_TYPE:", VIOLATION_TYPE)
                print("INSPECTION_DATE:", INSPECTION_DATE)
                print("INSPECTION_CLIENT_NAME:", INSPECTION_CLIENT_NAME)
                print("MUNICIPALITY:", MUNICIPALITY)
                print("COUNTY:", COUNTY)
                return
            content = (
                "<b>Report Details</b>"
                + '<table width = "100%"><tr><th>Inspection Client: </th><td>'
                + INSPECTION_CLIENT_NAME
                + "</td></tr>"
                + "<tr><th>Violation Type: </th><td>"
                + VIOLATION_TYPE
                + "</td></tr>"
                + "<tr><th>Violation Date: </th><td>"
                + str(VIOLATION_DATE)[:10]
                + "</td></tr>"
                + "<tr><th>Violation Code: </th><td>"
                + VIOLATION_CODE
                + "</td></tr>"
                + "<tr><th>Violation ID: </th><td>"
                + VIOLATION_ID
                + "</td></tr>"
                + "<tr><th>Permit API: </th><td>"
                + API_PERMIT
                + "</td></tr>"
                + "<tr><th>Unconventional: </th><td>"
                + UNCONVENTIONAL
                + "</td></tr>"
                + "<tr><th>County: </th><td>"
                + COUNTY
                + "</td></tr>"
                + "<tr><th>Municipality: </th><td>"
                + MUNICIPALITY
                + "</td></tr>"
                + "<tr><th>Inspection Type: </th><td>"
                + INSPECTION_TYPE
                + "</td></tr>"
                + "<tr><th>Inspection Date: </th><td>"
                + str(INSPECTION_DATE)[:10]
                + "</td></tr>"
                + "<tr><th>Comments: </th><td>"
                + INSPECTION_COMMENT
                + "</td></tr>"
                + "</table>"
            )

            tags = ["PADEP", "frack", "violation", "drilling"]

            about_url = "http://cedatareporting.pa.gov/Reportserver/Pages/ReportViewer.aspx?/Public/DEP/OG/SSRS/OG_Inspection_Docs"

            print(
                "summary:",
                summary,
                " VIOLATION_ID:",
                VIOLATION_ID,
                " VIOLATION_DATE:",
                VIOLATION_DATE,
            )
            unique = VIOLATION_ID  # "%s %s %s" % (summary, VIOLATION_ID, VIOLATION_DATE)
            feed_entry_id = self.uuid3_str(name=unique)

            post_fields = {
                "id": feed_entry_id,
                "title": title,
                "link": about_url,
                "summary": summary,
                "content": content,
                "lat": latitude,
                "lng": longitude,
                "source_id": self.source_ids[0],
                "kml_url": "",
                "incident_datetime": incident_datetime,
                "tags": tags,
                "status": "published",
            }
            url = settings.API_POST_FEEDENTRY
            print("post_fields:", post_fields)
            response = requests.post(url, data=post_fields)
            print(response.content)

        except Exception as e:
            print("Process Page PA DEP Violation Exception:", e)


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = PAPermits()
    it.main(sys.argv[1:])
