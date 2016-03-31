#!/usr/bin/python3

import env,subprocess,os,time
from log import logger

def sys_run(command):
    Ret = subprocess.run(command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, shell=True, check=False)
    return Ret

def new_group(group_name, size = "5000", file_path = "/opt/docklet/local/docklet-storage"):
    storage = env.getenv("STORAGE")
    logger.info("begin initialize lvm group:%s with size %sM" % (group_name,size))
    if storage == "file":
        #check vg
        Ret = sys_run("vgdisplay " + group_name)
        if Ret.returncode == 0:
            logger.info("lvm group: " + group_name + " already exists, delete it")
            Ret = sys_run("vgremove -f " + group_name)
            if Ret.returncode != 0:
                logger.error("delete VG %s failed:%s" % (group_name,Ret.stdout.decode('utf-8')))
        #check pv
        Ret = sys_run("pvdisplay /dev/loop0")
        if Ret.returncode == 0:
            Ret = sys_run("pvremove -ff /dev/loop0")
            if Ret.returncode != 0:
                logger.error("remove pv failed:%s" % Ret.stdout.decode('utf-8'))
        #check mountpoint
        Ret = sys_run("losetup /dev/loop0")
        if Ret.returncode == 0:
            logger.info("/dev/loop0 already exists, detach it")
            Ret = sys_run("losetup -d /dev/loop0")
            if Ret.returncode != 0:
                logger.error("losetup -d failed:%s" % Ret.stdout.decode('utf-8'))
        #check file_path
        if os.path.exists(file_path):
            logger.info(file_path + " for lvm group already exists, delete it")
            os.remove(file_path)
        if not os.path.isdir(file_path[:file_path.rindex("/")]):
            os.makedirs(file_path[:file_path.rindex("/")])
        sys_run("dd if=/dev/zero of=%s bs=1M seek=%s count=0" % (file_path,size))
        sys_run("losetup /dev/loop0 " + file_path)
        sys_run("vgcreate %s /dev/loop0" % group_name)
        logger.info("initialize lvm group:%s with size %sM success" % (group_name,size))
        return True
         
    elif storage == "disk":
        disk = env.getenv("DISK")
        if disk is None:
            logger.error("use disk for story without a physical disk")
            return False        
        #check vg
        Ret = sys_run("vgdisplay " + group_name)
        if Ret.returncode == 0:
            logger.info("lvm group: " + group_name + " already exists, delete it")
            Ret = sys_run("vgremove -f " + group_name)
            if Ret.returncode != 0:
                logger.error("delete VG %s failed:%s" % (group_name,Ret.stdout.decode('utf-8')))
        sys_run("vgcreate %s %s" % (group_name,disk))
        logger.info("initialize lvm group:%s with size %sM success" % (group_name,size))
        return True 
    
    else:
        logger.info("unknown storage type:" + storage)
        return False

def recover_group(group_name,file_path="/opt/docklet/local/docklet-storage"):
    storage = env.getenv("STORAGE")
    if storage == "file":
        if not os.path.exists(file_path):
            logger.error("%s not found, unable to recover VG" % file_path)
            return False
        #recover mountpoint
        Ret = sys_run("losetup /dev/loop0")
        if Ret.returncode != 0:
            Ret = sys_run("losetup /dev/loop0 " + file_path)
            if Ret.returncode != 0:
                logger.error("losetup failed:%s" % Ret.stdout.decode('utf-8'))
                return False
        time.sleep(1)
        #recover vg
        Ret = sys_run("vgdisplay " + group_name)
        if Ret.returncode != 0: 
            Ret = sys_run("vgcreate %s /dev/loop0" % group_name)
            if Ret.returncode != 0:
                logger.error("create VG %s failed:%s" % (group_name,Ret.stdout.decode('utf-8')))
                return False
        logger.info("recover VG %s success" % group_name)

    elif storage == "disk":
        disk = env.getenv("DISK")
        if disk is None:
            logger.error("use disk for story without a physical disk")
            return False        
        #recover vg
        Ret = sys_run("vgdisplay " + group_name)
        if Ret.returncode != 0: 
            Ret = sys_run("vgcreate %s %s" % (group_name,disk))
            if Ret.returncode != 0:
                logger.error("create VG %s failed:%s" % (group_name,Ret.stdout.decode('utf-8')))
                return False
        logger.info("recover VG %s success" % group_name)

def new_volume(group_name,volume_name,size):
    Ret = sys_run("lvdisplay %s/%s" % (group_name,volume_name))
    if Ret.returncode == 0:
        logger.info("logical volume already exists, delete it")
        Ret = sys_run("lvremove -f %s/%s" % (group_name,volume_name))
        if Ret.returncode != 0:
            logger.error("delete logical volume %s failed: %s" %
                    (volume_name, Ret.stdout.decode('utf-8')))
    Ret = sys_run("lvcreate -L %sM -n %s %s" % (size,volume_name,group_name))
    if Ret.returncode != 0:
        logger.error("lvcreate failed: %s" % Ret.stdout.decode('utf-8'))
        return False
    logger.info("create lv success")
    return True

def check_group(group_name):
    Ret = sys_run("vgdisplay %s" % group_name)
    if Ret.returncode == 0:
        return True
    else:
        return False

def check_volume(group_name,volume_name):
    Ret = sys_run("lvdisplay %s/%s" % (group_name,volume_name))
    if Ret.returncode == 0:
        return True
    else:
        return False

def delete_group(group_name):
    Ret = sys_run("vgdisplay %s" % group_name)
    if Ret.returncode == 0:
        Ret = sys_run("vgremove -f %s" % group_name)
        if Ret.returncode == 0:
            logger.info("delete vg %s success" % group_name)
            return True
        else:
            logger.error("delete vg %s failed:%s" % (group_name,Ret.stdout.decode('utf-8')))
            return False
    else:
        logger.info("vg %s does not exists" % group_name)
        return True

def delete_volume(group_name, volume_name):
    Ret = sys_run("lvdisplay %s/%s" % (group_name, volume_name))
    if Ret.returncode == 0:
        Ret = sys_run("lvremove -f %s/%s" % (group_name, volume_name))
        if Ret.returncode == 0:
            logger.info("delete lv %s in vg %s success" % (volume_name,group_name))
            return True
        else:
            logger.error("delete lv %s in vg %s failed:%s" % (volume_name,group_name,Ret.stdout.decode('utf-8')))
            return False
    else:
        logger.info("lv %s in vg %s does not exists" % (volume_name,group_name))
     
 
