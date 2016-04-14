#!/usr/bin/python3

import os,time,subprocess
import env
import json

class Guest(object):
    def __init__(self,vclusterMgr,nodemgr):
        self.libpath = env.getenv('DOCKLET_LIB')
        self.fspath = env.getenv('FS_PREFIX')
        self.lxcpath = "/var/lib/lxc"
        self.G_vclustermgr = vclusterMgr
        self.nodemgr = nodemgr
    
    def work(self):
        image = {}
        image['name'] = "base"
        image['type'] = "base"
        image['owner'] = "docklet"
        while len(self.nodemgr.get_rpcs()) < 1:
            time.sleep(10)
        if not os.path.isdir(self.fspath+"/global/users/guest"):
            subprocess.getoutput(self.libpath+"/userinit.sh guest")
        user_info = {}
        user_info["data"] = {}
        user_info["data"]["group"] = "primary" 
        user_info["data"]["groupinfo"] = {}
        user_info["data"]["groupinfo"]["cpu"] = 4
        user_info["data"]["groupinfo"]["memory"] = 2000
        user_info["data"]["groupinfo"]["disk"] = 2000
        user_info = json.dumps(user_info)
        self.G_vclustermgr.create_cluster("guestspace", "guest", image, user_info)
        while True:
            self.G_vclustermgr.start_cluster("guestspace", "guest")
            time.sleep(3600)
            self.G_vclustermgr.stop_cluster("guestspace", "guest")
            fspath = self.fspath + "/global/local/volume/guest-1-0/"
            subprocess.getoutput("(cd %s && rm -rf *)" % fspath)
