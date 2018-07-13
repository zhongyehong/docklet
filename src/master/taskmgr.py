import threading
import time

from concurrent import futures
import grpc
from protos.taskmgr_pb2 import Task, Reply
from protos.taskmgr_pb2_grpc import TaskReporterServicer, add_TaskReporterServicer_to_server

class TaskReport(TaskReporterServicer):

    def __init__(self, taskmgr):
        self.taskmgr = taskmgr

    def report(self, request, context):
        self.taskmgr.on_task_report(request)
        return Reply(message='received')

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
            time.sleep(1)


    def serve(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_TaskReporterServicer_to_server(TaskReport(self), self.server)
        self.server.add_insecure_port('[::]:50051')
        self.server.start()


    def stop(self):
        self.thread_stop = True
        self.server.stop(0)


    # this method is called when worker send heart-beat rpc request
    def on_task_report(self, task):
        self.taskQueue.append('task')
        print('rec')
        time.sleep(2)
        print(self.taskQueue)


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
    def add_task(self,user,task):
        pass


    # user: username
    # jobid: the id of job
    # taskid: the id of task
    # get the information of a task, including the status, task description and other information
    def get_task(self, user, jobid, taskid):
        pass
