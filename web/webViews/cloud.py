from flask import session, render_template, redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest
import time, re, json


class cloudView(normalView):
    template_path = "cloud.html"

    @classmethod
    def post(self):
        accounts = dockletRequest.post('/cloud/account/query/').get('accounts',[])
        return self.render(self.template_path, accounts = accounts)

    @classmethod
    def get(self):
        return self.post()

class cloudAccountAddView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/cloud/account/add/', request.form)
        return redirect('/cloud/')

class cloudAccountDelView(normalView):
    @classmethod
    def post(self):
        data = {
                'cloudname' : self.cloudname,
                }
        dockletRequest.post('/cloud/account/delete/', data)
        return redirect('/cloud/')

    @classmethod
    def get(self):
        return self.post()

class cloudAccountModifyView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/cloud/account/modify/', request.form)
        return redirect('/cloud/')
