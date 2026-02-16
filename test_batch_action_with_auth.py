import requests
import json

# 测试批量操作API（带认证）
def test_batch_action():
    # 首先获取认证token
    login_url = 'http://localhost:8000/api/login'
    login_data = {'account': 'admin', 'password': 'admin123'}
    
    print('获取认证token...')
    login_response = requests.post(login_url, data=login_data)
    print('Login status code:', login_response.status_code)
    
    if login_response.status_code != 200:
        print('Login failed:', login_response.json())
        return
    
    token = login_response.json().get('data', {}).get('token')
    if not token:
        print('No token found in login response')
        return
    
    print('Token obtained successfully')
    
    # 设置认证头
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    
    # 测试下载功能
    print('\n测试下载功能...')
    url = 'http://localhost:8000/api/admin/batch-action'
    data = {'action': 'download', 'image_ids': [1, 2, 3]}
    
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        print('Download status code:', response.status_code)
        print('Download content type:', response.headers.get('content-type'))
        
        if response.status_code == 200:
            if 'application/zip' in response.headers.get('content-type', ''):
                print('Download successful, received ZIP file')
                # 保存ZIP文件
                with open('test_download.zip', 'wb') as f:
                    f.write(response.content)
                print('ZIP file saved as test_download.zip')
            else:
                print('Download response:', response.json())
        else:
            print('Download failed:', response.json())
    except Exception as e:
        print('Download error:', str(e))
    
    print('\n' + '='*50 + '\n')
    
    # 测试移动功能
    print('测试移动功能...')
    data = {'action': 'move', 'image_ids': [1, 2, 3], 'target_category': 1}
    
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        print('Move status code:', response.status_code)
        print('Move response:', response.json())
    except Exception as e:
        print('Move error:', str(e))
    
    print('\n' + '='*50 + '\n')
    
    # 测试删除功能
    print('测试删除功能...')
    data = {'action': 'delete', 'image_ids': [1, 2, 3]}
    
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers)
        print('Delete status code:', response.status_code)
        print('Delete response:', response.json())
    except Exception as e:
        print('Delete error:', str(e))

if __name__ == '__main__':
    test_batch_action()
