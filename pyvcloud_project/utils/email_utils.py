"""
Module containing utility functions for sending emails.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import COMMASPACE, formatdate

# Needed for future
# import mimetypes
# from email.mime.base import MIMEBase
# from email import encoders
# from email.message import Message
# from email.mime.audio import MIMEAudio
# from email.mime.base import MIMEBase
# from email.mime.image import MIMEImage


def sendtestmail():
    """
    Send a test email.
    """
    email_message = 'test'
    email_subject = 'subject'
    contacts = ['firstname.surname@ericsson.com']
    email_params = {
        'recipients': contacts,
        'fromAddress': 'pyvcloud@ericsson.com',
        'bcc_recipients': ['firstname.surname@ericsson.com'],
        'subject': email_subject,
        'message': email_message
    }
    sendEmail(email_params)
    # sendEmail(email_params, bcc=True)


def sendEmail(Params, cc=False, bcc=False):
    """
    Send an email using the provided parameters.
    """
    recipients = Params["recipients"]
    fromaddr = Params["fromAddress"]
    subject = Params["subject"]
    message = Params["message"]
    # this will need to be changed when moving to production. will need to whitelist ip's.  https://ericsson-dwp.onbmc.com/dwp/app/#/knowledge/KBA00262734/rkm
    server = "smtps.internal.ericsson.com"
    # server="smtp-central.internal.ericsson.com"               #the proper smtps server to be used in production

    msg = MIMEMultipart()
    msg['From'] = fromaddr
    msg['To'] = COMMASPACE.join(recipients)
    if cc:
        cc_recipients = Params["cc_recipients"]
        msg['CC'] = COMMASPACE.join(cc_recipients)
        recipients.extend(cc_recipients)
    if bcc:
        bcc_recipients = Params['bcc_recipients']
        msg['BCC'] = COMMASPACE.join(bcc_recipients)
        recipients.extend(bcc_recipients)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg.attach(MIMEText(message))

    # smtp = smtplib.SMTP(server,25)   #the command to be used when in production and server ip' have been whitelisted correctly.
    smtp = smtplib.SMTP(server)
    smtp.sendmail(fromaddr, recipients, msg.as_string())

    smtp.close()

    return True
