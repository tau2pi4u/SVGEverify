import smtplib
import random
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging

# Generates and returns a random 10 character string of letters, numbers and punctuation
def GenerateRandomString():
    N = 10 # number of characters
    return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(N))

# Generates email text 
def GenerateEmailText(user, to, rand, cfg):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"{cfg['societyName']} Email Verification"
    msg['From'] = user
    msg['To'] = to
    html = cfg['gmail']['template']
    html = html.replace("[code]", rand, 2)
    html = MIMEText(html, 'html')
    msg.attach(html)
    return msg.as_string()
    

# Logs into an smtp server, sends an email and then logs out
async def SendMail(user, pw, to, text):
    try:  
        server_ssl = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server_ssl.ehlo()   # optional
        logging.info(f"Connected to {user}")
        server_ssl.login(user, pw)
        logging.info("Login successful")
        server_ssl.sendmail(user, to, text)
        logging.info(f"Sent message")
        server_ssl.close()
        logging.info("Disconnected")
        # ...send emails
    except Exception as e:  
        logging.warning(f"Failed to send email with reason {e}")