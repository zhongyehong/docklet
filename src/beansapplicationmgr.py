from model import db,User,ApplyMsg

class ApplicationMgr:
    
    def __init__(self):
        try:
            ApplyMsg.query.all()
        except:
            db.create_all()

    def apply(self,username,number,reason):
        applymsg = ApplyMsg(username,number,reason)
        db.session.add(applymsg)
        db.session.commit()
    
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
