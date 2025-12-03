import sys
import uuid
from datetime import datetime, timedelta
from os.path import *

import requests

sys.path.insert(0, "../")
from src.utils.db import NrcDatabase
from bs4 import BeautifulSoup
from src.utils import config
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as cond
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options as FirefoxOptions


class PAPermits:
    db = NrcDatabase()
    db.connect()
    target_url = None
    source_ids = [5]
    source_types = ["PA DEP SPUD"]
    before_counts = [00]
    after_counts = [0]
    name = "PA DEP SPUD"
    process_number_of_days = 12
    today = datetime.today()
    today_string = today.strftime("%m/%d/%Y")
    start_date = today - timedelta(days=int(process_number_of_days))
    start_date_string = start_date.strftime("%m/%d/%Y")
    num_reads = 0
    scraped_webpage_url = "http://cedatareporting.pa.gov/Reportserver/Pages/ReportViewer.aspx?/Public/DEP/OG/SSRS/Spud_External_Data"

    def main(self, args):
        try:
            for num, source_id in enumerate(self.source_ids, start=0):
                self.before_counts[num] = self.db.get_feedentry_count(source_id)["count"]

            try:
                options = FirefoxOptions()
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-gpu")
                driver = webdriver.Firefox(options=options)
                # Initialize a Firefox webdriver
                print("getting driver")
                # Grab the web page
                driver.get(self.scraped_webpage_url)
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
                print("submit")
                search_form = driver.find_element(By.NAME, "ReportViewerControl$ctl04$ctl00")
                search_form.click()
                # Wait as long as required, or maximum of 30 sec for alert to appear
                WebDriverWait(driver, 30).until(
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
                        WebDriverWait(driver, 30).until(
                            cond.element_to_be_clickable(
                                (By.ID, "ReportViewerControl_ctl05_ctl00_CurrentPage")
                            )
                        )
                        doc = BeautifulSoup(driver.page_source, "html.parser")

            except (NoAlertPresentException, TimeoutException) as py_ex:
                print("TimeoutException")
                print(py_ex)
                print(py_ex.args)
            except Exception as ex:
                print("Some other exception occurred:")
                print(ex)
            finally:
                driver.quit()

        except Exception as e:
            print("Main PA DEP SPUD Exception:", e)

        # Finish up
        for num, source_id in enumerate(self.source_ids, start=0):
            self.after_counts[num] = self.db.get_feedentry_count(source_id)["count"]
        email_subj = "PA DEP SPUD finished ("
        for num, source_id in enumerate(self.source_ids, start=0):
            print(
                "source_id:",
                source_id,
                " before:",
                int(self.before_counts[num]),
                " after:",
                int(self.after_counts[num]),
                " total added:",
                int(self.after_counts[num] - self.before_counts[num]),
            )
            email_subj += (
                "source_id:"
                + repr(source_id)
                + " "
                + repr(int(self.after_counts[num] - self.before_counts[num]))
                + " added  "
            )
        email_subj += ")"

    def uuid3_str(self, namespace=uuid.NAMESPACE_URL, name=None):
        return self.uuid_str(uuid.uuid3(namespace, name))

    def uuid_str(self, uuid_obj):
        s = uuid_obj.hex
        return "-".join([s[0:8], s[8:12], s[12:16], s[16:20], s[20:]])

    def process_page(self, doc):
        try:
            tbl = doc.find("table", attrs={"cols": "14"})
            try:
                rows = tbl.find_all("tr", attrs={"valign": "top"})
            except Exception as e:
                print(e)
                return
            print("rows=", len(rows), datetime.now(tz=None))
            cols = []
            rowx = 0
            for row in rows:
                self.num_reads = self.num_reads + 1
                trans = {}
                cellx = 0
                cells = row.find_all("td")
                for cell in cells:
                    first_div = cell.find("div")
                    if first_div != None:
                        second_div = first_div.find("div")
                        if second_div != None:
                            val = second_div.text
                            if rowx == 0:
                                cols.append(val)
                            else:
                                trans[cols[cellx]] = val
                    cellx += 1
                print("")
                print("trans:", trans)
                if rowx > 0:
                    SPUD_DATE = trans["SPUD DATE"]
                    API = trans["API / PERMIT"]
                    OGO_NUM = trans[" OGO #"]
                    OPERATOR = trans["OPERATOR"]
                    REGION = trans["REGION"]
                    COUNTY = trans["COUNTY"]
                    MUNICIPALITY = trans["MUNICIPALITY"]
                    FARM_NAME = trans["FARM NAME"]
                    LATITUDE = trans["LATITUDE"]
                    LONGITUDE = trans["LONGITUDE"]
                    UNCONVENTIONAL = trans["UNCONVENTIONAL"]

                    print("api_permit:", API, " found ", LATITUDE, LONGITUDE)
                    incident_datetime = SPUD_DATE
                    title = "%s Reports Drilling Started (SPUD) in %s Township" % (
                        OPERATOR,
                        MUNICIPALITY,
                    )

                    if OPERATOR == None:
                        OPERATOR = ""
                    if SPUD_DATE == None:
                        SPUD_DATE = ""
                    if FARM_NAME == None:
                        FARM_NAME = ""
                    if MUNICIPALITY == None:
                        MUNICIPALITY = ""
                    if COUNTY == None:
                        COUNTY = ""
                    summary = (
                        "%s reports drilling started on %s at site %s in %s township, %s county"
                        % (OPERATOR, SPUD_DATE, FARM_NAME, MUNICIPALITY, COUNTY)
                    )
                    print("summary:", summary)
                    content = (
                        "<b>Report Details</b>"
                        + '<table width = "100%"><tr><th>Operator: </th><td>'
                        + OPERATOR
                        + "</td></tr>"
                        + "<tr><th>SPUD Date: </th><td>"
                        + SPUD_DATE
                        + "</td></tr>"
                        + "<tr><th>Township: </th><td>"
                        + MUNICIPALITY
                        + "</td></tr>"
                        + "<tr><th>County: </th><td>"
                        + COUNTY
                        + "</td></tr>"
                        + "<tr><th>Unconventional: </th><td>"
                        + UNCONVENTIONAL
                        + "</td></tr>"
                        + "<tr><th>Well API Number: </th><td>"
                        + API
                        + "</td></tr>"
                        + "<tr><th>OGO Number: </th><td>"
                        + OGO_NUM
                        + "</td></tr>"
                        + "<tr><th>Region: </th><td>"
                        + REGION
                        + "</td></tr>"
                        + "</table>"
                    )
                    tags = ["PADEP", "frack", "spud", "drilling"]
                    unique = "%s %s" % (API, SPUD_DATE)
                    feed_entry_id = self.uuid3_str(name=unique)
                    post_fields = {
                        "id": feed_entry_id,
                        "title": title,
                        "link": self.scraped_webpage_url,
                        "summary": summary,
                        "content": content,
                        "lat": LATITUDE,
                        "lng": LONGITUDE,
                        "source_id": self.source_ids[0],
                        "kml_url": "",
                        "incident_datetime": incident_datetime,
                        "tags": tags,
                        "status": "published",
                    }

                    print("post_fields:", post_fields)
                    print(summary)
                    url = config.API_POST_FEEDENTRY
                    response = requests.post(url, data=post_fields)
                    print(response.content)

                rowx += 1

        except Exception as e:
            print("Process Page PA DEP SPUD Exception:", e)


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = PAPermits()
    it.main(sys.argv[1:])
