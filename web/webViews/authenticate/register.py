from webViews.view import normalView
from webViews.dockletrequest import dockletRequest
from flask import redirect, request, abort, render_template

class registerView(normalView):
    template_path = 'register.html'

    @classmethod
    def post(self):
        form = dict(request.form)
        if (request.form.get('username') == None or request.form.get('password') == None or request.form.get('password') != request.form.get('password2') or request.form.get('email') == None or request.form.get('description') == None):
            abort(500)
        result = dockletRequest.unauthorizedpost('/register/', form)
        return redirect("/login/")

    @classmethod
    def get(self):
        return render_template(self.template_path)
