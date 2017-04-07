import requests
from flask import abort, session
from webViews.log import logger
import os,sys,inspect

this_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe    ()))[0]))
src_folder = os.path.realpath(os.path.abspath(os.path.join(this_folder,"../..", "src")))
if src_folder not in sys.path:
    sys.path.insert(0, src_folder)

import env

masterips=env.getenv('MASTER_IPS').split(",")
#endpoint = "http://0.0.0.0:9000"
user_endpoint = "http://0.0.0.0:9100"

def getip(masterip):
    return masterip.split("@")[0]

def getname(masterip):
    return masterip.split("@")[1]

class dockletRequest():

    @classmethod
    def post(self, url = '/', data = {}, endpoint = "http://0.0.0.0:9000"):
        #try:
        data = dict(data)
        data['token'] = session['token']
        logger.info ("Docklet Request: user = %s data = %s, url = %s"%(session['username'], data, url))
        reqtype = url.split("/")[1]
        userreq = {
                'login',
                'register',
                'user',
                'beans',
                'notification',
                'cloud'
                }
        if ":" not in endpoint:
            endpoint = "http://"+endpoint+":9000"
        if reqtype in userreq:
            result = requests.post(user_endpoint + url, data=data).json()
        else:
            result = requests.post(endpoint + url, data=data).json()
        # logger.info('response content: %s'%response.content)
        # result = response.json()
        if (result.get('success', None) == "false" and result.get('reason', None) == "Unauthorized Action"):
            abort(401)
        if (result.get('Unauthorized', None) == 'True'):
            session['401'] = 'Token Expired'
            abort(401)
        logger.info ("Docklet Response: user = %s result = %s, url = %s"%(session['username'], result, url))
        return result
        #except:
            #abort(500)
    
    @classmethod
    def post_to_all(self, url = '/', data={}):
        if (url == '/'):
            return masterips
        data = dict(data)
        data['token'] = session['token']
        logger.info("Docklet Request: user = %s data = %s, url = %s"%(session['username'], data, url))
        result = {}
        for masterip in masterips:
            result[masterip] = requests.post("http://"+getip(masterip)+":9000"+url,data=data).json()
            logger.debug("get result from " + getip(masterip))

        return result

    @classmethod
    def unauthorizedpost(self, url = '/', data = None):
        data = dict(data)
        data_log = {'user': data.get('user', 'external')}
        logger.info("Docklet Unauthorized Request: data = %s, url = %s" % (data_log, url))
        result = requests.post(user_endpoint + url, data = data).json()
        logger.info("Docklet Unauthorized Response: result = %s, url = %s"%(result, url))
        return result
