from flask import session,render_template
from webViews.view import normalView
from webViews.dockletrequest import dockletRequest


class dashboardView(normalView):
    template_path = "dashboard.html"

    @classmethod
    def get(self):
        result = dockletRequest.post('/cluster/list/')
        images = dockletRequest.post('/image/list/').get("images")
        ok = result and result.get('clusters')
        clusters = result.get("clusters")
        if (result):
            full_clusters = []
            data={}
            for cluster in clusters:
                data["clustername"] = cluster
                single_cluster = {}
                single_cluster['name'] = cluster
                message = dockletRequest.post("/cluster/info/", data)
                if(message):
                    message = message.get("message")
                    single_cluster['status'] = message['status']
                    single_cluster['id'] = message['clusterid']
                    full_clusters.append(single_cluster)
                else:
                    self.error()
            return self.render(self.template_path, ok = ok, clusters = full_clusters, images = images)
        else:
            self.error()

    @classmethod
    def post(self):
        return self.get()

class dashboard_guestView(normalView):
    template_path = "dashboard_guest.html"

    @classmethod
    def get(self):
        mysession = {}
        mysession['avatar'] = "/static/avatar/default.png"
        mysession['nickname'] = "guest"
        mysession['description'] = "you are a guest"
        mysession['status'] = "guest"
        mysession['usergroup'] = "normal"
        return render_template(self.template_path, mysession = mysession)

    @classmethod
    def post(self):
        return self.get()
