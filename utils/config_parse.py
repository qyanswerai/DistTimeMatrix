import os
import configparser


def get_api_key(path='', method='amap'):
    # 创建一个 ConfigParser 对象
    config = configparser.ConfigParser()
    # 读取配置文件
    config.read(os.path.join(path, 'config.ini'))
    try:
        # 从配置文件中获取 API Key
        api_key = config.get('API', method)
        return api_key
    except (configparser.NoSectionError, configparser.NoOptionError):
        print("未找到 API Key 配置，请检查配置文件。")
        return None

def get_api_url(path='', method='amap'):
    # 创建一个 ConfigParser 对象
    config = configparser.ConfigParser()
    # 读取配置文件
    config.read(os.path.join(path, 'config.ini'))
    try:
        # 从配置文件中获取 API Key
        api_url = config.get('URL', method)
        return api_url
    except (configparser.NoSectionError, configparser.NoOptionError):
        print("未找到 API url 配置，请检查配置文件。")
        return None


if __name__ == "__main__":
    api_key = get_api_key('../', 'ors')
    if api_key:
        print(f"读取到的 API Key: {api_key}")

    api_url = get_api_url('../', 'ors')
    if api_url:
        print(f"读取到的 API url: {api_url}")