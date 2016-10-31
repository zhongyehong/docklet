import threading,datetime,random,time
from model import db,User,ApplyMsg
from userManager import administration_required
import env
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

email_from_address = env.getenv('EMAIL_FROM_ADDRESS')

def send_beans_email(to_address, username, beans):
    global email_from_address
    if (email_from_address in ['\'\'', '\"\"', '']):
        return
    #text = 'Dear '+ username + ':\n' + '  Your beans in docklet are less than' + beans + '.'
    text = '<html><h4>Dear '+ username + ':</h4>'
    text += '''<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Your beans in <a href='%s'>docklet</a> are %d now. </p>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;If your beans are less than or equal to 0, all your worksapces will be stopped.</p>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Please apply for more beans to keep your workspaces running by following link:</p>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href='%s/beans/application/'>%s/beans/application/</p>
               <br>
               <p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Note: DO NOT reply to this email!</p>
               <br><br>
               <p> <a href='http://docklet.unias.org'>Docklet Team</a>, SEI, PKU</p>
            ''' % (env.getenv("PORTAL_URL"), beans, env.getenv("PORTAL_URL"), env.getenv("PORTAL_URL"))
    text += '<p>'+  str(datetime.datetime.now()) + '</p>'
    text += '</html>'
    subject = 'Docklet beans alert'
    msg = MIMEMultipart()
    textmsg = MIMEText(text,'html','utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = email_from_address
    msg['To'] = to_address
    msg.attach(textmsg)
    s = smtplib.SMTP()
    s.connect()
    s.sendmail(email_from_address, to_address, msg.as_string())
    s.close()

class ApplicationMgr:
    
    def __init__(self):
        try:
            ApplyMsg.query.all()
        except:
            db.create_all()

    def apply(self,username,number,reason):
        user = User.query.filter_by(username=username).first()
        if user is not None and user.beans >= 1000:
            return [False, "Your beans must be less than 1000."]
        if int(number) < 100 or int(number) > 5000:
            return [False, "Number field must be between 100 and 5000!"]
        applymsgs = ApplyMsg.query.filter_by(username=username).all()
        lasti = len(applymsgs) - 1
        if lasti >= 0 and applymsgs[lasti].status == "Processing":
            return [False, "You already have a processing application, please be patient."] 
        applymsg = ApplyMsg(username,number,reason)
        db.session.add(applymsg)
        db.session.commit()
        return [True,""]
    
    def query(self,username):
        applymsgs = ApplyMsg.query.filter_by(username=username).all()
        ans = []
        for msg in applymsgs:
            ans.append(msg.ch2dict())
        return ans
    
    @administration_required
    def queryUnRead(self,*,cur_user):
        applymsgs = ApplyMsg.query.filter_by(status="Processing").all()
        ans = []
        for msg in applymsgs:
            ans.append(msg.ch2dict())
        return {"success":"true","applymsgs":ans}

    @administration_required
    def agree(self,msgid,*,cur_user):
        applymsg = ApplyMsg.query.get(msgid)
        if applymsg is None:
            return {"success":"false","message":"Application doesn\'t exist."}
        applymsg.status = "Agreed"
        user = User.query.filter_by(username=applymsg.username).first()
        if user is not None:
            user.beans += applymsg.number
        db.session.commit()
        return {"success":"true"}
    
    @administration_required
    def reject(self,msgid,*,cur_user):
        applymsg = ApplyMsg.query.get(msgid)
        if applymsg is None:
            return {"success":"false","message":"Application doesn\'t exist."}
        applymsg.status = "Rejected"
        db.session.commit()
        return {"success":"true"}

class ApprovalRobot(threading.Thread):

    def __init__(self,maxtime=3600):
        threading.Thread.__init__(self)
        self.stop = False
        self.interval = 20
        self.maxtime = maxtime
    
    def stop(self):
        self.stop = True 

    def run(self):
        while not self.stop:
            applymsgs = ApplyMsg.query.filter_by(status="Processing").all()
            for msg in applymsgs:
                secs = (datetime.datetime.now() - msg.time).seconds
                ranint = random.randint(self.interval,self.maxtime)
                if secs >= ranint:
                    msg.status = "Agreed"
                    user = User.query.filter_by(username=msg.username).first()
                    if user is not None:
                        user.beans += msg.number
                    db.session.commit()
            time.sleep(self.interval)
