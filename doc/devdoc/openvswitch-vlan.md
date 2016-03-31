# Test of VLAN on openvswitch

## Note 1
基本操作，建网桥，配置地址，启动网桥

    ovs-vsctl add-br br0
    ip address add 172.0.0.1/8 dev br0
    ip link set br0 up

## Note 2
LXC conf 中指定 pair 的名称，从而方便控制 网络链接

所以，需要修改 conf 文件来实现这一点

    lxc.network.type = veth
    lxc.network.name = eth0
    lxc.network.script.up = Bridge=br0 /home/leebaok/Container/lxc-ifup
    lxc.network.script.down = Bridge=br0 /home/leebaok/Container/lxc-ifdown
    lxc.network.veth.pair = base
    lxc.network.ipv4 = 172.0.0.10/8
    lxc.network.ipv4.gateway = 172.0.0.1
    lxc.network.flags = up
    lxc.network.mtu = 1420

我们对上面的配置解释一下：
* lxc.network.link 现在不需要了
* lxc.network.script.up/down 来指定container启动前和关闭后的网络准备和释放，这个脚本的路径是物理机的路径，因为这个脚本是由物理机来执行的，“Bridge=br0” 是为了传参数给后面的脚本
* lxc.network.veth.pair 是网络连接的名字，即container和物理机的哪个口连接

配置了网络设置的脚本路径，我们还需要实现这两个具体的脚本：
* /home/leebaok/Container/lxc-ifup  


    #!/bin/bash
    # $1 : name of container ( name in lxc-start with -n )
    # $2 : net
    # $3 : network flags, up or down
    # $4 : network type, for example, veth
    # $5 : value of lxc.network.veth.pair
    ovs-vsctl --may-exist add-port $Bridge $5
    # ovs-vsctl set port $5 tag=$Tag

* /home/leebaok/Container/lxc-ifdown


    #!/bin/bash
    # $1 : name of container ( name in lxc-start with -n )
    # $2 : net
    # $3 : network flags, up or down
    # $4 : network type, for example, veth
    # $5 : value of lxc.network.veth.pair
    ovs-vsctl --if-exists del-port $Bridge $5

## Note 3
VLAN tag 操作：

    ovs-vsctl set port <port-name> tag=<tag-id>
    ovs-vsctl clear port <port-name> tag

patch 是用来连接两个网桥的，操作如下：

    ovs-vsctl add-br br0
    ovs-vsctl add-br br1
    ovs-vsctl add-port br0 patch0 -- set interface patch0 type=patch options:peer=patch1
    ovs-vsctl add-port br1 patch1 -- set interface patch1 type=patch options:peer=patch0
    # NOW : two bridges are connected by patch


## Note 4
一台机器上一个域的网桥只有一个，比如在 host-0 上，建两个网桥：

    ovs-vsctl add-br br0
    ip address add 172.0.0.1/8 dev br0
    ip link set br0 up

    ovs-vsctl add-br br1
    ip address add 172.0.0.2/8 dev br1
    ip link set br1 up

则，后配置的那个网桥会失效

因为系统认为，172.0.0.1/8 内的机器都应该在 br0 中

而以下配置是正确的：

    ovs-vsctl add-br br0
    ip address add 172.0.0.1/24 dev br0
    ip link set br0 up

    ovs-vsctl add-br br1
    ip address add 172.0.1.1/24 dev br1
    ip link set br1 up

## Note 5
关于网关，网桥/交换机是二层设备，网关是三层组件，我们可以将网桥连接起来，多个网桥共用一个网关

    ovs-vsctl add-br br0
    ip link set br0 up
    ovs-vsctl add-br br1
    ip address add 172.0.0.1/24 dev br1
    ip link set br1 up
    ovs-vsctl add-port br0 patch0 -- set interface patch0 type=patch options:peer=patch1
    ovs-vsctl add-port br1 patch1 -- set interface patch1 type=patch options:peer=patch0

    # lxc config :
    #   ip -- 172.0.0.11/24
    #   gateway -- 172.0.0.1
    #   lxc.network.veth.pair -- base ,  base is connected on br0
    lxc-start -f container.conf -n base -F -- /bin/bash
    # NOW ： lxc network is running ok

## Note 6
基于多个网桥实现VLAN

### 方案一

    ovs-vsctl add-br br0
    ip link set br0 up
    ovs-vsctl add-br br1
    ip address add 172.0.0.1/24 dev br1
    ip link set br1 up
    ovs-vsctl add-port br0 patch0 -- set interface patch0 type=patch options:peer=patch1
    ovs-vsctl add-port br1 patch1 -- set interface patch1 type=patch options:peer=patch0

    # lxc config :
    #   ip -- 172.0.0.11/24
    #   gateway -- 172.0.0.1
    #   lxc.network.veth.pair -- base ,  base is connected on br0
    lxc-start -f container.conf -n base -F -- /bin/bash
    # NOW ： lxc network is running ok
    ## above is the same as before

    ovs-vsctl set port base tag=5
    ovs-vsctl set port patch0 tag=5
    # NOW : lxc network is running ok

    #  ARCH                                    
    +-----------------------+          +----------------------+
    | br0                   |          | br1 : 172.0.0.1/24   |
    +--+-----tag=5---tag=5--+          +---+-------+----------+
       |       |       |       patch       |       |
       |       |       +-------------------+       |
       |       |                                   |
    internal  base:172.0.0.11/24                internal
              (gateway:172.0.0.1)

    # flow : base --> patch --> br1/internal

* 方案可行
* 但是，每个 VLAN 需要一个网关

### 方案二 （不可行）

    #  ARCH                                    
    +-------------------------------------------------------------+
    | br0                                                         |
    +--+-----tag=5---tag=5---------+-----tag=6---tag=6---------+--+
       |       |       |  +-----+  |       |       |  +-----+  |
       |       |       +--| br1 |--+       |       +--| br2 |--+
       |       |          +-----+          |          +-----+    
    internal  base1:172.0.0.11/24         base2:172.0.0.12/24      

    # flow 1 : base1 --> br1 --> internal
    # flow 2 : base1 --> br1 --> br2 --> base2

* 方案不可行，因为上面的 flow 可以使得 base1、base2 在二层通信，无法隔离

## Note 7
上述可行方案的简化版
### 简化版一

    ovs-vsctl add-br br0
    ip link set br0 up
    # add a fake bridge connected to br0 with vlan tag=5
    ovs-vsctl add-br fakebr br0 5
    ip address add 172.0.0.1/24 dev fakebr
    ip link set fakebr up

    # lxc config:
    #   ip : 172.0.0.11/24
    #   gateway : 172.0.0.1/24
    #   lxc.network.veth.pair -- base ,  base is connected on br0
    lxc-start -f container.conf -n base -F -- /bin/bash

    ovs-vsctl set port base tag=5

    #  ARCH                                    
    +-----------------------+          
    | br0                   |    
    +--+-----tag=5---tag=5--+      
       |       |       |
       |       |     fakebr:172.0.0.1/24
       |       |                               
    internal  base:172.0.0.11/24             
              (gateway:172.0.0.1)

    # flow : base --> fakebr

### 简化版二

    ovs-vsctl add-br br0
    ip link set br0 up
    # add an internal interface for vlan
    ovs-vsctl add-port br0 vlanif tag=5 -- set interface vlanif type=internal
    ip address add 172.0.0.1/24 dev vlanif
    ip link set vlanif up

    # lxc config:
    #   ip : 172.0.0.11/24
    #   gateway : 172.0.0.1/24
    #   lxc.network.veth.pair -- base ,  base is connected on br0
    lxc-start -f container.conf -n base -F -- /bin/bash

    ovs-vsctl set port base tag=5

    #  ARCH                                    
    +-----------------------+          
    | br0                   |    
    +--+-----tag=5---tag=5--+      
       |       |       |
       |       |     vlanif:172.0.0.1/24
       |       |                               
    internal  base:172.0.0.11/24             
              (gateway:172.0.0.1)

    # flow : base --> vlanif

### 简化版一 & 简化版二
使用 ovs-vsctl show 查看的时候，上述两个版本显示的信息是一样的，说明 fakebr 其实本质上可能就是一个 internal interface

其实，方案一中，对 br1 的 IP（172.0.0.1/24）的配置，其实就是对 br1 的 internal 的 interface 的配置，所以其实多余的网桥不是必须的，而 interface 才是真正需要的。

而，internal interface 相当于是连接着本地Linux的虚拟网卡，这块网卡的另一端连着OVS的虚拟网桥。

而，Linux 的网络栈又管理着物理网卡、虚拟网卡，以及对这些网卡的包进行转发、路由等处理。

似乎，Linux 的网络栈又成了一个大的交换机/网桥，上面连接着 internal interface 和 物理网卡。

## Note 8
基于上述的实践和探索，其实 **我们需要给一个VLAN配置一个可以出去的网关、网卡。**

那么，我们一个简单可行的方案可以这样：

    +------------------------------------------------------------------------------+
    | bridge                                                                       |
    |        <------- VLAN ID=5 --------->              <---- VLAN ID=6 ------>    |
    +--+-----tag=5---tag=5------------tag=5-------------tag=6-------------tag=6----+
       |       |       |                |                 |                 |
       |       |  lxc-2:172.0.0.12/24   |                 |                 |
    internal   |  (gateway:172.0.0.1)   |                 |                 |
               |                        |                 |                 |
        lxc-1:172.0.0.11/24       gw5:172.0.0.1/24   lxc-3:172.0.1.11/24  gw6:172.0.1.1/24
        (gateway:172.0.0.1)       internal           (gateway:172.0.1.1)  internal
                                        |                                   |
                                        |                                   |
                                        +----------- NAT / iptables --------+
                                                          ||||
                                                          ||||
                                                         \\\///
                                                          \\//
                                                           \/




# end
