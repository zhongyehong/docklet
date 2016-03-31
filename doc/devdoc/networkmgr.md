# Network Manager

## About
网络管理是为docklet提供网络管理的模块。

关于需求，主要有两点：
* 一个中心管理池，按 网络段（IP/CIDR） 给用户分配网络池
* 很多用户网络池，按 一个或者几个网络地址 给用户的cluster分配网络地址

## Data Structure
面对这两种需求，设计了两种数据结构来管理网络地址。
* 区间池 / interval pool ： 分配、回收 网络段


    interval pool 中的元素为区间，其由很多个区间组成。
    一个朴素的 区间池 是这样的 ： interval pool : [A1,A2],[B1,B2],[C1,C2],...[X1,X2]
    每次申请一段地址的时候，从上述区间中选择一个区间分配，并将该区间中剩余部分放回区间池

    而考虑到 网络段（IP/CIDR） 是 2 的幂的结构，所以可以将区间池进一步设计成如下结构：
    interval pool:
            ... ...
            cidr=16 : [A1,A2], [A3,A4], ...
            cidr=17 : [B1,B2], [B3,B4], ...
            cidr=18 : [C1,C2], [C3,C4], ...
            ... ...
    上述结构还可以进一步优化，因为 每一个区间的结尾地址可以通过开始地址和CIDR算出来，所以每个区间只需要写一个起始地址就可以了
    所以：
    interval pool:
            ... ...
            cidr=16 : A1, A3, ...
            cidr=17 : B1, B3, ...
            cidr=18 : C1, C3, ...
            ... ...
    而其中，每一个元素，比如 A1，其实代表的是一个区间 [A1, A1+2^16-1]
    这种基于2的幂的区间设计的好处是可以方便的进行 分配 和 合并 区间，操作起来更加高效。

* 枚举池 / enumeration pool : 分配、回收一个、多个网络地址


    enum pool 中的元素为单个网络地址，比如：
    enum pool : A, B, C, D, ... X

## API
操作上述两种数据结构的API，这里省略

## Network Manager Storage Design
* center : 中心池，提供 用户网络段 的分配、回收


    info : IP/CIDR
    intervalpool :
            cidr16 : ...
            cidr17 : ...
            ... ...

* system ： 系统保留地址，为系统内部的 网络地址 提供 分配回收


    info : IP/CIDR
    enumpool : ...

* vlan/<username&gt; : 为某个用户提供地址分配、回收服务


    info : IP/CIDR
    enumpool : ...
    vlanid : id
