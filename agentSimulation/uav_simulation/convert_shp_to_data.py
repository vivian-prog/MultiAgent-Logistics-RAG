import numpy as np
import shapefile
import math
import os

# ---------------- 配置 ----------------
SHP_PATH = "agentSimulation/uav_simulation/shpsimulation/gis/gis数据/selection_SZ_building_for_UAV_test.shp"
OUTPUT_NPY = "agentSimulation/uav_simulation/map1_buildings.npy"

# 深圳参考原点 (必须与 core.py 保持一致)
ORIGIN_LNG = 113.70
ORIGIN_LAT = 22.40
SCALE_FACTOR = 1000.0

def mercator_to_wgs84(x, y):
    lon = (x / 20037508.34) * 180
    lat = (y / 20037508.34) * 180
    lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180)) - math.pi / 2)
    return lon, lat

def gps_to_grid(lng, lat):
    grid_x = (float(lng) - ORIGIN_LNG) * SCALE_FACTOR
    grid_y = (float(lat) - ORIGIN_LAT) * SCALE_FACTOR
    return grid_x, grid_y

def main():
    if not os.path.exists(SHP_PATH):
        print(f"Error: SHP file not found at {SHP_PATH}")
        return

    print(f"Reading SHP: {SHP_PATH}")
    sf = shapefile.Reader(SHP_PATH)

    shapes = sf.shapes()
    records = sf.records()

    print(f"Found {len(shapes)} buildings.")

    # 1. 扫描边界
    max_gx, max_gy = 0, 0
    converted_shapes = []

    for shp in shapes:
        grid_points = []
        for x, y in shp.points:
            lon, lat = mercator_to_wgs84(x, y)
            gx, gy = gps_to_grid(lon, lat)
            grid_points.append((gx, gy))
            max_gx = max(max_gx, gx)
            max_gy = max(max_gy, gy)
        converted_shapes.append(grid_points)

    map_w = int(max_gx) + 10
    map_h = int(max_gy) + 10

    print(f"Calculated Map Size: {map_w} x {map_h}")

    # 2. 栅格化
    buildings_location = np.zeros((map_w, map_h), dtype=np.float32)

    for i, points in enumerate(converted_shapes):
        try:
            height = float(records[i][1])
        except:
            height = 10.0

        poly_min_x = max(0, int(min(p[0] for p in points)))
        poly_max_x = min(map_w - 1, int(max(p[0] for p in points)))
        poly_min_y = max(0, int(min(p[1] for p in points)))
        poly_max_y = min(map_h - 1, int(max(p[1] for p in points)))

        buildings_location[poly_min_x:poly_max_x+1, poly_min_y:poly_max_y+1] = height

    # 3. 保存
    np.save(OUTPUT_NPY, buildings_location)
    print(f"Saved building data to {OUTPUT_NPY}")
    print("Done.")

if __name__ == "__main__":
    main()
