from flask import session, render_template, redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest


class NotificationView(normalView):
    template_path = 'notification.html'

    @classmethod
    def get(cls):
        return cls.render(cls.template_path)


class CreateNotificationView(normalView):
    @classmethod
    def post(cls):
        dockletRequest.post('/notification/create/', request.form)
        # return redirect('/admin/')
        return 'success'
