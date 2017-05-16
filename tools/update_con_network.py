


userpoint = "http://" + env.getenv('USER_IP') + ":" + str(env.getenv('USER_PORT'))
G_userip = env.getenv("USER_IP")

def post_to_user(url = '/', data={}):
    return requests.post(userpoint+url,data=data).json()
