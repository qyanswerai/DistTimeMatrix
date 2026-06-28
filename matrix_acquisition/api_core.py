from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import requests
import numpy as np
import math
from utils.coordinates import transform_coords
from utils.config_parse import get_api_url


# =========================
# 通用抽象（不依赖具体求解器）
# =========================

class CalConfig:
    def __init__(self,
                 google_key: str = "",
                 ors_key: str = "",
                 tomtom_key: str = "",
                 baidu_key: str = "",
                 amap_key: str = "",
                 timeout: int = 10,
                 backend_params: Dict[str, Any] = None):
        self.google_key = google_key
        self.ors_key = ors_key
        self.tomtom_key = tomtom_key
        self.amap_key = amap_key
        self.baidu_key = baidu_key
        self.timeout = timeout
        # 若为None则设置为{}
        self.backend_params = backend_params or {}

        self.google_url = get_api_url('./', 'google')
        self.ors_url = get_api_url('./', 'ors')
        self.valhalla_url = get_api_url('./', 'valhalla')
        self.tomtom_url = get_api_url('./', 'tomtom')
        self.amap_url = get_api_url('./', 'amap')
        self.baidu_url = get_api_url('./', 'baidu')


@dataclass
class CalVariable:
    origins: List[List[float]]
    destinations: List[List[float]]
    coord_type: str = "wgs84"


@dataclass
class CalResult:
    method_name: str
    status: str
    message: str = ""
    variable: Optional[CalVariable] = None
    distance_matrix: Optional[List[List[float]]] = None
    duration_matrix: Optional[List[List[float]]] = None
    # distance_matrix: List[List[float]] = field(default_factory=list)
    # duration_matrix: List[List[float]] = field(default_factory=list)


# =========================
# 策略模式：统一接口
# =========================

class CalMethod(ABC):
    @abstractmethod
    def solve(self, variable: CalVariable, config: CalConfig) -> CalResult:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


# =========================
# 具体策略：不同求解器实现
# =========================
class GoogleMethod(CalMethod):
    @property
    def name(self) -> str:
        return "Google"

    # @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api(self, origins: List[List[float]], destinations: List[List[float]],
                  config: CalConfig) -> tuple[None, str] | tuple[Any, str]:
        # 出发点支持100个坐标对，坐标对用“| ”分隔；经度和纬度用","分隔
        origins = [{"waypoint": {"location": {"latLng": {"latitude": o[1], "longitude": o[0]}}}} for o in origins]
        destinations = [{"waypoint": {"location": {"latLng": {"latitude": d[1], "longitude": d[0]}}}} for d in destinations]

        params = {"origins": origins, "destinations": destinations, "travelMode": "DRIVE", "routingPreference": "TRAFFIC_UNAWARE"}
        other_params = config.backend_params
        if "travelMode" in other_params:
            params["travelMode"] = other_params["travelMode"]
        if "routingPreference" in other_params:
            params["routingPreference"] = other_params["routingPreference"]

        headers = {"Content-Type": "application/json", "X-Goog-Api-Key": config.google_key,
                   "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,condition"}

        try:
            response = requests.post(config.google_url, headers=headers, json=params, timeout=config.timeout)
            if response.status_code == 200:
                response = response.json()
                return response, ""
            return None, response.reason

        except Exception as e:
            raise e

    def solve(self, variable: CalVariable, config: CalConfig) -> CalResult:
        origins = variable.origins
        destinations = variable.destinations
        coord_type = variable.coord_type
        # 1. 转换坐标
        target_type = "wgs84"
        origins = transform_coords(origins, coord_type, target_type)
        destinations = transform_coords(destinations, coord_type, target_type)

        # 2. 调用API获取距离、时间格式化字符串
        dist_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        dur_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        try:
            response, message = self._call_api(origins, destinations, config)

            if response is None:
                return CalResult(self.name, "failed", message, variable, None, None)

            if len(response) > 0:
                for result in response:
                    # {"originIndex": 1, "destinationIndex": 1, "distanceMeters": 5593, "duration": "438s", "condition": "ROUTE_EXISTS"}
                    o = result["originIndex"]
                    d = result["destinationIndex"]
                    if "distanceMeters" in result and result["distanceMeters"] >= 0:
                        dist_mat[d][o] = result["distanceMeters"]
                    if "duration" in result and result["duration"].endswith('s'):
                        dur_mat[d][o] = float(result["duration"].split('s')[0])

            return CalResult(self.name, "succeed", "succeed", variable, dist_mat, dur_mat)
        except Exception as e:
            return CalResult(self.name, "failed", str(e), variable, None, None)


class ORSMethod(CalMethod):
    @property
    def name(self) -> str:
        return "ORS"

    # @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api(self, origins: List[List[float]], destinations: List[List[float]],
                  config: CalConfig) -> tuple[None, str] | tuple[Any, str]:
        # 出发点支持100个坐标对，坐标对用“| ”分隔；经度和纬度用","分隔
        # 确定destinations对应的索引
        o_str = [','.join(map(str, o)) for o in origins]
        d_str = [','.join(map(str, o)) for o in destinations]
        l_str = o_str[::]
        des = []
        for i, d_s in enumerate(d_str):
            if d_s in o_str:
                des.append(i)
                continue
            else:
                des.append(len(l_str))
                l_str.append(d_s)

        locations = [list(map(float,l.split(','))) for l in l_str]

        params = {"metrics": ["distance", "duration"], "locations": locations, "destinations": des}
        other_params = config.backend_params
        if "metrics" in other_params:
            params["metrics"] = other_params['metrics']

        url = "https://api.openrouteservice.org/v2/matrix/"
        if "profile" in other_params:
            config.ors_url = url + f"{other_params['profile']}"
        headers = {"Content-Type": "application/json", "Authorization": config.ors_key}

        try:
            response = requests.post(config.ors_url, headers=headers, json=params, timeout=config.timeout)
            if response.status_code == 200:
                response = response.json()
                return response, ""
            return None, response.reason

        except Exception as e:
            raise e

    def solve(self, variable: CalVariable, config: CalConfig) -> CalResult:
        origins = variable.origins
        destinations = variable.destinations
        coord_type = variable.coord_type
        # 1. 转换坐标
        target_type = "wgs84"
        origins = transform_coords(origins, coord_type, target_type)
        destinations = transform_coords(destinations, coord_type, target_type)

        # 2. 调用API获取距离、时间格式化字符串
        dist_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        dur_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        try:
            response, message = self._call_api(origins, destinations, config)

            if response is None:
                return CalResult(self.name, "failed", message, variable, None, None)

            if "distances" in response:
                dist_mat = np.array(response["distances"][:len(origins)]).T.tolist()
            if "durations" in response:
                dur_mat = np.array(response["durations"][:len(origins)]).T.tolist()

            return CalResult(self.name, "succeed", "succeed", variable, dist_mat, dur_mat)
        except Exception as e:
            return CalResult(self.name, "failed", str(e), variable, None, None)


class ValhallaMethod(CalMethod):
    @property
    def name(self) -> str:
        return "Valhalla"

    # @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api(self, origins: List[List[float]], destinations: List[List[float]],
                  config: CalConfig) -> tuple[None, str] | tuple[Any, str]:
        # 出发点支持100个坐标对，坐标对用“| ”分隔；经度和纬度用","分隔
        sources = [{"lon": o[0], "lat": o[1]} for o in origins]
        targets = [{"lon": o[0], "lat": o[1]} for o in destinations]

        params = {"sources": sources, "targets": targets, "costing": "auto", "verbose": False}
        other_params = config.backend_params
        if "costing" in other_params:
            params["costing"] = other_params['costing']
        if "costing_options" in other_params:
            params["costing_options"] = other_params['costing_options']

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(config.valhalla_url, headers=headers, json=params, timeout=config.timeout)
            if response.status_code == 200:
                response = response.json()
                return response, ""
            return None, response.reason

        except Exception as e:
            raise e

    def solve(self, variable: CalVariable, config: CalConfig) -> CalResult:
        origins = variable.origins
        destinations = variable.destinations
        coord_type = variable.coord_type
        # 1. 转换坐标
        target_type = "wgs84"
        origins = transform_coords(origins, coord_type, target_type)
        destinations = transform_coords(destinations, coord_type, target_type)

        # 2. 调用API获取距离、时间格式化字符串
        dist_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        dur_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        try:
            response, message = self._call_api(origins, destinations, config)

            if response is None:
                return CalResult(self.name, "failed", message, variable, None, None)

            if "distances" in response["sources_to_targets"]:
                dist_mat = np.array(response["sources_to_targets"]["distances"]).T.tolist()
            if "durations" in response["sources_to_targets"]:
                dur_mat = np.array(response["sources_to_targets"]["durations"]).T.tolist()

            return CalResult(self.name, "succeed", "succeed", variable, dist_mat, dur_mat)
        except Exception as e:
            return CalResult(self.name, "failed", str(e), variable, None, None)


class TomTomMethod(CalMethod):
    @property
    def name(self) -> str:
        return "TomTom"

    # @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api(self, origins: List[List[float]], destinations: List[List[float]],
                  config: CalConfig) -> tuple[None, str] | tuple[Any, str]:
        params = {"key": config.tomtom_key}
        # 出发点支持100个坐标对，坐标对用“| ”分隔；经度和纬度用","分隔
        origins = [{"point": {"longitude": o[0], "latitude": o[1]}} for o in origins]
        destinations = [{"point": {"longitude": o[0], "latitude": o[1]}} for o in destinations]

        data = {"origins": origins, "destinations": destinations}
        other_params = config.backend_params
        if "options" in other_params:
            data["options"] = other_params['options']

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(config.tomtom_url, headers=headers, params=params, json=data, timeout=config.timeout)
            # requests调用TomTom的API时，可能无法验证服务器的 SSL 证书，建议安装/更新证书，此处可临时禁用 SSL 验证（仅用于测试/调试）
            # response = requests.post(config.tomtom_url, headers=headers, params=params, json=data, timeout=config.timeout, verify=False)
            if response.status_code == 200:
                response = response.json()
                return response, ""
            return None, response.reason

        except Exception as e:
            raise e

    def solve(self, variable: CalVariable, config: CalConfig) -> CalResult:
        origins = variable.origins
        destinations = variable.destinations
        coord_type = variable.coord_type
        # 1. 转换坐标
        target_type = "wgs84"
        origins = transform_coords(origins, coord_type, target_type)
        destinations = transform_coords(destinations, coord_type, target_type)

        # 2. 调用API获取距离、时间格式化字符串
        dist_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        dur_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        try:
            response, message = self._call_api(origins, destinations, config)

            if response is None:
                return CalResult(self.name, "failed", message, variable, None, None)

            distances = []
            durations = []
            for result in response["data"]:
                if "routeSummary" in result:
                    distances.append(result["routeSummary"]["lengthInMeters"])
                    durations.append(result["routeSummary"]["travelTimeInSeconds"])
                else:
                    distances.append(-1)
                    durations.append(-1)

            dist_mat = np.array(distances).reshape((len(origins), len(destinations))).T.tolist()
            dur_mat = np.array(durations).reshape((len(origins), len(destinations))).T.tolist()

            return CalResult(self.name, "succeed", "succeed", variable, dist_mat, dur_mat)
        except Exception as e:
            return CalResult(self.name, "failed", str(e), variable, None, None)


class BaiduMethod(CalMethod):
    @property
    def name(self) -> str:
        return "Baidu"

    # @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api(self, origins: List[List[float]], destinations: List[List[float]],
                  config: CalConfig) -> tuple[None, str] | tuple[None, Any] | tuple[Any, str]:
        params = {"ak": config.baidu_key}
        other_params = config.backend_params
        # ret_straight_dist为1时计算直线距离（按照60km/h计算duration），默认为0
        if "ret_straight_dist" in other_params:
            params["ret_straight_dist"] = other_params["ret_straight_dist"]

        # 出发点支持100个坐标对，坐标对用“| ”分隔；经度和纬度用","分隔
        origins = "|".join([f"{p[1]},{p[0]}" for p in origins])
        destinations = "|".join([f"{p[1]},{p[0]}" for p in destinations])
        params.update({"origins": origins, "destinations": destinations})
        try:
            response = requests.get(config.baidu_url, params=params, timeout=config.timeout)
            if response.status_code == 200:
                response = response.json()
                if response["status"] == 0:
                    return response, ""
                else:
                    print(response["message"])
                    return None, response["message"]
            return None, response.reason

        except Exception as e:
            raise e

    def solve(self, variable: CalVariable, config: CalConfig) -> CalResult:
        origins = variable.origins
        destinations = variable.destinations
        coord_type = variable.coord_type
        # 1. 转换坐标
        target_type = "bd09ll"
        origins = transform_coords(origins, coord_type, target_type)
        destinations = transform_coords(destinations, coord_type, target_type)

        # 2. 调用API获取距离、时间格式化字符串
        dist_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        dur_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        try:
            response, message = self._call_api(origins, destinations, config)

            if response is None:
                return CalResult(self.name, "failed", message, variable, None, None)

            distances = []
            durations = []
            for result in response["result"]:
                distances.append(result["distance"]["value"])
                durations.append(result["duration"]["value"])

            dist_mat = np.array(distances).reshape((len(origins), len(destinations))).T.tolist()
            dur_mat = np.array(durations).reshape((len(origins), len(destinations))).T.tolist()

            return CalResult(self.name, "succeed", "succeed", variable, dist_mat, dur_mat)
        except Exception as e:
            return CalResult(self.name, "failed", str(e), variable, None, None)


class AmapMethod(CalMethod):
    @property
    def name(self) -> str:
        return "Amap"

    # @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api(self, origins: List[List[float]], destinations: List[List[float]], config: CalConfig) -> tuple[
        list[Any], list[Any]]:
        params = {"key": config.amap_key}
        other_params = config.backend_params
        # type为0时计算直线距离（duration为0），默认为1
        if "type" in other_params:
            params["type"] = other_params["type"]

        # 出发点支持100个坐标对，坐标对用“| ”分隔；经度和纬度用","分隔
        # 目的点经度和纬度用","分隔
        origins = "|".join([f"{p[0]},{p[1]}" for p in origins])
        responses = []
        messages = []
        for destination in destinations:
            destination = ','.join(map(str, destination))
            params.update({"origins": origins, "destination": destination})
            try:
                response = requests.get(config.amap_url, params=params, timeout=config.timeout)
                if response.status_code == 200:
                    response = response.json()
                    if response["status"] == '1':
                        responses.append(response)
                        messages.append("")
                    else:
                        print(response["info"])
                        responses.append(None)
                        messages.append(response["info"])
                else:
                    responses.append(None)
                    messages.append(response.reason)

            except Exception as e:
                print(f'{origins}--{destination}获取距离矩阵、时间矩阵失败：{e}')
                messages.append(str(e))
                responses.append(None)

        return responses, messages

    def solve(self, variable: CalVariable, config: CalConfig) -> CalResult:
        origins = variable.origins
        destinations = variable.destinations
        coord_type = variable.coord_type
        # 1. 转换坐标
        target_type = "gcj02"
        origins = transform_coords(origins, coord_type, target_type)
        destinations = transform_coords(destinations, coord_type, target_type)

        # 2. 调用API获取距离、时间格式化字符串
        dist_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        dur_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        try:
            responses, messages = self._call_api(origins, destinations, config)
            message = ""
            for i, response in enumerate(responses):
                if response is None:
                    message += f"调用API求解第{i}个目标点的距离、时间时发生异常，信息为：{messages[i]}"
                    continue

                distance = [-1.0] * len(origins)
                duration = [-1.0] * len(origins)
                for j, result in enumerate(response["results"]):
                    distance[j] = float(result["distance"])
                    duration[j] = float(result["duration"])

                dist_mat[i] = distance
                dur_mat[i] = duration

            return CalResult(self.name, "succeed", message, variable, dist_mat, dur_mat)
        except Exception as e:
            return CalResult(self.name, "failed", str(e), variable, None, None)


class HaversineMethod(CalMethod):
    @property
    def name(self) -> str:
        return "Haversine"

    @staticmethod
    def _cal_haversine_dis(cur_point: List[float], next_point: List[float]) -> float:
        # in kilometers
        AVG_EARTH_RADIUS = 6371.0088

        lng1, lat1 = cur_point
        lng2, lat2 = next_point
        # 转换为弧度
        lng1_rad, lat1_rad, lng2_rad, lat2_rad = map(math.radians, [lng1, lat1, lng2, lat2])

        d_lng = lng2_rad - lng1_rad
        d_lat = lat2_rad - lat1_rad
        d = math.sin(d_lat * 0.5) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lng * 0.5) ** 2
        # in kilometers
        d = 2 * AVG_EARTH_RADIUS * math.asin(math.sqrt(d))
        return round(d * 1000, 2)

    def solve(self, variable: CalVariable, config: CalConfig) -> CalResult:
        origins = variable.origins
        destinations = variable.destinations
        coord_type = variable.coord_type

        # 1. 转换坐标
        target_type = "wgs84"
        origins = transform_coords(origins, coord_type, target_type)
        destinations = transform_coords(destinations, coord_type, target_type)

        # 2. 调用API获取距离、时间格式化字符串
        dist_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]
        # dur_mat = [[-1.0] * len(origins) for _ in range(len(destinations))]

        for i in range(len(destinations)):
            for j in range(len(origins)):
                if i == j:
                    dist_mat[i][j] = 0.0
                    continue

                dist_mat[i][j] = HaversineMethod._cal_haversine_dis(destinations[i], origins[j])

        return CalResult(self.name, "succeed", "succeed", variable, dist_mat, None)


# =========================
# 工厂模式：根据配置创建策略
# =========================

class MethodFactory:
    _registry = {
        "google": GoogleMethod,
        "ors": ORSMethod,
        "valhalla": ValhallaMethod,
        "tomtom": TomTomMethod,
        "baidu": BaiduMethod,
        "amap": AmapMethod,
        "haversine": HaversineMethod
    }

    @classmethod
    def create(cls, method_name: str) -> CalMethod:
        key = method_name.strip().lower()
        if key not in cls._registry:
            raise ValueError(f"Unsupported solver: {method_name}")

        return cls._registry[key]()


if __name__ == '__main__':

    pass