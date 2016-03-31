from webViews.view import normalView
from webViews.dockletrequest import dockletRequest
from flask import redirect, request, abort

class registerView(normalView):
    template_path = 'register.html'

    @classmethod
    def post(self):
        form = dict(request.form)
        if (request.form.get('username') == None or request.form.get('password') == None or request.form.get('password') != request.form.get('password2') or request.form.get('email') == None or request.form.get('description') == None):
            abort(500)
        result = dockletRequest.unauthorizedpost('/register/', form)
        return self.render('waitingRegister.html')
