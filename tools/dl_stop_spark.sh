#!/bin/sh

# a naive script to stop spark cluster, assuming host-0 master
# others slaves
# used with dl_start_spark.sh

SPARK_HOME=/home/spark

HOSTS=`grep -v localhost /etc/hosts | awk '{print $2}'`

for h in $HOSTS ; do
    echo "Stopping slave in $h"
    if [ $h  != 'host-0' ] ; then
        ssh root@$h /home/spark/sbin/stop-slave.sh
    else
        /home/spark/sbin/stop-slave.sh 
    fi
done

echo "Stopping master in host-0"

$SPARK_HOME/sbin/stop-master.sh

