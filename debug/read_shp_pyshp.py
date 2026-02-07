try:
    import shapefile

    shp_path = "agentSimulation/uav_simulation/shpsimulation/gis/gis数据/selection_SZ_building_for_UAV_test.shp"
    print(f"正在读取 (pyshp): {shp_path}")

    sf = shapefile.Reader(shp_path)
    print(f"读取成功！形状类型: {sf.shapeTypeName}")
    print(f"记录数量: {len(sf)}")

    fields = [f[0] for f in sf.fields[1:]] # 跳过DeletionFlag
    print("字段列表:", fields)

    # 读取第一条记录
    print("第一条记录:", sf.record(0))

    # 检查边界
    print(f"边界: {sf.bbox}")

except ImportError:
    print("Error: pyshp (shapefile) 未安装。请运行 `pip install pyshp`")
except Exception as e:
    print(f"Error: {e}")
