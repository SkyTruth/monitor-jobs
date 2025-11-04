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
MANDRILL_PASS = common.access_secret_version("skytruth-alerts2", "MANDRILL_PASS", "latest")
MANDRILL_TO = "ops@skytruth.org"

ALERTS2_API_URL = "https://skytruth-alerts2.appspot.com/api/"
