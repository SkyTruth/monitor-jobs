import os
import re
import sys
import unicodedata
from email.mime.text import MIMEText
from smtplib import SMTP
from urllib.parse import parse_qs, urlparse

from src.utils import config
from src.utils import db
from src.utils.config import ALERTS2_API_URL
from jinja2 import Environment
import logging

logging.basicConfig(level=logging.INFO)

filein = open("src/templates/index.html")
TEMPLATE = filein.read()

last_arg = ""
test_email = None
for arg in sys.argv:
    if last_arg == "-test":
        test_email = arg
    last_arg = arg
logging.info(f"test email is {test_email}")


def strip_accents(text):
    try:
        text = unicode(text, "utf-8")
    except NameError:
        pass
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
    return str(text)


if __name__ == "__main__":
    try:
        if test_email:
            subs = db.read_test_subscriptions(test_email)
        else:
            subs = db.read_subscriptions()
        logging.info(f"number of subscriptions with new alerts: {len(subs)}")
    except Exception as e:
        logging.error(f"Error getting subscriptions: {e}")

    emails_sent = 0
    dates_updated = 0
    total_alerts_included = 0

    for sub in subs:
        l = str(sub[4]) + ":" + str(sub[6]) + ":" + str(sub[5]) + ":" + str(sub[7])
        d = 50
        n = 100
        aoidescr = strip_accents(sub[1])
        aoiid = str(sub[0])
        email = str(sub[2])
        if email != "ethan@skytruth.org" and email != "will@skytruth.org":
            continue

        alerts2_latest_published = "2018-10-01"
        if test_email == None:
            if sub[3] != None:
                alerts2_latest_published = str(sub[3])[:23]
        regionid = sub[8]
        alerts2_status = sub[11]
        is_id = sub[12]
        fes = db.getNewAlertsForEmails(l, d, n, alerts2_latest_published, aoiid, regionid, email)
        if fes != None and len(fes) > 0:
            try:
                last_published = "2018-01-01"
                fe_count = 0
                for feedentry in fes:
                    fe_lp = str(feedentry[4])[0:23]
                    if fe_lp > last_published:
                        last_published = fe_lp
                    fe_count = fe_count + 1
                title = "New Alerts found in this Area of Interest "
                html_message_items = []
                text_message_items = []
                email = str(sub[2])
                params = {}
                map_height = 215
                map_width = 500

                try:
                    params["static_map_url"] = f"{ALERTS2_API_URL}aoi_static_map/{aoiid}"
                except:
                    params["static_map_url"] = ""
                params["static_map_width"] = map_width
                params["static_map_height"] = map_height
                msg = MIMEText(
                    Environment()
                    .from_string(TEMPLATE)
                    .render(
                        title=title,
                        aoidescr=aoidescr,
                        fes=fes,
                        mapurl=params["static_map_url"],
                        subscription_id=aoiid,
                        email=email,
                        count=fe_count,
                    ),
                    "html",
                )
                msg["Subject"] = "Found " + str(fe_count) + " new SkyTruth Alerts in " + aoidescr
                msg["From"] = "alerts@skytruth.org"
                if test_email:
                    msg["To"] = test_email
                else:
                    msg["To"] = email
                msg["Bcc"] = "tech@skytruth.org"
                user = config.MANDRILL_FROM
                pwd = config.MANDRILL_PASS
                server = config.MANDRILL_HOST
                server_port = config.MANDRILL_PORT

                try:
                    if emails_sent < 2000:
                        server = SMTP(server, server_port)
                        server.ehlo()
                        server.starttls()
                        server.login(user, pwd)
                        server.sendmail(msg["Subject"], [msg["To"]], msg.as_string())
                        server.close()
                        logging.info(
                            f"successfully sent the mail to {email} updating {aoiid} {aoidescr}"
                        )
                        emails_sent = emails_sent + 1
                        total_alerts_included = total_alerts_included + fe_count
                        dates_updated = dates_updated + 1
                        if is_id == 0:
                            db.upd_rss_last_email_sent(str(aoiid), str(last_published))
                        if is_id > 0:
                            db.upd_issuesubscription_last_email_sent(
                                str(is_id), str(last_published)
                            )
                except Exception as exception:
                    exc_info = sys.exc_info()
                    exc_type, exc_obj, exc_tb = exc_info
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    error = (
                        "failed to send mail to ",
                        msg["To"],
                        str(exception),
                        str(exc_type),
                        str(fname),
                        str(exc_tb.tb_lineno),
                        " see logfile for more info",
                    )
                    logging.error(error)

            except Exception as exception2:
                exc_info = sys.exc_info()
                exc_type, exc_obj, exc_tb = exc_info
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                error = (
                    "Exception while creating email for " + email + ": ",
                    str(exception2),
                    str(exc_type),
                    str(fname),
                    str(exc_tb.tb_lineno),
                    " see logfile for more info",
                )
                logging.error(error)
                try:
                    logging.info("mapurl: " + params["static_map_url"])
                except:
                    logging.info("no mapurl yet")
                logging.info("fe_count: " + str(fe_count))
