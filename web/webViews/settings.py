from flask import session,render_template,redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest

class settingsView(normalView):
    template_path = "settings.html"

    @classmethod
    def get(self):
        settings = dockletRequest.post('/settings/list/')['result']
        logs = dockletRequest.post('/logs/list/')['result']
        logs.sort()
        logs.sort(key = len)
        return self.render(self.template_path, settings = settings, logs = logs)

    @classmethod
    def post(self):
        result = dockletRequest.post('/settings/update/', request.form)
        return redirect('/settings/')
