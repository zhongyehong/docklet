from flask import redirect, request
from webViews.dockletrequest import dockletRequest
from webViews.view import normalView
import json

class userinfoView(normalView):
    template_path = "user/info.html"

    @classmethod
    def get(self):
        userinfo = dockletRequest.post('/user/selfQuery/')
        userinfo = userinfo["data"]
        return self.render(self.template_path, info = userinfo)

    @classmethod
    def post(self):
        result =  json.dumps(dockletRequest.post('/user/selfModify/', request.form))
        return result
