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
import logging

logging.basicConfig(level=logging.INFO)


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
    today_string = today.strftime("%m/%d/%Y")
    start_date = today - timedelta(days=int(process_number_of_days))
    start_date_string = start_date.strftime("%m/%d/%Y")
    num_reads = 0
    scraped_webpage_url = "http://cedatareporting.pa.gov/Reportserver/Pages/ReportViewer.aspx?/Public/DEP/OG/SSRS/Permits_Issued_Detail"

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
                logging.info("getting driver")
                driver.get(self.scraped_webpage_url)
                logging.info(f"dates: {self.start_date_string} to {self.today_string}")
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
                    logging.info(
                        f"processing page {current_page} of {total_pages} {datetime.now(tz=None)}"
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
                logging.exception(
                    "Selenium Webdriver Timed out while processing page. Quitting driver..."
                )
                raise
            finally:
                driver.quit()

        except Exception as e:
            logging.error(f"PAPermits error: {str(e)}")
            raise
        # Finish up
        for num, source_id in enumerate(self.source_ids, start=0):
            self.after_counts[num] = self.db.get_feedentry_count(source_id)["count"]
        for num, source_id in enumerate(self.source_ids, start=0):
            logging.info(
                f"{source_id} before: {int(self.before_counts[num])} after: {int(self.after_counts[num])} total added: {int(self.after_counts[num] - self.before_counts[num])}"
            )

    def uuid3_str(self, namespace=uuid.NAMESPACE_URL, name=None):
        return self.uuid_str(uuid.uuid3(namespace, name))

    def uuid_str(self, uuid_obj):
        s = uuid_obj.hex
        return "-".join([s[0:8], s[8:12], s[12:16], s[16:20], s[20:]])

    def process_page(self, doc):
        try:
            # get all tables
            tbls = doc.find_all("table", attrs={"role": "presentation"})

            # iterate all tables
            for tbl in tbls:
                process_tbl = True
                rows_outer = tbl.find_all("tr", attrs={"valign": "top"})
                for outer_row in rows_outer:
                    tbl2 = outer_row.find("table", attrs={"cols": "27"})
                    if tbl2 != None:
                        rows = tbl2.find_all("tr", attrs={"valign": "top"})
                        cols = []
                        rowx = 0
                        for row in rows:
                            self.num_reads = self.num_reads + 1
                            trans = {}
                            cellx = 0
                            cells = row.find_all("td")
                            for cell in cells:
                                if process_tbl:
                                    first_div = cell.find("div")
                                    if first_div != None:
                                        second_div = first_div.find("div")
                                        if second_div != None:
                                            val = second_div.text
                                            if rowx == 0:
                                                if cellx == 0:
                                                    if val != "REGION":
                                                        process_tbl = False
                                                cols.append(val)
                                            else:
                                                if process_tbl:
                                                    trans[cols[cellx]] = val
                                cellx += 1
                            if process_tbl:
                                if rowx > 0:
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
                                    LATITUDE_DECIMAL = trans["LATITUDE DECIMALNAD83"]
                                    LONGITUDE_DECIMAL = trans["LONGITUDE DECIMALNAD83"]
                                    OGO_NUM = trans["OPERATOROGO #"]
                                    PRMRY_FAC_ID = trans["PRIMARY FACILITY ID"]

                                    if CONFIGURATION in (
                                        "Horizontal Well",
                                        "Deviated Well",
                                    ):
                                        horiz = "Y"
                                    else:
                                        horiz = "N"
                                        if CONFIGURATION not in ("Vertical Well",):
                                            pass

                                    latitude = LATITUDE_DECIMAL
                                    longitude = LONGITUDE_DECIMAL
                                    logging.info(
                                        f"WELL_API: {WELL_API} latitude: {latitude} longitude: {longitude}"
                                    )
                                    self.db.insertPaPermit(
                                        str(WELL_API), str(latitude), str(longitude)
                                    )

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
                                    if WELL_TYPE:
                                        tags.append(WELL_TYPE)

                                    unique = "%s/%s/%s" % (
                                        summary,
                                        WELL_API,
                                        PERMIT_ISSUED_DATE,
                                    )
                                    feed_entry_id = self.uuid3_str(name=unique)
                                    post_fields = {
                                        "id": feed_entry_id,
                                        "title": title,
                                        "link": self.scraped_webpage_url,
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
                                    url = config.API_POST_FEEDENTRY
                                    response = requests.post(url, data=post_fields)
                                    logging.info(f"Response: {response.content}")

                            rowx += 1

        except Exception as e:
            logging.error(
                f"PA Permit scraper failed to process {summary} page with error, {str(e)}"
            )


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = PAPermits()
    it.main(sys.argv[1:])
