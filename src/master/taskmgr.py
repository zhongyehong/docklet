import threading
import time
import string
import random
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
    def __init__(self, info, priority, job_id):
        self.info = info
        self.status = WAITING
        self.instance_list = []
        self.token = ''
        # priority the bigger the better
        # self.priority the smaller the better
        self.priority = int(time.time()) / 60 / 60 - priority
        self.job_id = job_id

    def __lt__(self, other):
        return self.priority < other.priority


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
    def __init__(self, nodemgr, cloudmgr, monitor_fetcher,scheduler_interval=10, external_logger=None):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.jobmgr = None
        self.task_queue = []
        self.lazy_append_list = []
        self.lazy_delete_list = []
        self.task_queue_lock = threading.Lock()
        self.user_containers = {}

        self.scheduler_interval = scheduler_interval
        self.logger = logger

        self.master_port = env.getenv('BATCH_MASTER_PORT')
        self.worker_port = env.getenv('BATCH_WORKER_PORT')

        # nodes
        self.nodemgr = nodemgr
        self.cloudmgr = cloudmgr
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
            # task, instance_id, worker = self.task_scheduler()
            # if task is not None and worker is not None:
            #     self.task_processor(task, instance_id, worker)
            instance_worker_pair = self.task_scheduler_cloud()
            self.task_processor_cloud(instance_worker_pair)
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


    # this method is called when worker send heart-beat rpc request
    def on_task_report(self, report):
        self.logger.info('[on_task_report] receive task report: id %s-%d, status %d' % (report.taskid, report.instanceid, report.instanceStatus))
        task = self.get_task(report.taskid)
        if task == None:
            self.logger.error('[on_task_report] task not found')
            return

        instance = task.instance_list[report.instanceid]
        if instance['token'] != report.token:
            self.logger.warning('[on_task_report] wrong token')
            return
        username = task.info.username
        container_name = username + '-batch-' + task.info.id + '-' + str(report.instanceid) + '-' + report.token
        self.user_containers[username].remove(container_name)

        if instance['status'] != RUNNING:
            self.logger.error('[on_task_report] receive task report when instance is not running')

        if instance['status'] == RUNNING and report.instanceStatus != RUNNING:
            #self.cpu_usage[instance['worker']] -= task.info.cluster.instance.cpu
            #self.gpu_usage[instance['worker']] -= task.info.cluster.instance.gpu
            self.cloudmgr.engine.removeTaskFromNode(instance['worker'], task)

        instance['status'] = report.instanceStatus
        instance['error_msg'] = report.errmsg

        if report.instanceStatus == COMPLETED:
            self.check_task_completed(task)
        elif report.instanceStatus == FAILED or report.instanceStatus == TIMEOUT:
            if instance['try_count'] > task.info.maxRetryCount:
                self.check_task_completed(task)
        elif report.instanceStatus == OUTPUTERROR:
            self.task_failed(task)


    def check_task_completed(self, task):
        if len(task.instance_list) < task.info.instanceCount:
            return
        failed = False
        for instance in task.instance_list:
            if instance['status'] == RUNNING or instance['status'] == WAITING:
                return
            if instance['status'] == FAILED or instance['status'] == TIMEOUT:
                if instance['try_count'] > task.info.maxRetryCount:
                    failed = True
                else:
                    return
            if instance['status'] == OUTPUTERROR:
                failed = True
                break

        if failed:
            self.task_failed(task)
        else:
            self.task_completed(task)


    def task_completed(self, task):
        task.status = COMPLETED

        if self.jobmgr is None:
            self.logger.error('[task_completed] jobmgr is None!')
        else:
            self.jobmgr.report(task)
        self.logger.info('task %s completed' % task.info.id)
        self.lazy_delete_list.append(task)


    def task_failed(self, task):
        task.status = FAILED

        if self.jobmgr is None:
            self.logger.error('[task_failed] jobmgr is None!')
        else:
            self.jobmgr.report(task)
        self.logger.info('task %s failed' % task.info.id)
        self.lazy_delete_list.append(task)


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


    def task_processor(self, task, instance_id, worker_ip):
        task.status = RUNNING

        # properties for transaction
        task.info.instanceid = instance_id
        task.info.token = ''.join(random.sample(string.ascii_letters + string.digits, 8))

        instance = task.instance_list[instance_id]
        instance['status'] = RUNNING
        instance['try_count'] += 1
        instance['token'] = task.info.token
        instance['worker'] = worker_ip

        #self.cpu_usage[worker_ip] += task.info.cluster.instance.cpu
        #self.gpu_usage[worker_ip] += task.info.cluster.instance.gpu
        
        username = task.info.username
        container_name = task.info.username + '-batch-' + task.info.id + '-' + str(instance_id) + '-' + task.info.token
        if not username in self.user_containers.keys():
            self.user_containers[username] = []
        self.user_containers[username].append(container_name)

        try:
            self.logger.info('[task_processor] processing task [%s] instance [%d]' % (task.info.id, task.info.instanceid))
            channel = grpc.insecure_channel('%s:%s' % (worker_ip, self.worker_port))
            stub = WorkerStub(channel)
            response = stub.process_task(task.info)
            if response.status != Reply.ACCEPTED:
                raise Exception(response.message)
        except Exception as e:
            self.logger.error('[task_processor] rpc error message: %s' % e)
            instance['status'] = FAILED
            instance['try_count'] -= 1
            self.cloudmgr.engine.removeTaskFromNode(instance['worker'], task)
            self.user_containers[username].remove(container_name)


    def task_scheduler_cloud(self):
        
        instance_list = []
        instance_worker_pair = []
        
        for task in self.task_queue:
            if task in self.lazy_delete_list:
                continue

            while len(task.instance_list) < task.info.instanceCount:
                instance = {}
                instance['try_count'] = 0
                instance['task'] = task
                instance['idx'] = len(task.instance_list)
                task.instance_list.append(instance)
                instance_list.append(instance)

        for instance in instance_list:
            worker = self.find_proper_cloud_worker(instance['task'])
            if worker:
                instance_list.remove(instance)
                instance_worker_pair.append([instance['task'], instance['idx'], worker])

        cpu_total = 2.0
        memory_total = 8190.0 

        cpu_current = 0
        memory_current = 0
        disk_current = 0
        instance_current = []

        thread_list = []

        for instance in instance_list:
            cpu = instance['task'].info.cluster.instance.cpu
            memory = instance['task'].info.cluster.instance.memory
            disk = instance['task'].info.cluster.instance.disk
            if cpu + cpu_current <= cpu_total and memory + memory_current <= memory_total:
                cpu_current += cpu
                memory_current += memory
                disk_current += disk
                instance_current.append(instance)
            else:
                thread = threading.Thread(target = self.assign_task_to_worker, args=(instance_current, instance_worker_pair, 'ecs.g5.large', 'hdd', 50+int(disk_current/1024)))
                thread.setDaemon(True)
                thread.start()
                thread_list.append(thread)
                cpu_current += cpu
                memory_current += memory
                disk_current = disk
                instance_current = [instance]
        
        for thread in thread_list:
            thread.join()

        return instance_worker_pair

    def task_processor_cloud(self, instance_worker_pair):
        for item in instance_worker_pair:
            self.task_processor(item[0], item[1], item[2])


    # return task, worker
    def task_scheduler(self):
        # simple FIFO with priority
        self.logger.info('[task_scheduler] scheduling... (%d tasks remains)' % len(self.task_queue))

        # nodes = self.get_all_nodes()
        # if nodes is None or len(nodes) == 0:
        #     self.logger.info('[task_scheduler] no nodes found')
        # else:
        #     for worker_ip, worker_info in nodes:
        #         self.logger.info('[task_scheduler] nodes %s' % worker_ip)
        #         for key in worker_info:
        #             if key == 'cpu':
        #                 self.logger.info('[task_scheduler]     %s: %d/%d' % (key, self.get_cpu_usage(worker_ip), worker_info[key]))
        #             else:
        #                 self.logger.info('[task_scheduler]     %s: %d' % (key, worker_info[key]))

        for task in self.task_queue:
            if task in self.lazy_delete_list:
                continue
            # worker = self.find_proper_worker(task)
            worker = self.find_proper_cloud_worker(task)


            for index, instance in enumerate(task.instance_list):
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
                        #self.cpu_usage[instance['worker']] -= task.info.cluster.instance.cpu
                        #self.gpu_usage[instance['worker']] -= task.info.cluster.instance.gpu
                        self.cloudmgr.engine.removeTaskFromNode(instance['worker'], task)
                        self.logger.warning('[task_scheduler] worker dead, retry task [%s] instance [%d]' % (task.info.id, index))
                        if worker is not None:
                            return task, index, worker

            if worker is not None:
                # start new instance
                if len(task.instance_list) < task.info.instanceCount:
                    instance = {}
                    instance['try_count'] = 0
                    task.instance_list.append(instance)
                    return task, len(task.instance_list) - 1, worker

            self.check_task_completed(task)

        return None, None, None

    def find_proper_worker(self, task):
        nodes = self.get_all_nodes()
        if nodes is None or len(nodes) == 0:
            self.logger.warning('[task_scheduler] running nodes not found')
            return None

        for worker_ip, worker_info in nodes:
            if task.info.cluster.instance.cpu + self.get_cpu_usage(worker_ip) > worker_info['cpu']:
                continue
            if task.info.cluster.instance.memory > worker_info['memory']:
                continue
            # try not to assign non-gpu task to a worker with gpu
            if task.info.cluster.instance.gpu == 0 and worker_info['gpu'] > 0:
                continue
            if task.info.cluster.instance.gpu + self.get_gpu_usage(worker_ip) > worker_info['gpu']:
                continue
            return worker_ip


        return None

    def find_proper_cloud_worker(self, task, timeout=600, wait_period=3):

        nodes = self.cloudmgr.engine.listNodes()
        
        for node in nodes:
            if node.cpu_free >= task.info.cluster.instance.cpu and node.memory_free >= task.info.cluster.instance.memory:
                self.cloudmgr.engine.addTaskToNode(worker_ip, task)
                logger.info("find proper cloud worker, ip: {}".format(node.private_ip))
                return node.private_ip

        logger.info("proper cloud worker not found")

    def assign_task_to_worker(self, instance_list, instance_worker_pair, instance_type='ecs.g5.large', disk_type='hdd', disk_size=100):
        
        worker = self.create_new_worker(instance_type, disk_type, disk_size)
        
        for instance in instance_list:
            self.cloudmgr.engine.addTaskToNode(worker, instance['task'])
            instance_worker_pair.append([instance['task'], instance['idx'], worker])

    def create_new_worker(self, instance_type='ecs.g5.large', disk_type='hdd', disk_size=100):
        
        logger.info("create a new cloud worker with type - {}, disk_type - {}, disk_size - {}".format(instance_type, disk_type, str(disk_size)))

        result = self.cloudmgr.engine.addNode(instance_type, disk_type, disk_size)

        if result['success'] == 'false':
            logger.info("create cloud worker failed")
            return None

        node = result['node']

        logger.info("create cloud worker success, ip: {} - {}".format(node.public_ip, node.private_ip))

        return node.private_ip

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


    def set_jobmgr(self, jobmgr):
        self.jobmgr = jobmgr


    # save the task information into database
    # called when jobmgr assign task to taskmgr
    def add_task(self, username, jobid, taskid, json_task, task_priority=1):
        # decode json string to object defined in grpc
        self.logger.info('[taskmgr add_task] receive task %s' % taskid)
        image_dict = {
            "private": Image.PRIVATE,
            "base": Image.BASE,
            "public": Image.PUBLIC
        }
        # json_task = json.loads(json_task)
        task = Task(TaskInfo(
            id = taskid,
            username = username,
            instanceCount = int(json_task['instCount']),
            maxRetryCount = int(json_task['retryCount']),
            timeout = int(json_task['expTime']),
            parameters = Parameters(
                command = Command(
                    commandLine = json_task['command'],
                    packagePath = json_task['srcAddr'],
                    envVars = {}),
                stderrRedirectPath = json_task.get('stdErrRedPth',""),
                stdoutRedirectPath = json_task.get('stdOutRedPth',"")),
            cluster = Cluster(
                image = Image(
                    name = json_task['image'].split('_')[0], #json_task['cluster']['image']['name'],
                    type = image_dict[json_task['image'].split('_')[2]], #json_task['cluster']['image']['type'],
                    owner = username if not json_task['image'].split('_')[1] else json_task['image'].split('_')[1]), #json_task['cluster']['image']['owner']),
                instance = Instance(
                    cpu = int(json_task['cpuSetting']),
                    memory = int(json_task['memorySetting']),
                    disk = int(json_task['diskSetting']),
                    gpu = int(json_task['gpuSetting'])))),
            priority=task_priority,
            job_id=jobid)
        if 'mapping' in json_task:
            task.info.cluster.mount.extend([Mount(localPath=json_task['mapping'][mapping_key]['mappingLocalDir'],
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
