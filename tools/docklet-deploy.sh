if [ $# -lt 1 ]; then
    echo "please input master ip";
    exit 1;
fi
MASTER_IP=$1

#配置apt源
#echo "deb http://mirrors.ustc.edu.cn/ubuntu/ xenial main restricted universe multiverse
#deb http://mirrors.ustc.edu.cn/ubuntu/ xenial-security main restricted universe multiverse
#deb http://mirrors.ustc.edu.cn/ubuntu/ xenial-updates main restricted universe multiverse
#deb http://mirrors.ustc.edu.cn/ubuntu/ xenial-proposed main restricted universe multiverse
#deb http://mirrors.ustc.edu.cn/ubuntu/ xenial-backports main restricted universe multiverse" > /etc/apt/sources.list

#更新apt
apt-get update

#更新hosts
echo "$MASTER_IP docklet-master" >> /etc/hosts

#下载git包
apt-get install git

#下载docklet源码
git clone http://github.com/unias/docklet.git /home/docklet

#运行prepare.sh
/home/docklet/prepare.sh

#挂载global目录,通过gluster方式
mount -t glusterfs docklet-master:/docklet /opt/docklet/global

#下载base镜像
wget http://docklet.unias.org/images/basefs-0.11.tar.bz2 -P /opt/local/temp

#解压镜像
tar -zxvf /opt/local/temp/basefs-0.11.tar.bz2 -C /opt/local/

#获得docklet.conf
cp /home/docklet/conf/docklet.conf.template /home/docklet/conf/docklet.conf

#获得网卡名称
NETWORK_DEVICE=`route | grep default | awk {'print $8'};`

#更改配置文件
echo "DISKPOOL_SIZE=100000
ETCD=$MASTER_IP:2379
NETWORK_DEVICE=$NETWORK_DEVICE
PORTAL_URL=http://iwork.pku.edu.cn
PROXY_PORT=80" >> /home/docklet/conf/docklet.conf

#启动worker
/home/docklet/bin/docklet-worker start
exit 0
