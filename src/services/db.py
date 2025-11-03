import os
from stat import *
import config
import psycopg2
from datetime import datetime
import utils

os.environ["PL_API_KEY"] = config.PL_API_KEY
api_key = os.environ.get("PL_API_KEY")


def getNewAlertsForEmails(l, d, n, alerts2_last_published, aoiid, regionid, email):
    conn = None
    feedentry = None
    try:
        select = (
            "select fe.id, fe.title, fe.summary, fe.incident_datetime, fe.published, array_to_string(fe.tags, ', ') "
            + " from feedentry fe "
        )
        where = (
            " WHERE fe.published>'"
            + alerts2_last_published
            + "' AND fe.status='published' "
            + " AND ((email_selection IS NULL AND fe.source_id IN (1,4,5,9)) OR fe.source_id = ANY(email_selection)) "
        )
        if regionid:
            select += (
                " JOIN region reg on reg.id='"
                + str(regionid)
                + "'"
                + " AND ST_Intersects(ST_SetSRID(ST_POINT(fe.lng, fe.lat), 4326), reg.the_geom) "
                + " LEFT JOIN user_with_profile up on up.email = '"
                + email
                + "'"
            )
        else:
            if aoiid:
                select += (
                    ' JOIN "RSSEmailSubscription" rss on rss.id=\''
                    + aoiid
                    + "'"
                    + " AND ST_Intersects(ST_SetSRID(ST_POINT(fe.lng, fe.lat), 4326), rss.geom) "
                    + " LEFT JOIN user_with_profile up on up.email = rss.email "
                )
            else:
                where += (
                    " AND fe.lat>="
                    + bb[0]
                    + " AND fe.lat<="
                    + bb[2]
                    + " AND fe.lng>="
                    + bb[1]
                    + " AND fe.lng<="
                    + bb[3]
                )
        sql = (
            select + where + " ORDER BY fe.incident_datetime DESC" + " LIMIT " + str(n)
        )
        # print('')
        # print('email:', email)
        # print('sql:', sql)
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        conn.set_client_encoding("UTF8")
        cur = conn.cursor()
        cur.execute(sql)
        feedentry = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        utils.email_error("error on getNewAlertsForEmails:" + error)
    finally:
        if conn is not None:
            conn.close()
        return feedentry


def read_subscriptions():
    conn = None
    subs = None
    # AND region_id is null
    # like '%@skytruth.org'
    try:
        sql = """
            SELECT rss.id, rss.aoidescr, rss.email, rss.alerts2_latest_published, rss.lat1, rss.lat2, rss.lng1, rss.lng2, region_id,
                        ST_AsGeoJSON(geom), null as region_geom, rss.alerts2_status, 0 as is_id
                        FROM "RSSEmailSubscription" rss
                        LEFT JOIN user_with_profile up on up.email = rss.email 
                        WHERE confirmed=1 AND active=1 
                        AND 
                        (rss.geom IS NOT NULL AND (SELECT COUNT(*) FROM feedentry WHERE published>rss.alerts2_latest_published AND status='published' 
                    AND ((email_selection IS NULL AND source_id IN (1,4,5,9)) OR source_id = ANY(email_selection))
                    AND ST_Intersects(the_geom, rss.geom)) > 0)
            UNION
            SELECT rss.id, rss.aoidescr, rss.email, rss.alerts2_latest_published, rss.lat1, rss.lat2, rss.lng1, rss.lng2, region_id,
                    ST_AsGeoJSON(geom), ST_AsGeoJSON(reg.simple_geom) as region_geom, rss.alerts2_status, 0 as is_id
                    FROM "RSSEmailSubscription" rss
                    LEFT JOIN region reg on reg.id=rss.region_id
                    LEFT JOIN user_with_profile up on up.email = rss.email 
                    WHERE confirmed=1 AND active=1 AND include_on_tab = true
                    AND 
                ((SELECT COUNT(*) FROM feedentry WHERE published>rss.alerts2_latest_published AND status='published' 
                AND ((email_selection IS NULL AND source_id IN (1,4,5,9)) OR source_id = ANY(email_selection))
                AND ST_Intersects(feedentry.the_geom, reg.the_geom)) > 0)
            UNION
            SELECT rss.id, rss.aoidescr, isub.email, isub.alerts2_latest_published, rss.lat1, rss.lat2, rss.lng1, rss.lng2, rss.region_id,
                        ST_AsGeoJSON(geom), null as region_geom, alerts2_status, isub.id as is_id
                        FROM img_issuesubscriptions isub
                        LEFT JOIN img_issue i ON i.issue_id=isub.issue_id_id
                        LEFT JOIN "RSSEmailSubscription" rss ON rss.id=i.sub_id
                        WHERE isub.status='active' 
                        AND i.sub_id IS NOT NULL
                        AND confirmed=1 AND active=1 
                        AND 
                        (rss.geom IS NOT NULL AND (SELECT COUNT(*) FROM feedentry WHERE published>isub.alerts2_latest_published AND status='published' AND ST_Intersects(the_geom, rss.geom)) > 0)
            UNION
            SELECT rss.id, rss.aoidescr, isub.email, isub.alerts2_latest_published, rss.lat1, rss.lat2, rss.lng1, rss.lng2, rss.region_id,
                        ST_AsGeoJSON(geom), ST_AsGeoJSON(reg.simple_geom) as region_geom, alerts2_status, isub.id as is_id
                        FROM img_issuesubscriptions isub
                        LEFT JOIN img_issue i ON i.issue_id=isub.issue_id_id
                        LEFT JOIN "RSSEmailSubscription" rss ON rss.id=i.sub_id
                        LEFT JOIN region reg ON reg.id=rss.region_id
                        WHERE isub.status='active' 
                        AND i.sub_id IS NOT NULL
                        AND rss.confirmed=1 AND rss.active=1 
                        AND 
                        (rss.region_id IS NOT NULL AND (SELECT COUNT(*) FROM feedentry WHERE published>isub.alerts2_latest_published AND status='published' AND ST_Intersects(the_geom, reg.the_geom)) > 0)
            ORDER BY email
        """
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute(sql)
        subs = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        utils.email_error("error on read_subscriptions:" + error)
    finally:
        if conn is not None:
            conn.close()
        return subs


def read_test_subscriptions(test_email):
    conn = None
    subs = None
    try:
        sql = """
            SELECT rss.id, rss.aoidescr, rss.email, rss.alerts2_latest_published, rss.lat1, rss.lat2, rss.lng1, rss.lng2, region_id,
                        ST_AsGeoJSON(geom), null as region_geom, rss.alerts2_status, 0 as is_id
                        FROM "RSSEmailSubscription" rss
                        LEFT JOIN user_with_profile up on up.email = rss.email 
                        WHERE rss.email='%s' AND confirmed=1 AND active=1 AND include_on_tab=true
                        AND rss.geom IS NOT NULL
            """ % (test_email)
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute(sql)
        subs = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        utils.email_error("error on read_test_subscriptions:" + error)
    finally:
        if conn is not None:
            conn.close()
        return subs


def upd_rss_last_email_sent(aoiid, last_published):
    conn = None
    aoiid = str(aoiid)
    try:
        # self.db.updateEmailSubscription (sub['id'],
        #                     {'last_email_sent': format_datetime(datetime.now()), 'last_item_updated': msg_parts['last_item_updated']})
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        cur = conn.cursor()
        sql = (
            'UPDATE "RSSEmailSubscription" SET alerts2_last_email_sent=now(), alerts2_latest_published='
            + "'"
            + str(last_published)
            + "'"
            + " WHERE id="
            + "'"
            + aoiid
            + "'"
        )
        # print('update:', sql)
        cur.execute(sql)
        # print('1')
        conn.commit()
        # print('2')
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(str(error))
        print("error aoiid:", aoiid, " last_published:", str(last_published))
        print("")
        utils.email_error("error on upd_rss_last_email_sent:" + str(error))
    finally:
        if conn is not None:
            conn.close()


def upd_issuesubscription_last_email_sent(is_id, last_published):
    print("is_id:", is_id, " last_published:", str(last_published))
    conn = None
    is_id = str(is_id)
    try:
        # self.db.updateEmailSubscription (sub['id'],
        #                     {'last_email_sent': format_datetime(datetime.now()), 'last_item_updated': msg_parts['last_item_updated']})
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        cur = conn.cursor()
        sql = (
            "UPDATE img_issuesubscriptions SET alerts2_last_email_sent=now(), alerts2_latest_published="
            + "'"
            + str(last_published)
            + "'"
            + " WHERE id="
            + "'"
            + is_id
            + "'"
        )
        print("update:", sql)
        cur.execute(sql)
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(str(error))
        utils.email_error(
            "error on upd_issuesubscription_last_email_sent:" + str(error)
        )
    finally:
        if conn is not None:
            conn.close()


def get_next_uploaded_tiff():
    conn = None
    next_file = None
    try:
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM file_uploads WHERE status='uploaded' ORDER BY datetime_uploaded LIMIT 1"""
        )
        next_file = cur.fetchone()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        utils.email_error("error on get_last_published:" + error)
    finally:
        if conn is not None:
            conn.close()
        return next_file


def get_file_upload(storage_file_path):
    conn = None
    file_upload = None
    # print(storage_file_path)
    try:
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        cur = conn.cursor()
        sql = """SELECT * FROM file_uploads WHERE storage_file_path='%s' """ % (
            storage_file_path
        )
        # print('sql:', sql)
        cur.execute(sql)
        file_upload = cur.fetchone()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        utils.email_error("error on get_file_upload:" + error)
    finally:
        if conn is not None:
            conn.close()
        return file_upload


def get_next_uploaded_tiff_missing_coords():
    conn = None
    try:
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM file_uploads WHERE status='convertedToTiles' AND latitude IS NULL ORDER BY datetime_uploaded LIMIT 1"""
        )
        next_file = cur.fetchone()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        utils.email_error("error on get_last_published:" + error)
    finally:
        if conn is not None:
            conn.close()
        return next_file


def upd_file_upload(storage_file_path, status, message, latitude=None, longitude=None):
    # print('upd_file_upload:', storage_file_path, status, message, latitude, longitude, flush=True)
    conn = None
    try:
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        cur = conn.cursor()
        if (
            latitude != None
            and latitude != "NULL"
            and longitude != None
            and longitude != "NULL"
        ):
            sql = """UPDATE file_uploads SET status=%s, message=%s, latitude=%s, longitude=%s WHERE storage_file_path=%s"""
            cur.execute(sql, (status, message, latitude, longitude, storage_file_path))
        else:
            sql = """UPDATE file_uploads SET status=%s, message=%s WHERE storage_file_path=%s"""
            cur.execute(sql, (status, message, storage_file_path))
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        utils.email_error("error on upd_feedentry_tags:" + error)
    finally:
        if conn is not None:
            conn.close()


def insert_file_upload(
    storage_file_path,
    status,
    message,
    email,
    user_id,
    file_name,
    storage_bucket,
    latitude=None,
    longitude=None,
):
    # print('insert_file_upload:', storage_file_path, status, message, latitude, longitude, flush=True)
    conn = None
    try:
        dt = datetime.now()
        conn = psycopg2.connect(config.ALERTS2_CONNECTION_STRING)
        cur = conn.cursor()
        # if latitude != None and latitude != "NULL" and longitude != None and longitude != "NULL":
        sql = """
        INSERT INTO public.file_uploads(
        storage_bucket, file_name, email, user_id, status, datetime_uploaded, storage_file_path, file_size, latitude, longitude, message, file_label)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        cur.execute(
            sql,
            (
                storage_bucket,
                file_name,
                email,
                user_id,
                status,
                dt,
                storage_file_path,
                0,
                latitude,
                longitude,
                message,
                file_name,
            ),
        )
        # else:
        #     sql = '''UPDATE file_uploads SET status=%s, message=%s WHERE storage_file_path=%s'''
        #     cur.execute(sql, (status, message, storage_file_path))
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        utils.email_error("error on insert_file_upload:" + error)
    finally:
        if conn is not None:
            conn.close()
