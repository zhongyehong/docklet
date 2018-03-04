from flask import session,render_template,request,redirect
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest


class beansapplicationView(normalView):
    template_path = "beansapplication.html"

    @classmethod
    def get(self):
        result = dockletRequest.post('/beans/applymsgs/').get('applymsgs')
        return self.render(self.template_path, applications = result)

    @classmethod
    def post(self):
        return self.get()

class beansapplyView(normalView):
    template_path = "error.html"

    @classmethod
    def post(self):
        data = {"number":request.form["number"],"reason":request.form["reason"]}
        result = dockletRequest.post('/beans/apply/',data)
        success = result.get("success")
        if success == "true":
            return redirect("/beans/application/")
        else:
            return self.render(self.template_path, message = result.get("message"))

    @classmethod
    def get(self):
        return self.post()

class beansadminView(normalView):
    username = ""
    msgid = ""
    cmd = ""
    template_path = "error.html"

    @classmethod
    def get(self):
        data = {"username":self.username, "msgid":self.msgid}
        result = dockletRequest.post('/beans/admin/'+self.cmd+"/",data)
        success = result.get("success")
        if success == "true":
            return redirect("/user/list/")
        else:
            return self.render(self.template_path, message = result.get("message"))
