from coordTransform import wgs84_to_gcj02, wgs84_to_bd09, gcj02_to_wgs84, gcj02_to_bd09, bd09_to_wgs84, bd09_to_gcj02
from typing import List


def transform_coords(points: List[List[float]], from_type: str, to_type: str) -> List[List[float]]:
    if from_type == to_type:
        return points

    converted_list = []
    for lon, lat in points:
        converted = [lon, lat]
        try:
            if from_type == "wgs84" and to_type == "gcj02":
                converted = wgs84_to_gcj02(lon, lat)
            elif from_type == "wgs84" and to_type == "bd09ll":
                converted = wgs84_to_bd09(lon, lat)
            elif from_type == "gcj02" and to_type == "wgs84":
                converted = gcj02_to_wgs84(lon, lat)
            elif from_type == "gcj02" and to_type == "bd09ll":
                converted = gcj02_to_bd09(lon, lat)
            elif from_type == "bd09ll" and to_type == "wgs84":
                converted = bd09_to_wgs84(lon, lat)
            elif from_type == "bd09ll" and to_type == "gcj02":
                converted = bd09_to_gcj02(lon, lat)
            else:
                # 暂不支持的转换，原样返回并警告
                print(f"No converter for {from_type} -> {to_type}, using original.")
            converted_list.append(converted)
        except Exception as e:
            print(f"Coord transform error for point [{lon}, {lat}]: {e}")
            converted_list.append(converted)
    return converted_list


if __name__ == '__main__':
    coords = [[121.324471, 31.254744]]
    coords_type = ['wgs84', 'gcj02', 'bd09ll']
    converted = transform_coords(coords, coords_type[2], coords_type[1])
    print(converted)