import master.taskmgr
from concurrent import futures
import grpc
from protos import rpc_pb2, rpc_pb2_grpc
import threading, json, time


class SimulatedNodeMgr():
	def get_nodeips(self):
		return ['0.0.0.0']


class SimulatedMonitorFetcher():
	def __init__(self, ip):
		self.info = {}
		self.info['cpuconfig'] = [1,1,1,1]
		self.info['meminfo'] = {}
		self.info['meminfo']['free'] = 4 * 1024 * 1024 # (kb) simulate 4 GB memory
		self.info['diskinfo'] = []
		self.info['diskinfo'].append({})
		self.info['diskinfo'][0]['free'] = 8 * 1024 * 1024 * 1024 # (b) simulate 8 GB disk


class SimulatedTaskController(rpc_pb2_grpc.WorkerServicer):
	def process_task(self, task, context):
		print('[SimulatedTaskController] receive task [%s]' % task.id)
		return rpc_pb2.Reply(status=rpc_pb2.Reply.ACCEPTED,message="")


class SimulatedWorker(threading.Thread):

	def __init__(self):
		threading.Thread.__init__(self)
		self.thread_stop = False

	def run(self):
		server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
		rpc_pb2_grpc.add_WorkerServicer_to_server(SimulatedTaskController(), server)
		server.add_insecure_port('[::]:50052')
		server.start()
		while not self.thread_stop:
			time.sleep(5)
		server.stop(0)

	def stop(self):
		self.thread_stop = True


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
		print('[SimulatedJobMgr] task[%s] status %d' % (task.id, task.status))

	def asignTask(self, taskmgr, taskid, instance_count, retry_count, timeout, cpu, memory, disk):
		task = {}
		task['instanceCount'] = instance_count
		task['maxRetryCount'] = retry_count
		task['timeout'] = timeout
		task['parameters'] = {}
		task['parameters']['command'] = {}
		task['parameters']['command']['commandLine'] = ''
		task['parameters']['command']['packagePath'] = ''
		task['parameters']['command']['envVars'] = {'a':'1'}
		task['parameters']['stderrRedirectPath'] = ''
		task['parameters']['stdoutRedirectPath'] = ''
		task['cluster'] = {}
		task['cluster']['image'] = {}
		task['cluster']['image']['name'] = ''
		task['cluster']['image']['type'] = 1
		task['cluster']['image']['owner'] = ''
		task['cluster']['instance'] = {}
		task['cluster']['instance']['cpu'] = cpu
		task['cluster']['instance']['memory'] = memory
		task['cluster']['instance']['disk'] = disk
		task['cluster']['instance']['gpu'] = 0
		task['cluster']['mount'] = [{'remotePath':'', 'localPath':''}]

		taskmgr.add_task('user', taskid, json.dumps(task))


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

	taskmgr = master.taskmgr.TaskMgr(SimulatedNodeMgr(), SimulatedMonitorFetcher, SimulatedLogger())
	taskmgr.set_jobmgr(jobmgr)
	taskmgr.start()

	jobmgr.asignTask(taskmgr, 'task_0', 2, 2, 60, 2, 2048, 2048)


def stop():
	global worker
	global jobmgr
	global taskmgr

	worker.stop()
	jobmgr.stop()
	taskmgr.stop()
