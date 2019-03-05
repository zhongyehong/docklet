import threading
import time
import string
import os
import random, copy, subprocess
import json
from functools import wraps

# must import logger after initlogging, ugly
from utils.log import logger

# grpc
from concurrent import futures
import grpc
from protos.rpc_pb2 import *
from protos.rpc_pb2_grpc import MasterServicer, add_MasterServicer_to_server, WorkerStub
from utils.nettools import netcontrol
from utils import env

def ip_to_int(addr):
    [a, b, c, d] = addr.split('.')
    return (int(a)<<24) + (int(b)<<16) + (int(c)<<8) + int(d)

def int_to_ip(num):
    return str((num>>24)&255)+"."+str((num>>16)&255)+"."+str((num>>8)&255)+"."+str(num&255)

class Task():
    def __init__(self, task_id, username, at_same_time, priority, max_size, task_infos):
        self.id = task_id
        self.username = username
        self.status = WAITING
        # if all the vnodes must be started at the same time
        self.at_same_time = at_same_time
        # priority the bigger the better
        # self.priority the smaller the better
        self.priority = int(time.time()) / 60 / 60 - priority
        self.task_base_ip = None
        self.ips = None
        self.max_size = max_size

        self.subtask_list = [SubTask(
                idx = index,
                root_task = self, 
                vnode_info = task_info['vnode_info'], 
                command_info = task_info['command_info'], 
                max_retry_count = task_info['max_retry_count']
            ) for (index, task_info) in enumerate(task_infos)]

    def __lt__(self, other):
        return self.priority < other.priority

    def gen_ips_from_base(self,base_ip):
        if self.task_base_ip == None:
            return
        self.ips = []
        for i in range(self.max_size):
            self.ips.append(int_to_ip(base_ip + self.task_base_ip + i + 2))

    def gen_hosts(self):
        username = self.username
        taskid = self.id
        # logger.info("Generate hosts for user(%s) task(%s) base_ip(%s)"%(username,taskid,str(self.task_base_ip)))
        fspath = env.getenv('FS_PREFIX')
        if not os.path.isdir("%s/global/users/%s" % (fspath,username)):
            path = env.getenv('DOCKLET_LIB')
            subprocess.call([path+"/master/userinit.sh", username])
            # logger.info("user %s directory not found, create it" % username)

        hosts_file = open("%s/global/users/%s/%s.hosts" % (fspath,username,"batch-"+taskid),"w")
        hosts_file.write("127.0.0.1 localhost\n")
        i = 0
        for ip in self.ips:
            hosts_file.write(ip+" batch-"+str(i)+"\n")
            i += 1
        hosts_file.close()

class SubTask():
    def __init__(self, idx, root_task, vnode_info, command_info, max_retry_count):
        self.root_task = root_task
        self.vnode_info = vnode_info
        self.vnode_info.vnodeid = idx
        self.command_info = command_info
        self.command_info.vnodeid = idx
        self.max_retry_count = max_retry_count
        self.vnode_started = False
        self.task_started = False
        self.status = WAITING
        self.status_reason = ''
        self.try_count = 0
        self.worker = None

    def waiting_for_retry(self):
        self.try_count += 1
        self.status = WAITING if self.try_count <= self.max_retry_count else FAILED
        if self.status == FAILED and self.root_task.at_same_time:
            self.root_task.status = FAILED


class TaskReporter(MasterServicer):

    def __init__(self, taskmgr):
        self.taskmgr = taskmgr

    def report(self, request, context):
        for task_report in request.taskmsgs:
            self.taskmgr.on_task_report(task_report)
        return Reply(status=Reply.ACCEPTED, message='')


class TaskMgr(threading.Thread):

    # load task information from etcd
    # initial a task queue and task schedueler
    # taskmgr: a taskmgr instance
    def __init__(self, nodemgr, monitor_fetcher, master_ip, scheduler_interval=2, external_logger=None):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.jobmgr = None
        self.master_ip = master_ip
        self.task_queue = []
        self.lazy_append_list = []
        self.lazy_delete_list = []
        self.task_queue_lock = threading.Lock()
        #self.user_containers = {}

        self.scheduler_interval = scheduler_interval
        self.logger = external_logger

        self.master_port = env.getenv('BATCH_MASTER_PORT')
        self.worker_port = env.getenv('BATCH_WORKER_PORT')

        # nodes
        self.nodemgr = nodemgr
        self.monitor_fetcher = monitor_fetcher
        self.cpu_usage = {}
        self.gpu_usage = {}
        # self.all_nodes = None
        # self.last_nodes_info_update_time = 0
        # self.nodes_info_update_interval = 30 # (s)

        self.network_lock = threading.Lock()
        batch_net = env.getenv('BATCH_NET')
        self.batch_cidr = int(batch_net.split('/')[1])
        batch_net = batch_net.split('/')[0]
        task_cidr = int(env.getenv('BATCH_TASK_CIDR'))
        task_cidr = min(task_cidr,31-self.batch_cidr)
        self.task_cidr = max(task_cidr,2)
        self.base_ip = ip_to_int(batch_net)
        self.free_nets = []
        for i in range((1 << self.task_cidr), (1 << (32-self.batch_cidr)) - 1):
            self.free_nets.append(i)
        # self.logger.info("Free nets addresses pool %s" % str(self.free_nets))
        # self.logger.info("Each Batch Net CIDR:%s"%(str(self.task_cidr)))

    def queue_lock(f):
        @wraps(f)
        def new_f(self, *args, **kwargs):
            self.task_queue_lock.acquire()
            result = f(self, *args, **kwargs)
            self.task_queue_lock.release()
            return result
        return new_f

    def net_lock(f):
        @wraps(f)
        def new_f(self, *args, **kwargs):
            self.network_lock.acquire()
            result = f(self, *args, **kwargs)
            self.network_lock.release()
            return result
        return new_f

    def run(self):
        self.serve()
        while not self.thread_stop:
            self.sort_out_task_queue()
            task, sub_task_list = self.task_scheduler()
            if task is not None and sub_task_list is not None:
                self.task_processor(task, sub_task_list)
            else:
                time.sleep(self.scheduler_interval)

    def serve(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_MasterServicer_to_server(TaskReporter(self), self.server)
        self.server.add_insecure_port('[::]:' + self.master_port)
        self.server.start()
        self.logger.info('[taskmgr_rpc] start rpc server')

    def stop(self):
        self.thread_stop = True
        self.server.stop(0)
        self.logger.info('[taskmgr_rpc] stop rpc server')

    @queue_lock
    def sort_out_task_queue(self):
        while self.lazy_delete_list:
            task = self.lazy_delete_list.pop(0)
            self.task_queue.remove(task)
        if self.lazy_append_list:
            while self.lazy_append_list:
                task = self.lazy_append_list.pop(0)
                self.task_queue.append(task)
            self.task_queue = sorted(self.task_queue, key=lambda x: x.priority)

    def start_vnode(self, subtask):
        try:
            self.logger.info('[task_processor] Starting vnode for task [%s] vnode [%d]' % (subtask.vnode_info.taskid, subtask.vnode_info.vnodeid))
            channel = grpc.insecure_channel('%s:%s' % (subtask.worker, self.worker_port))
            stub = WorkerStub(channel)
            response = stub.start_vnode(subtask.vnode_info)
            if response.status != Reply.ACCEPTED:
                raise Exception(response.message)
        except Exception as e:
            self.logger.error('[task_processor] rpc error message: %s' % e)
            subtask.status_reason = str(e)
            return [False, e]
        subtask.vnode_started = True
        self.cpu_usage[subtask.worker] += subtask.vnode_info.vnode.instance.cpu
        self.gpu_usage[subtask.worker] += subtask.vnode_info.vnode.instance.gpu
        return [True, '']

    def stop_vnode(self, subtask):
        try:
            self.logger.info('[task_processor] Stopping vnode for task [%s] vnode [%d]' % (subtask.vnode_info.taskid, subtask.vnode_info.vnodeid))
            channel = grpc.insecure_channel('%s:%s' % (subtask.worker, self.worker_port))
            stub = WorkerStub(channel)
            response = stub.stop_vnode(subtask.vnode_info)
            if response.status != Reply.ACCEPTED:
                raise Exception(response.message)
        except Exception as e:
            self.logger.error('[task_processor] rpc error message: %s' % e)
            subtask.status_reason = str(e)
            return [False, e]
        subtask.vnode_started = False
        self.cpu_usage[subtask.worker] -= subtask.vnode_info.vnode.instance.cpu
        self.gpu_usage[subtask.worker] -= subtask.vnode_info.vnode.instance.gpu
        return [True, '']

    def start_task(self, subtask):
        try:
            self.logger.info('[task_processor] Starting task [%s] vnode [%d]' % (subtask.vnode_info.taskid, subtask.vnode_info.vnodeid))
            channel = grpc.insecure_channel('%s:%s' % (subtask.worker, self.worker_port))
            stub = WorkerStub(channel)
            response = stub.start_task(subtask.command_info)
            if response.status != Reply.ACCEPTED:
                raise Exception(response.message)
        except Exception as e:
            self.logger.error('[task_processor] rpc error message: %s' % e)
            subtask.status_reason = str(e)
        subtask.task_started = True

    def stop_task(self, subtask):
        try:
            self.logger.info('[task_processor] Stoping task [%s] vnode [%d]' % (subtask.vnode_info.taskid, subtask.vnode_info.vnodeid))
            channel = grpc.insecure_channel('%s:%s' % (subtask.worker, self.worker_port))
            stub = WorkerStub(channel)
            response = stub.stop_stask(subtask.command_info)
            if response.status != Reply.ACCEPTED:
                raise Exception(response.message)
        except Exception as e:
            self.logger.error('[task_processor] rpc error message: %s' % e)
            subtask.status = FAILED
            subtask.status_reason = str(e)
        subtask.task_started = False

    @net_lock
    def acquire_task_ips(self, task):
        self.logger.info("[acquire_task_ips] user(%s) task(%s) net(%s)" % (task.username, task.id, str(task.task_base_ip)))
        if task.task_base_ip == None:
            task.task_base_ip = self.free_nets.pop(0)
        return task.task_base_ip

    @net_lock
    def release_task_ips(self, task):
        self.logger.info("[release_task_ips] user(%s) task(%s) net(%s)" % (task.username, task.id, str(task.task_base_ip)))
        if task.task_base_ip == None:
            return
        self.free_nets.append(task.task_base_ip)
        task.task_base_ip = None
        self.logger.error('[release task_net] %s' % str(e))

    def setup_tasknet(self, task, workers=None):
        taskid = task.id
        username = task.username
        brname = "docklet-batch-%s-%s"%(username, taskid)
        gwname = "Batch-%s-%s"%(username, taskid)
        if task.task_base_ip == None:
            return [False, "task.task_base_ip is None!"]
        gatewayip = int_to_ip(self.base_ip + task.task_base_ip + 1)
        gatewayipcidr = "/" + str(32-self.task_cidr)
        netcontrol.new_bridge(brname)
        netcontrol.setup_gw(brname,gwname,gatewayipcidr,0,0)

        for wip in workers:
            netcontrol.setup_gre(brname,wip)
        return [True, gatewayip]

    def remove_tasknet(self, task):
        taskid = task.id
        username = task.username
        brname = "docklet-batch-%s-%s"%(username, taskid)
        netcontrol.del_bridge(brname)

    def task_processor(self, task, sub_task_list):
        task.status = RUNNING
        # self.jobmgr.report(task.id,'running')

        # properties for transactio

        self.acquire_task_ips(task)
        task.gen_ips_from_base(self.base_ip)
        task.gen_hosts()
        #need to create hosts
        [success, gwip] = self.setup_tasknet(task, [sub_task.worker for sub_task in sub_task_list])
        if not success:
            self.release_task_ips(task)
            return [False, gwip]

        placed_workers = []

        start_all_vnode_success = True
        # start vc
        for sub_task in sub_task_list:
            vnode_info = sub_task.vnode_info
            vnode_info.vnode.hostname = "batch-" + str(vnode_info.vnodeid % task.max_size)
            if sub_task.vnode_started:
                continue

            username = sub_task.root_task.username
            #container_name = task.info.username + '-batch-' + task.info.id + '-' + str(instance_id) + '-' + task.info.token
            #if not username in self.user_containers.keys():
                #self.user_containers[username] = []
            #self.user_containers[username].append(container_name)
            ipaddr = task.ips[vnode_info.vnodeid % task.max_size]
            brname = "docklet-batch-%s-%s" % (username, sub_task.root_task.id)
            networkinfo = Network(ipaddr=ipaddr, gateway=gwip, masterip=self.master_ip, brname=brname)
            vnode_info.vnode.network.CopyFrom(networkinfo)

            placed_workers.append(sub_task.worker)
            if not self.start_vnode(sub_task):
                sub_task.waiting_for_retry()
                sub_task.worker = None
                start_all_vnode_success = False

        if not start_all_vnode_success:
            return

        # start tasks
        for sub_task in sub_task_list:
            task_info = sub_task.command_info
            task_info.token = ''.join(random.sample(string.ascii_letters + string.digits, 8))

            if self.start_task(sub_task):
                sub_task.status = RUNNING
            else:
                sub_task.waiting_for_retry()

    def clear_sub_tasks(self, sub_task_list):
        for sub_task in sub_task_list:
            self.clear_sub_task(sub_task)

    def clear_sub_task(self, sub_task):
        if sub_task.task_started:
            self.stop_task(sub_task)
        if sub_task.vnode_started:
            self.stop_vnode(sub_task)

    def check_task_completed(self, task):
        if task.status == RUNNING or task.status == WAITING:
            for sub_task in task.subtask_list:
                if sub_task.status == RUNNING or sub_task.status == WAITING:
                    return False
        self.logger.info('task %s completed' % task.id)
        if task.at_same_time and task.status == FAILED:
            self.clear_sub_tasks(task.subtask_list)
        # TODO report to jobmgr
        self.lazy_delete_list.append(task)
        return True

    # this method is called when worker send heart-beat rpc request
    def on_task_report(self, report):
        self.logger.info('[on_task_report] receive task report: id %s-%d, status %d' % (report.taskid, report.vnodeid, report.subTaskStatus))
        task = self.get_task(report.taskid)
        if task == None:
            self.logger.error('[on_task_report] task not found')
            return

        sub_task = task.subtask_list[report.vnodeid]
        if sub_task.token != report.token:
            self.logger.warning('[on_task_report] wrong token')
            return
        username = task.username
        # container_name = username + '-batch-' + task.info.id + '-' + str(report.instanceid) + '-' + report.token
        # self.user_containers[username].remove(container_name)

        if sub_task.status != RUNNING:
            self.logger.error('[on_task_report] receive task report when instance is not running')

        sub_task.status = report.subTaskStatus
        sub_task.status_reason = report.errmsg

        self.clear_sub_task(sub_task)

        if report.subTaskStatus == FAILED or report.subTaskStatus == TIMEOUT:
            sub_task.waiting_for_retry()

    # return task, workers
    def task_scheduler(self):
        # simple FIFO with priority
        self.logger.info('[task_scheduler] scheduling... (%d tasks remains)' % len(self.task_queue))

        for task in self.task_queue:
            if task in self.lazy_delete_list:
                continue
            if self.check_task_completed(task):
                continue

            if task.at_same_time:
                # parallel tasks
                workers = self.find_proper_workers(task.subtask_list)
                if len(workers) == 0:
                    return None, None
                else:
                    for i in range(len(workers)):
                        task.subtask_list[i].worker = workers[i]
                    return task, task.subtask_list
            else:
                # traditional tasks
                for sub_task in task.subtask_list:
                    if sub_task.status == WAITING:
                        workers = self.find_proper_workers([sub_task])
                        if len(workers) > 0:
                            sub_task.worker = workers[0]
                            return task, [sub_task]

        return None, None

    def find_proper_workers(self, sub_task_list):
        nodes = self.get_all_nodes()
        if nodes is None or len(nodes) == 0:
            self.logger.warning('[task_scheduler] running nodes not found')
            return None

        proper_workers = []
        has_waiting = False
        for sub_task in sub_task_list:
            if sub_task.status == WAITING:
                has_waiting = True
            if sub_task.worker is not None and sub_task.vnode_started:
                proper_workers.append(sub_task.worker)
                continue
            needs = sub_task.vnode_info.vnode.instance
            proper_worker = None
            for worker_ip, worker_info in nodes:
                if needs.cpu + self.get_cpu_usage(worker_ip) > worker_info['cpu']:
                    continue
                elif needs.memory > worker_info['memory']:
                    continue
                elif needs.disk > worker_info['disk']:
                    continue
                # try not to assign non-gpu task to a worker with gpu
                #if needs['gpu'] == 0 and worker_info['gpu'] > 0:
                    #continue
                elif needs.gpu + self.get_gpu_usage(worker_ip) > worker_info['gpu']:
                    continue
                else:
                    worker_info['cpu'] -= needs.cpu
                    worker_info['memory'] -= needs.memory
                    worker_info['gpu'] -= needs.gpu
                    worker_info['disk'] -= needs.disk
                    proper_worker = worker_ip
                    break
            if proper_worker is not None:
                proper_workers.append(proper_worker)
            else:
                return []
        if has_waiting:
            return proper_workers
        else:
            return []

    def get_all_nodes(self):
        # cache running nodes
        # if self.all_nodes is not None and time.time() - self.last_nodes_info_update_time < self.nodes_info_update_interval:
        #     return self.all_nodes
        # get running nodes
        node_ips = self.nodemgr.get_batch_nodeips()
        all_nodes = [(node_ip, self.get_worker_resource_info(node_ip)) for node_ip in node_ips]
        return all_nodes

    def is_alive(self, worker):
        nodes = self.nodemgr.get_batch_nodeips()
        return worker in nodes

    def get_worker_resource_info(self, worker_ip):
        fetcher = self.monitor_fetcher(worker_ip)
        worker_info = fetcher.info
        info = {}
        info['cpu'] = len(worker_info['cpuconfig'])
        info['memory'] = (worker_info['meminfo']['buffers'] + worker_info['meminfo']['cached'] + worker_info['meminfo']['free']) / 1024 # (Mb)
        info['disk'] = sum([disk['free'] for disk in worker_info['diskinfo']]) / 1024 / 1024 # (Mb)
        info['gpu'] = len(worker_info['gpuinfo'])
        return info

    def get_cpu_usage(self, worker_ip):
        try:
            return self.cpu_usage[worker_ip]
        except:
            self.cpu_usage[worker_ip] = 0
            return 0


    def get_gpu_usage(self, worker_ip):
        try:
            return self.gpu_usage[worker_ip]
        except:
            self.gpu_usage[worker_ip] = 0
            return 0

    # save the task information into database
    # called when jobmgr assign task to taskmgr
    def add_task(self, username, taskid, json_task, task_priority=1):
        # decode json string to object defined in grpc
        self.logger.info('[taskmgr add_task] receive task %s' % taskid)
        image_dict = {
            "private": Image.PRIVATE,
            "base": Image.BASE,
            "public": Image.PUBLIC
        }
        task = Task(
            task_id = taskid,
            username = username,
            # all vnode must be started at the same time
            at_same_time = json_task['at_same_time'],
            priority = task_priority,
            max_size = (1 << self.task_cidr) - 2,
            task_infos = [{
                'max_retry_count': int(json_task['retryCount']),
                'vnode_info': VNodeInfo(
                    taskid = taskid,
                    username = username,
                    vnode = VNode(
                        image = Image(
                            name = json_task['image'].split('_')[0], #json_task['cluster']['image']['name'],
                            type = image_dict[json_task['image'].split('_')[2]], #json_task['cluster']['image']['type'],
                            owner = username if not json_task['image'].split('_')[1] else json_task['image'].split('_')[1]), #json_task['cluster']['image']['owner']),
                        instance = Instance(
                            cpu = int(json_task['cpuSetting']),
                            memory = int(json_task['memorySetting']),
                            disk = int(json_task['diskSetting']),
                            gpu = int(json_task['gpuSetting'])),
                        mount = [Mount(
                                    localPath = json_task['mapping'][mapping_key]['mappingLocalDir'],
                                    remotePath=json_task['mapping'][mapping_key]['mappingRemoteDir'])
                                for mapping_key in json_task['mapping']] if 'mapping' in json_task else []
                        ),
                ),
                'command_info': TaskInfo(
                    taskid = taskid,
                    username = username,
                    parameters = Parameters(
                        command = Command(
                            commandLine = json_task['command'],
                            packagePath = json_task['srcAddr'],
                            envVars = {}),
                        stderrRedirectPath = json_task.get('stdErrRedPth',""),
                        stdoutRedirectPath = json_task.get('stdOutRedPth',"")),
                    timeout = int(json_task['expTime'])
                # commands are executed in all vnodes / only excuted in the first vnode
                # if in traditional mode, commands will be executed in all vnodes
                ) if (not json_task['at_same_time'] or json_task['multicommand'] or instance_index == 0) else None
            } for instance_index in range(json_task['instCount'])])
        self.lazy_append_list.append(task)


    # user: username
    # get the information of a task, including the status, task description and other information
    @queue_lock
    def get_task(self, taskid):
        for task in self.task_queue:
            if task.id == taskid:
                return task
        return None

    # get names of all the batch containers of the user
    def get_user_batch_containers(self,username):
        if not username in self.user_containers.keys():
            return []
        else:
            return self.user_containers[username]
