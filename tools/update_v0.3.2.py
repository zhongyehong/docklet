import json

def isexist(quotas, key):
    flag = False
    for quota in quotas:
        if quota['name'] == key:
            flag = True
            return flag
    return flag

fspath = '/opt/docklet'
groupfile = open(fspath+"/global/sys/quota",'r')
groups = json.loads(groupfile.read())
groupfile.close()
for group in groups:
    group['quotas']['portmapping'] = 8
    group['quotas']['input_rate_limit'] = 10000
    group['quotas']['output_rate_limit'] = 10000
groupfile = open(fspath+"/global/sys/quota",'w')
groupfile.write(json.dumps(groups))
groupfile.close()

quotafile = open(fspath+"/global/sys/quotainfo",'r')
quotas = json.loads(quotafile.read())
quotafile.close()

if not isexist(quotas['quotainfo'], 'portmapping'):
    quotas['quotainfo'].append({'name':'portmapping', 'hint':'how many ports the user can map, e.g. 8'})
if not isexist(quotas['quotainfo'], 'input_rate_limit'):
    quotas['quotainfo'].append({'name':'input_rate_limit', 'hint':'the ingress speed of the network, number of kbps. 0 means the rate are unlimited.'})
if not isexist(quotas['quotainfo'], 'output_rate_limit'):
    quotas['quotainfo'].append({'name':'output_rate_limit', 'hint':'the egress speed of the network, number of kbps. 0 means the rate are unlimited.'})
quotafile = open(fspath+"/global/sys/quotainfo",'w')
quotafile.write(json.dumps(quotas))
quotafile.close()
