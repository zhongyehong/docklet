#!/usr/bin/python3

import os, json

fspath="/opt/docklet"

def update_quotainfo():
    if not os.path.exists(fspath+"/global/sys/quotainfo"):
        print("quotainfo file not exists, please run docklet to init it")
        return False
    quotafile = open(fspath+"/global/sys/quotainfo", 'r')
    quotas = json.loads(quotafile.read())
    quotafile.close()
    if type(quotas) is list:
        new_quotas = {}
        new_quotas['default'] = 'fundation'
        new_quotas['quotainfo'] = quotas
        quotas = new_quotas
        print("change the type of quotafile from list to dict")
    keys = []
    for quota in quotas['quotainfo']:
        keys.append(quota['name'])
    if 'cpu' not in keys:
        quotas['quotainfo'].append({'name':'cpu', 'hint':'the cpu quota, number of cores, e.g. 4'})
    if 'memory' not in keys:
        quotas['quotainfo'].append({'name':'memory', 'hint':'the memory quota, number of MB, e.g. 4000'})
    if 'disk' not in keys:
        quotas['quotainfo'].append({'name':'disk', 'hint':'the disk quota, number of MB, e.g. 4000'})
    if 'data' not in keys:
        quotas['quotainfo'].append({'name':'data', 'hint':'the quota of data space, number of GB, e.g. 100'})
    if 'image' not in keys:
        quotas['quotainfo'].append({'name':'image', 'hint':'how many images the user can have, e.g. 8'})
    if 'idletime' not in keys:
        quotas['quotainfo'].append({'name':'idletime', 'hint':'will stop cluster after idletime, number of hours, e.g. 24'})
    if 'vnode' not in keys:
        quotas['quotainfo'].append({'name':'vnode', 'hint':'how many containers the user can have, e.g. 8'})
    print("quotainfo updated")
    quotafile = open(fspath+"/global/sys/quotainfo", 'w')
    quotafile.write(json.dumps(quotas))
    quotafile.close()

if __name__ == '__main__':
    update_quotainfo()
