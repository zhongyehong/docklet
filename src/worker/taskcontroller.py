#!/usr/bin/python3
import sys
if sys.path[0].endswith("worker"):
    sys.path[0] = sys.path[0][:-6]
from utils import env, tools
config = env.getenv("CONFIG")
#config = "/opt/docklet/local/docklet-running.conf"
tools.loadenv(config)
from utils.log import initlogging
initlogging("docklet-taskcontroller")
from utils.log import logger

from concurrent import futures
import grpc
#from utils.log import logger
#from utils import env
import json,lxc,subprocess,threading,os,time,traceback
from utils import imagemgr,etcdlib,gputools
from worker import ossmounter
from protos import rpc_pb2, rpc_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24
MAX_RUNNING_TIME = _ONE_DAY_IN_SECONDS

def ip_to_int(addr):
    [a, b, c, d] = addr.split('.')
    return (int(a)<<24) + (int(b)<<16) + (int(c)<<8) + int(d)

def int_to_ip(num):
    return str((num>>24)&255)+"."+str((num>>16)&255)+"."+str((num>>8)&255)+"."+str(num&255)

class TaskController(rpc_pb2_grpc.WorkerServicer):

    def __init__(self):
        rpc_pb2_grpc.WorkerServicer.__init__(self)
        etcdaddr = env.getenv("ETCD")
        logger.info ("using ETCD %s" % etcdaddr )

        clustername = env.getenv("CLUSTER_NAME")
        logger.info ("using CLUSTER_NAME %s" % clustername )

        # init etcdlib client
        try:
            self.etcdclient = etcdlib.Client(etcdaddr, prefix = clustername)
        except Exception:
            logger.error ("connect etcd failed, maybe etcd address not correct...")
            sys.exit(1)
        else:
            logger.info("etcd connected")

        # get master ip and report port
        [success,masterip] = self.etcdclient.getkey("service/master")
        if not success:
            logger.error("Fail to get master ip address.")
            sys.exit(1)
        else:
            self.master_ip = masterip
            logger.info("Get master ip address: %s" % (self.master_ip))
        self.master_port = env.getenv('BATCH_MASTER_PORT')

        self.imgmgr = imagemgr.ImageMgr()
        self.fspath = env.getenv('FS_PREFIX')
        self.confpath = env.getenv('DOCKLET_CONF')

        self.taskmsgs = []
        self.msgslock = threading.Lock()
        self.report_interval = 2

        self.lock = threading.Lock()
        self.mount_lock = threading.Lock()
        self.cons_gateway = env.getenv('BATCH_GATEWAY')
        self.cons_ips = env.getenv('BATCH_NET')
        logger.info("Batch gateway ip address %s" % self.cons_gateway)
        logger.info("Batch ip pools %s" % self.cons_ips)

        self.cidr = 32 - int(self.cons_ips.split('/')[1])
        self.ipbase = ip_to_int(self.cons_ips.split('/')[0])
        self.free_ips = []
        for i in range(2, (1 << self.cidr) - 1):
            self.free_ips.append(i)
        logger.info("Free ip addresses pool %s" % str(self.free_ips))

        self.gpu_lock = threading.Lock()
        self.gpu_status = {}
        gpus = gputools.get_gpu_status()
        for gpu in gpus:
            self.gpu_status[gpu['id']] = ""

        self.start_report()
        logger.info('TaskController init success')

    # Need Locks
    def acquire_ip(self):
        self.lock.acquire()
        if len(self.free_ips) == 0:
            return [False, "No free ips"]
        ip = int_to_ip(self.ipbase + self.free_ips[0])
        self.free_ips.remove(self.free_ips[0])
        logger.info(str(self.free_ips))
        self.lock.release()
        return [True, ip + "/" + str(32 - self.cidr)]

    # Need Locks
    def release_ip(self,ipstr):
        self.lock.acquire()
        ipnum = ip_to_int(ipstr.split('/')[0]) - self.ipbase
        self.free_ips.append(ipnum)
        logger.info(str(self.free_ips))
        self.lock.release()

    def add_gpu_device(self, lxcname, gpu_need):
        if gpu_need < 1:
            return [True, ""]
        self.gpu_lock.acquire()
        use_gpus = []
        for gpuid in self.gpu_status.keys():
            if self.gpu_status[gpuid] == "":
                use_gpus.append(gpuid)
        if len(use_gpus) < gpu_need:
            self.gpu_lock.release()
            return [False, "No free GPUs"]
        for gpuid in use_gpus:
            self.gpu_status[gpuid] = lxcname
        try:
            gputools.add_device(lxcname, "/dev/nvidiactl")
            gputools.add_device(lxcname, "/dev/nvidia-uvm")
            for gpuid in use_gpus:
                gputools.add_device(lxcname,"/dev/nvidia"+str(gpuid))
                logger.info("Add gpu:"+str(gpuid) +" to lxc:"+str(lxcname))
        except Exception as e:
            logger.error(traceback.format_exc())
            for gpuid in use_gpus:
                self.gpu_status[gpuid] = ""
            self.gpu_lock.release()
            return [False, "Error occurs when adding gpu device."]

        self.gpu_lock.release()
        return [True, ""]

    def release_gpu_device(self, lxcname):
        self.gpu_lock.acquire()
        for gpuid in self.gpu_status.keys():
            if self.gpu_status[gpuid] == lxcname:
                self.gpu_status[gpuid] = ""
        self.gpu_lock.release()

    #mount_oss
    def mount_oss(self, datapath, mount_info):
        self.mount_lock.acquire()
        try:
            for mount in mount_info:
                provider = mount.provider
                mounter = getattr(ossmounter,provider+"OssMounter",None)
                if mounter is None:
                    self.mount_lock.release()
                    return [False, provider + " doesn't exist!"]
                [success, msg] = mounter.mount_oss(datapath,mount)
                if not success:
                    self.mount_lock.release()
                    return [False, msg]
        except Exception as err:
            self.mount_lock.release()
            logger.error(traceback.format_exc())
            return [False,""]

        self.mount_lock.release()
        return [True,""]

    #umount oss
    def umount_oss(self, datapath, mount_info):
        try:
            for mount in mount_info:
                provider = mount.provider
                mounter = getattr(ossmounter,provider+"OssMounter",None)
                if mounter is None:
                    return [False, provider + " doesn't exist!"]
                [success, msg] = mounter.umount_oss(datapath,mount)
                if not success:
                    return [False, msg]
        except Exception as err:
            logger.error(traceback.format_exc())
            return [False,""]

    def process_task(self, request, context):
        logger.info('excute task with parameter: ' + str(request))
        taskid = request.id
        instanceid = request.instanceid

        # get config from request
        command = request.parameters.command.commandLine #'/root/getenv.sh'  #parameter['Parameters']['Command']['CommandLine']
        #envs = {'MYENV1':'MYVAL1', 'MYENV2':'MYVAL2'} #parameters['Parameters']['Command']['EnvVars']
        pkgpath = request.parameters.command.packagePath
        envs = request.parameters.command.envVars
        envs['taskid'] = str(taskid)
        envs['instanceid'] = str(instanceid)
        image = {}
        image['name'] = request.cluster.image.name
        if request.cluster.image.type == rpc_pb2.Image.PRIVATE:
            image['type'] = 'private'
        elif request.cluster.image.type == rpc_pb2.Image.PUBLIC:
            image['type'] = 'public'
        else:
            image['type'] = 'base'
        image['owner'] = request.cluster.image.owner
        username = request.username
        token = request.token
        lxcname = '%s-batch-%s-%s-%s' % (username,taskid,str(instanceid),token)
        instance_type =  request.cluster.instance
        mount_list = request.cluster.mount
        outpath = [request.parameters.stdoutRedirectPath,request.parameters.stderrRedirectPath]
        for i in range(len(outpath)):
            if outpath[i] == "":
                outpath[i] = "/root/nfs/"
        timeout = request.timeout
        gpu_need = int(request.cluster.instance.gpu)

        # acquire ip
        [status, ip] = self.acquire_ip()
        if not status:
            return rpc_pb2.Reply(status=rpc_pb2.Reply.REFUSED, message=ip)

        # prepare image and filesystem
        status = self.imgmgr.prepareFS(username,image,lxcname,str(instance_type.disk))
        if not status:
            self.release_ip(ip)
            return rpc_pb2.Reply(status=rpc_pb2.Reply.REFUSED, message="Create container for batch failed when preparing filesystem")

        rootfs = "/var/lib/lxc/%s/rootfs" % lxcname

        if not os.path.isdir("%s/global/users/%s" % (self.fspath,username)):
            path = env.getenv('DOCKLET_LIB')
            subprocess.call([path+"/master/userinit.sh", username])
            logger.info("user %s directory not found, create it" % username)
            sys_run("mkdir -p /var/lib/lxc/%s" % lxcname)
            logger.info("generate config file for %s" % lxcname)

        def config_prepare(content):
            content = content.replace("%ROOTFS%",rootfs)
            content = content.replace("%HOSTNAME%","batch-%s" % str(instanceid))
            content = content.replace("%CONTAINER_MEMORY%",str(instance_type.memory))
            content = content.replace("%CONTAINER_CPU%",str(instance_type.cpu*100000))
            content = content.replace("%FS_PREFIX%",self.fspath)
            content = content.replace("%LXCSCRIPT%",env.getenv("LXC_SCRIPT"))
            content = content.replace("%USERNAME%",username)
            content = content.replace("%LXCNAME%",lxcname)
            content = content.replace("%IP%",ip)
            content = content.replace("%GATEWAY%",self.cons_gateway)
            return content

        logger.info(self.confpath)
        conffile = open(self.confpath+"/container.batch.conf", 'r')
        conftext = conffile.read()
        conffile.close()

        conftext = config_prepare(conftext)

        conffile = open("/var/lib/lxc/%s/config" % lxcname, 'w')
        conffile.write(conftext)

        #mount oss
        self.mount_oss("%s/global/users/%s/oss" % (self.fspath,username), mount_list)
        mount_str = "lxc.mount.entry = %s/global/users/%s/oss/%s %s/root/oss/%s none bind,rw,create=dir 0 0"
        for mount in mount_list:
            conffile.write("\n"+ mount_str % (self.fspath, username, mount.remotePath, rootfs, mount.remotePath))
        conffile.close()

        container = lxc.Container(lxcname)
        if not container.start():
            logger.error('start container %s failed' % lxcname)
            self.release_ip(ip)
            self.imgmgr.deleteFS(lxcname)
            return rpc_pb2.Reply(status=rpc_pb2.Reply.REFUSED,message="Can't start the container")

        logger.info('start container %s success' % lxcname)

        #add GPU
        [success, msg] = self.add_gpu_device(lxcname,gpu_need)
        if not success:
            logger.error("Fail to add gpu device. " + msg)
            container.stop()
            self.release_ip(ip)
            self.imgmgr.deleteFS(lxcname)
            return rpc_pb2.Reply(status=rpc_pb2.Reply.REFUSED,message="Fail to add gpu device. " + msg)

        thread = threading.Thread(target = self.execute_task, args=(username,taskid,instanceid,envs,lxcname,pkgpath,command,timeout,outpath,ip,token,mount_list))
        thread.setDaemon(True)
        thread.start()

        return rpc_pb2.Reply(status=rpc_pb2.Reply.ACCEPTED,message="")

    def write_output(self,lxcname,tmpfilename,content,lxcfspath,filepath):
        try:
            outfile = open(lxcfspath+"/root/output_tmp.txt","w")
            outfile.write(content.decode(encoding="utf-8"))
            outfile.close()
        except Exception as err:
            logger.error(traceback.format_exc())
            msg = "Fail to write to path(%s)" % (lxcfspath+"/root/output_tmp.txt")
            logger.error(msg)
            return [False,msg]
        logger.info("Succeed to writing to %s" % (lxcfspath+"/root/output_tmp.txt"))

        cmd = "lxc-attach -n " + lxcname + " -- mv %s %s"
        ret = subprocess.run(cmd % ("/root/output_tmp.txt","/root/nfs/"+tmpfilename),stdout=subprocess.PIPE,stderr=subprocess.STDOUT, shell=True)
        if ret.returncode != 0:
            msg = "Fail to move output_tmp.txt to nfs/%s" % tmpfilename
            logger.error(msg)
            logger.error(ret.stdout)
            return [False,msg]
        logger.info("Succeed to moving output_tmp to nfs/%s" % tmpfilename)

        if os.path.abspath("/root/nfs/"+tmpfilename) == os.path.abspath(filepath):
            return [True,""]
        ret = subprocess.run(cmd % ("/root/nfs/"+tmpfilename,filepath),stdout=subprocess.PIPE,stderr=subprocess.STDOUT, shell=True)
        if ret.returncode != 0:
            msg = ret.stdout.decode(encoding="utf-8")
            logger.error(msg)
            return [False,msg]
        logger.info("Succeed to moving nfs/%s to %s" % (tmpfilename,filepath))
        return [True,""]

    def execute_task(self,username,taskid,instanceid,envs,lxcname,pkgpath,command,timeout,outpath,ip,token,mount_info):
        lxcfspath = "/var/lib/lxc/"+lxcname+"/rootfs/"
        scriptname = "batch_job.sh"
        try:
            scriptfile = open(lxcfspath+"root/"+scriptname,"w")
            scriptfile.write("#!/bin/bash\n")
            scriptfile.write("cd "+str(pkgpath)+"\n")
            scriptfile.write(command)
            scriptfile.close()
        except Exception as err:
            logger.error(traceback.format_exc())
            logger.error("Fail to write script file with taskid(%s) instanceid(%s)" % (str(taskid),str(instanceid)))
        else:
            cmd = "lxc-attach -n " + lxcname
            for envkey,envval in envs.items():
                cmd = cmd + " -v %s=%s" % (envkey,envval)
            cmd = cmd + " -- /bin/bash \"" + "/root/" + scriptname + "\""
            logger.info('run task with command - %s' % cmd)
            p = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE, shell=True)
            #logger.info(p)
            if timeout == 0:
                to = MAX_RUNNING_TIME
            else:
                to = timeout
            while p.poll() is None and to > 0:
                time.sleep(min(2,to))
                to -= 2
            if p.poll() is None:
                p.kill()
                logger.info("Running time(%d) is out. Task(%s-%s-%s) will be killed." % (timeout,str(taskid),str(instanceid),token))
                self.add_msg(taskid,username,instanceid,rpc_pb2.TIMEOUT,token,"Running time is out.")
            else:
                out,err = p.communicate()
                logger.info(out)
                logger.info(err)
                stdoutname = str(taskid)+"-"+str(instanceid)+"-stdout.txt"
                stderrname = str(taskid)+"-"+str(instanceid)+"-stderr.txt"
                if outpath[0][-1] == "/":
                    outpath[0] += stdoutname
                if outpath[1][-1] == "/":
                    outpath[1] += stderrname
                [success1,msg1] = self.write_output(lxcname,stdoutname,out,lxcfspath,outpath[0])
                [success2,msg2] = self.write_output(lxcname,stderrname,err,lxcfspath,outpath[1])
                if not success1 or not success2:
                    if not success1:
                        msg = msg1
                    else:
                        msg = msg2
                    logger.info("Output error on Task(%s-%s-%s)." % (str(taskid),str(instanceid),token))
                    self.add_msg(taskid,username,instanceid,rpc_pb2.OUTPUTERROR,token,msg)
                else:
                    if p.poll() == 0:
                        logger.info("Task(%s-%s-%s) completed." % (str(taskid),str(instanceid),token))
                        self.add_msg(taskid,username,instanceid,rpc_pb2.COMPLETED,token,"")
                    else:
                        logger.info("Task(%s-%s-%s) failed." % (str(taskid),str(instanceid),token))
                        self.add_msg(taskid,username,instanceid,rpc_pb2.FAILED,token,"")

        container = lxc.Container(lxcname)
        if container.stop():
            logger.info("stop container %s success" % lxcname)
        else:
            logger.error("stop container %s failed" % lxcname)

        logger.info("deleting container:%s" % lxcname)
        if self.imgmgr.deleteFS(lxcname):
            logger.info("delete container %s success" % lxcname)
        else:
            logger.error("delete container %s failed" % lxcname)

        logger.info("release ip address %s" % ip)
        self.release_ip(ip)
        self.release_gpu_device(lxcname)

        #umount oss
        self.umount_oss("%s/global/users/%s/oss" % (self.fspath,username), mount_info)

    def stop_tasks(self, request, context):
        for msg in request.taskmsgs:
            lxcname = '%s-batch-%s-%s-%s' % (msg.username,msg.taskid,str(msg.instanceid),msg.token)
            logger.info("Stop the task with lxc:"+lxcname)
            subprocess.run("lxc-stop -k -n %s" % lxcname, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        return rpc_pb2.Reply(status=rpc_pb2.Reply.ACCEPTED,message="")

    def add_msg(self,taskid,username,instanceid,status,token,errmsg):
        self.msgslock.acquire()
        try:
            self.taskmsgs.append(rpc_pb2.TaskMsg(taskid=str(taskid),username=username,instanceid=int(instanceid),instanceStatus=status,token=token,errmsg=errmsg))
        except Exception as err:
            logger.error(traceback.format_exc())
        self.msgslock.release()
        #logger.info(str(self.taskmsgs))

    def report_msg(self):
        channel = grpc.insecure_channel(self.master_ip+":"+self.master_port)
        stub = rpc_pb2_grpc.MasterStub(channel)
        while True:
            self.msgslock.acquire()
            reportmsg = rpc_pb2.ReportMsg(taskmsgs = self.taskmsgs)
            try:
                response = stub.report(reportmsg)
                logger.info("Response from master by reporting: "+str(response.status)+" "+response.message)
            except Exception as err:
                logger.error(traceback.format_exc())
            self.taskmsgs = []
            self.msgslock.release()
            time.sleep(self.report_interval)

    def start_report(self):
        thread = threading.Thread(target = self.report_msg, args=())
        thread.setDaemon(True)
        thread.start()
        logger.info("Start to report task messages to master every %d seconds." % self.report_interval)


def TaskControllerServe():
    max_threads = int(env.getenv('BATCH_MAX_THREAD_WORKER'))
    worker_port = int(env.getenv('BATCH_WORKER_PORT'))
    logger.info("Max Threads on a worker is %d" % max_threads)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_threads))
    rpc_pb2_grpc.add_WorkerServicer_to_server(TaskController(), server)
    server.add_insecure_port('[::]:'+str(worker_port))
    server.start()
    logger.info("Start TaskController Servicer on port:%d" % worker_port)
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    TaskControllerServe()
