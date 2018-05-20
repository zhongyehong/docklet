apt-get update

apt-get install -y git

git clone http://github.com/unias/docklet.git /home/docklet

/home/docklet/prepare.sh

cp /home/docklet/conf/docklet.conf.template /home/docklet/conf/docklet.conf
cp /home/docklet/web/templates/home.template /home/docklet/web/templates/home.html

NETWORK_DEVICE=`route | grep default | awk {'print $8'};`

echo "DISKPOOL_SIZE=200000
ETCD=%MASTERIP%:2379
NETWORK_DEVICE=$NETWORK_DEVICE
PROXY_PORT=8000
NGINX_PORT=80" >> /home/docklet/conf/docklet.conf

#please modify the mount command for your corresponding distributed file system if you are not using glusterfs
mount -t glusterfs %VOLUMENAME% /opt/docklet/global/

if [ -f /opt/docklet/global/packagefs.tgz ]; then
	tar zxvf /opt/docklet/global/packagefs.tgz -C /opt/docklet/local/ > /dev/null
fi

/home/docklet/bin/docklet-worker start
exit 0
