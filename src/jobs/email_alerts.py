# This Python file uses the following encoding: utf-8
import db
from config import ALERTS2_API_URL
from smtplib import SMTP  # sending email
from jinja2 import Environment  # Jinja2 templating
from urllib.parse import urlparse, parse_qs
import re
import config
import sys
import os
from email.mime.text import MIMEText
import unicodedata


# open the file
filein = open("templates/index.html")
# read it
TEMPLATE = filein.read()

last_arg = ""
test_email = None
for arg in sys.argv:
    if last_arg == "-test":
        test_email = arg
    last_arg = arg
print("test email is ", test_email)


def compose_item_message(self, item, msg_templates):
    params = {}
    params["link"] = item["links"][0]["href"]
    params["title"] = item["title"]
    params["summary"] = item["summary"]
    tags = ""
    if "tags" in item:
        for t in item["tags"]:
            if tags != "":
                tags = tags + ", "
            tags = tags + t["term"]
            # tags.append(t['term'])
    params["tags"] = ", ".join(tags)

    print("params:", params)
    html_msg = msg_templates["html"]["item"].substitute(params)
    text_msg = msg_templates["text"]["item"].substitute(params)
    return {"text": text_msg, "html": html_msg}


def format_tags(item):
    # print('feedentry:', item)
    tags = ""
    # if 'tags' in item:
    try:
        for tag in tags:
            if tags != "":
                tags = tags + ", "
            # print('t:', tag)
        tags = tags + tag
        # tags.append(t['term'])
        # params['tags'] = ', '.join(tags)
        # print ('format_tags:', item, tags)
        return tags
    except error:
        print("format_tags error:", error)
        return item


def parse_rss_url(url):
    p = urlparse(url)
    q = parse_qs(p.query)

    for k in q.keys():
        q[k] = q[k][0]

    bounds = None

    # convert "l" to "bounds"
    l = q.get("l")
    if l:
        coords = re.split("[:,]", l)
        if len(coords) == 4:
            bounds = [
                [min(coords[0], coords[2]), min(coords[1], coords[3])],
                [max(coords[0], coords[2]), max(coords[1], coords[3])],
            ]
    # convert "BBOX" to "bounds"
    bbox = q.get("BBOX")
    if bbox:
        coords = re.split("[:,]", bbox)
        if len(coords) == 4:
            bounds = [
                [min(coords[1], coords[3]), min(coords[0], coords[2])],
                [max(coords[1], coords[3]), max(coords[0], coords[2])],
            ]

    if bounds:
        q["bounds"] = bounds

    return q


def strip_accents(text):
    try:
        text = unicode(text, "utf-8")
    except NameError:  # unicode is a default on python 3
        pass
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
    return str(text)


if __name__ == "__main__":
    try:
        if test_email:
            subs = db.read_test_subscriptions(test_email)
        else:
            subs = db.read_subscriptions()
        print("number of subscriptions with new alerts:", len(subs))
    except Exception as e:
        print("Error getting subscriptions:", e)

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

        alerts2_latest_published = "2018-10-01"  # last_published
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
                    fe_lp = str((feedentry[4]))[0:23]
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
                        print(
                            "successfully sent the mail to " + email + " updating " + aoiid,
                            aoidescr,
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
                    print("error:", error)
                    print("title:", title)
                    print("aoidescr:", aoidescr)
                    print("subscription_id:", aoiid)
                    print("mapurl:", params["static_map_url"])
                    print("fe_count:", fe_count)

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
                print("error:", error)
                print("title:", title)
                print("aoidescr:", aoidescr)
                print("subscription_id:", aoiid)
                try:
                    print("mapurl:", params["static_map_url"])
                except:
                    print("no mapurl yet")
                print("fe_count:", fe_count)
