from flask import session, render_template, redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest
from webViews.dashboard import *
import time, re, json

class adminView(normalView):
    template_path = "admin.html"

    @classmethod
    def get(self):
        result = dockletRequest.post('/user/groupList/')
        groups = result["groups"]
        quotas = result["quotas"]
        defaultgroup = result["default"]
        return self.render(self.template_path, groups = groups, quotas = quotas, defaultgroup = defaultgroup)

class groupaddView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/user/groupadd/', request.form)
        return redirect('/admin/')

class quotaaddView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/user/quotaadd/', request.form)
        return redirect('/admin/')

class chdefaultView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/user/chdefault/', request.form)
        return redirect('/admin/')

class groupdelView(normalView):
    @classmethod
    def post(self):
        data = {
                "name" : self.groupname,
        }
        dockletRequest.post('/user/groupdel/', data)
        return redirect('/admin/')

    @classmethod
    def get(self):
        return self.post()
