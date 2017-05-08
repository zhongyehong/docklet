#!/usr/bin/python3

import env
import json, os
from log import logger
from werkzeug.utils import secure_filename

logsPath = env.getenv('FS_PREFIX') + '/local/log/'

class logsClass:
    setting = {}

    def list(*args, **kwargs):
        if ( ('user_group' in kwargs) == False):
            return {"success":'false', "reason":"Cannot get user_group"}
        user_group = kwargs['user_group']
        if (not ((user_group == 'admin') or (user_group == 'root'))):
            return {"success": 'false', "reason": 'Unauthorized Action'}
        s = os.listdir(logsPath)
        r = []
        for i in s:
            if ('log' in i):
                r.append(i)
        return {'success': 'true', 'result': r}

    def get(*args, **kwargs):
        if ( ('user_group' in kwargs) == False):
            return {"success":'false', "reason":"Cannot get user_group"}
        user_group = kwargs['user_group']
        if (not ((user_group == 'admin') or (user_group == 'root'))):
            return {"success": 'false', "reason": 'Unauthorized Action'}
        filepath = logsPath + secure_filename(kwargs['filename'])
        try:
            if not os.path.exists(filepath):
                return {"success": 'false', "reason": 'file not exist'}
            logfile = open(filepath, 'r')
            logtext = logfile.read()
            logfile.close()
            return {'success': 'true', 'result': logtext}
        except:
            return {'success': 'false', 'reason': 'file read error'}



logs = logsClass()
