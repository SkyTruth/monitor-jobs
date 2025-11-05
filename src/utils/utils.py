import os
from stat import *
import config
import smtplib
from smtplib import SMTPException


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
            msg_content
            + "   "
            + str(exc_type)
            + ":"
            + str(fname)
            + ":"
            + str(exc_tb.tb_lineno)
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


def error_condition(program, error, exc_info):
    exc_type, exc_obj, exc_tb = exc_info
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    print(error, exc_type, fname, exc_tb.tb_lineno)
    send_email(
        program + " exception",
        str(error)
        + ":"
        + str(exc_type)
        + ":"
        + str(fname)
        + ":"
        + str(exc_tb.tb_lineno),
    )


def convert_well_class(well_class):
    # http://pipeline.wyo.gov/codes.html
    # O    =  Oil Well
    # G    =  Gas Well
    # C    =  Condensate
    # I      =  Injector Well
    # S    =  Source Well
    # D  = Disposal
    # M  = Monitor Well
    Well_Class = well_class
    if well_class == "O":
        Well_Class = "Oil"
    if well_class == "G":
        Well_Class == "Gas"
    if well_class == "C":
        Well_Class = "Condensate"
    if well_class == "I":
        Well_Class = "Injector Well"
    if well_class == "D":
        Well_Class = "Disposal"
    if well_class == "S":
        Well_Class = "Source Well"
    if well_class == "M":
        Well_Class = "Monitor Well"
    return Well_Class


def convert_status(status):
    # http://pipeline.wyo.gov/codes.html
    Status = status
    if status == "AP":
        Status = "Active Permit"
    if status == "EP":
        Status = "Expired Permit"
    if status == "DP":
        Status = "Drilling or Drilled Permit"
    if status == "NO":
        Status = "Denied or Cancelled"
    if status == "WP":
        Status = "Waiting on Approval"
    if status == "WD":
        Status = "Withdrawn"
    return Status
