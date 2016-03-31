# startup mode

## new mode
#### step 1 : data
           <Master>
    clean etcd table
    write token
    init etcd table
    clean global directory of user clusters
#### step 2 : nodemgr
           <Master>                                         <Slave>
    init network                                 
    wait for all nodes starts            
         |_____ listen node joins     IP:waiting  <---    worker starts
	            update etcd   ---->  IP:init-mode --->   worker init
			                                                  |____ stop all containers
				    										  |____ umount mountpoint, delete lxc files, delete LV
					    									  |____ delete VG, umount loop dev, delete loop file
						    								  |____ init loop file, loop dev, create VG
    			add node to list <--- IP:work      <----  init done, begin work
    check all nodes begin work
#### step 3 : vclustermgr
    Nothing to do




## recovery mode
#### step 1 : data
           <Master>
    write token
    init some of etcd table
#### step 2 : nodemgr
           <Master>                                         <Slave>
    init network                                 
    wait for all nodes starts            
          |_____ listen node joins     IP:waiting  <---    worker starts
	             update etcd   ---->  IP:init-mode --->   worker init
			                                                  |____ check loop file, loop dev, VG
				    										  |____ check all containers and mountpoint
			     add node to list <--- IP:work      <----  init done, begin work
    check all nodes begin work
#### step 3 : vclustermgr
           <Master>                                        <Slave>
    recover vclusters:some need start  --------------->   recover containers: some need start
