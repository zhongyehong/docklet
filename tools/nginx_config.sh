#!/bin/sh

MASTER_IP=0.0.0.0
NGINX_PORT=8080
PROXY_PORT=8000
WEB_PORT=8888
NGINX_CONF=/etc/nginx
DOCKLET_CONF=../conf

. $DOCKLET_CONF/docklet.conf

NGINX_CONF=${NGINX_CONF}/sites-enabled

echo "copy nginx_docklet.conf to nginx config path..."
cp ../conf/nginx_docklet.conf ${NGINX_CONF}/
sed -i "s/%MASTER_IP/${MASTER_IP}/g" ${NGINX_CONF}/nginx_docklet.conf
sed -i "s/%NGINX_PORT/${NGINX_PORT}/g" ${NGINX_CONF}/nginx_docklet.conf
if [ "${DISTRIBUTED_GATEWAY}" = "True" ]
then
  sed -i "s/%PROXY_SERVER_IP/\$1/g" ${NGINX_CONF}/nginx_docklet.conf
else
  sed -i "s/%PROXY_SERVER_IP/${MASTER_IP}/g" ${NGINX_CONF}/nginx_docklet.conf
fi

sed -i "s/%PROXY_PORT/${PROXY_PORT}/g" ${NGINX_CONF}/nginx_docklet.conf
sed -i "s/%WEB_PORT/${WEB_PORT}/g" ${NGINX_CONF}/nginx_docklet.conf

echo "restart nginx..."
/etc/init.d/nginx restart
