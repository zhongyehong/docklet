#!/usr/bin/python3
from io import StringIO
import os,sys,subprocess,time,re,datetime,threading,random
from model import db, Image
from deploy import *

from log import logger
import env
import requests

fspath = env.getenv('FS_PREFIX')

class CludAccountMgr():
    def cloud_account_query(*args, **kwargs):
        try:
            accountfile = open(fspath+"/global/sys/cloudaccount", 'r')
            account = json.loads(accountfile.read())
            accountfile.close()
        except:
            account = {}
            account['cloud'] = env.getenv('CLOUD') 
            account['accesskey'] = ""
            account['accesssecret'] = ""
        return {"success": 'true', 'accounts':account}

    def cloud_account_modify(*args, **kwargs):
        form = kwargs.get('form')
        account = {}
        account['cloud'] = form['cloud']
        account['accesskey'] = form['accesskey']
        account['accesssecret'] = form['accesssecret']
        accountfile = open(fspath+"/global/sys/cloudaccount", 'w')
        accountfile.write(json.dumps(account))
        accountfile.close()
        return {"success": "true"}


class AliyunMgr():
    def __init__(self):
        self.AcsClient = __import__('aliyunsdkcore.client')
        self.Request = __import__('aliyunsdkecs.request.v20140526')

    def loadClient(self):
        try:
            accountfile = open(fspath+"/global/sys/cloudaccount", 'r')
            account = json.loads(accountfile.read())
            accountfile.close()
            self.clt = self.AcsClient.AcsClient(account['accesskey'],account['accesssecret'],'cn-shanghai')
            logger.info("load CLT of Aliyun success")
            return True
        except:
            logger.error("account file not existed, can not load CLT")
            return False
    
    def createInstance(self,password):
        request = self.Request.CreateInstanceRequest.CreateInstanceRequest()
        request.set_accept_format('json')
        request.add_query_param('RegionId', 'cn-shanghai')
        request.add_query_param('ImageId', 'ubuntu_16_0402_64_20G_alibase_20170818.vhd')
        request.add_query_param('InternetMaxBandwidthOut', 1)
        request.add_query_param('InstanceName', 'docklet_tmp_worker')
        request.add_query_param('HostName', 'worker-tmp')
        request.add_query_param('SystemDisk.Size', 500)
        request.add_query_param('InstanceType', 'ecs.xn4.small')
        request.add_query_param('Password', password)
        response = self.clt.do_action_with_exception(request)
        logger.info(response)
    
        # 获取实例ID
        instanceid=json.loads(bytes.decode(response))['InstanceId']
        return instanceid
        
    # 启动ECS
    def startInstance(self, instanceid):
        request = self.Request.StartInstanceRequest.StartInstanceRequest()
        request.set_accept_format('json')
        request.add_query_param('InstanceId', instanceid)
        response = self.clt.do_action_with_exception(request)
        logger.info(response)
        
    
    # 创建EIP
    def createEIP(self):
        request = self.Request.AllocateEipAddressRequest.AllocateEipAddressRequest()
        request.set_accept_format('json')
        request.add_query_param('RegionId', 'cn-shanghai')
        response = self.clt.do_action_with_exception(request)
        logger.info(response)
    
        response=json.loads(bytes.decode(response))
        eipid=response['AllocationId']
        eipaddr=response['EipAddress']

        return [eipid, eipaddr]


    # 绑定EIP
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

    def rentServers(self):
        instanceids=[]
        eipids=[]
        eipaddrs=[]
        for i in range(int(number)):
            instanceids.append(self.createInstance(password))
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

    def addNodes(self,number=1,password="Unias1616"):
        if not loadClient():
            return False
        [masterip, eipaddrs] = self.rentServers(number,password)
        threads = []
        for eip in eipaddrs:
            thread = threading.Thread(target = deploy, args=(eip,masterip,'root',password))
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
        return True
