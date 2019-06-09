#!/usr/bin/python3

"""
design:
    1. When user create an image, it will upload to an image server, at the same time, local host
    will save an image. A time file will be made with them. Everytime a container start by this
    image, the time file will update.
    2. When user save an image, if it is a update option, it will faster than create a new image.
    3. At image server and every physical host, run a shell script to delete the image, which is
    out of time.
    4. We can show every user their own images and the images are shared by other. User can new a
    cluster or scale out a new node by them. And user can remove his own images.
    5. When a remove option occur, the image server will delete it. But some physical host may
    also maintain it. I think it doesn't matter.
    6. The manage of lvm has been including in this module.
"""


from configparser import ConfigParser
from io import StringIO
import os,sys,subprocess,time,re,datetime,threading,random
import xmlrpc.client
from utils.model import db, Image

from utils.log import logger
from utils import env, updatebase
from utils.lvmtool import *
import requests

master_port = str(env.getenv('MASTER_PORT'))

class ImageMgr():
    #def sys_call(self,command):
    #    output = subprocess.getoutput(command).strip()
    #    return None if output == '' else output

    def sys_return(self,command):
        return_value = subprocess.call(command,shell=True)
        return return_value

    def __init__(self):
        self.NFS_PREFIX = env.getenv('FS_PREFIX')
        self.imgpath = self.NFS_PREFIX + "/global/images/"
        self.srcpath = env.getenv('DOCKLET_LIB') + "/"
        self.imageserver = "192.168.6.249"
        self.layer_count = {}

    def datetime_toString(self,dt):
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def string_toDatetime(self,string):
        return datetime.datetime.strptime(string, "%Y-%m-%d %H:%M:%S")

    def updateinfo(self,user,imagename,description):
        '''image_info_file = open(imgpath+"."+image+".info",'w')
        image_info_file.writelines([self.datetime_toString(datetime.datetime.now()) + "\n", "unshare"])
        image_info_file.close()
        image_description_file = open(imgpath+"."+image+".description", 'w')
        image_description_file.write(description)
        image_description_file.close()'''
        image = Image.query.filter_by(ownername=user,imagename=imagename).first()
        if image is None:
            newimage = Image(imagename,True,False,user,description)
            db.session.add(newimage)
            db.session.commit()
        else:
            image.description = description
            image.create_time = datetime.datetime.now()
            db.session.commit()


    def dealpath(self,fspath):
        if fspath[-1:] == "/":
            return self.dealpath(fspath[:-1])
        else:
            return fspath

    def createImage(self,user,image, lxc, description="Not thing", imagenum=10):
        fspath = self.NFS_PREFIX + "/local/volume/" + lxc
        tmppath = self.NFS_PREFIX + "/local/imagetmp/" + lxc
        imagelayer = self.get_image_layer(lxc)
        imgpath = self.imgpath + "private/" + user + "/"
        #tmppath = self.NFS_PREFIX + "/local/tmpimg/"
        #tmpimage = str(random.randint(0,10000000)) + ".tz"

        if not os.path.exists(imgpath+image) and os.path.exists(imgpath):
            cur_imagenum = 0
            for filename in os.listdir(imgpath):
                if os.path.isdir(imgpath+filename):
                    cur_imagenum += 1
            if cur_imagenum >= int(imagenum):
                return [False,"image number limit exceeded"]
        #sys_run("mkdir -p %s" % tmppath, True)
        sys_run("mkdir -p %s" % imgpath,True)
        sys_run("mkdir -p %s" % tmppath,True)
        try:
            sys_run("mount -t aufs -o br=%s=rw:%s=ro+wh -o udba=reval none %s/" % (fspath, imagelayer, tmppath),True)
            sys_run("tar -cvf %s -C %s ." % (imgpath+image+".tz",self.dealpath(tmppath)), True)
            sys_run("umount %s" % tmppath, True)
            sys_run("rm -rf %s" % tmppath, True)
        except Exception as e:
            logger.error(e)
        #try:
            #sys_run("cp %s %s" % (tmppath+tmpimage, imgpath+image+".tz"), True)
            #sys_run("rsync -a --delete --exclude=lost+found/ --exclude=root/nfs/ --exclude=dev/ --exclude=mnt/ --exclude=tmp/ --exclude=media/ --exclude=proc/ --exclude=sys/ %s/ %s/" % (self.dealpath(fspath),imgpath+image),True)
        #except Exception as e:
        #    logger.error(e)
        #sys_run("rm -f %s" % tmppath+tmpimage, True)
        #sys_run("rm -f %s" % (imgpath+"."+image+"_docklet_share"),True)
        self.updateinfo(user,image,description)
        logger.info("image:%s from LXC:%s create success" % (image,lxc))
        return [True, "create image success"]

    def prepareImage(self,user,image):
        imagename = image['name']
        imagetype = image['type']
        imageowner = image['owner']
        #tmppath = self.NFS_PREFIX + "/local/tmpimg/"
        #tmpimage = str(random.randint(0,10000000)) + ".tz"
        if imagename == "base" and imagetype == "base":
            return self.NFS_PREFIX + "/local/imagelayer/empty"
        if imagetype == "private":
            imgpath = self.imgpath + "private/" + user + "/"
        else:
            imgpath = self.imgpath + "public/" + imageowner + "/"
        timestamp = self.get_image_timestamp(imageowner, imagename, imagetype)
        imagelayer = "%s/local/imagelayer/%s_%s_%s/%s" % (self.NFS_PREFIX, imagename, imagetype, imageowner, timestamp)
        if os.path.isdir(imagelayer):
            return imagelayer
        else: 
            os.makedirs(imagelayer)
        #try:
        #    sys_run("cp %s %s" % (imgpath+imagename+".tz", tmppath+tmpimage))
        #except Exception as e:
        #    logger.error(e)
        try:
            sys_run("tar -C %s -xvf %s" % (self.dealpath(imagelayer),imgpath+imagename+".tz"), True)
            #sys_run("rsync -a --delete --exclude=lost+found/ --exclude=root/nfs/ --exclude=dev/ --exclude=mnt/ --exclude=tmp/ --exclude=media/ --exclude=proc/ --exclude=sys/ %s/ %s/" % (imgpath+imagename,self.dealpath(fspath)),True)
        except Exception as e:
            logger.error(e)
        #sys_run("rm -f %s" % tmppath+tmpimage)

        #self.sys_call("rsync -a --delete --exclude=nfs/ %s/ %s/" % (imgpath+image,self.dealpath(fspath)))
        #self.updatetime(imgpath,image)
        return imagelayer

    def prepareFS(self,user,image,lxc,size="1000",vgname="docklet-group"):
        rootfs = "/var/lib/lxc/%s/rootfs" % lxc
        layer = self.NFS_PREFIX + "/local/volume/" + lxc
        #check mountpoint
        Ret = sys_run("mountpoint %s" % rootfs)
        if Ret.returncode == 0:
            logger.info("%s not clean" % rootfs)
            sys_run("umount -l %s" % rootfs)
        Ret = sys_run("mountpoint %s" % layer)
        if Ret.returncode == 0:
            logger.info("%s not clean" % layer)
            sys_run("umount -l %s" % layer)

        try:
            sys_run("rm -rf %s %s" % (rootfs, layer))
            sys_run("mkdir -p %s %s" % (rootfs, layer))
        except Exception as e:
            logger.error(e)


        #prepare volume
        if check_volume(vgname,lxc):
            logger.info("volume %s already exists, delete it")
            delete_volume(vgname,lxc)
        if not new_volume(vgname,lxc,size):
            logger.error("volume %s create failed" % lxc)
            return False

        try:
            sys_run("mkfs.ext4 /dev/%s/%s" % (vgname,lxc),True)
            sys_run("mount /dev/%s/%s %s" %(vgname,lxc,layer),True)
            #self.sys_call("mkdir -p %s/overlay %s/work" % (layer,layer))
            #self.sys_call("mount -t overlay overlay -olowerdir=%s/local/basefs,upperdir=%s/overlay,workdir=%s/work %s" % (self.NFS_PREFIX,layer,layer,rootfs))
            #self.prepareImage(user,image,layer+"/overlay")
            imagelayer = self.prepareImage(user,image)
            layerfile = self.NFS_PREFIX + "/local/volume/." + lxc + ".layer"
            with open(layerfile, 'w') as f:
                f.write(imagelayer)
            logger.debug(imagelayer)
            logger.info("image has been prepared")
            sys_run("mount -t aufs -o br=%s=rw:%s=ro+wh:%s/local/packagefs=ro+wh:%s/local/basefs=ro+wh -o udba=reval none %s/" % (layer,imagelayer,self.NFS_PREFIX,self.NFS_PREFIX,rootfs),True)
            if imagelayer in self.layer_count:
                self.layer_count[imagelayer] += 1
            else:
                self.layer_count[imagelayer] = 1
            sys_run("mkdir -m 777 -p %s/local/temp/%s" % (self.NFS_PREFIX,lxc))

        except Exception as e:
            logger.error(e)

        logger.info("FS has been prepared for user:%s lxc:%s" % (user,lxc))
        return True
    
    def get_image_layer(self, lxc):
        layerfile = self.NFS_PREFIX + "/local/volume/." + lxc + ".layer"
        with open(layerfile, 'r') as f:
            imagelayer = f.readline().strip()
        return imagelayer

    def deleteFS(self,lxc,vgname="docklet-group"):
        rootfs = "/var/lib/lxc/%s/rootfs" % lxc
        layer = self.NFS_PREFIX + "/local/volume/" + lxc
        layerfile = self.NFS_PREFIX + "/local/volume/." + lxc + ".layer"
        lxcpath = "/var/lib/lxc/%s" % lxc
        sys_run("lxc-stop -k -n %s" % lxc)
        #check mountpoint
        Ret = sys_run("mountpoint %s" % rootfs)
        if Ret.returncode == 0:
            sys_run("umount -l %s" % rootfs)
        Ret = sys_run("mountpoint %s" % layer)
        if Ret.returncode == 0:
            sys_run("umount -l %s" % layer)
        if check_volume(vgname, lxc):
            delete_volume(vgname, lxc)
        try:
            sys_run("rm -rf %s %s" % (layer,lxcpath))
            sys_run("rm -rf %s/local/temp/%s" % (self.NFS_PREFIX,lxc))
            imagelayer = self.get_image_layer(lxc)
            self.layer_count[imagelayer] -= 1
            if self.layer_count[imagelayer] == 0 and not imagelayer.endswith("empty"):
                del self.layer_count[imagelayer]
                sys_run("rm -rf %s" % imagelayer)
            sys_run("rm %s" % (layerfile))
        except Exception as e:
            logger.error(e)

        return True

    def detachFS(self, lxc, vgname="docklet-group"):
        rootfs = "/var/lib/lxc/%s/rootfs" % lxc
        Ret = sys_run("umount %s" % rootfs)
        if Ret.returncode != 0:
            logger.error("cannot umount rootfs:%s" % rootfs)
            return False
        return True

    def checkFS(self, lxc, vgname="docklet-group"):
        rootfs = "/var/lib/lxc/%s/rootfs" % lxc
        layer = self.NFS_PREFIX + "/local/volume/" + lxc
        if not os.path.isdir(layer):
            sys_run("mkdir -p %s" % layer)
        #check mountpoint
        Ret = sys_run("mountpoint %s" % layer)
        if Ret.returncode != 0:
            sys_run("mount /dev/%s/%s %s" % (vgname,lxc,layer))
        Ret = sys_run("mountpoint %s" % rootfs)
        imagelayer = self.get_image_layer(lxc)
        if Ret.returncode != 0:
            sys_run("mount -t aufs -o br=%s=rw:%s=ro+wh:%s/local/packagefs=ro+wh:%s/local/basefs=ro+wh -o udba=reval none %s/" % (layer, imagelayer, self.NFS_PREFIX,self.NFS_PREFIX,rootfs))
        if imagelayer in self.layer_count:
            self.layer_count[imagelayer] += 1
        else:
            self.layer_count[imagelayer] = 1
        return True


    def removeImage(self,user,imagename):
        imgpath = self.imgpath + "private/" + user + "/"
        try:
            image = Image.query.filter_by(imagename=imagename,ownername=user).first()
            image.hasPrivate = False
            if image.hasPublic == False:
                db.session.delete(image)
            db.session.commit()
            sys_run("rm -rf %s/" % imgpath+imagename+".tz", True)
            #sys_run("rm -f %s" % imgpath+"."+image+".info", True)
            #sys_run("rm -f %s" % (imgpath+"."+image+".description"), True)
        except Exception as e:
            logger.error(e)

    def shareImage(self,user,imagename):
        imgpath = self.imgpath + "private/" + user + "/"
        share_imgpath = self.imgpath + "public/" + user + "/"
        '''image_info_file = open(imgpath+"."+image+".info", 'r')
        [createtime, isshare] = image_info_file.readlines()
        isshare = "shared"
        image_info_file.close()
        image_info_file = open(imgpath+"."+image+".info", 'w')
        image_info_file.writelines([createtime, isshare])
        image_info_file.close()'''
        try:
            image = Image.query.filter_by(imagename=imagename,ownername=user).first()
            if image.hasPublic == True:
                return
            image.hasPublic = True
            db.session.commit()
            sys_run("mkdir -p %s" % share_imgpath, True)
            sys_run("cp %s %s" % (imgpath+imagename+".tz", share_imgpath+imagename+".tz"), True)
            #sys_run("rsync -a --delete %s/ %s/" % (imgpath+image,share_imgpath+image), True)
        except Exception as e:
            logger.error(e)
        #$sys_run("cp %s %s" % (imgpath+"."+image+".info",share_imgpath+"."+image+".info"), True)
        #sys_run("cp %s %s" % (imgpath+"."+image+".description",share_imgpath+"."+image+".description"), True)



    def unshareImage(self,user,imagename):
        public_imgpath = self.imgpath + "public/" + user + "/"
        imgpath = self.imgpath + "private/" + user + "/"
        '''if os.path.isfile(imgpath + image + ".tz"):
            image_info_file = open(imgpath+"."+image+".info", 'r')
            [createtime, isshare] = image_info_file.readlines()
            isshare = "unshare"
            image_info_file.close()
            image_info_file = open(imgpath+"."+image+".info", 'w')
            image_info_file.writelines([createtime, isshare])
            image_info_file.close()'''
        try:
            #sys_run("rm -rf %s/" % public_imgpath+image, True)
            image = Image.query.filter_by(imagename=imagename,ownername=user).first()
            image.hasPublic = False
            if image.hasPrivate == False:
                db.session.delete(image)
            db.session.commit()
            sys_run("rm -f %s" % public_imgpath+imagename+".tz", True)
            #sys_run("rm -f %s" % public_imgpath+"."+image+".info", True)
            #sys_run("rm -f %s" % public_imgpath+"."+image+".description", True)
        except Exception as e:
            logger.error(e)

    def copyImage(self,user,image,token,target):
        path = "/opt/docklet/global/images/private/"+user+"/"
        '''image_info_file = open(path+"."+image+".info", 'r')
        [createtime, isshare] = image_info_file.readlines()
        recordshare = isshare
        isshare = "unshared"
        image_info_file.close()
        image_info_file = open(path+"."+image+".info", 'w')
        image_info_file.writelines([createtime, isshare])
        image_info_file.close()'''
        try:
            sys_run('ssh root@%s "mkdir -p %s"' % (target,path))
            sys_run('scp %s%s.tz root@%s:%s' % (path,image,target,path))
            #sys_run('scp %s.%s.description root@%s:%s' % (path,image,target,path))
            #sys_run('scp %s.%s.info root@%s:%s' % (path,image,target,path))
            resimage = Image.query.filter_by(ownername=user,imagename=image).first()
            auth_key = env.getenv('AUTH_KEY')
            url = "http://" + target + ":" + master_port + "/image/copytarget/"
            data = {"token":token,"auth_key":auth_key,"user":user,"imagename":image,"description":resimage.description}
            result = requests.post(url, data=data).json()
            logger.info("Response from target master: " + str(result))
        except Exception as e:
            logger.error(e)
            '''image_info_file = open(path+"."+image+".info", 'w')
            image_info_file.writelines([createtime, recordshare])
            image_info_file.close()'''
            return {'success':'false', 'message':str(e)}
        '''image_info_file = open(path+"."+image+".info", 'w')
        image_info_file.writelines([createtime, recordshare])
        image_info_file.close()'''
        logger.info("copy image %s of %s to %s success" % (image,user,target))
        return {'success':'true', 'action':'copy image'}

    def update_basefs(self,imagename):
        imgpath = self.imgpath + "private/root/"
        basefs = self.NFS_PREFIX+"/local/packagefs/"
        tmppath = self.NFS_PREFIX + "/local/tmpimg/"
        tmpimage = str(random.randint(0,10000000))
        try:
            sys_run("mkdir -p %s" % tmppath+tmpimage)
            sys_run("tar -C %s -xvf %s" % (tmppath+tmpimage,imgpath+imagename+".tz"),True)
            logger.info("start updating base image")
            updatebase.aufs_update_base(tmppath+tmpimage, basefs)
            logger.info("update base image success")
        except Exception as e:
            logger.error(e)
        sys_run("rm -rf %s" % tmppath+tmpimage)
        return True

    def update_base_image(self, user, vclustermgr, image):
        if not user == "root":
            logger.info("only root can update base image")
        #vclustermgr.stop_allclusters()
        #vclustermgr.detach_allclusters()
        workers = vclustermgr.nodemgr.get_nodeips()
        logger.info("update base image in all workers")
        for worker in workers:
            workerrpc = vclustermgr.nodemgr.ip_to_rpc(worker)
            workerrpc.update_basefs(image)
        logger.info("update base image success")
        #vclustermgr.mount_allclusters()
        #logger.info("mount all cluster success")
        #vclustermgr.recover_allclusters()
        #logger.info("recover all cluster success")
        return [True, "update base image"]

    def get_image_info(self, user, imagename, imagetype):
        '''if imagetype == "private":
            imgpath = self.imgpath + "private/" + user + "/"
        else:
            imgpath = self.imgpath + "public/" + user + "/"
        image_info_file = open(imgpath+"."+image+".info",'r')
        time = image_info_file.readline()
        image_info_file.close()
        image_description_file = open(imgpath+"."+image+".description",'r')
        description = image_description_file.read()
        image_description_file.close()'''
        image = Image.query.filter_by(imagename=imagename,ownername=user).first()
        if image is None:
            return ["", ""]
        time = image.create_time.strftime("%Y-%m-%d %H:%M:%S")
        description = image.description
        if len(description) > 15:
            description = description[:15] + "......"
        return [time, description]
    
    def get_image_timestamp(self, user, imagename, imagetype):
        image = Image.query.filter_by(imagename=imagename,ownername=user).first()
        return image.create_time.strftime("%Y%m%d%H%M%S")

    def get_image_description(self, user, image):
        '''if image['type'] == "private":
            imgpath = self.imgpath + "private/" + user + "/"
        else:
            imgpath = self.imgpath + "public/" + image['owner'] + "/"
        image_description_file = open(imgpath+"."+image['name']+".description", 'r')
        description = image_description_file.read()
        image_description_file.close()'''
        image = Image.query.filter_by(imagename=image['name'],ownername=image['owner']).first()
        if image is None:
            return ""
        return image.description


    def get_image_size(self, image):
        imagename = image['name']
        imagetype = image['type']
        imageowner = image['owner']
        if imagename == "base" and imagetype == "base":
            return 0
        if imagetype == "private":
            imgpath = self.imgpath + "private/" + imageowner + "/"
        else:
            imgpath = self.imgpath + "public/" + imageowner + "/"
        return os.stat(os.path.join(imgpath, imagename+".tz")).st_size // (1024*1024)


    def format_size(self, size_in_byte):
        if size_in_byte < 1024:
            return str(size_in_byte) + "B"
        elif size_in_byte < 1024*1024:
            return str(size_in_byte//1024) + "KB"
        elif size_in_byte < 1024*1024*1024:
            return str(size_in_byte//(1024*1024)) + "MB"
        else:
            return str(size_in_byte//(1024*1024*1024)) + "GB"

    def list_images(self,user):
        images = {}
        images["private"] = []
        images["public"] = {}
        imgpath = self.imgpath + "private/" + user + "/"
        try:
            Ret = sys_run("ls %s" % imgpath, True)
            private_images = str(Ret.stdout,"utf-8").split()
            for image in private_images:
                if not image[-3:] == '.tz':
                    continue
                imagename = image[:-3]
                fimage={}
                fimage["name"] = imagename
                fimage["isshared"] = self.isshared(user,imagename)
                [time, description] = self.get_image_info(user, imagename, "private")
                fimage["time"] = time
                fimage["description"] = description
                fimage["size"] = os.stat(os.path.join(imgpath, image)).st_size
                fimage["size_format"] = self.format_size(fimage["size"])
                fimage["size_in_mb"] = fimage["size"] // (1024*1024)
                images["private"].append(fimage)
        except Exception as e:
            logger.error(e)

        imgpath = self.imgpath + "public" + "/"
        try:
            Ret = sys_run("ls %s" % imgpath, True)
            public_users = str(Ret.stdout,"utf-8").split()
            for public_user in public_users:
                imgpath = self.imgpath + "public/" + public_user + "/"
                try:
                    Ret = sys_run("ls %s" % imgpath, True)
                    public_images = str(Ret.stdout,"utf-8").split()
                    if len(public_images)==0:
                        continue
                    images["public"][public_user] = []
                    for image in public_images:
                        if not image[-3:] == '.tz':
                            continue
                        imagename = image[:-3]
                        fimage = {}
                        fimage["name"] = imagename
                        [time, description] = self.get_image_info(public_user, imagename, "public")
                        fimage["time"] = time
                        fimage["description"] = description
                        fimage["size"] = os.stat(os.path.join(imgpath, image)).st_size
                        fimage["size_format"] = self.format_size(fimage["size"])
                        fimage["size_in_mb"] = fimage["size"] // (1024*1024)
                        images["public"][public_user].append(fimage)
                except Exception as e:
                    logger.error(e)
        except Exception as e:
            logger.error(e)

        return images

    def isshared(self,user,imagename):
        '''imgpath = self.imgpath + "private/" + user + "/"
        image_info_file = open(imgpath+"."+image+".info",'r')
        [time, isshare] = image_info_file.readlines()
        image_info_file.close()'''
        image = Image.query.filter_by(imagename=imagename,ownername=user).first()
        if image is None:
            return ""
        if image.hasPublic == True:
            return "true"
        else:
            return "false"

if __name__ == '__main__':
    mgr = ImageMgr()
    if sys.argv[1] == "prepareImage":
        mgr.prepareImage(sys.argv[2],sys.argv[3],sys.argv[4])
    elif sys.argv[1] == "create":
        mgr.createImage(sys.argv[2],sys.argv[3],sys.argv[4])
    else:
        logger.warning("unknown option")
