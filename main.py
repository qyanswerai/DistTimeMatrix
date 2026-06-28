from utils.config_parse import get_api_key
from matrix_acquisition.api_call import process


def matrix_acquire_test():
    # 坐标点（越南）
    origins = [[106.669182, 10.780865],
               [106.683256, 10.761083],
               [106.704547, 10.770797],
               [106.698990, 10.788026]]
    destinations = [[106.669182, 10.780865],
                    [106.683256, 10.761083],
                    [106.704547, 10.770797]]

    # 坐标点（美国）
    # origins = [[-122.081356, 37.420761],
    #            [-122.097371, 37.403184]]
    # destinations = [[-122.086894, 37.420999],
    #                 [-122.044651, 37.383047]]

    # 坐标点（上海）
    # origins = [[121.324471, 31.254744],
    #            [121.41385, 31.24494],
    #            [121.212419, 31.220244],
    #            [121.320917, 31.195166]]

    # destinations = [[121.324471, 31.254744],
    #                 [121.41385, 31.24494],
    #                 [121.212419, 31.220244],
    #                 [121.320917, 31.195166]]
    # destinations = [[121.324471, 31.254744],
    #                 [121.41385, 31.24494],
    #                 [121.212419, 31.220244]]

    coord_type = ['wgs84', 'gcj02', 'bd09ll'][0]

    # 关键点：只改这里就能切换求解器
    method_name = ['google', 'ors', 'valhalla', 'tomtom', 'baidu', 'amap', 'haversine'][1]
    key = get_api_key(method=method_name)
    # key = ""

    inputs = {"origins": origins,
              "destinations": destinations,
              "coord_type": coord_type,
              "method_name": method_name,
              "key": key}

    result = process(inputs)
    return result


if __name__ == '__main__':
    # 测试距离矩阵、时间矩阵获取功能
    matrix_acquire_test()

    print('finished')