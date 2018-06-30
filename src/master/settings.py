#!/usr/bin/python3

from utils import env
import json, os
from functools import wraps
from utils.log import logger


class settingsClass:
    setting = {}
    def __init__(self):
        settingPath = env.getenv('FS_PREFIX') + '/local/settings.conf'
        if not os.path.exists(settingPath):
            settingFile = open(settingPath,'w')
            setting = {}
            settingFile.write(json.dumps(setting))
            settingFile.close()
        else:
            settingFile = open(settingPath, 'r')
            settingText = settingFile.read()
            settingFile.close()
            self.setting = json.loads(settingText)

    def get(self, arg):
        return self.setting.get(arg,'')

    def list(*args, **kwargs):
        if ( ('user_group' in kwargs) == False):
            return {"success":'false', "reason":"Cannot get user_group"}
        user_group = kwargs['user_group']
        if (not ((user_group == 'admin') or (user_group == 'root'))):
            return {"success": 'false', "reason": 'Unauthorized Action'}
        return {'success': 'true', 'result': args[0].setting}

    def update(*args, **kwargs):
        try:
            if ( ('user_group' in kwargs) == False):
                return {"success":'false', "reason":"Cannot get user_group"}
            user_group = kwargs['user_group']
            if (not ((user_group == 'admin') or (user_group == 'root'))):
                return {"success": 'false', "reason": 'Unauthorized Action'}
            newSetting = kwargs['newSetting']
            settingPath = env.getenv('FS_PREFIX') + '/local/settings.conf';
            settingText = json.dumps(newSetting)
            settingFile = open(settingPath,'w')
            settingFile.write(settingText)
            settingFile.close()
            args[0].setting = newSetting
            return {'success': 'true'}
        except:
            return {'success': 'false'}


settings = settingsClass()
