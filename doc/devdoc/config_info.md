# Info of docklet

## container info
    container name : username-clusterid-nodeid
    hostname : host-nodeid  
    lxc config : /var/lib/lxc/username-clusterid-nodeid/config
    lxc rootfs : /var/lib/lxc/username-clusterid-nodeid/rootfs
    lxc rootfs
          |__ / : aufs : basefs + volume/username-clusterid-nodeid
	      |__ /nfs : global/users/username/data
	      |__ /etc/hosts : global/users/username/clusters/clusterid/hosts
	      |__ /root/.ssh : global/users/username/ssh


## ETCD Table
we use etcd for some configuration information of our clusters, here is some details.

every cluster has a CLUSTER_NAME and all data of this cluster is put in a directory called CLUSTER_NAME in etcd just like a table.

so, different cluster should has different CLUSTER_NAME.

below is content of cluster info in CLUSTER_NAME 'table' in etcd:

    <type>		<name>		<content>		<description>   
    key    token             random code    token for checking whether master and workers has the same global filesystem

    dir    machines            ...        info of physical clusters
    dir    machines/allnodes  ip:ok       record all nodes, for recovery and checks  
    dir    machines/runnodes  ip: ?       record running node for this start up.
                                      when startup:          ETCD
									                   |   IP:waiting    |   1. worker write worker-ip:waiting
                   2. master update IP:init-mode       |   IP:init-mode  |   3. worker init itself by init-mode
									                   |   IP:work       |   4. worker finish init and update IP:work
               5. master add workerip and update IP:ok |   IP:ok         |

    key    service/master   master-ip
    key    service/mode     new,recovery  start mode of cluster

    key    vcluster/nextid  ID            next available ID



## filesystem
here is the path and content description of docklet filesystem

    FS_PREFIX
      |__ global/users/{username}
      |                  |__ clusters/clustername : clusterid, cluster size, status, containers, ...  in json format
      |                  |__ hosts/id.hosts : ip  host-nodeid  host-nodeid.clustername
      |                  |__ data : direcroty in distributed filesystem for user to put his data
      |                  |__ ssh  : ssh keys
      |
      |__ local
            |__ docklet-storage : loop file for lvm
	        |__ basefs : base image
	        |__ volume / { username-clusterid-nodeid } : upper layer of container



## vcluster files

### hosts file:(raw)
    IP-0  host-0  host-0.clustername
    IP-1  host-1  host-1.clustername
    ...

### info file:(json)
    {
	    clusterid: ID ,
	    status: stopped/running ,
    	size: size ,
	    containers: [
	    	{ containername: lxc_name, hostname: hostname, ip: lxc_ip, host: host_ip },
	    	{ containername: lxc_name, hostname: hostname, ip: lxc_ip, host: host_ip },
	    	...
							]
    }  
