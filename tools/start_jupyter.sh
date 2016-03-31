#!/bin/sh 

#
# this script should be placed in basefs/home/jupyter
# 

# This next line determines what user the script runs as.
DAEMON_USER=root

# settings for docklet worker
DAEMON=/usr/local/bin/jupyterhub-singleuser
DAEMON_NAME=jupyter
# The process ID of the script when it runs is stored here:
PIDFILE=/home/jupyter/$DAEMON_NAME.pid

RUN_DIR=/root

#export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games

#export HOME=/home

#export SHELL=/bin/bash

#export LOGNAME=root

# JPY_API_TOKEN is needed by jupyterhub-singleuser
# it will send this token in request header to hub-api-url for authorization
# but we don't use this by now
export JPY_API_TOKEN=not-use

# user for this notebook
USER=root
# port to start service
PORT=10000
# cookie name to get from http request and send to hub_api_url for authorization
COOKIE_NAME=docklet-jupyter-cookie
# base url of this server. client will use this url for request
BASE_URL=/workspace/$USER
# prefix for login and logout
HUB_PREFIX=/jupyter
# URL for authorising cookie
HUB_API_URL=http://192.168.192.64:9000/jupyter
# IP for listening request
IP=0.0.0.0

[ -f /home/jupyter/jupyter.config ] && . /home/jupyter/jupyter.config

[ -z $IP ] && IP=$(ip address show dev eth0 | grep -P -o '10\.[0-9]*\.[0-9]*\.[0-9]*(?=/)')

DAEMON_OPTS="--no-browser --user=$USER --port=$PORT --cookie-name=$COOKIE_NAME --base-url=$BASE_URL --hub-prefix=$HUB_PREFIX --hub-api-url=$HUB_API_URL --ip=$IP --debug"

. /lib/lsb/init-functions

###########

start-stop-daemon --start --oknodo --background -d $RUN_DIR --pidfile $PIDFILE --make-pidfile --user $DAEMON_USER --chuid $DAEMON_USER --startas $DAEMON -- $DAEMON_OPTS
