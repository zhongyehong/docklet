from flask import session,render_template,redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest

class logsView(normalView):
    template_path = "logs.html"

    @classmethod
    def get(self):
        logs = dockletRequest.post('/logs/list/')['result']
        logs.sort()
        logs.sort(key = len)
        return self.render(self.template_path, logs = logs)
