#!/usr/bin/python3

#实例ip调用describe api获取
import paramiko, time
from log import logger
import env

def myexec(ssh,command):
    stdin,stdout,stderr = ssh.exec_command(command)
    endtime = time.time() + 300
    while not stdout.channel.eof_received:
        time.sleep(2)
        if time.time() > endtime:
            stdout.channel.close()
            logger.error(command + ": fail")
#    for line in stdout.readlines():
#        if line is None:
#            time.sleep(5)
#        else:
#            print(line)

#上传deploy脚本
def deploy(ipaddr,masterip,account,password):
    while True:
        try:
            transport = paramiko.Transport((ipaddr,22))
            transport.connect(username=account,password=password)
            break
        except Exception as e:
            time.sleep(2)
            pass
    sftp = paramiko.SFTPClient.from_transport(transport)

    fspath = env.getenv('FS_PREFIX')
    sftp.put('/home/zhong/docklet-deploy.sh','/root/docklet-deploy.sh')
    sftp.put('/home/zhong/docklet-deploy.sh','/root/docklet-deploy.sh')
    transport.close()
    
    #执行deploy脚本
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    while True:
        try:
            ssh.connect(ipaddr, username = account, password = password, timeout = 300)
            break
        except Exception as e:
            time.sleep(2)
            pass
    #这行日后可以删掉
    myexec(ssh,'chmod +x /root/docklet-deploy.sh')
    myexec(ssh,"sed -i 's/%MASTERIP%/" + masterip + "/g' /root/docklet-deploy.sh")
    myexec(ssh,'/root/docklet-deploy.sh ' + ipaddr)
    myexec(ssh,'mount -t glusterfs ' + masterip + ':docklet /opt/docklet/global/')
    myexec(ssh,'/home/docklet/bin/docklet-worker start')
    ssh.close()
    return
