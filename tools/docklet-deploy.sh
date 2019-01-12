apt-get update

apt-get install -y git

git clone http://github.com/unias/docklet.git /home/docklet

NETWORK_DEVICE=`route | grep default | awk {'print $8'};`

echo "DISKPOOL_SIZE=%DISKSIZE%
ETCD=%MASTERIP%:2379
NETWORK_DEVICE=$NETWORK_DEVICE
PROXY_PORT=8000
NGINX_PORT=80" >> /home/docklet/conf/docklet.conf

echo "%MASTERIP% master" >> /etc/hosts

#please modify the mount command for your corresponding distributed file system if you are not using glusterfs
mount -t glusterfs master:%VOLUMENAME% /opt/docklet/global/

/home/docklet/bin/docklet-worker start
exit 0
