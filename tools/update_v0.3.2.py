import json

fspath = '/opt/docklet'
groupfile = open(fspath+"/global/sys/quota",'r')
groups = json.loads(groupfile.read())
groupfile.close()
for group in groups:
    group['quotas']['input_rate_limit'] = 10000
    group['quotas']['output_rate_limit'] = 10000
groupfile = open(fspath+"/global/sys/quota",'w')
groupfile.write(json.dumps(groups))
groupfile.close()

quotafile = open(fspath+"/global/sys/quotainfo",'r')
quotas = json.loads(quotafile.read())
quotafile.close()
quotas['quotainfo'].append({'name':'input_rate_limit', 'hint':'the ingress speed of the network, number of kbps. 0 means the rate are unlimited.'})
quotas['quotainfo'].append({'name':'output_rate_limit', 'hint':'the egress speed of the network, number of kbps. 0 means the rate are unlimited.'})
quotafile = open(fspath+"/global/sys/quotainfo",'w')
quotafile.write(json.dumps(quotas))
quotafile.close()
