from flask import session,render_template
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest


class dashboardView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        result = dockletRequest.post_to_all('/cluster/list/')
        desc = dockletRequest.getalldesc()
        allclusters={}
        for master in result:
            clusters = result[master].get("clusters")
            full_clusters = []
            data={}
            for cluster in clusters:
                data["clustername"] = cluster
                single_cluster = {}
                single_cluster['name'] = cluster
                message = dockletRequest.post("/cluster/info/", data , master.split("@")[0])
                if(message):
                    message = message.get("message")
                    single_cluster['status'] = message['status']
                    single_cluster['id'] = message['clusterid']
                    single_cluster['proxy_server_ip'] = message['proxy_server_ip']
                    full_clusters.append(single_cluster)
                else:
                    self.error()
            allclusters[master] = full_clusters
        return self.render(self.template_path,  allclusters = allclusters, desc=desc)
        #else:
        #    self.error()

    @classmethod
    def post(self):
        return self.get()
