from model import db,User,ApplyMsg

class ApplicationMgr:
    
    def __init__(self):
        try:
            ApplyMsg.query.all()
        except:
            db.create_all()

    def apply(self,username,number,reason):
        if int(number) < 100 or int(number) > 5000:
            return [False, "Number field must be between 100 and 5000!"]
        applymsgs = ApplyMsg.query.filter_by(username=username).all()
        lasti = len(applymsgs) - 1
        if applymsgs[lasti].status == "Processing":
            return [False, "You already have a processing application, please be patient."] 
        applymsg = ApplyMsg(username,number,reason)
        db.session.add(applymsg)
        db.session.commit()
        return [True,""]
    
    def query(self,username):
        applymsgs = ApplyMsg.query.filter_by(username=username).all()
        return list(eval(str(applymsgs)))

    def queryUnRead(self):
        applymsgs = ApplyMsg.query.filter_by(status="Processing").all()
        return list(eval(str(applymsgs)))

    def agree(self,msgid):
        try:
            applymsg = ApplyMsg.query.get(msgid)
        except:
            return
        applymsg.status = "Agreed"
        db.session.commit()

    def reject(self,msgid):
        try:
            applymsg = ApplyMsg.query.get(msgid)
        except:
            return
        applymsg.status = "Rejected"
        db.session.commit()
