#!/bin/sh

# a naive script to fast start spark cluster, assuming host-0 master,
# others slaves.
# used with dl_stop_spark.sh

SPARK_HOME=/home/spark

HOSTS=`grep -v localhost /etc/hosts | awk '{print $2}'`

echo "Starting master in host-0"

$SPARK_HOME/sbin/start-master.sh

for h in $HOSTS ; do
    echo "Starting slave in $h"
    if [ $h  != 'host-0' ] ; then
        ssh root@$h /home/spark/sbin/start-slave.sh spark://host-0:7077
    else
        /home/spark/sbin/start-slave.sh spark://host-0:7077
    fi
done
