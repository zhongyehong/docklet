from flask import session,render_template,request,redirect
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest


class reportBugView(normalView):
    template_path = "opsuccess.html"

    @classmethod
    def get(self):
        dockletRequest.post("/bug/report/", {'bugmessage': self.bugmessage})
        return self.render(self.template_path, message="Thank You!")

    @classmethod
    def post(self):
        return self.get()
