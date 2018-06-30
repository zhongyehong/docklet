#!/bin/bash

if [[ "`whoami`" != "root" ]]; then
	echo "FAILED: Require root previledge !" > /dev/stderr
	exit 1
fi

pip3 install aliyun-python-sdk-core-v3
pip3 install aliyun-python-sdk-ecs

exit 0
