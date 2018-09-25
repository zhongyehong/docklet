import sys
if sys.path[0].endswith("master"):
    sys.path[0] = sys.path[0][:-6]

import grpc

from protos import rpc_pb2, rpc_pb2_grpc

def run():
    channel = grpc.insecure_channel('localhost:50051')
    stub = rpc_pb2_grpc.WorkerStub(channel)

    comm = rpc_pb2.Command(commandLine="echo \"stestsfdsf\\ntewtgsdgfdsgret\newarsafsda\" > /root/nfs/test-for-docklet/test.txt;ls /root/nfs/test-for-docklet", packagePath="/root", envVars={'test1':'10','test2':'20'}) # | awk '{print \"test\\\"\\n\"}'
    paras = rpc_pb2.Parameters(command=comm, stderrRedirectPath="/root/nfs/", stdoutRedirectPath="/root/nfs/test-for-docklet")

    img = rpc_pb2.Image(name="base", type=rpc_pb2.Image.BASE, owner="docklet")
    inst = rpc_pb2.Instance(cpu=2, memory=2000, disk=500, gpu=0)
    mnt = rpc_pb2.Mount(localPath="",remotePath="test-for-docklet",endpoint="oss-cn-beijing.aliyuncs.com",accessKey="LTAIdl7gmmIhfqA9",secretKey="")
    clu = rpc_pb2.Cluster(image=img, instance=inst, mount=[mnt])

    task = rpc_pb2.TaskInfo(id="test",username="root",instanceid=1,instanceCount=1,maxRetryCount=1,parameters=paras,cluster=clu,timeout=5,token="test")

    response = stub.process_task(task)
    print("Batch client received: " + str(response.status)+" "+response.message)


if __name__ == '__main__':
    run()
