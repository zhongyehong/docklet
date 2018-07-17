import threading
import time

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
    def __init__(self):
        threading.Thread.__init__(self)
        self.thread_stop = False
        self.taskQueue = []


    def run(self):
        self.serve()
        while not self.thread_stop:
            task = self.task_scheduler()
            if task is not None:
                self.task_processor(task)
            time.sleep(2)


    def serve(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_MasterServicer_to_server(TaskReporter(self), self.server)
        self.server.add_insecure_port('[::]:50051')
        self.server.start()


    def stop(self):
        self.thread_stop = True
        self.server.stop(0)


    # this method is called when worker send heart-beat rpc request
    def on_task_report(self, report):
        logger.info('[on_task_report] receive task report: id %d, status %d' % (report.id, report.status))
        task = get_task(report.id)
        if task == None:
            logger.error('[on_task_report] task not found')
            return

        task.status = report.status
        if task.status == Task.RUNNING:
            pass
        elif task.status == Task.COMPLETED:
            # tell jobmgr
            pass
        elif task.status == Task.FAILED || task.status == Task.TIMEOUT:
            # retry
            if task.maxRetryCount <= 0:
                # tell jobmgr
                pass
            else:
                # decrease max retry count & waiting for retry
                task.maxRetryCount -= 1
                task.status = Task.WAITING
        else:
            logger.error('[on_task_report] receive report from waiting task')


    # this is a thread to process task(or a instance)
    def task_processor(self,task):
        # call the rpc to call a function in worker
        # create container -> execute task
        # (one instance or multiple instances)
        # retry when failed
        print('processing %s' % task)


    # this is a thread to schdule the tasks
    def task_scheduler(self):
        try:
            task = self.taskQueue.pop(0)
        except:
            task = None
        return task


    # user: username
    # task: a json string
    # save the task information into database
    # called when jobmgr assign task to taskmgr
    def add_task(self, task):
        pass


    # user: username
    # get the information of a task, including the status, task description and other information
    def get_task(self, taskid):
        for task in self.taskQueue:
            if task.id == taskid:
                return task
        return None
