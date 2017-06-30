# Architecture of Network

## Architecture of containers networks
In current version, to avoid VLAN ID using up, docklet employs a new architecture of containers networks. According to the new architecture, users' networks are exclusive, while the network were shared by all users before. And the new architecture gets rid of VLAN, so it solves the problem of VLAN ID using up. The architecture is shown as follows:

![](./ovs_arch.png)

There are some points to describe the architecture:

1.Each user has an unique and exclusive virtual network. The container inside the network communicates with outside via gateway.

2.If there is a container in the host, then there will be a user's OVS bridge. Each user's container will connect to user's OVS bridge by Veth Pair. A user's OVS bridge will be named after "docklet-br-<userid>".

3.Each user's network is star topology, each host on which there is no gateway will connect to the host on which the user's gateway is by GRE tunnel. Thus, there may be many GRE tunnels between two hosts(Each GRE tunnels belongs to different user.), Docklet takes user's id as keys to distinguish from each other. 

4.OVS bridge and GRE tunnels are created and destroyed dynamically, which means that network including bridge and GRE tunnels is created only when user starts the container and is destroyed by calling '/conf/lxc-script/lxc-ifdown' script only when user stops the container.   

5.There are two modes to set up gateways: distributed or centralized. Centralized gateways is the default mode and it will set up the gateways only on Master host, while distributed gateways mode will set up gateways on different workers, just like the picture shown above. NAT/iptables in Linux Kernel is needed when container communicate with outside network via gateway.

## Processing users' requests (Workspace requests)
The picture of processing user's requests will show the whole architecture of Docklet. The process is shown as follows, firstly, these are the requests to Workspace: 

![](./workspace_requests.png)

## Processing users' requests (Other requests)
Other requests.

![](./other_requests.png)
