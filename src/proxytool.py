#!/usr/bin/python3

import requests, json

proxy_control="http://localhost:8001/api/routes"

def get_routes():
    try:
        resp = requests.get(proxy_control)
    except:
        return [False, 'Connect Failed']
    return [True, resp.json()]

def set_route(path, target):
    path='/'+path.strip('/')
    if path=='' or target=='':
        return [False, 'input not valid']
    try:
        resp = requests.post(proxy_control+path, data=json.dumps({'target':target}))
    except:
        return [False, 'Connect Failed']
    return [True, 'set ok']
    
def delete_route(path):
    path='/'+path.strip('/')
    try:
        resp = requests.delete(proxy_control+path)
    except:
        return [False, 'Connect Failed']
    # if exist and delete, status_code=204, if not exist, status_code=404
    return [True, 'delete ok']
