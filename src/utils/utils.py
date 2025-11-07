import os
import smtplib
from smtplib import SMTPException
from stat import *

import config


def send_email(subject, text, to=None):
    gmail_user = config.GMAIL_USER
    gmail_pwd = config.GMAIL_PWD
    FROM = config.EMAIL_FROM_USER
    TO = "tech@skytruth.org"
    if to != None:
        TO = to
    SUBJECT = subject
    TEXT = text

    # Prepare actual message
    message = """From: %s\nTo: %s\nSubject: %s\n\n%s
        """ % (FROM, TO, SUBJECT, TEXT)
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(gmail_user, gmail_pwd)
        server.sendmail(FROM, TO, message)
        server.close()
        print("successfully sent the mail")
    except SMTPException as excep:
        print("failed to send mail with SMTP exception: " + str(excep))
    except Exception as excep:
        print("failed to send mail with exception: " + str(excep))


def send_alert(message, exc_info=None):
    msg_content = message
    if exc_info:
        exc_type, exc_obj, exc_tb = exc_info
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        msg_content = (
            msg_content + "   " + str(exc_type) + ":" + str(fname) + ":" + str(exc_tb.tb_lineno)
        )
    email_error(msg_content)


def email_error(error_msg):
    user = config.GMAIL_USER
    pwd = config.GMAIL_PWD
    gmail_user = user
    gmail_pwd = pwd
    FROM = user
    TO = "ops@skytruth.org,tech@skytruth.org"
    SUBJECT = "Error found"
    TEXT = error_msg

    # Prepare actual message
    message = """From: %s\nTo: %s\nSubject: %s\n\n%s
        """ % (FROM, TO, SUBJECT, TEXT)
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(gmail_user, gmail_pwd)
        server.sendmail(FROM, TO, message)
        server.close()
        print("successfully sent the mail")
    except:
        print("failed to send mail")
