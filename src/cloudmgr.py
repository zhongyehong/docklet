#!/usr/bin/python3
from io import StringIO
import os,sys,subprocess,time,re,datetime,threading,random,shutil
from model import db, Image
from deploy import *
import json

from log import logger
import env
import requests

fspath = env.getenv('FS_PREFIX')


class AliyunMgr():
    def __init__(self):
        self.AcsClient = __import__('aliyunsdkcore.client', fromlist=["AcsClient"])
        self.Request = __import__('aliyunsdkecs.request.v20140526', fromlist=[
            "CreateInstanceRequest",
            "StopInstanceRequest",
            "DescribeInstancesRequest",
            "DeleteInstanceRequest",
            "StartInstanceRequest",
            "DescribeInstancesRequest",
            "AllocateEipAddressRequest",
            "AssociateEipAddressRequest"])

    def loadClient(self):
        if not os.path.exists(fspath+"/global/sys/cloudsetting.json"):
            currentfilepath = os.path.dirname(os.path.abspath(__file__))
            templatefilepath = currentfilepath + "/../tools/cloudsetting.aliyun.template.json"
            shutil.copyfile(templatefilepath,fspath+"/global/sys/cloudsetting.json")
            logger.error("please modify the setting file first")
            return False
        try:
            settingfile = open(fspath+"/global/sys/cloudsetting.json", 'r')
            self.setting = json.loads(settingfile.read())
            settingfile.close()
            self.clt = self.AcsClient.AcsClient(self.setting['AccessKeyId'],self.setting['AccessKeySecret'], self.setting['RegionId'])
            logger.info("load CLT of Aliyun success")
            return True
        except Exception as e:
            logger.error(e)
            return False
    
    def createInstance(self):
        request = self.Request.CreateInstanceRequest.CreateInstanceRequest()
        request.set_accept_format('json')
        request.add_query_param('RegionId', self.setting['RegionId'])
        if 'ZoneId' in self.setting and not self.setting['ZoneId'] == "": 
            request.add_query_param('ZoneId', self.setting['ZoneId'])
        if 'VSwitchId' in self.setting and not self.setting['VSwitchId'] == "":
            request.add_query_param('VSwitchId', self.setting['VSwitchId'])
        request.add_query_param('ImageId', 'ubuntu_16_0402_64_20G_alibase_20170818.vhd')
        request.add_query_param('InternetMaxBandwidthOut', 1)
        request.add_query_param('InstanceName', 'docklet_tmp_worker')
        request.add_query_param('HostName', 'worker-tmp')
        request.add_query_param('SystemDisk.Size', int(self.setting['SystemDisk.Size']))
        request.add_query_param('InstanceType', self.setting['InstanceType'])
        request.add_query_param('Password', self.setting['Password'])
        response = self.clt.do_action_with_exception(request)
        logger.info(response)
    
        instanceid=json.loads(bytes.decode(response))['InstanceId']
        return instanceid
        
    def startInstance(self, instanceid):
        request = self.Request.StartInstanceRequest.StartInstanceRequest()
        request.set_accept_format('json')
        request.add_query_param('InstanceId', instanceid)
        response = self.clt.do_action_with_exception(request)
        logger.info(response)
        
    
    def createEIP(self):
        request = self.Request.AllocateEipAddressRequest.AllocateEipAddressRequest()
        request.set_accept_format('json')
        request.add_query_param('RegionId', self.setting['RegionId'])
        response = self.clt.do_action_with_exception(request)
        logger.info(response)
    
        response=json.loads(bytes.decode(response))
        eipid=response['AllocationId']
        eipaddr=response['EipAddress']

        return [eipid, eipaddr]


    def associateEIP(self, instanceid, eipid):
        request = self.Request.AssociateEipAddressRequest.AssociateEipAddressRequest()
        request.set_accept_format('json')
        request.add_query_param('AllocationId', eipid)
        request.add_query_param('InstanceId', instanceid)
        response = self.clt.do_action_with_exception(request)
        logger.info(response)

    
    def getInnerIP(self, instanceid):
        request = self.Request.DescribeInstancesRequest.DescribeInstancesRequest()
        request.set_accept_format('json')
        response = self.clt.do_action_with_exception(request)
        instances = json.loads(bytes.decode(response))['Instances']['Instance']
        for instance in instances:
            if instance['InstanceId'] == instanceid:
                return instance['NetworkInterfaces']['NetworkInterface'][0]['PrimaryIpAddress']
        return json.loads(bytes.decode(response))['Instances']['Instance'][0]['VpcAttributes']['PrivateIpAddress']['IpAddress'][0]

    def isStarted(self, instanceids):
        request = self.Request.DescribeInstancesRequest.DescribeInstancesRequest()
        request.set_accept_format('json')
        response = self.clt.do_action_with_exception(request)
        instances = json.loads(bytes.decode(response))['Instances']['Instance']
        for instance in instances:
            if instance['InstanceId'] in instanceids:
                if not instance['Status'] == "Running":
                    return False
        return True

    def rentServers(self,number):
        instanceids=[]
        eipids=[]
        eipaddrs=[]
        for i in range(int(number)):
            instanceids.append(self.createInstance())
            time.sleep(2)
        time.sleep(10)
        for i in range(int(number)):
            [eipid,eipaddr]=self.createEIP()
            eipids.append(eipid)
            eipaddrs.append(eipaddr)
            time.sleep(2)
        masterip=env.getenv('ETCD').split(':')[0]
        for i in range(int(number)):
            self.associateEIP(instanceids[i],eipids[i])
            time.sleep(2)
        time.sleep(5)
        for instanceid in instanceids:
            self.startInstance(instanceid)
            time.sleep(2)
        time.sleep(10)
        while not self.isStarted(instanceids):
            time.sleep(10)
        time.sleep(5)
        return [masterip, eipaddrs]

    def addNode(self):
        if not self.loadClient():
            return {'success':'false'}
        [masterip, eipaddrs] = self.rentServers(1)
        threads = []
        for eip in eipaddrs:
            thread = threading.Thread(target = deploy, args=(eip,masterip,'root',self.setting['Password'],self.setting['VolumeName']))
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
        return {'success':'true'}

    def addNodeAsync(self):
        thread = threading.Thread(target = self.addNode)
        thread.setDaemon(True)
        thread.start()

class CloudMgr():
    
    def getSettingFile(self):
        if not os.path.exists(fspath+"/global/sys/cloudsetting.json"):
            currentfilepath = os.path.dirname(os.path.abspath(__file__))
            templatefilepath = currentfilepath + "/../tools/cloudsetting.aliyun.template.json"
            shutil.copyfile(templatefilepath,fspath+"/global/sys/cloudsetting.json")
        settingfile = open(fspath+"/global/sys/cloudsetting.json", 'r')
        setting = settingfile.read()
        settingfile.close()
        return {'success':'true', 'result':setting}

    def modifySettingFile(self, setting):
        if setting == None:
            logger.error("setting is None")
            return {'success':'false'}
        settingfile = open(fspath+"/global/sys/cloudsetting.json", 'w')
        settingfile.write(setting)
        settingfile.close()
        return {'success':'true'}


    def __init__(self):
        self.engine = AliyunMgr()
