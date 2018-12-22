import time, threading, random, string, os, traceback
import master.monitor
import subprocess

from utils.log import initlogging, logger
from utils import env

class BatchJob(object):
    def __init__(self, user, job_info):
        self.user = user
        self.raw_job_info = job_info
        self.task_queue = []
        self.task_finished = []
        self.job_id = None
        self.job_name = job_info['jobName']
        self.job_priority = int(job_info['jobPriority'])
        self.status = 'pending'
        self.create_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
        self.top_sort()

    # transfer the dependency graph into a job queue
    def top_sort(self):
        logger.debug('top sorting')
        tasks = self.raw_job_info["tasks"]
        logger.debug('top sorting test')
        dependency_graph = {}
        logger.debug('top sorting test2')
        logger.info(tasks)
        for task_idx in tasks:
            dependency_graph[task_idx] = set()
            task_info = tasks[task_idx]
            dependency = task_info['dependency'].strip().replace(' ', '').split(',')
            if len(dependency) == 1 and dependency[0] == '':
                continue
            for t in dependency:
                if not t in tasks:
                    raise ValueError('task %s is not defined in the dependency of task %s' % (t, task_idx))
                dependency_graph[task_idx].add(t)
        logger.debug('top sorting end')
        while len(dependency_graph) > 0:
            s = set()
            flag = False
            for task_idx in dependency_graph:
                if len(dependency_graph[task_idx]) == 0:
                    flag = True
                    s.add(task_idx)
            for task_idx in s:
                dependency_graph.pop(task_idx)
            #there is a circle in the graph
            if not flag:
                raise ValueError('there is a circle in the dependency graph')
                break
            for task_idx in dependency_graph:
                for t in s:
                    if t in dependency_graph[task_idx]:
                        dependency_graph[task_idx].remove(t)
            self.task_queue.append({
                'task_idx': s,
                'status': 'pending'
            })
        logger.debug('top sorting return')

    # get a task and pass it to taskmgr
    def get_task(self):
        for task in self.task_queue:
            if task['status'] == 'pending':
                task_idx = task['task_idx'].pop()
                task['status'] = 'running'
                task_name = self.user + '_' + self.job_id + '_' + task_idx
                return task_name, self.raw_job_info["tasks"][task_idx]
        return '', None

    # a task has finished
    def finish_task(self, task_idx):
        pass

class JobMgr(threading.Thread):
    # load job information from etcd
    # initial a job queue and job schedueler
    def __init__(self, taskmgr):
        threading.Thread.__init__(self)
        self.job_queue = []
        self.job_map = {}
        self.taskmgr = taskmgr
        self.fspath = env.getenv('FS_PREFIX')

    def run(self):
        while True:
            self.job_scheduler()
            time.sleep(2)

    # user: username
    # job_data: a json string
    # user submit a new job, add this job to queue and database
    def add_job(self, user, job_info):
        try:
            logger.info(self.job_queue)
            job = BatchJob(user, job_info)
            logger.info("test2")
            job.job_id = self.gen_jobid()
            logger.info("test3")
            self.job_queue.append(job.job_id)
            self.job_map[job.job_id] = job
        except ValueError as err:
            logger.error(err)
            return [False, err.args[0]]
        except Exception as err:
            return [False, err.args[0]]
        finally:
            return [True, "add batch job success"]

    # user: username
    # list a user's all job
    def list_jobs(self,user):
        res = []
        logger.info(self.job_queue)
        for job_id in self.job_queue:
            job = self.job_map[job_id]
            logger.debug('job_id: %s, user: %s' % (job_id, job.user))
            if job.user == user:
                all_tasks = job.raw_job_info['tasks']
                tasks_instCount = {}
                for task in all_tasks.keys():
                    tasks_instCount[task] = int(all_tasks[task]['instCount'])
                res.append({
                    'job_name': job.job_name,
                    'job_id': job.job_id,
                    'status': job.status,
                    'create_time': job.create_time,
                    'tasks': list(all_tasks.keys()),
                    'tasks_instCount': tasks_instCount
                })
        return res

    # user: username
    # jobid: the id of job
    # get the information of a job, including the status, json description and other information
    # call get_task to get the task information
    def get_job(self, user, job_id):
        pass

    # check if a job exists
    def is_job_exist(self, job_id):
        return job_id in self.job_queue

    # generate a random job id
    def gen_jobid(self):
        job_id = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        while self.is_job_exist(job_id):
            job_id = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        return job_id

    # this is a thread to process a job
    def job_processor(self, job):
        task_name, task_info = job.get_task()
        if not task_info:
            return False
        else:
            task_priority = job.job_priority
            self.taskmgr.add_task(job.user, task_name, task_info, task_priority)
            return True

    # this is a thread to schedule the jobs
    def job_scheduler(self):
        # choose a job from queue, create a job processor for it
        for job_id in self.job_queue:
            job = self.job_map[job_id]
            if self.job_processor(job):
                job.status = 'running'
                break
            else:
                job.status = 'done'

    # a task has finished
    def report(self, task):
        pass

    def get_output(self, username, jobid, taskid, instid, issue):
        filename = username + "_" + jobid + "_" + taskid + "_" + instid + "_" + issue + ".txt"
        fpath = "%s/global/users/%s/data/batch_%s/%s" % (self.fspath,username,jobid,filename)
        logger.info("Get output from:%s" % fpath)
        try:
            ret = subprocess.run('tail -n 100 ' + fpath,stdout=subprocess.PIPE,stderr=subprocess.STDOUT, shell=True)
            if ret.returncode != 0:
                raise IOError(ret.stdout.decode(encoding="utf-8"))
        except Exception as err:
            logger.error(traceback.format_exc())
            return ""
        else:
            return ret.stdout.decode(encoding="utf-8")
