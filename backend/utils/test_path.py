import os

# 测试错误页面路径构建
def test_error_page_path():
    # 模拟get_error_page函数中的路径构建
    error_type = "404页面不存在"
    error_page_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "Status_Code", f"{error_type}.html")
    
    print(f"构建的错误页面路径: {error_page_path}")
    print(f"路径是否存在: {os.path.exists(error_page_path)}")
    
    # 打印当前工作目录
    print(f"当前工作目录: {os.getcwd()}")
    
    # 打印utils.py文件的绝对路径
    print(f"utils.py文件的绝对路径: {os.path.abspath(__file__)}")

if __name__ == "__main__":
    test_error_page_path()
