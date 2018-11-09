from master.settings import settings
import smtplib
from utils.log import logger
from utils import env
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
import json

def send_bug_mail(username, bugmessage):
    #admin_email_address = env.getenv('ADMIN_EMAIL_ADDRESS')
    nulladdr = ['\'\'', '\"\"', '']
    email_from_address = settings.get('EMAIL_FROM_ADDRESS')
    admin_email_address = settings.get('ADMIN_EMAIL_ADDRESS')
    logger.info("receive bug from %s: %s" % (username, bugmessage))
    if (email_from_address in nulladdr or admin_email_address in nulladdr):
        return {'success': 'false'}
    #text = 'Dear '+ username + ':\n' + '  Your account in docklet has been activated'
    text = '<html><h4>Dear '+ 'admin' + ':</h4>'
    text += '''<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A bug has been report by %s.</p>
               <br/>
               <strong>&nbsp; %s &nbsp;</strong>
               <br/>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Please check it !</p>
               <br/><br/>
               <p> Docklet Team, SEI, PKU</p>
            ''' % (username, bugmessage)
    text += '<p>'+  str(datetime.utcnow()) + '</p>'
    text += '</html>'
    subject = 'A bug of Docklet has been reported'
    if admin_email_address[0] == '"':
        admins_addr = admin_email_address[1:-1].split(" ")
    else:
        admins_addr = admin_email_address.split(" ")
    alladdr=""
    for addr in admins_addr:
        alladdr = alladdr+addr+", "
    alladdr=alladdr[:-2]
    msg = MIMEMultipart()
    textmsg = MIMEText(text,'html','utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = email_from_address
    msg['To'] = alladdr
    msg.attach(textmsg)
    s = smtplib.SMTP()
    s.connect()
    try:
        s.sendmail(email_from_address, admins_addr, msg.as_string())
    except Exception as e:
        logger.error(e)
    s.close()
    return {'success':'true'}
