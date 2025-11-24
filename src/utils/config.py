from src.utils import common
import os

# Planet API key
PL_API_KEY = common.access_secret_version("skytruth-alerts2", "PL_API_KEY", "latest")
ENVIRONMENT = os.getenv("ENVIRONMENT")  # Environment variable set in docker

EMAIL_FROM_USER = "no-reply@skytruth.org"  # backend from user
GMAIL_USER = "no-reply@skytruth.org"  # backend email user

MANDRILL_FROM = "alerts@skytruth.org"
MANDRILL_HOST = "smtp.mandrillapp.com"
MANDRILL_PORT = 587
MANDRILL_PASS = common.access_secret_version("skytruth-alerts2", "MANDRILL_PASS", "latest")

ALERTS2_API_URL = "https://skytruth-alerts2.appspot.com/api/"
# DB_CONNECTION_STRING = common.access_secret_version(
#     "skytruth-alerts2", "DB_CONNECTION_STRING_DEV", "latest"
# )

if ENVIRONMENT == "DEV":
    # DB_HOST = "34.75.201.96"  # Prod DB local connect
    DB_HOST = "35.190.140.113"  # Clone DB local connect
elif ENVIRONMENT == "PROD":
    # DB_HOST = "/cloudsql/skytruth-alerts2:us-east1:alerts12pg"  # Socket for prod DB
    DB_HOST = "/cloudsql/skytruth-alerts2:us-east1:alerts12pg-clone"  # Socket for clone DB
DB_USER = "postgres"
DB_PASS = common.access_secret_version("skytruth-alerts2", "ALERTS2_PASSWORD", "latest")
DB_DATABASE = "alerts2"

DB_CONNECTION_STRING = (
    f"dbname='{DB_DATABASE}' user='{DB_USER}' host='{DB_HOST}' password='{DB_PASS}'"
)
# API URL
# PRODUCTION
# API_POST_FEEDENTRY = "https://skytruth-alerts2.appspot.com/api/api_post_feedentry/" # production
# API_POST_FEEDENTRY = "http://host.docker.internal:8000/api/api_post_feedentry/" local dev
API_POST_FEEDENTRY = (
    "https://dev-dot-skytruth-alerts2.ue.r.appspot.com/api/api_post_feedentry/"  # clone DB
)
# GMAIL_FROM = "alerts@skytruth.org"  # scraper from user
# GMAIL_USER = "data@skytruth.org"  # scraper email user
