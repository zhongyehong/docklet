#!/bin/sh

toolsdir=${0%/*}
DOCKLET_TOOLS=$(cd $toolsdir; pwd)
DOCKLET_HOME=${DOCKLET_TOOLS%/*}
DOCKLET_CONF=$DOCKLET_HOME/conf

. $DOCKLET_CONF/docklet.conf

masterip=$(ifconfig ${NETWORK_DEVICE} | awk '/inet/ {print $2}' | awk -F: '{print $2}' | head -1)
cons=$(ls /var/lib/lxc)

echo ${masterip}
for i in ${cons}
do
    sed -i "s/BASE_URL=\/go/BASE_URL=\/${masterip}\/go/g" /var/lib/lxc/${i}/rootfs/home/jupyter/jupyter.config
    running=$(lxc-info -n ${i} | grep RUNNING)
    if [ "${running}" != '' ]
    then
        echo "Stop ${i}..."
        lxc-stop -k -n ${i}
        echo "Start ${i}..."
        lxc-start -n ${i}
        lxc-attach -n ${i} -- su -c /home/jupyter/start_jupyter.sh
        lxc-attach -n ${i} -- service ssh start
    fi
done
