#!/user/bin/python3
import json

job_data = {'image_1': 'base_base_base', 'mappingRemoteDir_2_2': 'sss', 'dependency_1': 'aaa', 'mappingLocalDir_2_1': 'xxx', 'mappingLocalDir_1_2': 'aaa', 'mappingLocalDir_1_1': 'aaa', 'mappingLocalDir_2_3': 'fdsffdf', 'mappingRemoteDir_1_1': 'ddd', 'mappingRemoteDir_2_3': 'sss', 'srcAddr_1': 'aaa', 'mappingSource_2_1': 'Aliyun', 'cpuSetting_1': '1', 'mappingSource_2_2': 'Aliyun', 'retryCount_2': '1', 'mappingSource_1_1': 'Aliyun', 'expTime_1': '60', 'diskSetting_2': '1024', 'diskSetting_1': '1024', 'dependency_2': 'ddd', 'memorySetting_1': '1024', 'command_2': 'ccc', 'mappingRemoteDir_1_2': 'ddd', 'gpuSetting_2': '0', 'memorySetting_2': '1024', 'gpuSetting_1': '0', 'mappingLocalDir_2_2': 'bbb', 'mappingSource_1_2': 'Aliyun', 'expTime_2': '60', 'mappingRemoteDir_2_1': 'vvv', 'srcAddr_2': 'fff', 'cpuSetting_2': '1', 'instCount_1': '1', 'mappingSource_2_3': 'Aliyun', 'token': 'ZXlKaGJHY2lPaUpJVXpJMU5pSXNJbWxoZENJNk1UVXpNelE0TVRNMU5Td2laWGh3SWpveE5UTXpORGcwT1RVMWZRLmV5SnBaQ0k2TVgwLkF5UnRnaGJHZXhJY2lBSURZTUd5eXZIUVJnUGd1ZTA3OEtGWkVoejJVMkE=', 'instCount_2': '1', 'retryCount_1': '1', 'command_1': 'aaa', 'taskPriority': '0', 'image_2': 'base_base_base', 'jobName': 'aaa'}

def parse(job_data):
    job_info = {}
    message = {}
    for key in job_data:
        key_arr = key.split('_')
        value = job_data[key]
        if len(key_arr) == 1:
            job_info[key_arr[0]] = value
        elif len(key_arr) == 2:
            key_prefix, task_idx = key_arr[0], key_arr[1]
            task_idx = 'task_' + task_idx
            if task_idx in job_info:
                job_info[task_idx][key_prefix] = value
            else:
                tmp_dict = {
                    key_prefix: value
                }
                job_info[task_idx] = tmp_dict
        elif len(key_arr) == 3:
            key_prefix, task_idx, mapping_idx = key_arr[0], key_arr[1], key_arr[2]
            task_idx = 'task_' + task_idx
            mapping_idx = 'mapping_' + mapping_idx
            if task_idx in job_info:
                if "mapping" in job_info[task_idx]:
                    if mapping_idx in job_info[task_idx]["mapping"]:
                        job_info[task_idx]["mapping"][mapping_idx][key_prefix] = value
                    else:
                        tmp_dict = {
                            key_prefix: value
                        }
                        job_info[task_idx]["mapping"][mapping_idx] = tmp_dict
                else:
                    job_info[task_idx]["mapping"] = {
                        mapping_idx: {
                            key_prefix: value
                        }
                    }
            else:
                tmp_dict = {
                    "mapping":{
                        mapping_idx: {
                            key_prefix: value
                        }
                    }
                }
                job_info[task_idx] = tmp_dict
    print(json.dumps(job_info, indent=4))

if __name__ == '__main__':
    parse(job_data) 
