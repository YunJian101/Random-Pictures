import requests
import json

# 测试批量操作API
def test_batch_action():
    url = 'http://localhost:8000/api/admin/batch-action'
    
    # 测试下载功能
    print('测试下载功能...')
    data = {'action': 'download', 'image_ids': [1, 2, 3]}
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        print('Status code:', response.status_code)
        print('Response:', response.json())
    except Exception as e:
        print('Error:', str(e))
    
    print('\n' + '='*50 + '\n')
    
    # 测试移动功能
    print('测试移动功能...')
    data = {'action': 'move', 'image_ids': [1, 2, 3], 'category_id': 1}
    
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        print('Status code:', response.status_code)
        print('Response:', response.json())
    except Exception as e:
        print('Error:', str(e))
    
    print('\n' + '='*50 + '\n')
    
    # 测试删除功能
    print('测试删除功能...')
    data = {'action': 'delete', 'image_ids': [1, 2, 3]}
    
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        print('Status code:', response.status_code)
        print('Response:', response.json())
    except Exception as e:
        print('Error:', str(e))

if __name__ == '__main__':
    test_batch_action()
