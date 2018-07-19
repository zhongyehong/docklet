#!/usr/bin/python3
import sys
if sys.path[0].endswith("worker"):
    sys.path[0] = sys.path[0][:-6]
from utils import env, tools
#config = env.getenv("CONFIG")
config = "/opt/docklet/local/docklet-running.conf"
tools.loadenv(config)
from utils.log import initlogging
initlogging("docklet-worker")
from utils.log import logger

from concurrent import futures
import grpc
#from utils.log import logger
#from utils import env
import json,lxc,subprocess,threading,os,time
from utils import imagemgr
from protos import rpc_pb2, rpc_pb2_grpc

class TaskController(rpc_pb2_grpc.WorkerServicer):

    def __init__(self):
        rpc_pb2_grpc.WorkerServicer.__init__(self)
        self.imgmgr = imagemgr.ImageMgr()
        self.fspath = env.getenv('FS_PREFIX')
        self.confpath = env.getenv('DOCKLET_CONF')
        #self.masterip = '162.105.88.190'
        #self.masterport = 9002
        #self.masterrpc = xmlrpc.client.ServerProxy("http://%s:%s" % (self.masterip,self.masterport))
        logger.info('TaskController init success')

    def process_task(self, request, context):
        logger.info('excute task with parameter: ' + str(request))
        taskid = request.id
        instanceid = request.instanceid

        command = request.parameters.command.commandLine #'/root/getenv.sh'  #parameter['Parameters']['Command']['CommandLine']
        #envs = {'MYENV1':'MYVAL1', 'MYENV2':'MYVAL2'} #parameters['Parameters']['Command']['EnvVars']
        envs = request.parameters.command.envVars
        image = {}
        image['name'] = request.cluster.image.name
        image['type'] = 'private' if request.cluster.image.type == rpc_pb2.Image.PRIVATE else 'public'
        image['owner'] = request.cluster.image.owner
        username = request.username
        lxcname = '%s-batch-%s-%s' % (username,taskid,str(instanceid))
        instance_type =  request.cluster.instance

        status = self.imgmgr.prepareFS(username,image,lxcname,str(instance_type.disk))
        if not status:
            return rpc_pb2.Reply(status=rpc_pb2.Reply.REFUSED, message="Create container for batch failed when preparing filesystem")

        rootfs = "/var/lib/lxc/%s/rootfs" % lxcname

        if not os.path.isdir("%s/global/users/%s" % (self.fspath,username)):
            path = env.getenv('DOCKLET_LIB')
            subprocess.call([path+"/userinit.sh", username])
            logger.info("user %s directory not found, create it" % username)
            sys_run("mkdir -p /var/lib/lxc/%s" % lxcname)
            logger.info("generate config file for %s" % lxcname)

        def config_prepare(content):
            content = content.replace("%ROOTFS%",rootfs)
            content = content.replace("%HOSTNAME%","batch-%s" % instanceid)
            content = content.replace("%CONTAINER_MEMORY%",str(instance_type.memory))
            content = content.replace("%CONTAINER_CPU%",str(instance_type.cpu*100000))
            content = content.replace("%FS_PREFIX%",self.fspath)
            content = content.replace("%LXCSCRIPT%",env.getenv("LXC_SCRIPT"))
            content = content.replace("%USERNAME%",username)
            content = content.replace("%LXCNAME%",lxcname)
            return content

        logger.info(self.confpath)
        conffile = open(self.confpath+"/container.batch.conf", 'r')
        conftext = conffile.read()
        conffile.close()

        conftext = config_prepare(conftext)

        conffile = open("/var/lib/lxc/%s/config" % lxcname, 'w')
        conffile.write(conftext)
        conffile.close()

        container = lxc.Container(lxcname)
        if not container.start():
            logger.error('start container %s failed' % lxcname)
            return rpc_pb2.Reply(status=rpc_pb2.Reply.ACCEPTED,message="")
            #return json.dumps({'success':'false','message': "start container failed"})
        else:
            logger.info('start container %s success' % lxcname)

        #mount oss here

        #thread = threading.Thread(target = self.excute_task, args=(jobid,taskid,envs,lxcname,command))
        #thread.setDaemon(True)
        #thread.start()

        return rpc_pb2.Reply(status=rpc_pb2.Reply.ACCEPTED,message="")
        #return json.dumps({'success':'true','message':'task is running'})

    def excute_task(self,jobid,taskid,envs,lxcname,command):
        cmd = "lxc-attach -n " + lxcname
        for envkey,envval in envs.items():
            cmd = cmd + " -v %s=%s" % (envkey,envval)
        cmd = cmd + " " + command
        logger.info('run task with command - %s' % cmd)
        Ret = subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT, shell=True)
        if Ret == 0:
            #call master rpc function to tell the taskmgr
            self.masterrpc.complete_task(jobid,taskid)
        else:
            self.masterrpc.fail_task(jobid,taskid)
            #call master rpc function to tell the wrong

        #umount oss here

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

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

def TaskControllerServe():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rpc_pb2_grpc.add_WorkerServicer_to_server(TaskController(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    logger.info("Start TaskController Servicer")
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    TaskControllerServe()
