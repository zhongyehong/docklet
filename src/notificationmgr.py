import json

from log import logger
from model import db, Notification, NotificationGroups
from userManager import administration_required


class NotificationMgr:
    def __init__(self):
        logger.info("Notification Manager init...")
        try:
            Notification.query.all()
        except:
            db.create_all()
        try:
            NotificationGroups.query.all()
        except:
            db.create_all()
        logger.info("Notification Manager init done!")

    @administration_required
    def create_notification(self, *args, **kwargs):
        '''
        Usage: createNotification(cur_user = 'Your current user', form = 'Post form')
        Post form: {title: 'Your title', content: 'Your content', groups: "['groupA', 'groupB']"}
        '''
        form = kwargs['form']
        notify = Notification(form['title'], form['content'])
        db.session.add(notify)
        db.session.commit()
        groups = json.loads(form['groups'])
        for group_name in groups:
            notify_groups = NotificationGroups(notify.id, group_name)
            db.session.add(notify_groups)
        db.session.commit()
        return {"success": 'true'}

    @administration_required
    def list_notifications(self, *args, **kwargs):
        notifies = Notification.query.all()
        notify_infos = []
        for notify in notifies:
            groups = NotificationGroups.query.filter_by(notification_id=notify.id).all()
            notify_infos.append({
                'id': notify.id,
                'title': notify.title,
                'content': notify.content,
                'create_date': notify.create_date,
                'status': notify.status,
                'groups': [group.group_name for group in groups]
            })
        return {'success': 'true', 'data': notify_infos}
