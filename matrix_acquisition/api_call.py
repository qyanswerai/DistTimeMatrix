from pydantic import BaseModel, ValidationError
from typing import List, Dict, Any, Optional
from matrix_acquisition.api_core import CalConfig, CalVariable, CalMethod, CalResult, MethodFactory
from utils.config_parse import get_api_key

# =========================
# 统一入口：业务层调用
# =========================
class SolverEngineItem(BaseModel):
    origins: List[List[float]]
    destinations : List[List[float]]
    coord_type: str
    method_name: str
    backend_params: object = None
    timeout: int = 10
    key: str = ""


class SolverEngine:
    method_domain = ['google', 'ors', 'valhalla', 'tomtom', 'baidu', 'amap', 'haversine']
    registry = {
        "google": "wgs84",
        "ors": "wgs84",
        "valhalla": "wgs84",
        "tomtom": "wgs84",
        "baidu": "bd09ll",
        "amap": "gcj02",
        "haversine": "wgs84"
    }

    def __init__(self, method: CalMethod):
        self.method = method

    def solve(self, variable: CalVariable, config: CalConfig) -> CalResult:
        # 可在这里加：
        # - 模型合法性检查
        # - 统一日志
        # - 统计耗时
        # - 异常包装
        print(f"[Engine] use solver = {self.method.name}")
        result = self.method.solve(variable, config)
        print(f"[Engine] status = {result.status}")
        print(f"[Engine] message = {result.message}")

        return result

def process(inputs):
    SolverEngineItem(**inputs)

    origins = inputs["origins"]
    destinations = inputs["destinations"]
    coord_type = inputs["coord_type"]
    method_name = inputs["method_name"]
    key = inputs["key"]

    variable = CalVariable(origins, destinations, coord_type)

    if method_name == 'valhalla' or method_name == 'haversine':
        config = CalConfig()
    else:
        if "key" not in inputs:
            raise Exception("Missing 'key' in inputs")

        config = CalConfig(**{method_name + '_key' : key})

    if method_name in SolverEngine.method_domain:
        if coord_type == SolverEngine.registry[method_name]:
            print("method 与 coord type匹配，可直接调用API计算distance及duration")
        else:
            print("method 与 coord type不匹配，调用API前会进行坐标转换，然后计算distance及duration")
        method = MethodFactory.create(method_name)

        engine = SolverEngine(method)
        result = engine.solve(variable, config)

        print("\n=== Final Result ===")
        print(f"[Engine] distance matrix = {result.distance_matrix}")
        print(f"[Engine] duration matrix = {result.duration_matrix}")

        return result
    else:
        print(f"暂不支持{method_name}，需换用{SolverEngine.method_domain}中的任一方法计算")
        return None


if __name__ == "__main__":
    pass