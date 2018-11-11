import sys
if sys.path[0].endswith("master"):
    sys.path[0] = sys.path[0][:-6]

import grpc,time

from protos import rpc_pb2, rpc_pb2_grpc

def run():
    channel = grpc.insecure_channel('localhost:50051')
    stub = rpc_pb2_grpc.WorkerStub(channel)

    comm = rpc_pb2.Command(commandLine="echo \"stestsfdsf\\ntewtgsdgfdsgret\newarsafsda\" > /root/test.txt;ls /root;sleep 2", packagePath="/root", envVars={'test1':'10','test2':'20'}) # | awk '{print \"test\\\"\\n\"}'
    paras = rpc_pb2.Parameters(command=comm, stderrRedirectPath="/root/nfs/", stdoutRedirectPath="")

    img = rpc_pb2.Image(name="tensorflow", type=rpc_pb2.Image.PRIVATE, owner="root")
    inst = rpc_pb2.Instance(cpu=2, memory=2000, disk=500, gpu=0)
    mnt = rpc_pb2.Mount(localPath="",provider='aliyun',remotePath="test-for-docklet",other="oss-cn-beijing.aliyuncs.com",accessKey="LTAIdl7gmmIhfqA9",secretKey="")
    clu = rpc_pb2.Cluster(image=img, instance=inst, mount=[])

    task = rpc_pb2.TaskInfo(id="test",username="root",instanceid=1,instanceCount=1,maxRetryCount=1,parameters=paras,cluster=clu,timeout=600,token="test")

    response = stub.process_task(task)
    print("Batch client received: " + str(response.status)+" "+response.message)

def stop_task():
    channel = grpc.insecure_channel('localhost:50051')
    stub = rpc_pb2_grpc.WorkerStub(channel)

    taskmsg = rpc_pb2.TaskMsg(taskid="test",username="root",instanceid=1,instanceStatus=rpc_pb2.COMPLETED,token="test",errmsg="")
    reportmsg = rpc_pb2.ReportMsg(taskmsgs = [taskmsg])

    response = stub.stop_tasks(reportmsg)
    print("Batch client received: " + str(response.status)+" "+response.message)

if __name__ == '__main__':
    run()
    #time.sleep(4)
    #stop_task()
