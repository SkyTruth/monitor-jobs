from __future__ import absolute_import
from datetime import datetime, timedelta
import requests
import sys
from os.path import *
import uuid

sys.path.insert(0, "../")
from src.utils.db import NrcDatabase

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as cond
from selenium.common.exceptions import NoAlertPresentException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from src.utils import config
from selenium.webdriver.firefox.options import Options as FirefoxOptions


class PAPermits:
    db = NrcDatabase()
    db.connect()
    target_url = None
    source_ids = [4]
    source_types = ["PA DEP Permit"]
    before_counts = [00]
    after_counts = [0]
    name = "PA DEP Permit00"
    process_number_of_days = 10
    today = datetime.today()
    # war_start = '2023-03-31'
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
                # Initialize a Firefox webdriver
                options = FirefoxOptions()
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-gpu")
                driver = webdriver.Firefox(options=options)
                print("getting driver")
                driver.get(
                    "http://cedatareporting.pa.gov/Reportserver/Pages/ReportViewer.aspx?/Public/DEP/OG/SSRS/Permits_Issued_Detail"
                )
                print("dates:", self.start_date_string, self.today_string)
                from_date = driver.find_element(By.NAME, "ReportViewerControl$ctl04$ctl03$txtValue")
                driver.execute_script(
                    "arguments[0].setAttribute('value', '" + self.start_date_string + "')",
                    from_date,
                )
                to_date = driver.find_element(By.NAME, "ReportViewerControl$ctl04$ctl05$txtValue")
                driver.execute_script(
                    "arguments[0].setAttribute('value', '" + self.today_string + "')",
                    to_date,
                )
                search_form = driver.find_element(By.NAME, "ReportViewerControl$ctl04$ctl00")
                search_form.click()
                # Wait as long as required, or maximum of 30 sec for alert to appear
                WebDriverWait(driver, 40).until(
                    cond.visibility_of_any_elements_located(
                        (By.XPATH, '//table[@role="presentation"]')
                    )
                )
                doc = BeautifulSoup(driver.page_source, "html.parser")
                total_pages = int(
                    doc.find(
                        "span",
                        attrs={"id": "ReportViewerControl_ctl05_ctl00_TotalPages"},
                    ).text
                )
                current_page = 1

                while current_page <= total_pages:
                    print("")
                    print(
                        "processing page ",
                        current_page,
                        " of ",
                        total_pages,
                        datetime.now(tz=None),
                    )
                    doc = BeautifulSoup(driver.page_source, "html.parser")
                    self.process_page(doc)
                    current_page += 1
                    if current_page <= total_pages:
                        go_to_page = driver.find_element(
                            By.ID, "ReportViewerControl_ctl05_ctl00_CurrentPage"
                        )
                        go_to_page.clear()
                        go_to_page.send_keys(str(current_page))
                        go_to_page.send_keys(Keys.ENTER)
                        WebDriverWait(driver, 40).until(
                            cond.element_to_be_clickable(
                                (By.ID, "ReportViewerControl_ctl05_ctl00_CurrentPage")
                            )
                        )
                        doc = BeautifulSoup(driver.page_source, "html.parser")

            except (NoAlertPresentException, TimeoutException) as py_ex:
                print("TimeoutException")
                print(py_ex)
                print(py_ex.args)
                raise
            finally:
                driver.quit()

        except Exception as e:
            print("PAPermits error:", str(e), flush=True)
            raise
        # Finish up
        for num, source_id in enumerate(self.source_ids, start=0):
            self.after_counts[num] = self.db.get_feedentry_count(source_id)["count"]
        email_subj = "PA DEP Permit finished ("
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

    def process_page(self, doc):
        # print('doc:', doc, flush=True)

        try:
            # get all tables
            tbls = doc.find_all("table", attrs={"role": "presentation"})

            # iterate all tables
            for tbl in tbls:
                process_tbl = True
                rows_outer = tbl.find_all("tr", attrs={"valign": "top"})
                for outer_row in rows_outer:
                    # print(156, flush=True)
                    tbl2 = outer_row.find("table", attrs={"cols": "27"})
                    # print(158, tbl2, flush=True)
                    if tbl2 != None:
                        # for tbl2 in tbl2s:
                        rows = tbl2.find_all("tr", attrs={"valign": "top"})
                        # print('155 rows=', len(rows))
                        # if len(rows) == 22:
                        #     print(158, rows, flush=True)
                        cols = []
                        rowx = 0
                        for row in rows:
                            self.num_reads = self.num_reads + 1
                            trans = {}
                            cellx = 0
                            cells = row.find_all("td")
                            for cell in cells:
                                if process_tbl:
                                    # print('cell:', cell, flush=True)
                                    first_div = cell.find("div")
                                    if first_div != None:
                                        second_div = first_div.find("div")
                                        if second_div != None:
                                            # print('second_div:', second_div)
                                            val = second_div.text
                                            # print('171 val:', val)
                                            if rowx == 0:
                                                if cellx == 0:
                                                    if val != "REGION":
                                                        process_tbl = False
                                                # print(173, val, flush=True)
                                                cols.append(val)
                                                # cellx += 1
                                            else:
                                                if process_tbl:
                                                    # print(176, cols, cellx, val, flush=True)
                                                    trans[cols[cellx]] = val
                                cellx += 1
                            # print(191, rowx, cellx,flush=True)
                            if process_tbl:
                                if rowx == 0:
                                    print("180 cols:", cols, flush=True)
                                # else:
                                #     print(185, trans, flush=True)
                                if rowx > 0:
                                    print("", flush=True)
                                    print("191 trans:", trans, flush=True)

                                    REGION = trans["REGION"]
                                    COUNTY = trans["COUNTY"]
                                    MUNICIPALITY = trans["MUNICIPALITY"]
                                    PERMIT_ISSUED_DATE = trans["PERMIT ISSUED DATE"].replace(
                                        "T", " "
                                    )
                                    OPERATOR = trans["OPERATOR"]
                                    APPLICATION_TYPE = trans["APPLICATION TYPE"]
                                    AUTH_TYPE_DESCRIPTION = trans["AUTHORIZATION TYPE"]
                                    WELL_API = trans["API / PERMIT"]
                                    UNCONVENTIONAL = trans["UNCONVENTIONAL"]
                                    CONFIGURATION = trans["CONFIGURATION"]
                                    WELL_TYPE = trans["WELL TYPE"]
                                    FARM_NAME = trans["FARM NAME"]
                                    # SPUD_DATE not always present
                                    # SPUD_DATE = trans['SPUD DATE']
                                    LATITUDE_DECIMAL = trans["LATITUDE DECIMALNAD83"]
                                    LONGITUDE_DECIMAL = trans["LONGITUDE DECIMALNAD83"]
                                    OGO_NUM = trans["OPERATOROGO #"]
                                    # 2023-07-21 commented out the following; not used and creating errors
                                    # OPERATOR_ADDRESS = trans['OPERATOR ADDRESS']
                                    # CITY = trans['CITY']
                                    # STATE = trans['STATE']
                                    # ZIP_CODE = trans['ZIP']
                                    # AUTHORIZATION_ID = trans['AUTHORIZATION ID']
                                    # CLIENT_ID = trans['CLIENT_ID']
                                    PRMRY_FAC_ID = trans["PRIMARY FACILITY ID"]
                                    # MARCELLUS_SHALE_WELL = trans['MARCELLUS_SHALE_WELL']

                                    if CONFIGURATION in (
                                        "Horizontal Well",
                                        "Deviated Well",
                                    ):
                                        horiz = "Y"
                                    else:
                                        horiz = "N"
                                        if CONFIGURATION not in ("Vertical Well",):
                                            print("Unknown PA Configuration: " + CONFIGURATION)

                                    latitude = LATITUDE_DECIMAL
                                    longitude = LONGITUDE_DECIMAL
                                    print(
                                        "WELL_API:",
                                        WELL_API,
                                        " latitude:",
                                        latitude,
                                        " longitude:",
                                        longitude,
                                    )
                                    it = self.db.insertPaPermit(
                                        str(WELL_API), str(latitude), str(longitude)
                                    )

                                    # Use return here if you're just loading PaPermit
                                    # return

                                    if WELL_TYPE == "GAS":
                                        WELL_TYPE = "Gas"
                                    if WELL_TYPE == "OIL":
                                        WELL_TYPE = "Oil"
                                    title = "PA %s Drilling Permit Issued in %s Township" % (
                                        WELL_TYPE,
                                        MUNICIPALITY,
                                    )
                                    incident_datetime = PERMIT_ISSUED_DATE
                                    summary = (
                                        WELL_TYPE
                                        + " permit issued on "
                                        + PERMIT_ISSUED_DATE
                                        + " to "
                                        + OPERATOR
                                        + " for site "
                                        + FARM_NAME
                                        + " in "
                                        + MUNICIPALITY
                                        + " township"
                                        + ", "
                                        + COUNTY
                                        + " county"
                                    )

                                    content = (
                                        "<b>Report Details</b>"
                                        + "<table>"
                                        + "<tr><th>Well Type:</th><td>"
                                        + WELL_TYPE
                                        + "</td></tr>"
                                        + "<tr><th>Permit Issued:</th><td>"
                                        + PERMIT_ISSUED_DATE
                                        + "</td></tr>"
                                        + "<tr><th>Operator:</th><td>"
                                        + OPERATOR
                                        + "</td></tr>"
                                        + "<tr><th>Site Name:</th><td>"
                                        + FARM_NAME
                                        + "</td></tr>"
                                        + "<tr><th>Township:</th><td>"
                                        + MUNICIPALITY
                                        + "</td></tr>"
                                        + "<tr><th>County:</th><td>"
                                        + COUNTY
                                        + "</td></tr>"
                                        + "<tr><th>Permit Type:</th><td>"
                                        + APPLICATION_TYPE
                                        + "</td></tr>"
                                        + "<tr><th>Description:</th><td>"
                                        + AUTH_TYPE_DESCRIPTION
                                        + "</td></tr>"
                                        + "<tr><th>Unconventional:</th><td>"
                                        + UNCONVENTIONAL
                                        + "</td></tr>"
                                        + "<tr><th>Horizontal:</th><td>"
                                        + horiz
                                        + "</td></tr>"
                                        + "<tr><th>Total Depth:</th><td>"
                                        + "</td></tr>"
                                        + "<tr><th>Well API Number:</th><td>"
                                        + WELL_API
                                        + "</td></tr>"
                                        + "<tr><th>OGO Number:</th><td>"
                                        + OGO_NUM
                                        + "</td></tr>"
                                        + "<tr><th>Facility ID:</th><td>"
                                        + PRMRY_FAC_ID
                                        + "</td></tr>"
                                        + "</table>"
                                    )

                                    tags = ["PADEP", "permit", "drilling"]
                                    if UNCONVENTIONAL == "Yes":
                                        tags.append("frack")

                                    # if MARCELLUS_SHALE_WELL == 'Y':
                                    #     tags.append('marcellus')
                                    if WELL_TYPE:
                                        tags.append(WELL_TYPE)

                                    about_url = "http://cedatareporting.pa.gov/Reportserver/Pages/ReportViewer.aspx?/Public/DEP/OG/SSRS/Permits_Issued_Detail"
                                    unique = "%s/%s/%s" % (
                                        summary,
                                        WELL_API,
                                        PERMIT_ISSUED_DATE,
                                    )
                                    # print('unique:', unique)
                                    # feed_entry_id = self.uuid3_str(name=unique.encode('ASCII'))
                                    feed_entry_id = self.uuid3_str(name=unique)
                                    # print('feed_entry_id:', feed_entry_id)
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
                                    # print(summary)
                                    print("", flush=True)
                                    print(298, post_fields, flush=True)
                                    url = config.API_POST_FEEDENTRY
                                    response = requests.post(url, data=post_fields)
                                    print(response.content)

                            rowx += 1

        except Exception as e:
            print("process_page error:", str(e), flush=True)


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = PAPermits()
    it.main(sys.argv[1:])
