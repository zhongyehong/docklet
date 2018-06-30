class TaskMgr(object):

    # task: a json string
    # this is a thread to process task(or a instance)
    def task_processor(self,task):
        # call the rpc to call a function in worker
        # create container -> execute task
        # (one instance or multiple instances)
        # retry when failed
        pass

    # this is a thread to schdule the tasks
    def task_scheduler(self):
        # choose a task from queue, create a task processor for it
        pass

    # user: username
    # task: a json string
    # save the task information into database
    def add_task(self,user,task):
        pass

    # user: username
    # jobid: the id of job
    # taskid: the id of task
    # get the information of a task, including the status, task description and other information
    def get_task(self, user, jobid, taskid):
        pass
    
    # task: a json string
    # this is a rpc function for worker, task processor call this function to execute a task in a worker
    @staticmethod
    def execute_task(self,task):
        return


    # load task information from etcd
    # initial a task queue and task schedueler
    # taskmgr: a taskmgr instance
    def __init__(self):
        pass
