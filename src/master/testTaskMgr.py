import master.taskmgr
from concurrent import futures
import grpc
from protos.rpc_pb2 import *
from protos.rpc_pb2_grpc import *
import threading, json, time, random
from utils import env


class SimulatedNodeMgr():
	def get_batch_nodeips(self):
		return ['0.0.0.0']


class SimulatedMonitorFetcher():
	def __init__(self, ip):
		self.info = {}
		self.info['cpuconfig'] = [1,1,1,1,1,1,1,1]
		self.info['meminfo'] = {}
		self.info['meminfo']['free'] = 8 * 1024 * 1024 # (kb) simulate 8 GB memory
		self.info['meminfo']['buffers'] = 8 * 1024 * 1024
		self.info['meminfo']['cached'] = 8 * 1024 * 1024
		self.info['diskinfo'] = []
		self.info['diskinfo'].append({})
		self.info['diskinfo'][0]['free'] = 16 * 1024 * 1024 * 1024 # (b) simulate 16 GB disk
		self.info['gpuinfo'] = [1,1]


class SimulatedTaskController(WorkerServicer):

	def __init__(self, worker):
		self.worker = worker

	def start_vnode(self, vnodeinfo, context):
		print('[SimulatedTaskController] start vnode, taskid [%s] vnodeid [%d]' % (vnodeinfo.taskid, vnodeinfo.vnodeid))
		return Reply(status=Reply.ACCEPTED,message="")
	
	def stop_vnode(self, vnodeinfo, context):
		print('[SimulatedTaskController] stop vnode, taskid [%s] vnodeid [%d]' % (vnodeinfo.taskid, vnodeinfo.vnodeid))
		return Reply(status=Reply.ACCEPTED,message="")

	def start_task(self, taskinfo, context):
		print('[SimulatedTaskController] start task, taskid [%s] vnodeid [%d] token [%s]' % (taskinfo.taskid, taskinfo.vnodeid, taskinfo.token))
		worker.process(taskinfo)
		return Reply(status=Reply.ACCEPTED,message="")

	def stop_task(self, taskinfo, context):
		print('[SimulatedTaskController] stop task, taskid [%s] vnodeid [%d] token [%s]' % (taskinfo.taskid, taskinfo.vnodeid, taskinfo.token))
		return Reply(status=Reply.ACCEPTED,message="")


class SimulatedWorker(threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.thread_stop = False
		self.tasks = []

	def run(self):
		worker_port = env.getenv('BATCH_WORKER_PORT')
		server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
		add_WorkerServicer_to_server(SimulatedTaskController(self), server)
		server.add_insecure_port('[::]:' + worker_port)
		server.start()
		while not self.thread_stop:
			for task in self.tasks:
				seed = random.random()
				if seed < 0.25:
					report(task.taskid, task.vnodeid, RUNNING, task.token)
				elif seed < 0.5:
					report(task.taskid, task.vnodeid, COMPLETED, task.token)
					self.tasks.remove(task)
					break
				elif seed < 0.75:
					report(task.taskid, task.vnodeid, FAILED, task.token)
					self.tasks.remove(task)
					break
				else:
					pass
			time.sleep(5)
		server.stop(0)

	def stop(self):
		self.thread_stop = True

	def process(self, task):
		self.tasks.append(task)


class SimulatedJobMgr(threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.thread_stop = False

	def run(self):
		while not self.thread_stop:
			time.sleep(5)
		server.stop(0)

	def stop(self):
		self.thread_stop = True

	def report(self, task):
		print('[SimulatedJobMgr] task[%s] status %d' % (task.info.id, task.status))

	def assignTask(self, taskmgr, taskid, instance_count, retry_count, timeout, cpu, memory, disk, gpu):
		task = {}
		task['instCount'] = instance_count
		task['retryCount'] = retry_count
		task['expTime'] = timeout
		task['at_same_time'] = True
		task['multicommand'] = True
		task['command'] = 'ls'
		task['srcAddr'] = ''
		task['envVars'] = {'a':'1'}
		task['stdErrRedPth'] = ''
		task['stdOutRedPth'] = ''
		task['image'] = 'root_root_base'
		task['cpuSetting'] = cpu
		task['memorySetting'] = memory
		task['diskSetting'] = disk
		task['gpuSetting'] = 0
		task['mapping'] = []

		taskmgr.add_task('root', taskid, task)


class SimulatedLogger():
	def info(self, msg):
		print('[INFO]    ' + msg)

	def warning(self, msg):
		print('[WARNING] ' + msg)

	def error(self, msg):
		print('[ERROR]   ' + msg)


def test():
	global worker
	global jobmgr
	global taskmgr

	worker = SimulatedWorker()
	worker.start()
	jobmgr = SimulatedJobMgr()
	jobmgr.start()

	taskmgr = master.taskmgr.TaskMgr(SimulatedNodeMgr(), SimulatedMonitorFetcher, master_ip='', scheduler_interval=2, external_logger=SimulatedLogger())
	# taskmgr.set_jobmgr(jobmgr)
	taskmgr.start()

	add('task_0', instance_count=2, retry_count=2, timeout=60, cpu=2, memory=2048, disk=2048, gpu=0)


def test2():
	global jobmgr
	global taskmgr
	jobmgr = SimulatedJobMgr()
	jobmgr.start()

	taskmgr = master.taskmgr.TaskMgr(SimulatedNodeMgr(), SimulatedMonitorFetcher, master_ip='', scheduler_interval=2, external_logger=SimulatedLogger())
	taskmgr.set_jobmgr(jobmgr)
	taskmgr.start()

	add('task_0', instance_count=2, retry_count=2, timeout=60, cpu=2, memory=2048, disk=2048, gpu=0)



def add(taskid, instance_count, retry_count, timeout, cpu, memory, disk, gpu):
	global jobmgr
	global taskmgr
	jobmgr.assignTask(taskmgr, taskid, instance_count, retry_count, timeout, cpu, memory, disk, gpu)


def report(taskid, instanceid, status, token):
	global taskmgr

	master_port = env.getenv('BATCH_MASTER_PORT')
	channel = grpc.insecure_channel('%s:%s' % ('0.0.0.0', master_port))
	stub = MasterStub(channel)
	response = stub.report(ReportMsg(taskmsgs=[TaskMsg(taskid=taskid, username='root', vnodeid=instanceid, subTaskStatus=status, token=token)]))


def stop():
	global worker
	global jobmgr
	global taskmgr

	worker.stop()
	jobmgr.stop()
	taskmgr.stop()
