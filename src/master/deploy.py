#!/usr/bin/python3

import paramiko, time, os
from utils.log import logger
from utils import env

def myexec(ssh, command):
    stdin,stdout,stderr = ssh.exec_command(command)
    endtime = time.time() + 3600
    while not stdout.channel.eof_received:
        time.sleep(2)
        if time.time() > endtime:
            stdout.channel.close()
            logger.error(command + ": fail")
            return
#    for line in stdout.readlines():
#        if line is None:
#            time.sleep(5)
#        else:
#            print(line)

def deploy(ipaddr, masterip, account, password, volumename, disksize):
    while True:
        try:
            transport = paramiko.Transport((ipaddr,22))
            transport.connect(username=account,password=password)
            break
        except Exception as e:
            time.sleep(2)
            pass
    sftp = paramiko.SFTPClient.from_transport(transport)

    currentfilepath = os.path.dirname(os.path.abspath(__file__))
    deployscriptpath = currentfilepath + "/../../tools/docklet-deploy.sh"
    sftp.put(deployscriptpath,'/root/docklet-deploy.sh')
    # sftp.put('/etc/hosts', '/etc/hosts')
    transport.close()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    while True:
        try:
            ssh.connect(ipaddr, username = account, password = password, timeout = 300)
            break
        except Exception as e:
            time.sleep(2)
            pass
    myexec(ssh,"sed -i 's/%MASTERIP%/" + masterip + "/g' /root/docklet-deploy.sh")
    myexec(ssh,"sed -i 's/%VOLUMENAME%/" + volumename + "/g' /root/docklet-deploy.sh")
    myexec(ssh,"sed -i 's/%DISKSIZE%/" + str(disksize) + "/g' /root/docklet-deploy.sh")
    myexec(ssh,'chmod +x /root/docklet-deploy.sh')
    myexec(ssh,'/root/docklet-deploy.sh')
    ssh.close()
    return
