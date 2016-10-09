import requests
endpoint = 'http://0.0.0.0:9000/inside/cluster/scaleout/'
data = {"imagename": 'base', 'image':'base_base_base', 'clustername': 'asdf', 'diskSetting': '200', 'imageowner': 'base', 'cpuSetting': '1', 'memorySetting': '200'}
result = requests.post(endpoint , data = data).json()
