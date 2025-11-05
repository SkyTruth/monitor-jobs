import common

# Planet API key
PL_API_KEY = common.access_secret_version("skytruth-alerts2", "PL_API_KEY", "latest")

# db connection string
ALERTS2_CONNECTION_STRING = common.access_secret_version(
    "skytruth-alerts2", "ALERTS2_CONNECTION_STRING", "latest"
)

EMAIL_FROM_USER = "no-reply@skytruth.org"

GMAIL_USER = "no-reply@skytruth.org"
GMAIL_PWD = common.access_secret_version("skytruth-alerts2", "GMAIL_PWD", "latest")
EMAIL_SERVER = "smtp.gmail.com"
EMAIL_SERVER_PORT = 587

MANDRILL_FROM = "alerts@skytruth.org"
MANDRILL_HOST = "smtp.mandrillapp.com"
MANDRILL_PORT = 587
MANDRILL_USER = "paul@skytruth.org"
MANDRILL_PASS = common.access_secret_version(
    "skytruth-alerts2", "MANDRILL_PASS", "latest"
)
MANDRILL_TO = "ops@skytruth.org"

ALERTS2_API_URL = "https://skytruth-alerts2.appspot.com/api/"

BOT_NAME = "PAPermitScraper"

SPIDER_MODULES = ["PAPermitScraper.spiders"]
NEWSPIDER_MODULE = "PAPermitScraper.spiders"


# Crawl responsibly by identifying yourself (and your website) on the user-agent
# USER_AGENT = 'permits (+http://www.yourdomain.com)'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True
LOG_LEVEL = "INFO"
DEFAULT_ITEM_CLASS = "nrc.items.NrcScrapedReport"
# USER_AGENT = '%s/%s' % (BOT_NAME, BOT_VERSION)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_7) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1180.73 Safari/537.1"
ITEM_PIPELINES = {
    #'nrc.pipelines.NrcDatabasePipeline': 300
}
DOWNLOAD_TIMEOUT = 900  # 15 min  (for WV Marcellus Shale permits -- 22MB)

DOWNLOADER_MIDDLEWARES = {
    #'nrc.middlewares.CustomCookiesMiddleware': 700,
    "scrapy.downloadermiddlewares.cookies.CookiesMiddleware": None,
    "scrapy.downloadermiddlewares.httpauth.HttpAuthMiddleware": None,
    "scrapy.downloadermiddlewares.downloadtimeout.DownloadTimeoutMiddleware": 800,
}

# EXTENSIONS = {
#        'nrc.extensions.failLogger.FailLogger': 599,
# }

# CONCURRENT_REQUESTS_PER_SPIDER = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True

DB_CONNECTION_STRING = common.access_secret_version(
    "skytruth-alerts2", "DB_CONNECTION_STRING", "latest"
)
DB_HOST = "34.75.201.96"
GEO_DB_HOST = "34.75.201.96"
DB_USER = "postgres"
DB_PASS = common.access_secret_version("skytruth-alerts2", "ALERTS2_PASSWORD", "latest")
DB_DATABASE = "alerts2"
#
GEO_DB_USER = "postgres"
GEO_DB_PASS = common.access_secret_version(
    "skytruth-alerts2", "ALERTS2_PASSWORD", "latest"
)
GEO_DB_DATABASE = "alerts2"

# API URL
# PRODUCTION
API_POST_FEEDENTRY = "https://skytruth-alerts2.appspot.com/api/api_post_feedentry/"


GOOGLE_MAPS_API_KEY = common.access_secret_version(
    "skytruth-alerts2", "GOOGLE_MAPS_API_KEY", "latest"
)

CERULEAN_CONNECTION_STRING = common.access_secret_version(
    "skytruth-alerts2", "CERULEAN_CONNECTION_STRING", "latest"
)

GMAIL_FROM = "alerts@skytruth.org"
GMAIL_USER = "data@skytruth.org"
GMAIL_PWD = common.access_secret_version("skytruth-alerts2", "GMAIL_PWD", "latest")
GMAIL_HOST = "smtp.gmail.com"
GMAIL_PORT = 587
