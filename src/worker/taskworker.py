import sys
if sys.path[0].endswith("worker"):
    sys.path[0] = sys.path[0][:-6]
from utils import env, tools
config = env.getenv("CONFIG")
#config = "/opt/docklet/local/docklet-running.conf"
tools.loadenv(config)
from utils.log import initlogging
initlogging("docklet-taskworker")
from utils.log import logger

from concurrent import futures
import grpc
#from utils.log import logger
#from utils import env
import json,lxc,subprocess,threading,os,time,traceback
from utils import imagemgr,etcdlib,gputools
from utils.lvmtool import sys_run
from worker import ossmounter
from protos import rpc_pb2, rpc_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24
MAX_RUNNING_TIME = _ONE_DAY_IN_SECONDS

class TaskWorker(rpc_pb2_grpc.WorkerServicer):

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

        self.gpu_lock = threading.Lock()
        self.gpu_status = {}
        gpus = gputools.get_gpu_status()
        for gpu in gpus:
            self.gpu_status[gpu['id']] = ""

        self.start_report()
        logger.info('TaskWorker init success')

    def start_vnode(self, request, context):
        logger.info('start vnode with config: ' + str(request))
        taskid = request.taskid
        vnodeid = request.vnodeid

        envs = {}
        envs['taskid'] = str(taskid)
        envs['vnodeid'] = str(vnodeid)
        image = {}
        image['name'] = request.vnode.image.name
        if request.vnode.image.type == rpc_pb2.Image.PRIVATE:
            image['type'] = 'private'
        elif request.vnode.image.type == rpc_pb2.Image.PUBLIC:
            image['type'] = 'public'
        else:
            image['type'] = 'base'
        image['owner'] = request.vnode.image.owner
        username = request.username
        lxcname = '%s-batch-%s-%s' % (username,taskid,str(vnodeid))
        instance_type =  request.vnode.instance
        mount_list = request.vnode.mount
        gpu_need = int(request.vnode.instance.gpu)

    def start_task(self, request, context):
        pass

    def stop_task(self, request, context):
        pass

    def stop_vnode(self, request, context):
        pass

    def add_msg(self,taskid,username,vnodeid,status,token,errmsg):
        self.msgslock.acquire()
        try:
            self.taskmsgs.append(rpc_pb2.TaskMsg(taskid=str(taskid),username=username,vnodeid=int(vnodeid),subTaskStatus=status,token=token,errmsg=errmsg))
        except Exception as err:
            logger.error(traceback.format_exc())
        self.msgslock.release()

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

def TaskWorkerServe():
    max_threads = int(env.getenv('BATCH_MAX_THREAD_WORKER'))
    worker_port = int(env.getenv('BATCH_WORKER_PORT'))
    logger.info("Max Threads on a worker is %d" % max_threads)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_threads))
    rpc_pb2_grpc.add_WorkerServicer_to_server(TaskWorker(), server)
    server.add_insecure_port('[::]:'+str(worker_port))
    server.start()
    logger.info("Start TaskWorker Servicer on port:%d" % worker_port)
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    TaskControllerServe()
