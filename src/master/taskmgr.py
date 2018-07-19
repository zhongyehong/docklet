import threading
import time

import master.monitor

# must import logger after initlogging, ugly
from utils.log import initlogging
initlogging("docklet-taskmgr")
from utils.log import logger

# grpc
from concurrent import futures
import grpc
from protos.rpc_pb2 import Task, Reply
from protos.rpc_pb2_grpc import MasterServicer, add_MasterServicer_to_server

class TaskReporter(MasterServicer):

    def __init__(self, taskmgr):
        self.taskmgr = taskmgr

    def report(self, request, context):
        self.taskmgr.on_task_report(request)
        return Reply(message=Reply.ACCEPTED)

class TaskMgr(threading.Thread):

    # load task information from etcd
    # initial a task queue and task schedueler
    # taskmgr: a taskmgr instance
    def __init__(self, nodemgr):
        threading.Thread.__init__(self)
        self.thread_stop = False

        # tasks
        self.task_queue = []

        # nodes
        self.nodemgr = nodemgr
        self.all_nodes = None
        self.last_nodes_info_update_time = 0
        self.nodes_info_update_interval = 30 # (s)


    def run(self):
        self.serve()
        while not self.thread_stop:
            task, instance_id, worker = self.task_scheduler()
            if task is not None and worker is not None:
                self.task_processor(task, instance_id, worker)
            else:
                time.sleep(2)


    def serve(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_MasterServicer_to_server(TaskReporter(self), self.server)
        self.server.add_insecure_port('[::]:50051')
        self.server.start()
        logger.info('[taskmgr_rpc] start rpc server')


    def stop(self):
        self.thread_stop = True
        self.server.stop(0)
        logger.info('[taskmgr_rpc] stop rpc server')


    # this method is called when worker send heart-beat rpc request
    def on_task_report(self, report):
        logger.info('[on_task_report] receive task report: id %d, status %d' % (report.id, report.status))
        task = get_task(report.id)
        if task == None:
            logger.error('[on_task_report] task not found')
            return

        instance_id = report.parameters.command.envVars['INSTANCE_ID']
        instance = task.instance_list[instance_id]

        if report.status == Task.RUNNING:
            pass
        elif report.status == Task.COMPLETED:
            instance['status'] = 'completed'
            check_task_completed(task)
        elif report.status == Task.FAILED || report.status == Task.TIMEOUT:
            instance['status'] = 'failed'
            if instance['try_count'] > task.maxRetryCount:
                check_task_completed(task)
        else:
            logger.error('[on_task_report] receive report from waiting task')


    def check_task_completed(self, task):
        if len(task.instance_list) < task.instanceCount:
            return
        failed = False
        for instance in task.instance_list:
            if instance['status'] == 'running':
                return
            if instance['status'] == 'failed':
                if instance['try_count'] > task.maxRetryCount:
                    failed = True
                else:
                    return
        if failed:
            # tell jobmgr task failed
            task.status = Task.FAILED
        else:
            # tell jobmgr task completed
            task.status = Task.COMPLETED
        self.task_queue.remove(task)


    def task_processor(self, task, instance_id, worker):
        task.status = Task.RUNNING
        task.parameters.command.envVars['INSTANCE_ID'] = instance_id
        # TODO call the rpc to call a function in worker
        print('processing %s' % task.id)


    # return task, worker
    def task_scheduler(self):
        # simple FIFO
        for task in self.task_queue:
            worker = self.find_proper_worker(task)
            if worker is not None:
                # find instance to retry
                for instance, index in enumerate(task.instance_list):
                    if instance['status'] == 'failed' and instance['try_count'] <= task.maxRetryCount:
                        instance['try_count'] += 1
                        return task, index, worker

                # start new instance
                if len(task.instance_list) < task.instanceCount:
                    instance = {}
                    instance['status'] = 'running'
                    instance['try_count'] = 0
                    task.instance_list.append(instance)
                    return task, len(task.instance_list) - 1, worker
        return None


    def find_proper_worker(self, task):
        nodes = get_all_nodes()
        if nodes is None or len(nodes) == 0:
            logger.warning('[task_scheduler] running nodes not found')
            return None

        # TODO
        return nodes[0]


    def get_all_nodes(self):
        # cache running nodes
        if self.all_nodes is not None and time.time() - self.last_nodes_info_update_time < self.nodes_info_update_interval:
            return self.all_nodes
        # get running nodes
        node_ips = self.nodemgr.get_nodeips()
        self.all_nodes = []
        for node_ip in node_ips:
            fetcher = master.monitor.Fetcher(node_ip)
            self.all_nodes.append(fetcher.info)
        return self.all_nodes


    # user: username
    # task: a json string
    # save the task information into database
    # called when jobmgr assign task to taskmgr
    def add_task(self, task):
        # decode json string to object defined in grpc
        task.instance_list = []
        self.task_queue.append(task)


    # user: username
    # get the information of a task, including the status, task description and other information
    def get_task(self, taskid):
        for task in self.task_queue:
            if task.id == taskid:
                return task
        return None
