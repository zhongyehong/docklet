#!/usr/bin/python3
from io import StringIO
import threading
import os,sys,subprocess,time,re,threading,random,shutil
from datetime import datetime, timedelta
from utils.model import db, Image, CloudNode
from master.deploy import *
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import NodeAuthPassword
import json

from utils.log import logger
from utils import env
import requests

fspath = env.getenv('FS_PREFIX')



class AliyunMgr(threading.Thread):
    def __init__(self, nodemgr): 
        threading.Thread.__init__(self)
        try:
            CLoudNode.query.all()
        except:
            db.create_all()
        self.nodemgr = nodemgr
        self.cls = get_driver(Provider.ALIYUN_ECS)
        self.loadSetting()
        self.sizes = self.driver.list_sizes()
        logger.info("load cloud instance type success")
        images = self.driver.list_images()
        self.image = [i for i in images if self.setting['ImageName'] == i.name][0]
        logger.info("load cloud image success")
        sgs = self.driver.ex_list_security_groups()
        self.sg = [s for s in sgs if "docklet" == s.name][0].id
        logger.info("load security group success")
        self.auth = NodeAuthPassword(self.setting['Password'])
        # self.master_ip = env.getenv('ETCD').split(':')[0]
        self.master_ip = "192.168.0.110"
        self.DISK_TYPE_MAP = {
            'hdd': {
                'type': self.driver.disk_categories.CLOUD_EFFICIENCY,
                'price': 0.00049
            },
            'ssd': {
                'type': self.driver.disk_categories.CLOUD_SSD,
                'price': 0.0014
            }
        }
        self.INSTANCE_TYPE_MAP = {
            'ecs.g5.large': {
                'cpu': 2.0,
                'memory': 8190.0,
                'price': 0.89
            },
            'ecs.hfg5.large': {
                'cpu': 2.0,
                'memory': 8192.0,
                'price': 1.15
            }
        }

    def run(self):
        self.autoRemove()

    def loadSetting(self):
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
            self.driver = self.cls(self.setting['AccessKeyId'], self.setting['AccessKeySecret'], region = self.setting['RegionId'])
            logger.info("load CLT of Aliyun success")
            return True
        except Exception as e:
            logger.error(e)
            return False

    def generateDiskConf(self, disk_type, disk_size):
        return {
            'size': disk_size,
            'category': self.DISK_TYPE_MAP[disk_type]['type']
        }

    def getInstanceTypeInfoByName(self, instance_type):
        return self.INSTANCE_TYPE_MAP[instance_type]

    def getDiskPrice(self, disk_type, disk_size):
        return self.DISK_TYPE_MAP[disk_type]['price'] * disk_size

    def createInstance(self, instance_type, disk):
        node = None
        try:
            size = [s for s in self.sizes if s.id == instance_type][0]
            node = self.driver.create_node(name=self.setting['NodeName'], size=size, image=self.image, auth=self.auth, 
                ex_public_ip=True,
                ex_system_disk=disk,
                ex_vswitch_id=self.setting["VSwitchId"], 
                ex_security_group_id=self.sg,
                ex_internet_charge_type="PayByTraffic",
                ex_internet_max_bandwidth_out=30)
            logger.info("create instance success, id: {}, ip: {}".format(node.id, node.public_ips[0]))
        except Exception as ex:
            logger.error("an error occured during creating instance -- {}".format(ex))
            return None

        return node

    def addNode(self, instance_type, disk_type, disk_size):
        disk = self.generateDiskConf(disk_type, disk_size)
        node = self.createInstance(instance_type, disk)
        if node:
            try:
                deploy(node.public_ips[0], self.master_ip, 'root', self.setting['Password'], self.setting['VolumeName'], 1024*int(disk_size-20))
                self._wait_until_start(node)
                instance_type_info =  self.getInstanceTypeInfoByName(instance_type)
                disk_price = self.getDiskPrice(disk_type, disk_size)
                node_info = CloudNode(node.id, node.public_ips[0], node.private_ips[0], self.setting['Password'],
                    instance_type, instance_type_info['cpu'], instance_type_info['memory'], disk_size*1024, instance_type_info['price'] + disk_price)
                db.session.add(node_info)
                db.session.commit()
                return {'success': 'true', 'node': node_info}
            except Exception as ex:
                logger.error("an error occured during deploying docklet -- {}".format(ex))
                self.driver.destroy_node(node)
                return {'success': 'false'}
        else:
            return {'success':'false'}

    def _wait_until_start(self, node, wait_period=3, timeout=600):
        start = time.time()
        end = start + timeout

        while(time.time() < end):
            all_nodes = self.nodemgr.get_batch_nodeips()
            if node.private_ips[0] in all_nodes:
                return 
            else:
                time.sleep(wait_period)

        raise ValueError('start instance failed')

    def deleteNode(self, node_id):
        try:
            node_info = CloudNode.query.filter_by(node_id=node_id).first()
            nodes = self.driver.list_nodes(ex_node_ids=[node_id])
            if len(nodes) != 1:
                logger.error("node_id could not be found in aliyun")
                db.session.delete(node_info)
                db.session.commit()
                return {'success': 'false'}
            node = nodes[0]
            self.driver.destroy_node(node)
            db.session.delete(node_info)
            db.session.commit()
            logger.info("delete node: {} success".format(node_id))
            return {'success': 'true'}
        except Exception as ex:
            logger.error("destroy node: {} -- {}".format(node_id, ex))
            return {'success': 'false'}

    def listNodes(self):
        nodes = CloudNode.query.all()
        return nodes

    def listNodesInfo(self):
        nodes = CloudNode.query.all()
        node_info_list = []
        for node in nodes:
            node_info_list.append(json.loads(str(node)))
        return node_info_list

    def addTaskToNode(self, node_ip, task):
        node = CloudNode.query.filter_by(private_ip=node_ip).first()
        node.cpu_free -= task.info.cluster.instance.cpu
        node.memory_free -= task.info.cluster.instance.memory
        node.disk_free -= task.info.cluster.instance.disk
        node.running_task_number += 1
        db.session.commit()
        return True


    def removeTaskFromNode(self, node_ip, task):
        node = CloudNode.query.filter_by(private_ip=node_ip).first()
        node.cpu_free += task.info.cluster.instance.cpu
        node.memory_free += task.info.cluster.instance.memory
        node.disk_free += task.info.cluster.instance.disk
        node.running_task_number -= 1
        db.session.commit()
        return True

    def addNodeAsync(self, instance_type, disk_type, disk_size):
        thread = threading.Thread(target = self.addNode, args=(instance_type, disk_type, disk_size))
        thread.setDaemon(True)
        thread.start()

    def autoRemove(self, wait_period=120, maintain_time=300):
        while True:
            logger.info("checking free node")
            now_time = datetime.now()
            delta = timedelta(seconds=maintain_time)
            nodes = CloudNode.query.all()
            for node in nodes:
                if node.running_task_number < 10 and node.updated_time + delta < now_time:
                    self.deleteNode(node.node_id)
            time.sleep(wait_period)

class EmptyMgr():
    def addNodeAsync(self):
        logger.error("current cluster does not support scale out")
        return False

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


    def __init__(self, nodemgr=None):
        if env.getenv("ALLOW_SCALE_OUT") == "True":
            self.engine = AliyunMgr(nodemgr)
            self.engine.start()
        else:
            self.engine = EmptyMgr()
