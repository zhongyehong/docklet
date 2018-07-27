import sys
if sys.path[0].endswith("master"):
    sys.path[0] = sys.path[0][:-6]

import grpc

from protos import rpc_pb2, rpc_pb2_grpc

def run():
    channel = grpc.insecure_channel('localhost:50051')
    stub = rpc_pb2_grpc.WorkerStub(channel)

    comm = rpc_pb2.Command(commandLine=r"echo \"s\" | awk '{print \"test\n\\\"\"}' > test.txt;cat test.txt", packagePath="/root", envVars={'test1':'10','test2':'20'}) # | awk '{print \"test\\\"\\n\"}'
    paras = rpc_pb2.Parameters(command=comm, stderrRedirectPath="", stdoutRedirectPath="")

    img = rpc_pb2.Image(name="base", type=rpc_pb2.Image.BASE, owner="docklet")
    inst = rpc_pb2.Instance(cpu=2, memory=2000, disk=500, gpu=0)
    mnt = rpc_pb2.Mount(localPath="",remotePath="")
    clu = rpc_pb2.Cluster(image=img, instance=inst, mount=[mnt])

    task = rpc_pb2.Task(id="test",username="root",instanceid=0,instanceCount=1,maxRetryCount=1,parameters=paras,cluster=clu,timeout=10)

    response = stub.process_task(task)
    print("Batch client received: " + str(response.status)+" "+response.message)


if __name__ == '__main__':
    run()
