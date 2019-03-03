import threading
import time
import string
import random, copy
import json
from functools import wraps

# must import logger after initlogging, ugly
from utils.log import logger

# grpc
from concurrent import futures
import grpc
from protos.rpc_pb2 import *
from protos.rpc_pb2_grpc import MasterServicer, add_MasterServicer_to_server, WorkerStub

from utils import env

class Task():
    def __init__(self, configinfo, vnodeinfo, taskinfo, priority):
        self.vnodeinfo = vnodeinfo
        self.taskinfo = taskinfo
        self.status = WAITING
        self.subtask_list = []
        self.token = ''
        self.maxRetryCount = self.configinfo['maxRetryCount']
        self.atSameTime = self.configinfo['atSameTime']
        self.multicommand = self.configinfo['multicommand']
        self.vnode_nums = self.configinfo['vnode_nums']
        # priority the bigger the better
        # self.priority the smaller the better
        self.priority = int(time.time()) / 60 / 60 - priority

        for i in range(self.vnode_nums):
            self.subtask_list.append({'status':'WAITING','try_count':0})

    def __lt__(self, other):
        return self.priority < other.priority

    def get_one_resources_need(self):
        return self.vnodeinfo.vnode.instance

    def get_all_resources_need(self):
        return [self.vnodeinfo.vnode.instance for i in range(self.vnode_nums)]


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
    def __init__(self, nodemgr, monitor_fetcher, scheduler_interval=2, external_logger=None):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.jobmgr = None
        self.task_queue = []
        self.lazy_append_list = []
        self.lazy_delete_list = []
        self.task_queue_lock = threading.Lock()
        #self.user_containers = {}

        self.scheduler_interval = scheduler_interval
        self.logger = logger

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


    def queue_lock(f):
        @wraps(f)
        def new_f(self, *args, **kwargs):
            self.task_queue_lock.acquire()
            result = f(self, *args, **kwargs)
            self.task_queue_lock.release()
            return result
        return new_f


    def run(self):
        self.serve()
        while not self.thread_stop:
            self.sort_out_task_queue()
            task, vnodes_workers = self.task_scheduler()
            if task is not None and workers is not None:
                self.task_processor(task, vnodes_workers)
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

    def task_processor(self, task, vnodes_workers):
        task.status = RUNNING
        self.jobmgr.report(task.taskinfo.taskid,'running')

        # properties for transaction

        token = ''.join(random.sample(string.ascii_letters + string.digits, 8))

        for vid, worker in vnodes_workers:
            vnodeinfo = copy.copy(task.vnodeinfo)
            vnodeinfo.vnodeid = vid
            vnode = task.subtask_list[vid]
            vnode['status'] = RUNNING
            vnode['try_count'] += 1
            vnode['token'] = token
            vnode['worker'] = worker

            self.cpu_usage[worker] += task.vnodeinfo.vnode.instance.cpu
            self.gpu_usage[worker] += task.vnodeinfo.vnode.instance.gpu
            username = task.vnodeinfo.username
            #container_name = task.info.username + '-batch-' + task.info.id + '-' + str(instance_id) + '-' + task.info.token
            #if not username in self.user_containers.keys():
                #self.user_containers[username] = []
            #self.user_containers[username].append(container_name)

            try:
                self.logger.info('[task_processor] starting vnode for task [%s] instance [%d]' % (task.vnodeinfo.id, vid))
                channel = grpc.insecure_channel('%s:%s' % (worker, self.worker_port))
                stub = WorkerStub(channel)
                response = stub.start_vnode(vnodeinfo)
                if response.status != Reply.ACCEPTED:
                    raise Exception(response.message)
            except Exception as e:
                self.logger.error('[task_processor] rpc error message: %s' % e)
                vnode['status'] = FAILED
                vnode['try_count'] -= 1
                return
                #self.user_containers[username].remove(container_name)

        for vid, worker in vnodes_workers:
            taskinfo = copy.copy(task.taskinfo)
            taskinfo.vnodeid = vid
            taskinfo.token = token
            vnode = task.subtask_list[vid]
            try:
                self.logger.info('[task_processor] starting task [%s] instance [%d]' % (task.vnodeinfo.id, vid))
                channel = grpc.insecure_channel('%s:%s' % (worker, self.worker_port))
                stub = WorkerStub(channel)
                response = stub.start_task(taskinfo)
                if response.status != Reply.ACCEPTED:
                    raise Exception(response.message)
            except Exception as e:
                self.logger.error('[task_processor] rpc error message: %s' % e)
                vnode['status'] = FAILED
                vnode['try_count'] -= 1

    # return task, workers
    def task_scheduler(self):
        # simple FIFO with priority
        self.logger.info('[task_scheduler] scheduling... (%d tasks remains)' % len(self.task_queue))

        for task in self.task_queue:
            if task in self.lazy_delete_list:
                continue

            if task.atSameTime:
                # parallel tasks
                if task.status == RUNNING:
                    continue
                workers = self.find_proper_workers(task.get_all_resources_need())
                if len(workers) < task.vnode_nums:
                    return None, None
                else:
                    idxs = [i for i in range(task.vnode_nums)]
                    return task, zip(idxs,workers)
            else:
                # traditional tasks
                workers = self.find_proper_workers([task.get_one_resources_need()])
                if len(workers) < task.vnode_nums:
                    return None, None, None
                '''for index, instance in enumerate(task.instance_list):
                    # find instance to retry
                    if (instance['status'] == FAILED or instance['status'] == TIMEOUT) and instance['try_count'] <= task.info.maxRetryCount:
                        if worker is not None:
                            self.logger.info('[task_scheduler] retry')
                            return task, index, worker
                    # find timeout instance
                    elif instance['status'] == RUNNING:
                        if not self.is_alive(instance['worker']):
                            instance['status'] = FAILED
                            instance['token'] = ''
                            self.cpu_usage[instance['worker']] -= task.info.cluster.instance.cpu
                            self.gpu_usage[instance['worker']] -= task.info.cluster.instance.gpu

                            self.logger.warning('[task_scheduler] worker dead, retry task [%s] instance [%d]' % (task.info.id, index))
                            if worker is not None:
                                return task, index, worker

                if worker is not None:
                    # start new instance
                    if len(task.instance_list) < task.info.instanceCount:
                        instance = {}
                        instance['try_count'] = 0
                        task.instance_list.append(instance)
                        return task, len(task.instance_list) - 1, worker'''

            self.check_task_completed(task)

        return None, None, None

    def find_proper_workers(self, vnodes_configs):
        nodes = self.get_all_nodes()
        if nodes is None or len(nodes) == 0:
            self.logger.warning('[task_scheduler] running nodes not found')
            return None

        proper_workers = []
        for needs in vnodes_configs:
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
                    proper_workers.append(worker_ip)
                    break
            else:
                return []
        return proper_workers

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
        configinfo  = {'vnode_nums':7,'atSameTime':True,'MultiStart':True,
                        'maxRetryCount':int(json_task['retryCount'])}
        # json_task = json.loads(json_task)
        task = Task(configinfo,
            VNodeInfo(
            taskid = taskid,
            username = username,
            vnode = Vnode(
                image = Image(
                    name = json_task['image'].split('_')[0], #json_task['cluster']['image']['name'],
                    type = image_dict[json_task['image'].split('_')[2]], #json_task['cluster']['image']['type'],
                    owner = username if not json_task['image'].split('_')[1] else json_task['image'].split('_')[1]), #json_task['cluster']['image']['owner']),
                instance = Instance(
                    cpu = int(json_task['cpuSetting']),
                    memory = int(json_task['memorySetting']),
                    disk = int(json_task['diskSetting']),
                    gpu = int(json_task['gpuSetting'])))
            ),
            TaskInfo(
            taskid = taskid,
            username = username,
            parameters = Parameters(
                command = Command(
                    commandLine = json_task['command'],
                    packagePath = json_task['srcAddr'],
                    envVars = {}),
                stderrRedirectPath = json_task.get('stdErrRedPth',""),
                stdoutRedirectPath = json_task.get('stdOutRedPth',"")),
            timeout = int(json_task['expTime']),
            ),
            priority=task_priority)
        if 'mapping' in json_task:
            task.vnodeinfo.vnode.mount.extend([Mount(localPath=json_task['mapping'][mapping_key]['mappingLocalDir'],
                                                  remotePath=json_task['mapping'][mapping_key]['mappingRemoteDir'])
                                            for mapping_key in json_task['mapping']])
        self.lazy_append_list.append(task)


    # user: username
    # get the information of a task, including the status, task description and other information
    @queue_lock
    def get_task(self, taskid):
        for task in self.task_queue:
            if task.info.id == taskid:
                return task
        return None

    # get names of all the batch containers of the user
    def get_user_batch_containers(self,username):
        if not username in self.user_containers.keys():
            return []
        else:
            return self.user_containers[username]
