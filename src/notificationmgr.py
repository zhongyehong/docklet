from model import db, Notification, NotificationGroups
from userManager import administration_required


class NotificationMgr:
    def __init__(self):
        try:
            Notification.query.all()
        except:
            db.create_all()

    @administration_required
    def create_notification(self, *args, **kwargs):
        '''
        Usage: createNotification(cur_user = 'Your current user', form = 'Post form')
        Post form: {title: 'Your title', content: 'Your content', groups: ['groupA', 'groupB']}
        '''
        form = kwargs['form']
        notify = Notification(form['title'], form['content'])
        db.session.add(notify)
        db.session.commit()
        for group_name in form['groups']:
            notify_groups = NotificationGroups(notify.id, group_name)
            db.session.add(notify_groups)
        db.session.commit()
        return {"success": 'true'}

