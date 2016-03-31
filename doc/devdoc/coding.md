# NOTE

## here is some thinking and notes in coding

* path : scripts' path should be known by scripts to call/import other script -- use environment variables

* FS_PREFIX : docklet filesystem path to put data

* overlay : " modprobe overlay " to add overlay module

* after reboot :
    * bridges lost -- it's ok, recreate it
    * loop device lost -- losetup /dev/loop0 BLOCK_FILE again, and lvm will get group and volume back automatically

* lvm can do snapshot, image management can use lvm's snapshot -- No! lvm snapshot will use the capacity of LVM group.

* cgroup memory control maybe not work. need run command below:
        echo 'GRUB_CMDLINE_LINUX="cgroup_enable=memory swapaccount=1"' >> /etc/default/grub && update-grub && reboot

* debian don't support cpu.cfs_quota_us option in cgroup. it needs to recompile linux kernel with CONFIG_CFS_BANDWIDTH option

* ip can add bridge/link/GRE, maybe we should test whether ip can replace of ovs-vsctl and brctl. ( see "man ip-link" )

* lxc.mount.entry :
	* do not use relevant path. use absolute path, like :
			lxc.mount.entry = /root/from-dir /root/rootfs/to-dir none bind 0 0         # lxc.rootfs = /root/rootfs
		if use relevant paht, container path will be mounted on /usr/lib/x86_64..../ , a not existed path
	* path of host and container should both exist. if not exist in container, it will be mounted on /usr/lib/x86_64....
	* if path in container not exists, you can use option : create=dir/file, like :
			lxc.mount.entry = /root/from-dir /root/rootfs/to-dir none bind,create=dir 0 0  # lxc.rootfs = /root/rootfs

* lxc.mount.entry : bind and rbind ( see "man mount" )
	* bind means mount a part of filesystem on somewhere else of this filesystem
	* but bind only attachs a single filesystem. That means the submount of source directory of mount may disappear in target directory.
	* if you want to make submount work, use rbind option.
	rbind will make entire file hierarchy including submounts mounted on another place.
	* NOW, we use bind in container.sh. maybe it need rbind if FS_PREFIX/global/users/$USERNAME/nfs is under glusterfs mountpoint  

* rpc server maybe not security. anyone can call rpc method if he knows ip address.
    * maybe we can use "transport" option of xmlrpc.client.ServerProxy(uri,       transport="http://user:pass@host:port/path") and SimpleXMLRPCRequestHandler of xmlrpc.server.SimpleXMLRPCServer(addr, requestHandler=..) to parse the rpc request and authenticate the request
 xmlrpc.client.ServerProxy can also support https request, it is also a security method
	* If we use rpc with authentication, maybe we can use http server and http request to replace rpc

* frontend and backend
        arch:
                          +-----------------+
        Web -- Flask --HttpRest   Core	    |
	                      +-----------------+
	Now, HttpRest and Core work as backend
	Web and Flask work as frontend
	all modules are in backend
	Flask just dispatch urls and render web pages
	(Maybe Flask can be merged in Core and works as http server)
	(Then Flask needs to render pages, parse urls, response requests, ...)
	(It maybe not fine)

* httprest.py :
	httphandler needs to call vclustermgr/nodemgr/... to handler request
	we need to call these classes in httphandler
	Way-1: init/new these classes in httphandler init function (httphandler need to init parent class) -- wrong : httpserver will create a new httphandler instance for every http request ( see /usr/lib/python3.4/socketserver.py )
	Way-2: use global varibles -- Now this way

* in shell, run python script or other not built-in command, the command will run in new process and new process group ( see csapp shell lab )
	so, the environment variables set in shell can not be see in python/...
	but command like below can work :  
			A=ab B=ba ./python.py

* maybe we need to parse argvs in python
	some module to parse argvs : sys.argv, optparse, getopt, argparse

* in shell, { command; } means run command in current shell, ";" is necessary
	( command; ) means run command in sub shell

* function in registered in rpc server must have return.
	without return, the rpc client will raise an exception

*	** NEED TO BE FIX **
	we add a prefix in etcdlib
	so when we getkey, key may be a absolute path from base url
	when we setkey use the key we get, etcdlib will append the absolute path to prefix, it will wrong

* overlay : upperdir and workdir must in the same mount filesystem.
	that means we should mount LV first and then mkdir upperdir and workdir in the LV mountpoint

* when use 'worker.py > log' to redirect output of python script, it will empty output of log.
	because python interpreter will use buffer to collect output.
	we can use ways below to fix this problem:
		stdbuf -o 0 worker.py > log  # but it fail in my try. don't know why
		python3 -u worker.py > log # recommended, -u option of python3
		print('output', flush=True) # flush option of print
		sys.stdout.flush() # flush by hand

* CPU QUOTA should not be too small. too small it will work so slowly
