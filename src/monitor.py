#!/usr/bin/python3

'''
Monitor for Docklet
Description:Monitor system for docklet will collect data on resources usages and status of vnode 
            and phyiscal machines. And master can fetch these data and then show them on the web page.
            Besides, Monitor will also bill the vnodes according to their resources usage amount.

Design:Monitor mainly consists of three parts: Collectors, Master_Collector and Fetchers.
       1.Collectors will collect data every two seconds on each worker. And 'Container_Collector' will 
       collect data of containers(vnodes), while 'Collector' will collect data of physical machines.
       2.'Master_Collector' only runs on Master. It fetches the data on workers every two seconds by rpc 
       and stores them in the memory of Master.
       3.Fetchers are classes that Master will use them to fetch specific data in the memory and then show 
       them on the web. 'Container_Fetcher' is the class to fetch the containers data in 'monitor_vnodes', 
       while 'Fetcher' is the class to fetch the data of physical machines in 'monitor_hosts'.
'''


import subprocess,re,os,etcdlib,psutil,math,sys
import time,threading,json,traceback,platform
import env
from datetime import datetime

from model import db,VNode,History,User
from log import logger
from httplib2 import Http
from urllib.parse import urlencode

# billing parameters
a_cpu = 500         # seconds
b_mem = 1000000     # MB
c_disk = 4000       # MB

# major dict to store the monitoring data
# only use on Master
# monitor_hosts: use workers' ip addresses as first key.
# second key: cpuinfo,diskinfo,meminfo,osinfo,cpuconfig,running,containers,containerslist
# 1.cpuinfo stores the cpu usages data, and it has keys: user,system,idle,iowait
# 2.diskinfo stores the disks usages data, and it has keys: device,mountpoint,total,used,free,percent
# 3.meminfo stores the memory usages data, and it has keys: total,used,free,buffers,cached,percent
# 4.osinfo stores the information of operating system, 
# and it has keys: platform,system,node,release,version,machine,processor              
# 5.cpuconfig stores the information of processors, and it is a list, each element of list is a dict
# which stores the information of a processor, each element has key: processor,model name,
# core id, cpu MHz, cache size, physical id.
# 6.running indicates the status of worker,and it has two values: True, False.
# 7.containers store the amount of containers on the worker.
# 8.containers store a list which consists of the names of containers on the worker.
moitor_hosts = {}

# monitor_vnodes: use the names of vnodes(containers) as first key.
# second key: cpu_use,mem_use,disk_use,basic_info,quota
# 1.cpu_use has keys: val,unit,hostpercent
# 2.mem_use has keys: val,unit,usedp
# 3.disk_use has keys: device,mountpoint,total,used,free,percent
# 4.basic_info has keys: Name,State,PID,IP,RunningTime,billing,billing_this_hour
# 5.quota has keys: cpu,memeory
monitor_vnodes = {}

# major dict to store the monitoring data on Worker
# only use on Worker
# workerinfo: only store the data collected on current Worker, 
# has the first keys same as the second keys in monitor_hosts.
workerinfo = {}

# workercinfo: only store the data collected on current Worker,
# has the first keys same as the second keys in monitor_vnodes.
workercinfo = {}

# only use on worker
containerpids = []
pid2name = {}
G_masterip = ""

# only use on worker
laststopcpuval = {}
laststopruntime = {}
lastbillingtime = {}        
# increment has keys: lastcputime,memincrement. 
# record the cpu val at last billing time and accumulate the memory usages during this billing hour.    
increment = {}  

# send http request to master
def request_master(url,data):
    global G_masterip
    header = {'Content-Type':'application/x-www-form-urlencoded'}
    http = Http()
    [resp,content] = http.request("http://"+G_masterip+url,"POST",urlencode(data),headers = header)
    logger.info("response from master:"+content.decode('utf-8'))  

# The class is to collect data of containers on each worker
class Container_Collector(threading.Thread):

    def __init__(self,test=False):
        global laststopcpuval
        global workercinfo
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.interval = 2       
        self.billingtime = 3600     # billing interval
        self.test = test
        self.cpu_last = {}
        self.cpu_quota = {}
        self.mem_quota = {}
        self.cores_num = int(subprocess.getoutput("grep processor /proc/cpuinfo | wc -l"))
        containers = self.list_container()
        for container in containers:    # recovery
            if not container == '':
                try:
                    vnode = VNode.query.get(container)
                    laststopcpuval[container] = vnode.laststopcpuval
                    laststopruntime[container] = vnode.laststopruntime
                    workercinfo[container] = {}
                    workercinfo[container]['basic_info'] = {}
                    workercinfo[container]['basic_info']['billing'] = vnode.billing
                    workercinfo[container]['basic_info']['RunningTime'] = vnode.laststopruntime
                except:
                    laststopcpuval[container] = 0
                    laststopruntime[container] = 0
        return
    
    # list containers on this worker
    def list_container(self):
        output = subprocess.check_output(["sudo lxc-ls"],shell=True)
        output = output.decode('utf-8')
        containers = re.split('\s+',output)
        return containers
    
    # get running time of a process, return seconds
    def get_proc_etime(self,pid):
        fmt = subprocess.getoutput("ps -A -opid,etime | grep '^ *%d ' | awk '{print $NF}'" % pid).strip()
        if fmt == '':
            return -1
        parts = fmt.split('-')
        days = int(parts[0]) if len(parts) == 2 else 0
        fmt = parts[-1]
        parts = fmt.split(':')
        hours = int(parts[0]) if len(parts) == 3 else 0
        parts = parts[len(parts)-2:]
        minutes = int(parts[0])
        seconds = int(parts[1])
        return ((days * 24 + hours) * 60 + minutes) * 60 + seconds
    
    # compute the billing val this running hour
    # if isreal is True, it will also make users' beans decrease to pay for the bill.
    @classmethod
    def billing_increment(cls,vnode_name,isreal=True):
        global increment
        global workercinfo
        global G_masterip
        global a_cpu
        global b_mem
        global c_disk
        cpu_val = '0'
        if vnode_name not in workercinfo.keys():
            return 0
        if 'cpu_use' in workercinfo[vnode_name].keys():
            cpu_val = workercinfo[vnode_name]['cpu_use']['val']
        if vnode_name not in increment.keys():
            increment[vnode_name] = {}
            increment[vnode_name]['lastcputime'] = cpu_val
            increment[vnode_name]['memincrement'] = 0
        cpu_increment = float(cpu_val) - float(increment[vnode_name]['lastcputime'])
        #logger.info("billing:"+str(cpu_increment)+" "+str(increment[container_name]['lastcputime']))
        if cpu_increment == 0.0:
            avemem = 0
        else:
            avemem = cpu_increment*float(increment[vnode_name]['memincrement'])/1800.0
        if 'disk_use' in workercinfo[vnode_name].keys():
            disk_quota = workercinfo[vnode_name]['disk_use']['total']
        else:
            disk_quota = 0
        billingval = math.ceil(cpu_increment/a_cpu + avemem/b_mem + float(disk_quota)/1024.0/1024.0/c_disk)
        if billingval > 100:
            logger.info("Huge Billingval for "+vnode_name+". cpu_increment:"+str(cpu_increment)+" avemem:"+str(avemem)+" disk:"+str(disk_quota)+"\n")
        if not isreal:
            return math.ceil(billingval)
        increment[vnode_name]['lastcputime'] = cpu_val
        increment[vnode_name]['memincrement'] = 0
        if 'basic_info' not in workercinfo[vnode_name].keys():
            workercinfo[vnode_name]['basic_info'] = {}
            workercinfo[vnode_name]['basic_info']['billing'] = 0
            workercinfo[vnode_name]['basic_info']['RunningTime'] = 0
        nowbillingval = workercinfo[vnode_name]['basic_info']['billing']
        nowbillingval += billingval
        try:
            vnode = VNode.query.get(vnode_name)
            vnode.billing = nowbillingval
        except Exception as err:
            vnode = VNode(vnode_name)
            vnode.billing = nowbillingval
            db.session.add(vnode)
            logger.warning(err)
        try:
            db.session.commit()
        except Exception as err:
            db.session.rollback()
            logger.warning(traceback.format_exc())
            logger.warning(err)
            raise
        workercinfo[vnode_name]['basic_info']['billing'] = nowbillingval
        owner_name = get_owner(vnode_name)
        owner = User.query.filter_by(username=owner_name).first()
        if owner is None:
            logger.warning("Error!!! Billing User %s doesn't exist!" % (owner_name))
        else:
            #logger.info("Billing User:"+str(owner))
            oldbeans = owner.beans
            owner.beans -= billingval
            #logger.info(str(oldbeans) + " " + str(owner.beans))
            if oldbeans > 0 and owner.beans <= 0 or oldbeans >= 100 and owner.beans < 100 or oldbeans >= 500 and owner.beans < 500 or oldbeans >= 1000 and owner.beans < 1000:
                data = {"to_address":owner.e_mail,"username":owner.username,"beans":owner.beans}
                request_master("/beans/mail/",data)
            try:
                db.session.commit()
            except Exception as err:
                db.session.rollback()
                logger.warning(traceback.format_exc())
                logger.warning(err)
            #logger.info("Billing User:"+str(owner))
            if owner.beans <= 0:
                logger.info("The beans of User(" + str(owner) + ") are less than or equal to zero, the container("+vnode_name+") will be stopped.")
                form = {'username':owner.username}
                request_master("/cluster/stopall/",form)
        return billingval

    def collect_containerinfo(self,container_name):
        global workerinfo
        global workercinfo
        global increment
        global lastbillingtime
        global containerpids
        global pid2name
        global laststopcpuval
        global laststopruntime
        output = subprocess.check_output("sudo lxc-info -n %s" % (container_name),shell=True)
        output = output.decode('utf-8')
        parts = re.split('\n',output)
        info = {}
        basic_info = {}
        basic_exist = 'basic_info' in workercinfo[container_name].keys()
        if basic_exist:
            basic_info = workercinfo[container_name]['basic_info']
        else:
            basic_info['RunningTime'] = 0
            basic_info['billing'] = 0
        if 'billing_this_hour' not in basic_info.keys():
            basic_info['billing_this_hour'] = 0
        for part in parts:
            if not part == '':
                key_val = re.split(':',part)
                key = key_val[0]
                val = key_val[1]
                info[key] = val.lstrip()
        basic_info['Name'] = info['Name']
        basic_info['State'] = info['State']
        #if basic_exist:
         #   logger.info(workercinfo[container_name]['basic_info'])
        if(info['State'] == 'STOPPED'):
            workercinfo[container_name]['basic_info'] = basic_info
            #logger.info(basic_info)
            return False
        if not info['PID'] in containerpids:
            containerpids.append(info['PID'])
            pid2name[info['PID']] = container_name
        running_time = self.get_proc_etime(int(info['PID']))
        running_time += laststopruntime[container_name]
        basic_info['PID'] = info['PID']
        basic_info['IP'] = info['IP']
        basic_info['RunningTime'] = running_time
        workercinfo[container_name]['basic_info'] = basic_info

        cpu_parts = re.split(' +',info['CPU use'])
        cpu_val = float(cpu_parts[0].strip())
        cpu_unit = cpu_parts[1].strip()
        if not container_name in self.cpu_last.keys():
            confpath = "/var/lib/lxc/%s/config"%(container_name)
            if os.path.exists(confpath):
                confile = open(confpath,'r')
                res = confile.read()
                lines = re.split('\n',res)
                for line in lines:
                    words = re.split('=',line)
                    key = words[0].strip()
                    if key == "lxc.cgroup.memory.limit_in_bytes":
                        self.mem_quota[container_name] = float(words[1].strip().strip("M"))*1000000/1024
                    elif key == "lxc.cgroup.cpu.cfs_quota_us":
                        tmp = int(words[1].strip())
                        if tmp < 0:
                            self.cpu_quota[container_name] = self.cores_num
                        else:
                            self.cpu_quota[container_name] = tmp/100000.0
                quota = {'cpu':self.cpu_quota[container_name],'memory':self.mem_quota[container_name]}
                #logger.info(quota)
                workercinfo[container_name]['quota'] = quota
            else:
                logger.error("Cant't find config file %s"%(confpath))
                return False
            self.cpu_last[container_name] = 0 
        cpu_use = {}
        lastval = 0
        try:
            lastval = laststopcpuval[container_name]
        except:
            logger.warning(traceback.format_exc())   
        cpu_val += lastval
        cpu_use['val'] = cpu_val
        cpu_use['unit'] = cpu_unit
        cpu_usedp = (float(cpu_val)-float(self.cpu_last[container_name]))/(self.cpu_quota[container_name]*self.interval*1.05)
        cpu_use['hostpercent'] = (float(cpu_val)-float(self.cpu_last[container_name]))/(self.cores_num*self.interval*1.05)
        if(cpu_usedp > 1 or cpu_usedp < 0):
            cpu_usedp = 1
        cpu_use['usedp'] = cpu_usedp
        self.cpu_last[container_name] = cpu_val;
        workercinfo[container_name]['cpu_use'] = cpu_use
        
        if container_name not in increment.keys():
            increment[container_name] = {}
            increment[container_name]['lastcputime'] = cpu_val
            increment[container_name]['memincrement'] = 0

        mem_parts = re.split(' +',info['Memory use'])
        mem_val = mem_parts[0].strip()
        mem_unit = mem_parts[1].strip()
        mem_use = {}
        mem_use['val'] = mem_val
        mem_use['unit'] = mem_unit
        if(mem_unit == "MiB"):
            increment[container_name]['memincrement'] += float(mem_val)
            mem_val = float(mem_val) * 1024
        elif (mem_unit == "GiB"):
            increment[container_name]['memincrement'] += float(mem_val)*1024
            mem_val = float(mem_val) * 1024 * 1024
        mem_usedp = float(mem_val) / self.mem_quota[container_name]
        mem_use['usedp'] = mem_usedp
        workercinfo[container_name]['mem_use'] = mem_use
        workercinfo[container_name]['basic_info']['billing_this_hour'] = self.billing_increment(container_name,False)
        
        if not container_name in lastbillingtime.keys():
            lastbillingtime[container_name] = int(running_time/self.billingtime)
        lasttime = lastbillingtime[container_name]
        #logger.info(lasttime)
        if not int(running_time/self.billingtime) == lasttime:
            #logger.info("billing:"+str(float(cpu_val)))
            lastbillingtime[container_name] = int(running_time/self.billingtime)
            self.billing_increment(container_name)
        #print(output)
        #print(parts)
        return True

    def run(self):
        global workercinfo
        global workerinfo
        cnt = 0
        while not self.thread_stop:
            containers = self.list_container()
            countR = 0
            conlist = []
            for container in containers:
                if not container == '':
                    conlist.append(container)
                    if not container in workercinfo.keys():
                        workercinfo[container] = {}
                    try:
                        success= self.collect_containerinfo(container)
                        if(success):
                            countR += 1
                    except Exception as err:
                        logger.warning(traceback.format_exc())
                        logger.warning(err)
            containers_num = len(containers)-1
            concnt = {}
            concnt['total'] = containers_num
            concnt['running'] = countR
            workerinfo['containers'] = concnt
            time.sleep(self.interval)
            if cnt == 0:
                workerinfo['containerslist'] = conlist
            cnt = (cnt+1)%5
            if self.test:
                break
        return

    def stop(self):
        self.thread_stop = True


class Collector(threading.Thread):

    def __init__(self,test=False):
        global workerinfo
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.interval = 1
        self.test=test
        workerinfo['concpupercent'] = {}
        return

    def collect_meminfo(self):
        meminfo = psutil.virtual_memory()
        memdict = {}
        memdict['total'] = meminfo.total/1024
        memdict['used'] = meminfo.used/1024
        memdict['free'] = meminfo.free/1024
        memdict['buffers'] = meminfo.buffers/1024
        memdict['cached'] = meminfo.cached/1024
        memdict['percent'] = meminfo.percent
        #print(output)
        #print(memparts)
        return memdict

    def collect_cpuinfo(self):
        cpuinfo = psutil.cpu_times_percent(interval=1,percpu=False)
        cpuset = {}
        cpuset['user'] = cpuinfo.user
        cpuset['system'] = cpuinfo.system
        cpuset['idle'] = cpuinfo.idle
        cpuset['iowait'] = cpuinfo.iowait
        output = subprocess.check_output(["cat /proc/cpuinfo"],shell=True)
        output = output.decode('utf-8')
        parts = output.split('\n')
        info = []
        idx = -1
        for part in parts:
            if not part == '':
                key_val = re.split(':',part)
                key = key_val[0].rstrip()
                if key == 'processor':
                    info.append({})
                    idx += 1
                val = key_val[1].lstrip()
                if key=='processor' or key=='model name' or key=='core id' or key=='cpu MHz' or key=='cache size' or key=='physical id':
                    info[idx][key] = val
        return [cpuset, info]

    def collect_diskinfo(self):
        global workercinfo
        parts = psutil.disk_partitions()
        setval = []
        devices = {}
        for part in parts:
            if not part.device in devices:
                devices[part.device] = 1
                diskval = {}
                diskval['device'] = part.device
                diskval['mountpoint'] = part.mountpoint
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    diskval['total'] = usage.total
                    diskval['used'] = usage.used
                    diskval['free'] = usage.free
                    diskval['percent'] = usage.percent
                    if(part.mountpoint.startswith('/opt/docklet/local/volume')):
                        names = re.split('/',part.mountpoint)
                        container = names[len(names)-1]
                        if not container in workercinfo.keys():
                            workercinfo[container] = {}
                        workercinfo[container]['disk_use'] = diskval 
                    setval.append(diskval)
                except Exception as err:
                    logger.warning(traceback.format_exc())
                    logger.warning(err)
        #print(output)
        #print(diskparts)
        return setval

    def collect_osinfo(self):
        uname = platform.uname()
        osinfo = {}
        osinfo['platform'] = platform.platform()
        osinfo['system'] = uname.system
        osinfo['node'] = uname.node
        osinfo['release'] = uname.release
        osinfo['version'] = uname.version
        osinfo['machine'] = uname.machine
        osinfo['processor'] = uname.processor
        return osinfo

    def collect_concpuinfo(self):
        global workerinfo
        global containerpids
        global pid2name
        l = len(containerpids)
        if l == 0:
            return
        cmd = "sudo top -bn 1"
        for pid in containerpids:
            cmd = cmd + " -p " + pid
        #child = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        #[stdout,errout] = child.communicate()
        #logger.info(errout)
        #logger.info(stdout)
        output = ""
        output = subprocess.check_output(cmd,shell=True)
        output = output.decode('utf-8')
        parts = re.split("\n",output)
        concpupercent = workerinfo['concpupercent']
        for line in parts[7:]:
            if line == "":
                continue
            info = re.split(" +",line)
            pid = info[1].strip()
            cpupercent = float(info[9].strip())
            name = pid2name[pid]
            concpupercent[name] = cpupercent

    def run(self):
        global workerinfo
        workerinfo['osinfo'] = self.collect_osinfo()
        while not self.thread_stop:
            workerinfo['meminfo'] = self.collect_meminfo()
            [cpuinfo,cpuconfig] = self.collect_cpuinfo()
            #self.collect_concpuinfo()
            workerinfo['cpuinfo'] = cpuinfo
            workerinfo['cpuconfig'] = cpuconfig
            workerinfo['diskinfo'] = self.collect_diskinfo()
            workerinfo['running'] = True
            #time.sleep(self.interval)
            if self.test:
                break
            #   print(self.etcdser.getkey('/meminfo/total'))
        return

    def stop(self):
        self.thread_stop = True

def workerFetchInfo(master_ip):
    global workerinfo
    global workercinfo
    global G_masterip
    G_masterip = master_ip
    return str([workerinfo, workercinfo])

def get_owner(container_name):
    names = container_name.split('-')
    return names[0]

class Master_Collector(threading.Thread):

    def __init__(self,nodemgr,master_ip):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.nodemgr = nodemgr
        self.master_ip = master_ip
        return

    def run(self):
        global monitor_hosts
        global monitor_vnodes
        while not self.thread_stop:
            for worker in monitor_hosts.keys():
                monitor_hosts[worker]['running'] = False
            workers = self.nodemgr.get_rpcs()
            for worker in workers:
                try:
                    ip = self.nodemgr.rpc_to_ip(worker)
                    info = list(eval(worker.workerFetchInfo(self.master_ip)))
                    #logger.info(info[0])
                    monitor_hosts[ip] = info[0]
                    for container in info[1].keys():
                        owner = get_owner(container)
                        if not owner in monitor_vnodes.keys():
                            monitor_vnodes[owner] = {}
                        monitor_vnodes[owner][container] = info[1][container]
                except Exception as err:
                    logger.warning(traceback.format_exc())
                    logger.warning(err)
            time.sleep(2)
            #logger.info(History.query.all())
            #logger.info(VNode.query.all())
        return

    def stop(self):
        self.thread_stop = True
        return

class Container_Fetcher:
    def __init__(self,container_name):
        self.owner = get_owner(container_name)
        self.con_id = container_name
        return

    def get_cpu_use(self):
        global monitor_vnodes
        try:
            res = monitor_vnodes[self.owner][self.con_id]['cpu_use']
            res['quota'] = monitor_vnodes[self.owner][self.con_id]['quota']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_mem_use(self):
        global monitor_vnodes
        try:
            res = monitor_vnodes[self.owner][self.con_id]['mem_use']
            res['quota'] = monitor_vnodes[self.owner][self.con_id]['quota']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_disk_use(self):
        global monitor_vnodes
        try:
            res = monitor_vnodes[self.owner][self.con_id]['disk_use']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_basic_info(self):
        global monitor_vnodes
        try:
            res = monitor_vnodes[self.owner][self.con_id]['basic_info']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

class Fetcher:

    def __init__(self,host):
        global monitor_hosts
        self.info = monitor_hosts[host]
        return

    #def get_clcnt(self):
    #   return DockletMonitor.clcnt

    #def get_nodecnt(self):
    #   return DockletMonitor.nodecnt

    #def get_meminfo(self):
    #   return self.get_meminfo_('172.31.0.1')

    def get_meminfo(self):
        try:
            res = self.info['meminfo']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_cpuinfo(self):
        try:
            res = self.info['cpuinfo']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_cpuconfig(self):
        try:
            res = self.info['cpuconfig']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_diskinfo(self):
        try:
            res = self.info['diskinfo']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_osinfo(self):
        try:
            res = self.info['osinfo']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_concpuinfo(self):
        try:
            res = self.info['concpupercent']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_containers(self):
        try:
            res = self.info['containers']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

    def get_status(self):
        try:
            isexist = self.info['running']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            isexist = False
        if(isexist):
            return 'RUNNING'
        else:
            return 'STOPPED'

    def get_containerslist(self):
        try:
            res = self.info['containerslist']
        except Exception as err:
            logger.warning(traceback.format_exc())
            logger.warning(err)
            res = {}
        return res

class History_Manager:
    
    def __init__(self):
        try:
            VNode.query.all()
            History.query.all()
        except:
            db.create_all(bind='__all__')

    def getAll(self):
        return History.query.all()
    
    def log(self,vnode_name,action):
        global workercinfo
        global laststopcpuval
        res = VNode.query.filter_by(name=vnode_name).first()
        if res is None:
            vnode = VNode(vnode_name)
            vnode.histories = []
            db.session.add(vnode)
            db.session.commit()
        vnode = VNode.query.get(vnode_name)
        billing = 0
        cputime = 0
        runtime = 0
        owner = get_owner(vnode_name)
        try:
            billing = int(workercinfo[vnode_name]['basic_info']['billing'])
        except:
            billing = 0
        try:
            cputime = float(workercinfo[vnode_name]['cpu_use']['val'])
        except:
            cputime = 0.0
        try:    
            runtime = float(workercinfo[vnode_name]['basic_info']['RunningTime'])
        except Exception as err:
            #print(traceback.format_exc())
            runtime = 0
        history = History(action,runtime,cputime,billing)
        vnode.histories.append(history)
        if action == 'Stop' or action == 'Create':
            laststopcpuval[vnode_name] = cputime
            vnode.laststopcpuval = cputime
            laststopruntime[vnode_name] = runtime
            vnode.laststopruntime = runtime
        db.session.add(history)
        db.session.commit()

    def getHistory(self,vnode_name):
        vnode = VNode.query.filter_by(name=vnode_name).first()
        if vnode is None:
            return []
        else:
            res = History.query.filter_by(vnode=vnode_name).all()
            return list(eval(str(res)))

    def getCreatedVNodes(self,owner):
        vnodes = VNode.query.filter(VNode.name.startswith(owner)).all()
        res = []
        for vnode in vnodes:
            tmp = {"name":vnode.name,"billing":vnode.billing}
            res.append(tmp)
        return res
