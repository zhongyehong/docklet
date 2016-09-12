from flask import session,render_template
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
