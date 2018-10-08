import abc
import subprocess, os
from utils.log import logger

class OssMounter(object):
    __metaclass__ = abc.ABCMeta

    @staticmethod
    def execute_cmd(cmd):
        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        if ret.returncode != 0:
            msg = ret.stdout.decode(encoding="utf-8")
            logger.error(msg)
            return [False,msg]
        else:
            return [True,""]

    @staticmethod
    @abc.abstractmethod
    def mount_oss(datapath, mount_info):
        # mount oss
        pass

    @staticmethod
    @abc.abstractmethod
    def umount_oss(datapath, mount_info):
        # umount oss
        pass

class aliyunOssMounter(OssMounter):

    @staticmethod
    def mount_oss(datapath, mount_info):
        # mount oss
        try:
            pwdfile = open("/etc/passwd-ossfs","w")
            pwdfile.write(mount_info.remotePath+":"+mount_info.accessKey+":"+mount_info.secretKey+"\n")
            pwdfile.close()
        except Exception as err:
            logger.error(traceback.format_exc())
            return [False,msg]

        cmd = "chmod 640 /etc/passwd-ossfs"
        [success1, msg] = OssMounter.execute_cmd(cmd)
        mountpath = datapath+"/"+mount_info.remotePath
        logger.info("Mount oss %s %s" % (mount_info.remotePath, mountpath))
        if not os.path.isdir(mountpath):
            os.makedirs(mountpath)
        cmd = "ossfs %s %s -ourl=%s" % (mount_info.remotePath, mountpath, mount_info.endpoint)
        [success, msg] = OssMounter.execute_cmd(cmd)
        return [True,""]

    @staticmethod
    def umount_oss(datapath, mount_info):
        mountpath = datapath + "/" + mount_info.remotePath
        logger.info("UMount oss %s %s" % (mount_info.remotePath, mountpath))
        cmd = "fusermount -u %s" % (mountpath)
        [success, msg] = self.execute_cmd(cmd)
        [success, msg] = self.execute_cmd("rm -rf %s" % mountpath)
        return [True,""]
