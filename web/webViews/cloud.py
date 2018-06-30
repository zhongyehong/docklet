from flask import session, render_template, redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest
import time, re, json


class cloudView(normalView):
    template_path = "cloud.html"

    @classmethod
    def post(self):
        settings = dockletRequest.post_to_all('/cloud/setting/get/')
        return self.render(self.template_path, settings = settings)

    @classmethod
    def get(self):
        return self.post()

class cloudSettingModifyView(normalView):
    @classmethod
    def post(self):
        dockletRequest.post('/cloud/setting/modify/', request.form, self.masterip)
        return redirect('/cloud/')

class cloudNodeAddView(normalView):
    @classmethod
    def post(self):
        data = {}
        dockletRequest.post('/cloud/node/add/', data, self.masterip)
        return redirect('/hosts/')

    @classmethod
    def get(self):
        return self.post()
