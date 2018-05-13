#配置apt源
#echo "deb http://mirrors.ustc.edu.cn/ubuntu/ xenial main restricted universe multiverse
#deb http://mirrors.ustc.edu.cn/ubuntu/ xenial-security main restricted universe multiverse
#deb http://mirrors.ustc.edu.cn/ubuntu/ xenial-updates main restricted universe multiverse
#deb http://mirrors.ustc.edu.cn/ubuntu/ xenial-proposed main restricted universe multiverse
#deb http://mirrors.ustc.edu.cn/ubuntu/ xenial-backports main restricted universe multiverse" > /etc/apt/sources.list

#更新apt
apt-get update


#下载git包
apt-get install -y git

#下载docklet源码
git clone http://github.com/unias/docklet.git /home/docklet

#运行prepare.sh
sed -i '61s/^/#&/g' /home/docklet/prepare.sh
sed -i '62s/^/#&/g' /home/docklet/prepare.sh
/home/docklet/prepare.sh

#挂载global目录,通过gluster方式
#mount -t glusterfs docklet-master:/docklet /opt/docklet/global

#下载base镜像
#wget http://docklet.unias.org/images/basefs-0.11.tar.bz2 -P /opt/local/temp

#解压镜像
#mkdir -p /opt/docklet/local
#mkdir -p /opt/docklet/global
#tar -jxvf /root/basefs-0.11.tar.bz2 -C /opt/docklet/local/

#获得docklet.conf
cp /home/docklet/conf/docklet.conf.template /home/docklet/conf/docklet.conf
cp /home/docklet/web/templates/home.template /home/docklet/web/templates/home.html

#获得网卡名称
NETWORK_DEVICE=`route | grep default | awk {'print $8'};`

#更改配置文件
echo "DISKPOOL_SIZE=20000
ETCD=%MASTERIP%:2379
NETWORK_DEVICE=$NETWORK_DEVICE
PROXY_PORT=8000
NGINX_PORT=80" >> /home/docklet/conf/docklet.conf

#启动worker
#/home/docklet/bin/docklet-supermaster init
#/home/docklet/bin/docklet-worker start
exit 0
