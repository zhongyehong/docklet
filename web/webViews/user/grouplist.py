from flask import redirect, request
from webViews.dockletrequest import dockletRequest
from webViews.view import normalView
import json

class grouplistView(normalView):
    template_path = "user/grouplist.html"

class groupdetailView(normalView):
    @classmethod
    def post(self):
        return json.dumps(dockletRequest.post('/user/groupList/'))

class groupqueryView(normalView):
    @classmethod
    def post(self):
        return json.dumps(dockletRequest.post('/user/groupQuery/', request.form))

class groupmodifyView(normalView):
    @classmethod
    def post(self):
        result =  json.dumps(dockletRequest.post('/user/groupModify/', request.form))
        return redirect('/admin/')
