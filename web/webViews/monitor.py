from flask import session
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest


class statusView(normalView):
    template_path = "monitor/status.html"

    @classmethod
    def get(self):
        data = {}
        allclusters = dockletRequest.post_to_all('/cluster/list/')
        for master in allclusters:
            allclusters[master] = allclusters[master].get('clusters')
        result = dockletRequest.post('/user/selfQuery/')
        quotas = result['data']['groupinfo']
        quotanames = quotas.keys()
        '''result = dockletRequest.post('/monitor/user/quotainfo/', data)
        quotainfo = result.get('quotainfo')
        quotainfo['cpu'] = int(int(quotainfo['cpu']))
        print(quotainfo)'''
        allcontainers = {}
        if (result):
            for master in allclusters:
                allcontainers[master] = {}
                for cluster in allclusters[master]:
                    data["clustername"] = cluster
                    message = dockletRequest.post('/cluster/info/', data, master.split("@")[0])
                    if (message):
                        message = message.get('message')
                    else:
                        self.error()
                    allcontainers[master][cluster] = message
                message = dockletRequest.post('/batch/vnodes/list/', data, master.split("@")[0])
                message = message.get('data')
                containers = []
                for m in message:
                    container = {}
                    container['containername'] = m
                    container['ip'] = '--'
                    containers.append(container)
                tmp = {}
                tmp['containers'] = containers
                tmp['status'] = 'running'
                allcontainers[master]['Batch_Job'] = tmp
            return self.render(self.template_path,  quotas = quotas, quotanames = quotanames, allcontainers = allcontainers, user = session['username'])
        else:
            self.error()

class statusRealtimeView(normalView):
    template_path = "monitor/statusRealtime.html"
    node_name = ""

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/vnodes/%s/basic_info/'%(self.node_name), data, masterip)
        basic_info = result.get('monitor').get('basic_info')
        return self.render(self.template_path, node_name = self.node_name, user = session['username'], container = basic_info, masterip=masterip)

class historyView(normalView):
    template_path = "monitor/history.html"

    @classmethod
    def get(self):
        data = {
            "user": session['username'],
        }
        allvnodes = {}
        result = dockletRequest.post_to_all('/monitor/user/createdvnodes/', data)
        for master in result:
            allvnodes[master] = result[master].get('createdvnodes')
        return self.render(self.template_path, user = session['username'],allvnodes = allvnodes)

class historyVNodeView(normalView):
    template_path = "monitor/historyVNode.html"
    vnode_name = ""

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/vnodes/%s/history/'%(self.vnode_name), data, masterip)
        history = result.get('monitor').get('history')
        return self.render(self.template_path, vnode_name = self.vnode_name, user = session['username'], history = history)

class hostsRealtimeView(normalView):
    template_path = "monitor/hostsRealtime.html"
    com_ip = ""

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/hosts/%s/cpuconfig/'%(self.com_ip), data,masterip)
        proc = result.get('monitor').get('cpuconfig')
        result = dockletRequest.post('/monitor/hosts/%s/osinfo/'%(self.com_ip), data,masterip)
        osinfo = result.get('monitor').get('osinfo')
        result = dockletRequest.post('/monitor/hosts/%s/diskinfo/'%(self.com_ip), data,masterip)
        diskinfos = result.get('monitor').get('diskinfo')

        return self.render(self.template_path, com_ip = self.com_ip, user = session['username'],processors = proc, OSinfo = osinfo, diskinfos = diskinfos, masterip = masterip)

class hostsConAllView(normalView):
    template_path = "monitor/hostsConAll.html"
    com_ip = ""

    @classmethod
    def get(self):
        masterip = self.masterip
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/hosts/%s/containerslist/'%(self.com_ip), data, masterip)
        containers = result.get('monitor').get('containerslist')
        containerslist = []
        for container in containers:
            result = dockletRequest.post('/monitor/vnodes/%s/basic_info/'%(container), data, masterip)
            basic_info = result.get('monitor').get('basic_info')
            result = dockletRequest.post('/monitor/vnodes/%s/owner/'%(container), data, masterip)
            owner = result.get('monitor')
            basic_info['owner'] = owner
            containerslist.append(basic_info)
        return self.render(self.template_path, containerslist = containerslist, com_ip = self.com_ip, user = session['username'], masterip = masterip)

class hostsView(normalView):
    template_path = "monitor/hosts.html"

    @classmethod
    def get(self):
        data = {
            "user": session['username'],
        }
        allresult = dockletRequest.post_to_all('/monitor/listphynodes/', data)
        allmachines = {}
        all_cloud_nodes = {}
        for master in allresult:
            allmachines[master] = []
            all_cloud_nodes[master] = dockletRequest.post('/cloud/node/list/', data, master.split("@")[0]).get('nodes')
            iplist = allresult[master].get('monitor').get('allnodes')
            for ip in iplist:
                containers = {}
                result = dockletRequest.post('/monitor/hosts/%s/containers/'%(ip), data, master.split("@")[0])
                containers = result.get('monitor').get('containers')
                result = dockletRequest.post('/monitor/hosts/%s/status/'%(ip), data, master.split("@")[0])
                status = result.get('monitor').get('status')
                allmachines[master].append({'ip':ip,'containers':containers, 'status':status})
        #print(machines)
        return self.render(self.template_path, allmachines = allmachines, user = session['username'], all_cloud_nodes = all_cloud_nodes)

class monitorUserAllView(normalView):
    template_path = "monitor/monitorUserAll.html"

    @classmethod
    def get(self):
        data = {
            "user": session['username'],
        }
        result = dockletRequest.post('/monitor/listphynodes/', data)
        userslist = [{'name':'root'},{'name':'libao'}]
        for user in userslist:
            result = dockletRequest.post('/monitor/user/%s/clustercnt/'%(user['name']), data)
            user['clustercnt'] = result.get('monitor').get('clustercnt')
        return self.render(self.template_path, userslist = userslist, user = session['username'])
