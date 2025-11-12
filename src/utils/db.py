import logging
import os
import uuid
from datetime import datetime
from stat import *

from src.utils import config
import psycopg2

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)
from src.utils.items import NrcItem
from psycopg2.extras import RealDictCursor as DictCursor
from scrapy import exceptions

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
        sql = select + where + " ORDER BY fe.incident_datetime DESC" + " LIMIT " + str(n)
        # print('')
        # print('email:', email)
        # print('sql:', sql)
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
        conn.set_client_encoding("UTF8")
        cur = conn.cursor()
        cur.execute(sql)
        feedentry = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
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
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute(sql)
        subs = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
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
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute(sql)
        subs = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
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
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
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
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
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
    finally:
        if conn is not None:
            conn.close()


def get_next_uploaded_tiff():
    conn = None
    next_file = None
    try:
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM file_uploads WHERE status='uploaded' ORDER BY datetime_uploaded LIMIT 1"""
        )
        next_file = cur.fetchone()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
        return next_file


def get_file_upload(storage_file_path):
    conn = None
    file_upload = None
    # print(storage_file_path)
    try:
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
        cur = conn.cursor()
        sql = """SELECT * FROM file_uploads WHERE storage_file_path='%s' """ % (storage_file_path)
        # print('sql:', sql)
        cur.execute(sql)
        file_upload = cur.fetchone()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
        return file_upload


def get_next_uploaded_tiff_missing_coords():
    conn = None
    try:
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM file_uploads WHERE status='convertedToTiles' AND latitude IS NULL ORDER BY datetime_uploaded LIMIT 1"""
        )
        next_file = cur.fetchone()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
        return next_file


def upd_file_upload(storage_file_path, status, message, latitude=None, longitude=None):
    # print('upd_file_upload:', storage_file_path, status, message, latitude, longitude, flush=True)
    conn = None
    try:
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
        cur = conn.cursor()
        if latitude != None and latitude != "NULL" and longitude != None and longitude != "NULL":
            sql = """UPDATE file_uploads SET status=%s, message=%s, latitude=%s, longitude=%s WHERE storage_file_path=%s"""
            cur.execute(sql, (status, message, latitude, longitude, storage_file_path))
        else:
            sql = """UPDATE file_uploads SET status=%s, message=%s WHERE storage_file_path=%s"""
            cur.execute(sql, (status, message, storage_file_path))
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
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
        conn = psycopg2.connect(config.DB_CONNECTION_STRING)
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
    finally:
        if conn is not None:
            conn.close()


class NrcDatabase:
    @staticmethod
    def uuid_str(uuid_obj):
        s = uuid_obj.hex
        return "-".join([s[0:8], s[8:12], s[12:16], s[16:20], s[20:]])

    @staticmethod
    def uuid3_str(namespace=uuid.NAMESPACE_URL, name=None):
        return NrcDatabase.uuid_str(uuid.uuid3(namespace, name))

    @staticmethod
    def uuid4_str():
        return NrcDatabase.uuid_str(uuid.uuid4())

    @staticmethod
    def uuid5_str(namespace=uuid.NAMESPACE_URL, name=None):
        return NrcDatabase.uuid_str(uuid.uuid5(namespace, name))

    def __init__(self):
        print("NrcDatabase __init__")
        self.db_connection_string = settings.DB_CONNECTION_STRING
        self.host = settings.DB_HOST
        self.user = settings.DB_USER
        self.passwd = settings.DB_PASS
        self.dbname = settings.DB_DATABASE
        self.db = None
        psycopg2.extras.register_uuid()
        self.table_keyfields = {}
        # print('NrcDatabase __init__ 2')

    def connect(self):
        try:
            self.db = psycopg2.connect(self.db_connection_string)
            self.db.autocommit = True
            logging.info(
                "Connected to database %s as %s using database %s"
                % (self.host, self.user, self.dbname)
            )
        except psycopg2.Error as e:
            self.db = None
            logging.INFO("Unable to connect to database: Error %s" % (e,), level=logging.ERROR)
            raise

    def match_PA_permit(self, api_number):
        c = self.db.cursor(cursor_factory=DictCursor)
        sql = (
            "SELECT lat,lng FROM feedentry WHERE source_id=4 AND content LIKE '%"
            + api_number
            + "%' LIMIT 1"
        )
        c.execute(sql)
        # print('c.fetchone:', one) #c.fetchone())
        return c.fetchone()

    def get_feedentry_count(self, source_id):
        c = self.db.cursor(cursor_factory=DictCursor)
        sql = "SELECT COUNT(*) FROM feedentry WHERE source_id=%s"
        c.execute(sql, (source_id,))
        # print('c.fetchone:', one) #c.fetchone())
        return c.fetchone()

    def reportExists(self, reportnum):
        cur = self.db.cursor()
        cur.execute(
            'SELECT reportnum FROM "NrcScrapedReport" WHERE reportnum = %s',
            (reportnum,),
        )
        n = cur.rowcount
        return n > 0

    def fullReportExists(self, reportnum):
        cur = self.db.cursor()
        cur.execute(
            'SELECT reportnum FROM "NrcScrapedFullReport" WHERE reportnum = %s',
            reportnum,
        )
        n = cur.rowcount
        return n > 0

    def materialExists(self, reportnum):
        cur = self.db.cursor()
        cur.execute('SELECT reportnum FROM "NrcScrapedMaterial" WHERE reportnum = %s', reportnum)
        n = cur.rowcount
        return n > 0

    def latestReportDate(self):
        cur = self.db.cursor()
        cur.execute('select MAX(incident_datetime) from "NrcScrapedReport"')
        n = cur.rowcount
        dt = None
        if n > 0:
            dt = cur.fetchone()[0]
        return dt

    def itemExists(self, item):
        table_name = item.__class__.__name__
        key_fields = item.keyFields()
        where_sql = ['"%s"=%s' % (key, "%s") for key in key_fields]
        where_values = [item.get(key) for key in key_fields]

        where_sql = " AND ".join(where_sql)

        sql = 'SELECT * FROM "%s" WHERE %s' % (table_name, where_sql)
        c = self.db.cursor()
        c.execute(sql, where_values)
        n = c.rowcount
        return n > 0

    def storeItem(self, item):
        if isinstance(item, NrcItem):
            return self.insertItem(item, item.insert_mode)
        else:
            return self.replaceItem(item)

    def replaceItem(self, item):
        return self.insertItem(item, "replace")

    def loadItem(self, item, match_fields=None):
        return self._loadItems(item, match_fields, return_single=True)

    def loadItems(self, item, match_fields=None):
        return self._loadItems(item, match_fields, return_single=False)

    def _loadItems(self, item, match_fields, return_single):
        table_name = item.__class__.__name__
        if match_fields:
            key_fields = match_fields.keys()
        else:
            key_fields = item.keyFields()
        where_sql = ['"%s"=%s' % (key, "%s") for key in key_fields]
        where_values = [(match_fields or item).get(key) for key in key_fields]
        where_sql = " AND ".join(where_sql)
        sql = 'SELECT * FROM "%s" WHERE %s' % (table_name, where_sql)
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql, where_values)
        if return_single:
            return c.fetchone()
        else:
            return c.fetchall()

    # insert_mode can be one of ( insert | replace )
    def insertItem(self, item, insert_mode="replace"):
        if hasattr(item, "returning") and item.returning:
            rtn_clause = "RETURNING %s as return_id" % item.returning
        else:
            rtn_clause = "RETURNING 1 as return_id"

        table_name = item.__class__.__name__
        fieldnms = item.keys()
        values = item.values()
        try:
            keyfields = item.keyFields()
        except AttributeError:
            keyfields = None

        # postgres does not do REPALCE so we run this method
        if insert_mode.lower() == "replace":
            return self._do_replace(table_name, fieldnms, values, rtn_clause, keyfields)

        field_str = '"%s"' % '", "'.join(fieldnms)
        value_str = ("%s," * len(values))[:-1]
        sql = '%s INTO "%s" (%s) VALUES (%s) %s;' % (
            insert_mode,
            table_name,
            field_str,
            value_str,
            rtn_clause,
        )
        c = self.db.cursor(cursor_factory=DictCursor)
        try:
            c.execute(sql, values)
        except:
            logging.INFO(
                "insertItem error on %s:\n\t%s" % (table_name, c.mogrify(sql, values)),
                level=logging.INFO,
            )  # DEBUG
            raise
        return c.fetchone()["return_id"]

    def updateItem(self, table_name, id, update_fields, id_field="id"):
        if update_fields:
            field_str = "=%s,".join(update_fields.keys())
            field_str += "=%s"

            sql = """UPDATE "%s" SET %s WHERE %s='%s'""" % (
                table_name,
                field_str,
                id_field,
                id,
            )
            c = self.db.cursor()
            c.execute(sql, update_fields.values())
            return c.rowcount
        return -1

    def deleteItem(self, table_name, id, id_field="id"):
        sql = """DELETE FROM "%s" WHERE %s='%s';""" % (table_name, id_field, id)
        c = self.db.cursor()
        c.execute(sql)
        return c.rowcount

    def loadScrapedReport(self, reportnum):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "NrcScrapedReport" WHERE reportnum=%s', (reportnum,))
        return c.fetchone()

    def loadScrapedFullReport(self, reportnum):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "NrcScrapedFullReport" WHERE reportnum=%s', (reportnum,))
        return c.fetchone()

    def loadParsedReport(self, reportnum):
        # print 'loadParsedReport:', reportnum
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "NrcParsedReport" WHERE reportnum=%s', (reportnum,))
        return c.fetchone()

    def loadGeocodes(self, reportnum):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "NrcGeocode" WHERE reportnum=%s', (reportnum,))
        return c.fetchall()

    def loadBestGeocode(self, reportnum):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(
            'SELECT * from "NrcGeocode" WHERE reportnum=%s ORDER BY "precision" DESC LIMIT 1',
            (reportnum,),
        )
        return c.fetchone()

    def loadNrcTags(self, reportnum):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "NrcTag" WHERE reportnum=%s', (reportnum,))
        return c.fetchall()

    def loadScrapedMaterial(self, reportnum):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "NrcScrapedMaterial" WHERE reportnum=%s', (reportnum,))
        return c.fetchall()

    def loadAnalysis(self, reportnum):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "NrcAnalysis" WHERE reportnum=%s', (reportnum,))
        return c.fetchone()

    def getBotTasks(self, bot, task_id=None):
        c = self.db.cursor(cursor_factory=DictCursor)
        if not task_id:
            #            sql = """SELECT t.id as task_id FROM "BotTask" t LEFT JOIN "BotTaskStatus" s ON t.id = s.task_id AND t.bot = s.bot WHERE t.bot = '%s' AND ((s.task_id is NULL) or (TIMESTAMPDIFF(SECOND, s.time_stamp, NOW()) > t.process_interval_secs)) ORDER BY t.id ASC""" % (bot,)
            sql = """SELECT t.id as task_id FROM "BotTask" t
                     LEFT JOIN "BotTaskStatus" s
                         ON t.id = s.task_id AND t.bot = s.bot
                     WHERE t.bot = %s
                         AND ((s.task_id is NULL)
                           or (now() - s.time_stamp) >
                              t.process_interval_secs * interval '1 second')"""
            c.execute(sql, (bot,))
            return c.fetchall()
        else:
            sql = 'SELECT id as task_id FROM "BotTask" WHERE id=%s and bot = %s'
            c.execute(sql, (task_id, bot))
            return c.fetchone()

    def getBotTaskParams(self, bot, task_id):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "BotTaskParams" WHERE bot=%s AND task_id=%s', (bot, task_id))
        return c.fetchall()

    def updateBotTaskParam(self, bot, task_id, key, value):
        # sql = 'REPLACE INTO "BotTaskParams" (bot, task_id, "key", "value") VALUES (%s, %s, %s, %s)'
        # c = self.db.cursor()
        # c.execute (sql, (bot, task_id, key, value))
        self._do_replace(
            "BotTaskParams",
            ("bot", "task_id", "key", "value"),
            (bot, task_id, key, value),
        )

    def updateBotTaskLastProcessed(self, task_id):
        sql = "UPDATE BotTask SET last_processed=NOW() WHERE id=%s"
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql, (task_id,))

    def getBotTaskCount(self, bot, status):
        c = self.db.cursor(cursor_factory=DictCursor)
        sql = 'SELECT count(*) as count FROM "BotTaskStatus" WHERE bot=%s AND status = %s'
        c.execute(sql, (bot, status))
        return c.fetchall()

    def getBotTaskBatch(self, bot, batch_size, set_status, match_conditions):
        c = self.db.cursor(cursor_factory=DictCursor)

        # Clear any existing status lines that might be left over
        sql = 'DELETE FROM "BotTaskStatus" WHERE bot=%s AND status = %s'
        c.execute(sql, (bot, set_status))

        if len(match_conditions) < 1:
            raise exceptions.NotSupported("getBotTaskBatch must have at least one match condition")

        join_sql = []
        timestamp_sql = []
        for cbot, cstatus in match_conditions.items():
            idx = len(join_sql)
            if cstatus == "*":
                join_sql.append("c%s.bot='%s' " % (idx, cbot))
            else:
                join_sql.append("c%s.bot='%s' AND c%s.status='%s'" % (idx, cbot, idx, cstatus))

            timestamp_sql.append("t1.time_stamp < c%s.time_stamp" % idx)

        #        sql = """REPLACE INTO "BotTaskStatus"
        #                 SELECT c0.task_id, '%s' as bot, '%s' as status,
        #                        CURRENT_TIMESTAMP as time_stamp
        #                 FROM "BotTaskStatus" c0""" % (bot, set_status)
        sql = """SELECT c0.task_id, '%s' as bot, '%s' as status,
                        CURRENT_TIMESTAMP as time_stamp
                 FROM "BotTaskStatus" c0""" % (bot, set_status)
        join_sql_0 = join_sql.pop(0)
        idx = 1
        for join_sql_n in join_sql:
            sql += ' JOIN "BotTaskStatus" c%s ON c0.task_id = c%s.task_id AND %s AND %s' % (
                idx,
                idx,
                join_sql_0,
                join_sql_n,
            )
            idx += 1
        sql += (
            """ LEFT JOIN "BotTaskStatus" t1 ON c0.task_id = t1.task_id AND t1.bot='%s' AND %s """
            % (bot, join_sql_0)
        )
        sql += " WHERE (t1.task_id IS NULL OR %s)" % " OR ".join(timestamp_sql)
        sql += " AND %s LIMIT %s" % (join_sql_0, batch_size)

        logging.INFO("getBotTaskBatch query1: %s" % (sql,), level=logging.INFO)  # DEBUG
        c.execute(sql)
        _all = c.fetchall()
        logging.INFO(
            "getBotTaskBatch query1 records: %s" % (len(_all),), level=logging.INFO
        )  # DEBUG
        # for rec in c.fetchall():
        for rec in _all:
            self._do_replace(
                "BotTaskStatus",
                ("task_id", "bot", "status", "time_stamp"),
                (rec["task_id"], rec["bot"], rec["status"], rec["time_stamp"]),
            )

        sql = """SELECT task_id FROM "BotTaskStatus" WHERE bot='%s' AND status='%s'""" % (
            bot,
            set_status,
        )
        logging.INFO("getBotTaskBatch query2: %s" % (sql,), level=logging.INFO)  # DEBUG
        c.execute(sql)
        _all = c.fetchall()
        logging.INFO(
            "getBotTaskBatch query2 records: %s" % (len(_all),), level=logging.INFO
        )  # DEBUG
        # return c.fetchall ()
        return _all

    def setBotTaskStatus(self, task_id, bot, status):
        # sql = "REPLACE INTO BotTaskStatus (task_id, bot, status) VALUES (%s, %s, %s)"
        # self.db.cursor().execute (sql, (task_id, bot, status))
        self._do_replace("BotTaskStatus", ("task_id", "bot", "status"), (task_id, bot, status))

    # TODO: this is crazy inefficient - need to explicitly create a temporary table and use a join instead of IN()
    def purgeOldBotTaskStatus(
        self, days_to_keep=60
    ):  # specify the age in days to keep.  All older bot task status entries will be removed
        #        sql = 'delete from "BotTaskStatus" where task_id in (select * from(select distinct task_id from "BotTaskStatus" where DATEDIFF (NOW(), time_stamp) > %s) as _t)'
        sql = (
            'delete from "BotTaskStatus" '
            "where task_id in (select * "
            "from(select distinct task_id "
            'from "BotTaskStatus" '
            "where (NOW() - time_stamp) > interval '%s days') "
            "as _t)"
        ) % days_to_keep
        self.db.cursor().execute(sql)

    def getBotTaskStatusSummary(self, interval):
        c = self.db.cursor(cursor_factory=DictCursor)
        #        sql = 'select  bot, count(*) as count, "status" from "BotTaskStatus" where time_stamp >= DATE_SUB(NOW(), INTERVAL %s DAY) group by bot, "status";' % interval
        sql = (
            'select  bot, count(*) as count, "status" from "BotTaskStatus" '
            "where now() - time_stamp < interval '%s days'"
            'group by bot, "status";' % interval
        )
        c.execute(sql)
        return c.fetchall()

    def getAreaCodeMap(self):
        sql = 'SELECT * FROM "AreaCodeMap"'
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql)
        return c.fetchall()

    def getBlockCentroid(self, area_code, blockid):
        sql = 'SELECT * FROM "LeaseBlockCentroid" WHERE areaid=%s AND blockid=%s'
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql, (area_code, blockid))
        return c.fetchone()

    def getNrcUnits(self):
        sql = 'SELECT * FROM "NrcUnits"'
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql)
        return c.fetchall()

    def getNrcMaterials(self):
        sql = 'SELECT * FROM "NrcMaterials"'
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql)
        return c.fetchall()

    # TODO: defunct
    def getRssFeeds(self, feed_id=None):
        c = self.db.cursor(cursor_factory=DictCursor)
        if not feed_id:
            sql = "SELECT * FROM \"RssFeed\" WHERE NOW() - last_read > (update_interval_secs * interval '1 second')"
            c.execute(sql)
            return c.fetchall()
        else:
            sql = 'SELECT * FROM "RssFeed" WHERE id=%s'
            c.execute(sql, (feed_id,))
            return c.fetchone()

    # TODO: defunct
    def updateRssFeedLastRead(self, feed_id):
        sql = 'UPDATE "RssFeed" SET last_read=NOW() WHERE id=%s'
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql, (feed_id,))

    def rssFeedItemExists(self, item_id):
        cur = self.db.cursor()
        cur.execute('SELECT item_id FROM "RssFeedItem" WHERE item_id = %s', (item_id,))
        n = cur.rowcount
        return n > 0

    def getNextNrcScraperTarget(self, id):
        c = self.db.cursor(cursor_factory=DictCursor)
        if id not in ("next", "NEXT"):
            sql = 'SELECT * FROM "NrcScraperTarget" WHERE id=%s'
            c.execute(sql, (id,))
        else:
            sql = 'SELECT * FROM "NrcScraperTarget" WHERE done=0 ORDER BY execute_order ASC LIMIT 1'
            c.execute(sql)
        result = c.fetchone()
        if result:
            sql = "UPDATE NrcScraperTarget SET done=1 WHERE id=%s"
            c.execute(sql, (result["id"],))
        return result

    def getGeocodeCache(self, key):
        # print ('getGeocodeCache:', key)
        sql = """SELECT * FROM "GeocodeCache" WHERE _key=%s AND (NOW() - updated) < interval '180 days'"""
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql, (key,))
        # print('c.fetchone:', one) #c.fetchone())
        return c.fetchone()

    def putGeocodeCache(self, key, lat, lng):
        self._do_replace(
            "GeocodeCache",
            ("_key", "lat", "lng", "updated"),
            (key, lat, lng, date.today()),
        )

    def getEmailSubscriptionsForUpdate(self):
        #        sql = 'SELECT * FROM "RSSEmailSubscription" WHERE confirmed = 1 AND active = 1 AND (last_update_sent is null or DATE_SUB(NOW(), INTERVAL interval_hours HOUR) >= last_update_sent)'
        sql = (
            'SELECT * FROM "RSSEmailSubscription" '
            "WHERE confirmed = 1 AND active = 1 AND (last_update_sent is null "
            "or (now() - last_update_sent ) "
            "> ( interval_hours * interval '1 hours'))"
        )
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql)
        return c.fetchall()

    def updateEmailSubscription(self, id, update_fields):
        self.updateItem("RSSEmailSubscription", id, update_fields)

    def getEmailSubscriptionsForConfirmation(self):
        sql = 'SELECT * FROM "RSSEmailSubscription" WHERE confirmed = 0 AND last_email_sent is NULL'
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql)
        return c.fetchall()

    def isFeedItemPublished(self, task_id, item_id):
        sql = 'SELECT task_id FROM "PublishedFeedItems" WHERE task_id = %s AND feed_item_id = %s'
        c = self.db.cursor()
        c.execute(sql, (task_id, item_id))
        n = c.rowcount
        return n > 0

    def setFeedItemPublished(self, task_id, item_id):
        self._do_replace("PublishedFeedItems", ("task_id", "feed_item_id"), (task_id, item_id))

    def loadFracFocusParse(self, seqid):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "FracFocusParse" WHERE seqid=%s', (seqid,))
        return c.fetchone()

    def loadFracFocusParseChemicals(self, report_seqid):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(
            'SELECT * from "FracFocusParseChemical" WHERE report_seqid=%s',
            (report_seqid,),
        )
        return c.fetchall()

    def loadFracFocusReport(self, pdf_seqid):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "FracFocusReport" WHERE pdf_seqid=%s', (pdf_seqid,))
        return c.fetchone()

    def loadFracFocusReportChemicals(self, pdf_seqid):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "FracFocusReportChemical" WHERE pdf_seqid=%s', (pdf_seqid,))
        return c.fetchall()

    def getColoradoPermitBatch(self, last_seqid, batch_size):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(
            'SELECT ft_id, seqid from "CO_Permits" WHERE seqid>%s ORDER BY seqid ASC LIMIT %s',
            (last_seqid, batch_size),
        )
        return c.fetchall()

    def loadColoradoPermitReport(self, ft_id):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "CO_Permits" WHERE ft_id=%s', (ft_id,))
        return c.fetchone()

    def loadFracFocusScrape(self, seqid):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "FracFocusScrape" WHERE seqid=%s', (seqid,))
        return c.fetchone()

    def loadFracFocusPDF(self, seqid):
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute('SELECT * from "FracFocusPDF" WHERE seqid=%s', (seqid,))
        return c.fetchone()

    def increment_FFS_PDF_Download_Attempts(self, seqid):
        c = self.db.cursor()
        c.execute(
            'UPDATE "FracFocusScrape" SET pdf_download_attempts=pdf_download_attempts+1 WHERE seqid=%s',
            (seqid,),
        )

    def _do_replace(self, tablenm, fieldnms, values, rtn_clause="", keyfields=None):
        """Combine insert and update to replace MySQL REPLACE statement."""
        field_str = '"%s"' % '","'.join(fieldnms)
        value_str = ("%s," * len(values))[:-1]
        sql = 'INSERT INTO "%s"  (%s) VALUES (%s) %s ' % (
            tablenm,
            field_str,
            value_str,
            rtn_clause,
        )
        c = self.db.cursor(cursor_factory=DictCursor)
        try:
            c.execute(sql, values)
            if rtn_clause:
                return c.fetchone()["return_id"]
            return
        except Exception as e:
            if isinstance(e, psycopg2.IntegrityError) and str(e).find("duplicate key value") >= 0:
                pass
            else:
                logging.INFO("_do_replace error: %s" % c.mogrify(sql, values), level=logging.INFO)
                raise
        # We get a list of table key fields here
        if not keyfields:
            try:
                keyfields = self.table_keyfields[tablenm]
            except KeyError:
                sql = (
                    "SELECT column_name "
                    "FROM information_schema.key_column_usage "
                    "WHERE table_name = '%s'" % tablenm
                )
                c2 = self.db.cursor()
                c2.execute(sql)
                keyfields = [row[0] for row in c2.fetchall()]
                self.table_keyfields[tablenm] = keyfields
        # now we separate table keys from attributes
        key_list = []
        key_strs = []
        attr_list = []
        attr_strs = []
        for fieldnm, value in zip(fieldnms, values):
            substr = ' "%s"=%%s ' % (fieldnm,)
            if fieldnm in keyfields:
                key_list.append(value)
                key_strs.append(substr)
            else:
                attr_list.append(value)
                attr_strs.append(substr)

        if not attr_list:
            return 1
        if not key_list:
            logging.INFO("_do_replace UPDATE %s: no key values" % (tablenm,), level=logging.ERROR)
            return 0

        # build the sql statement
        sql = 'UPDATE "%s" SET %s WHERE %s %s;' % (
            tablenm,
            ",".join(attr_strs),
            "AND ".join(key_strs),
            rtn_clause,
        )
        try:
            c.execute(sql, attr_list + key_list)
            if c.rowcount == 0:
                logging.INFO(
                    "_do_replace UPDATE %s: no key: %s\n%s"
                    % (
                        tablenm,
                        ", ".join([str(s) for s in key_list]),
                        c.mogrify(sql, attr_list + key_list),
                    ),
                    level=logging.WARNING,
                )
                return 0
            if rtn_clause:
                return c.fetchone()["return_id"]
        except:
            logging.INFO(
                "_do_replace error: %s" % c.mogrify(sql, attr_list + key_list),
                level=logging.INFO,
            )
            raise
        return

    def feedentryCounts(self):
        sql = """
            SELECT COUNT(*), fs.id, fs.name FROM feedentry fe JOIN feedsource fs ON fe.source_id=fs.id 
            WHERE incident_datetime>'2018-08-01' AND STATUS='published' GROUP BY fs.id, fs.name ORDER BY fs.id
        """
        c = self.db.cursor(cursor_factory=DictCursor)
        c.execute(sql)
        return c.fetchall()

    def insertPaPermit(self, api, lat, lng):
        c = self.db.cursor(cursor_factory=DictCursor)
        sql = "SELECT * FROM img_papermit WHERE api_permit = %s"
        c.execute(sql, (api,))
        n = c.rowcount
        if n == 0:
            c = self.db.cursor(cursor_factory=DictCursor)
            sql = "INSERT INTO public.img_papermit(api_permit, lat, lng) VALUES (%s, %s, %s);"
            c.execute(sql, (api, lat, lng))
        return

    def getPaPermit(self, api):
        c = self.db.cursor(cursor_factory=DictCursor)
        sql = "SELECT * FROM img_papermit WHERE api_permit = %s"
        c.execute(sql, (api,))
        return c.fetchone()

    def getSourceItemIdCount(self, source_id, source_item_id):
        c = self.db.cursor(cursor_factory=DictCursor)
        sql = "SELECT * FROM feedentry WHERE source_item_id=%s AND source_id=%s"
        c.execute(sql, (source_item_id, source_id))
        n = c.rowcount
        return n

    def seeIfFeedentryExists(self, id):
        # print 'getFeedentryById', id
        c = self.db.cursor(cursor_factory=DictCursor)
        sql = "SELECT * FROM feedentry WHERE id='%s'" % id
        # print sql
        c.execute(sql)  # , (id))
        n = c.rowcount
        return n

    def update_NY_non_ascii(self):
        print("update_NY_non_ascii")
        try:
            sql = """
                UPDATE feedentry SET title = regexp_replace(title, '[\u0080-\u00ff]', '', 'g') WHERE source_id=1060 and title ~ '[^[:ascii:]]';
                UPDATE feedentry SET summary = regexp_replace(summary, '[\u0080-\u00ff]', '', 'g') WHERE source_id=1060 and summary ~ '[^[:ascii:]]';
                UPDATE feedentry SET content = regexp_replace(content, '[\u0080-\u00ff]', '', 'g') WHERE source_id=1060 and content ~ '[^[:ascii:]]';
            """
            c = self.db.cursor(cursor_factory=DictCursor)
            c.execute(sql)
            print("finished OK")
            return "ok"
        except Exception as e:
            print("update_NY_non_ascii error:", e)
            return "error"

    def getLastSourceItemId(self, source_id):
        c = self.db.cursor(cursor_factory=DictCursor)
        sql = (
            "SELECT source_item_id FROM feedentry WHERE source_id=%s ORDER BY source_item_id DESC LIMIT 1"
            % source_id
        )
        c.execute(sql)  # , (source_id))

        return c.fetchone()
