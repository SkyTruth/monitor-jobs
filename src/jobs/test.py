from src.utils.db import read_test_subscriptions
import sys

import os
import sys
import glob
from datetime import datetime
from pathlib import Path

import psycopg2
import argparse
import google_crc32c
import smtplib
from smtplib import SMTPException
from smtplib import SMTP  # sending email
from jinja2 import Environment  # Jinja2 templating
from urllib.parse import urlparse, parse_qs
import re
from email.mime.text import MIMEText
import unicodedata
import requests

import rasterio
import rasterio.warp
from rasterio.crs import CRS
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.http import MediaIoBaseDownload

# from items import NrcTag, BotTaskError, FeedEntryTag
# from database import NrcDatabase
# import utils
# import settings

# from __future__ import division
# from __future__ import print_function
# from __future__ import unicode_literals

import re
from datetime import datetime
import os
import sys
import urllib
import psycopg2
import xlrd
import requests
from scrapy.loader import ItemLoader
from scrapy.selector import Selector

import time
import random
from dateutil.parser import parse as parse_date

# from scrapy.loader.processors import TakeFirst, MapCompose, Join
from itemloaders.processors import TakeFirst, MapCompose, Join
import smtplib

# from __future__ import absolute_import
import uuid
import logging

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as cond
from selenium.common.exceptions import NoAlertPresentException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from pyvirtualdisplay.display import Display
import hashlib

import argparse
import google_crc32c
import json
import csv


last_arg = ""
test_email = None
for arg in sys.argv:
    if last_arg == "-test":
        test_email = arg
    last_arg = arg
print("test email is ", test_email)
print("I'm running!")
subs = read_test_subscriptions(test_email)
print(subs)
print("Python version:", sys.version)
print("rasterio version:", rasterio.__version__)
