from flask import session
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest
from webViews.dashboard import *
import time, re

class adminView(normalView):
    template_path = "admin.html"

    @classmethod
    def get(self):
        groups = dockletRequest.post('/user/groupNameList/')["groups"]
        return self.render(self.template_path, groups = groups)

