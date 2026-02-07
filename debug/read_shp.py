try:
    import geopandas as gpd
    import matplotlib.pyplot as plt
    import numpy as np

    shp_path = "agentSimulation/uav_simulation/shpsimulation/gis/gis数据/selection_SZ_building_for_UAV_test.shp"
    print(f"正在读取: {shp_path}")

    gdf = gpd.read_file(shp_path)
    print("读取成功！")
    print(f"总要素数量: {len(gdf)}")
    print("字段列表:", gdf.columns.tolist())
    print("前几行数据:")
    print(gdf.head())

    # 检查是否有高度字段
    possible_height_cols = [c for c in gdf.columns if 'height' in c.lower() or 'floor' in c.lower()]
    print(f"疑似高度字段: {possible_height_cols}")

    # 获取边界范围
    bounds = gdf.total_bounds
    print(f"地理范围 (minx, miny, maxx, maxy): {bounds}")

except ImportError:
    print("Error: geopandas 未安装。请运行 `pip install geopandas`")
except Exception as e:
    print(f"Error: {e}")
