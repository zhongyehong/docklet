# Some Note for configurable-http-proxy usage

## intsall
    sudo apt-get install nodejs nodejs-legacy npm
    sudo npm install -g configurable-http-proxy

## start
    configurable-http-proxy -h  : for help
    configurable-http-proxy --ip IP \
					    	--port PORT \
					     	--api-ip IP \
					    	--api-port PORT \
					    	--default-target http://IP:PORT \
					    	--log-level debug/info/warn/error
default ip:port is 0.0.0.0:8000,
default api-ip:api-port is localhost:8001

## control route table
### get route table
* without token:
    	curl http://localhost:8001/api/routes
* with token:
     	curl -H "Authorization: token TOKEN" http://localhost:8001/api/routes
### add/set route table
* without token:
    	curl -XPOST --data '{"target":"http://TARGET-IP:TARGET-PORT"}' http://localhost:8001/api/routes/PROXY-URL
* with token:
    	curl -H "Authorization: token TOKEN" -XPOST --data '{"target":"http://TARGET-IP:TARGET-PORT"}' http://localhost:8001/api/routes/PROXY-URL
### delete route table line
* without token:
    	curl -XDELETE http://localhost:8001/api/routes/PROXY-URL
* with token:
    	curl -H "Authorization: token TOKEN" -XDELETE http://localhost:8001/api/routes/PROXY-URL
