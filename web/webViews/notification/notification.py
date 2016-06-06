from flask import session, render_template, redirect, request
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest


class NotificationView(normalView):
    template_path = 'notification.html'

    @classmethod
    def get(cls):
        result = dockletRequest.post('/notification/list/')
        notifications = result['data']
        notification_titles = [notify['title'] for notify in notifications]
        return cls.render(cls.template_path, notifications=notifications, notification_titles=notification_titles)


class CreateNotificationView(normalView):
    template_path = 'create_notification.html'

    @classmethod
    def get(cls):
        groups = dockletRequest.post('/user/groupNameList/')['groups']
        return cls.render(cls.template_path, groups=groups)

    @classmethod
    def post(cls):
        dockletRequest.post('/notification/create/', request.form)
        # return redirect('/admin/')
        return 'success'
