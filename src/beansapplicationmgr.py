from model import db,User,ApplyMsg
from userManager import administration_required

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
        return list(eval(str(applymsgs)))
    
    @administration_required
    def queryUnRead(self,*,cur_user):
        applymsgs = ApplyMsg.query.filter_by(status="Processing").all()
        msgs = list(eval(str(applymsgs)))
        return {"success":"true","applymsgs":msgs}

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
