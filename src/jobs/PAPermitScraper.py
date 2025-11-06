# PA Well Permit Scraper
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re
from datetime import datetime, timedelta
import uuid
import requests
from xml.etree import ElementTree
import sys

sys.path.insert(0, "../")
from database import NrcDatabase


class PAPermitScraper:
    db = NrcDatabase()
    db.connect()
    target_url = None
    source_id = 4

    def write_rawdata(self, rawdata):
        date_fmt = "%Y_%m_%d_%H:%M"
        f = open("rawdata/pa_permits_" + datetime.today().strftime((date_fmt)) + ".xml", "w")
        f.write(rawdata)

    def parse_atom_field(self, field):
        tag = re.sub("\{.*\}", "", field.tag)
        if tag == "content" and field.get("type") == "application/xml":
            self.parse_xml_properties(field)

    # @staticmethod
    def uuid3_str(self, namespace=uuid.NAMESPACE_URL, name=None):
        return self.uuid_str(uuid.uuid3(namespace, name))

    # @staticmethod
    def uuid_str(self, uuid_obj):
        s = uuid_obj.hex
        return "-".join([s[0:8], s[8:12], s[12:16], s[16:20], s[20:]])

    def parse_xml_properties(self, element):
        try:
            properties = {}
            P_START_DATE = None
            P_END_DATE = None
            P_COUNTY = None
            P_MUNICIPALITY = None
            P_REGION = None
            P_SEARCH_NAME = None
            P_UNCONVENTIONAL = None
            P_WELL_TYPE = None
            REGION = None
            COUNTY = None
            MUNICIPALITY = None
            PERMIT_ISSUED_DATE = None
            OPERATOR = None
            APPLICATION_TYPE = None
            AUTH_TYPE_DESCRIPTION = None
            WELL_API = None
            UNCONVENTIONAL = None
            CONFIGURATION = None
            WELL_TYPE = None
            FARM_NAME = None
            SPUD_DATE = None
            LATITUDE_DEGREES = None
            LONGITUDE_DEGREES = None
            LATITUDE_DECIMAL = None
            LONGITUDE_DECIMAL = None
            OGO_NUM = None
            OPERATOR_ADDRESS = None
            CITY = None
            STATE = None
            ZIP_CODE = None
            AUTHORIZATION_ID = None
            CLIENT_ID = None
            PRMRY_FAC_ID = None
            MARCELLUS_SHALE_WELL = None
            for child in element:
                for p in child.getiterator():
                    # print(p.tag, p.text)
                    p.tag = p.tag[p.tag.find("}") + 1 :]
                    if p.tag == "P_START_DATE":
                        P_START_DATE = p.text
                    if p.tag == "P_END_DATE":
                        P_END_DATE = p.text
                    if p.tag == "P_COUNTY":
                        P_COUNTY = p.text
                    if p.tag == "P_MUNICIPALITY":
                        P_MUNICIPALITY = p.text
                    if p.tag == "P_REGION":
                        P_REGION = p.text
                    if p.tag == "P_SEARCH_NAME":
                        P_SEARCH_NAME = p.text
                    if p.tag == "P_UNCONVENTIONAL":
                        P_UNCONVENTIONAL = p.text
                    if p.tag == "P_WELL_TYPE":
                        P_WELL_TYPE = p.text
                    if p.tag == "REGION":
                        REGION = p.text
                    if p.tag == "COUNTY":
                        COUNTY = p.text
                    if p.tag == "MUNICIPALITY":
                        MUNICIPALITY = p.text
                    if p.tag == "PERMIT_ISSUED_DATE":
                        PERMIT_ISSUED_DATE = p.text.replace("T", " ")
                    if p.tag == "OPERATOR":
                        OPERATOR = p.text
                    if p.tag == "APPLICATION_TYPE":
                        APPLICATION_TYPE = p.text
                    if p.tag == "AUTH_TYPE_DESCRIPTION":
                        AUTH_TYPE_DESCRIPTION = p.text
                    if p.tag == "WELL_API":
                        WELL_API = p.text
                    if p.tag == "UNCONVENTIONAL":
                        UNCONVENTIONAL = p.text
                    if p.tag == "CONFIGURATION":
                        CONFIGURATION = p.text
                    if p.tag == "WELL_TYPE":
                        WELL_TYPE = p.text
                    if p.tag == "FARM_NAME":
                        FARM_NAME = p.text
                    if p.tag == "SPUD_DATE":
                        SPUD_DATE = p.text
                    if p.tag == "LATITUDE_DEGREES":
                        LATITUDE_DEGREES = p.text
                    if p.tag == "LONGITUDE_DEGREES":
                        LONGITUDE_DEGREES = p.text
                    if p.tag == "LATITUDE_DECIMAL":
                        LATITUDE_DECIMAL = p.text
                    if p.tag == "LONGITUDE_DECIMAL":
                        LONGITUDE_DECIMAL = p.text
                    if p.tag == "OGO_NUM":
                        OGO_NUM = p.text
                    if p.tag == "OPERATOR_ADDRESS":
                        OPERATOR_ADDRESS = p.text
                    if p.tag == "CITY":
                        CITY = p.text
                    if p.tag == "STATE":
                        STATE = p.text
                    if p.tag == "ZIP_CODE":
                        ZIP_CODE = p.text
                    if p.tag == "AUTHORIZATION_ID":
                        AUTHORIZATION_ID = p.text
                    if p.tag == "CLIENT_ID":
                        CLIENT_ID = p.text
                    if p.tag == "PRMRY_FAC_ID":
                        PRMRY_FAC_ID = p.text
                    if p.tag == "MARCELLUS_SHALE_WELL":
                        MARCELLUS_SHALE_WELL = p.text

            if CONFIGURATION in ("Horizontal Well", "Deviated Well"):
                horiz = "Y"
            else:
                horiz = "N"
                if CONFIGURATION not in ("Vertical Well",):
                    print("Unknown PA Configuration: " + CONFIGURATION)

            latitude = LATITUDE_DECIMAL
            longitude = LONGITUDE_DECIMAL
            print("WELL_API:", WELL_API, " latitude:", latitude, " longitude:", longitude)
            it = self.db.insertPaPermit(str(WELL_API), str(latitude), str(longitude))

            # Use return here if you're just loading PaPermit
            # return

            if WELL_TYPE == "GAS":
                WELL_TYPE = "Gas"
            if WELL_TYPE == "OIL":
                WELL_TYPE = "Oil"
            title = "PA %s Drilling Permit Issued in %s Township" % (WELL_TYPE, MUNICIPALITY)
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

            tags = ["PADEP", "frack", "permit", "drilling"]

            if MARCELLUS_SHALE_WELL == "Y":
                tags.append("marcellus")
            if WELL_TYPE:
                tags.append(WELL_TYPE)

            about_url = "http://www.depreportingservices.state.pa.us/ReportServer/Pages/ReportViewer.aspx?/Oil_Gas/Permits_Issued_Detail"
            unique = "%s/%s/%s" % (summary, WELL_API, PERMIT_ISSUED_DATE)
            feed_entry_id = self.uuid3_str(name=unique.encode("ASCII"))

            post_fields = {
                "id": feed_entry_id,
                "title": title,
                "link": about_url,
                "summary": summary,
                "content": content,
                "lat": latitude,
                "lng": longitude,
                "source_id": 4,
                "kml_url": "",
                "incident_datetime": incident_datetime,
                "tags": tags,
                "status": "published",
            }
            print(summary)
            url = settings.API_POST_FEEDENTRY
            response = requests.post(url, data=post_fields)
            print(response.content)

        except Exception as e:
            print("Exception in parse_xml_properties:", e)

    def process_item(self):
        try:
            before_count = self.db.get_feedentry_count(self.source_id)["count"]
            to_date = datetime.today()
            from_date = to_date - timedelta(days=int(15))
            # Use these dates for bringing over img_papermit. Start by adding 1000 to existing to_date timedelta.
            # to_date = to_date - timedelta(days=int(7500))
            # from_date = to_date - timedelta(days=int(1000))

            # target_url_start = "http://www.depreportingservices.state.pa.us/ReportServer?%2FOil_Gas%2FPermits_Issued_Detail&P_COUNTY%3Aisnull=True&P_MUNICIPALITY%3Aisnull=True&P_SEARCH_NAME%3Aisnull=True&rs%3AParameterLanguage=&rs%3ACommand=Render&rs%3AFormat=ATOM&rc%3ADataFeed=xAx0x0"
            target_url_start = "http://cedatareporting.pa.gov/ReportServer?%2FOil_Gas%2FPermits_Issued_Detail&P_COUNTY%3Aisnull=True&P_MUNICIPALITY%3Aisnull=True&P_SEARCH_NAME%3Aisnull=True&rs%3AParameterLanguage=&rs%3ACommand=Render&rs%3AFormat=ATOM&rc%3ADataFeed=xAx0x0"
            # target_url_start = "http://cedatareporting.pa.gov/Reportserver/Pages/ReportViewer.aspx?/Public/DEP/OG/SSRS/Permits_Issued_Detail
            date_fmt = "%m/%d/%Y 23:59:59"
            self.target_url = "%s&P_START_DATE=%s&P_END_DATE=%s" % (
                target_url_start,
                from_date.strftime(date_fmt),
                to_date.strftime(date_fmt),
            )
            print("target_url:", self.target_url)
            response = requests.get(self.target_url)
            feed = ElementTree.XML(response.content)
            self.write_rawdata(response.content)

            for entry in feed.findall("{http://www.w3.org/2005/Atom}entry"):
                for field in entry:
                    print("field:", field.tag, field.text)
                    self.parse_atom_field(field)

            after_count = self.db.get_feedentry_count(self.source_id)["count"]
            print("before:", before_count)
            print("after:", after_count)
            print("total added:", (before_count - after_count))
        except Exception as e:
            print("Exception in process_item:", e)


# /* ======================================================================= */#
# /*     Commandline Execution
# /* ======================================================================= */#

if __name__ == "__main__":
    it = PAPermitScraper()
    it.process_item()
