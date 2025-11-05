import common

# Planet API key
PL_API_KEY = common.access_secret_version("skytruth-alerts2", "PL_API_KEY", "latest")

# db connection string
ALERTS2_CONNECTION_STRING = common.access_secret_version(
    "skytruth-alerts2", "ALERTS2_CONNECTION_STRING", "latest"
)

EMAIL_FROM_USER = "no-reply@skytruth.org"  # backend from user
GMAIL_USER = "no-reply@skytruth.org"  # backend email user

GMAIL_PWD = common.access_secret_version("skytruth-alerts2", "GMAIL_PWD", "latest")
MANDRILL_FROM = "alerts@skytruth.org"
MANDRILL_HOST = "smtp.mandrillapp.com"
MANDRILL_PORT = 587
MANDRILL_PASS = common.access_secret_version("skytruth-alerts2", "MANDRILL_PASS", "latest")

ALERTS2_API_URL = "https://skytruth-alerts2.appspot.com/api/"
DB_CONNECTION_STRING = common.access_secret_version(
    "skytruth-alerts2", "DB_CONNECTION_STRING", "latest"
)
DB_HOST = "34.75.201.96"
DB_USER = "postgres"
DB_PASS = common.access_secret_version("skytruth-alerts2", "ALERTS2_PASSWORD", "latest")
DB_DATABASE = "alerts2"

# API URL
# PRODUCTION
API_POST_FEEDENTRY = "https://skytruth-alerts2.appspot.com/api/api_post_feedentry/"
# GMAIL_FROM = "alerts@skytruth.org"  # scraper from user
# GMAIL_USER = "data@skytruth.org"  # scraper email user
GMAIL_PWD = common.access_secret_version("skytruth-alerts2", "GMAIL_PWD", "latest")
