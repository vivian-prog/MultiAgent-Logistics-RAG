import csv
import random
import sys
import gym
from gym import spaces
import numpy as np
import shapefile  # 需安装：pip install pyshp
import argparse
from typing import List, Tuple, Dict

# -------------------------- 核心配置与工具函数 --------------------------
class EnvConfig:
    """环境配置类"""
    def __init__(self):
        self.map_w = 0          # 地图宽度
        self.map_h = 0          # 地图高度
        self.map_z = 5          # 地图最大高度（默认5）
        self.uav_r = 0.3        # 无人机半径
        self.max_speed = 0.3    # 无人机最大速度
        self.volatility = 0.02  # 速度随机波动
        self.tolerance = 0.1    # 到达目标点的容差

# -------------------------- Shp文件解析工具 --------------------------
import shapefile
import numpy as np
from typing import Tuple, List

def parse_shp_file(shp_path: str, grid_resolution: float = 1.0) -> Tuple[np.ndarray, int, int]:
    """
    修复版Shp解析函数：将地理坐标映射到网格坐标，避免超大数组
    Args:
        shp_path: Shp文件路径
        grid_resolution: 网格分辨率（每个网格代表的实际距离，单位：米）
    Returns:
        buildings_location: 2D数组 [grid_w, grid_h]，值为对应网格的建筑高度
        grid_w: 网格宽度（小范围，如50/100）
        grid_h: 网格高度（小范围，如50/100）
    """
    # 1. 读取Shp文件
    sf = shapefile.Reader(shp_path)
    shapes = sf.shapes()
    records = sf.records()
    
    if len(shapes) == 0 or len(records) == 0:
        raise ValueError("Shp文件无数据！")
    
    # 2. 提取Shp的地理坐标范围，计算偏移量（将大坐标映射到0开始）
    all_x = []
    all_y = []
    for shape in shapes:
        x = [p[0] for p in shape.points]
        y = [p[1] for p in shape.points]
        all_x.extend(x)
        all_y.extend(y)
    
    # 地理坐标的最小/最大值
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    # 3. 计算网格尺寸（基于分辨率，将地理范围转为小网格）
    grid_w = int((max_x - min_x) / grid_resolution) + 1
    grid_h = int((max_y - min_y) / grid_resolution) + 1
    
    # 限制网格最大尺寸（避免极端情况）
    max_grid_size = 1000  # 最大1000x1000网格
    if grid_w > max_grid_size or grid_h > max_grid_size:
        grid_w = max_grid_size
        grid_h = max_grid_size
        print(f"警告：网格尺寸过大，自动限制为 {max_grid_size}x{max_grid_size}")
    
    # 4. 初始化建筑高度网格（默认0）
    buildings_location = np.zeros((grid_w, grid_h), dtype=np.float32)
    
    # 5. 定位height字段索引
    field_names = [f[0].lower() for f in sf.fields[1:]]
    height_field_idx = -1
    for idx, name in enumerate(field_names):
        if name in ["height", "高度", "h", "elev"]:
            height_field_idx = idx
            break
    if height_field_idx == -1:
        raise ValueError(f"未找到height字段！现有字段：{field_names}")
    
    # 6. 填充建筑高度（地理坐标→网格坐标映射）
    for shape, record in zip(shapes, records):
        try:
            height = float(record[height_field_idx])
            if height < 0:
                continue  # 跳过无效高度
        except (ValueError, IndexError):
            continue
        
        # 获取建筑的边界范围（地理坐标）
        bbox = shape.bbox  # (xmin, ymin, xmax, ymax)
        xmin, ymin, xmax, ymax = bbox
        
        # 转换为网格坐标（偏移+缩放）
        grid_xmin = int((xmin - min_x) / grid_resolution)
        grid_ymin = int((ymin - min_y) / grid_resolution)
        grid_xmax = int((xmax - min_x) / grid_resolution)
        grid_ymax = int((ymax - min_y) / grid_resolution)
        
        # 确保网格坐标在有效范围内
        grid_xmin = max(0, min(grid_xmin, grid_w-1))
        grid_ymin = max(0, min(grid_ymin, grid_h-1))
        grid_xmax = max(0, min(grid_xmax, grid_w-1))
        grid_ymax = max(0, min(grid_ymax, grid_h-1))
        
        # 填充建筑高度到对应网格
        for x in range(grid_xmin, grid_xmax + 1):
            for y in range(grid_ymin, grid_ymax + 1):
                buildings_location[x][y] = max(buildings_location[x][y], height)
    
    print(f"Shp解析完成：地理范围 [{min_x:.2f},{max_x:.2f}]x[{min_y:.2f},{max_y:.2f}]")
    print(f"网格尺寸：{grid_w}x{grid_h}，分辨率：{grid_resolution}米/网格")
    return buildings_location, grid_w, grid_h, min_x, min_y

# -------------------------- CSV解析工具 --------------------------
def parse_csv_file(csv_path: str) -> Tuple[List[int], List[np.ndarray], List[np.ndarray]]:
    """
    解析CSV文件，格式：无人机id,起始点x,起始点y,起始点z,终点x,终点y,终点z
    Args:
        csv_path: CSV文件路径
    Returns:
        uav_ids: 无人机ID列表
        start_points: 起始点列表 (n,3)
        end_points: 终点列表 (n,3)
    """
    uav_ids = []
    start_points = []
    end_points = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # 兼容两种格式：列名包含"起始点"/"终点" 或 直接x/y/z
        for row in reader:
            # 解析无人机ID
            uav_id = int(row['无人机id'] if '无人机id' in row else row['id'])
            # 解析起始点
            if '起始点x' in row:
                start_x = float(row['起始点x'])
                start_y = float(row['起始点y'])
                start_z = float(row['起始点z'])
            else:
                start_x = float(row['start_x'])
                start_y = float(row['start_y'])
                start_z = float(row['start_z'])
            # 解析终点
            if '终点x' in row:
                end_x = float(row['终点x'])
                end_y = float(row['终点y'])
                end_z = float(row['终点z'])
            else:
                end_x = float(row['end_x'])
                end_y = float(row['end_y'])
                end_z = float(row['end_z'])
            
            uav_ids.append(uav_id)
            start_points.append(np.array([start_x, start_y, start_z], dtype=np.float32))
            end_points.append(np.array([end_x, end_y, end_z], dtype=np.float32))
    
    return uav_ids, start_points, end_points

# -------------------------- 无人机环境核心类 --------------------------
class UAVEnv(gym.Env):
    def __init__(self, uav_num: int, map_w: int, map_h: int, map_z: int, 
                 init_states: np.ndarray, buildings_location: np.ndarray, config: EnvConfig):
        super(UAVEnv, self).__init__()
        # 基础配置
        self.uav_num = uav_num
        self.map_w = map_w
        self.map_h = map_h
        self.map_z = map_z
        self.buildings_location = buildings_location
        self.config = config
        
        # 无人机状态：[x, y, z, vx, vy, vz, sensor_status] * uav_num
        self.state = init_states.copy()
        # 轨迹记录
        self.position_pool = [[] for _ in range(self.uav_num)]
        
        # 动作空间：[vx, vy, vz, sensor_status] * uav_num
        self.action_space = spaces.Box(
            low=np.array([-config.max_speed, -config.max_speed, -config.max_speed, 0] * uav_num),
            high=np.array([config.max_speed, config.max_speed, config.max_speed, 1] * uav_num),
            dtype=np.float32
        )
        
        # 观测空间
        self.observation_space = spaces.Box(
            low=np.array([0, 0, 0, -config.max_speed, -config.max_speed, -config.max_speed, 0] * uav_num),
            high=np.array([map_w, map_h, map_z, config.max_speed, config.max_speed, config.max_speed, 1] * uav_num),
            dtype=np.float32
        )

    def recorder(self, env_t: int):
        """记录无人机轨迹（每2步记录一次）"""
        if env_t % 2 == 0:
            for i in range(self.uav_num):
                x, y, z = self.state[i][:3]
                self.position_pool[i].append([x, y, z, env_t])

    def step(self, actions: np.ndarray, env_t: int) -> Tuple[np.ndarray, float, bool, dict]:
        """执行动作，更新无人机状态"""
        actions = np.array(actions).reshape(self.uav_num, 4)
        
        for i in range(self.uav_num):
            # 更新位置（x/y/z = 原位置 + 速度*时间步，假设t=1）
            self.state[i][0] += actions[i][0]
            self.state[i][1] += actions[i][1]
            self.state[i][2] += actions[i][2]
            # 更新速度
            self.state[i][3:6] = actions[i][:3]
            # 更新传感器状态
            self.state[i][6] = actions[i][3]
        
        # 记录轨迹
        self.recorder(env_t)
        
        return self.state.copy(), 0.0, False, {}

    def reset(self) -> np.ndarray:
        """重置环境"""
        self.state = np.zeros((self.uav_num, 7), dtype=np.float32)
        return self.state.copy()

# -------------------------- 无人机运动控制器 --------------------------
class MvController:
    def __init__(self, config: EnvConfig, map_w: int, map_h: int, map_z: int, buildings_location: np.ndarray):
        self.config = config
        self.map_w = map_w
        self.map_h = map_h
        self.map_z = map_z
        self.buildings_location = buildings_location

    def move_to(self, uav_pos: np.ndarray, aim_pos: np.ndarray) -> Tuple[float, float, float]:
        """计算朝向目标点的速度"""
        x_diff = aim_pos[0] - uav_pos[0]
        y_diff = aim_pos[1] - uav_pos[1]
        z_diff = aim_pos[2] - uav_pos[2]
        distance = np.sqrt(x_diff**2 + y_diff**2 + z_diff**2)
        
        # 避免除零
        if distance < 1e-6:
            return 0.0, 0.0, 0.0
        
        # 归一化速度 + 随机波动
        vx_normalized = x_diff / distance
        vy_normalized = y_diff / distance
        vz_normalized = z_diff / distance
        
        vx = vx_normalized * self.config.max_speed + random.gauss(0, self.config.volatility)
        vy = vy_normalized * self.config.max_speed + random.gauss(0, self.config.volatility)
        vz = vz_normalized * self.config.max_speed + random.gauss(0, self.config.volatility)
        
        return vx, vy, vz

    def is_arrive(self, uav_pos: np.ndarray, aim_pos: np.ndarray) -> bool:
        """判断是否到达目标点"""
        x_error = abs(uav_pos[0] - aim_pos[0])
        y_error = abs(uav_pos[1] - aim_pos[1])
        z_error = abs(uav_pos[2] - aim_pos[2])
        return x_error < self.config.tolerance and y_error < self.config.tolerance and z_error < self.config.tolerance

    def will_enter_buildings(self, uav_pos: np.ndarray, action: List[float]) -> bool:
        """判断下一步是否会进入建筑"""
        next_x = uav_pos[0] + action[0]
        next_y = uav_pos[1] + action[1]
        next_z = uav_pos[2] + action[2]
        
        # 转换为网格坐标
        grid_x = int(round(next_x))
        grid_y = int(round(next_y))
        
        # 检查网格是否有效
        if 0 <= grid_x < self.map_w and 0 <= grid_y < self.map_h:
            building_height = self.buildings_location[grid_x][grid_y]
            return next_z - self.config.uav_r <= building_height
        return False

    def is_outside_map(self, uav_pos: np.ndarray, action: List[float]) -> bool:
        """判断下一步是否超出地图边界"""
        next_x = uav_pos[0] + action[0]
        next_y = uav_pos[1] + action[1]
        next_z = uav_pos[2] + action[2]
        
        return (next_x < 0 or next_x >= self.map_w or
                next_y < 0 or next_y >= self.map_h or
                next_z < 0 or next_z >= self.map_z)

    def move_up(self) -> Tuple[float, float, float]:
        """向上移动（避障）"""
        return 0.0, 0.0, 0.2

# -------------------------- 主函数 --------------------------
def main():
    # 1. 解析命令行参数 cmd:python uav_simulation_shp.py --csv /UAVCSVData/uav_test_config.csv --shp gis/gis数据/selection_SZ_building_for_UAV_test.shp --max_steps 2000
    parser = argparse.ArgumentParser(description='无人机运动模拟（无3D渲染）')
    parser.add_argument('--csv', required=True, help='无人机配置CSV文件路径')
    parser.add_argument('--shp', required=True, help='地图Shp文件路径')
    parser.add_argument('--max_steps', type=int, default=1000, help='最大模拟步数')
    args = parser.parse_args()

    # 2. 初始化配置
    config = EnvConfig()
    
    # 3. 解析Shp文件（获取建筑高度网格和地图尺寸）
    print(f"正在解析Shp文件: {args.shp}")
    buildings_location, map_w, map_h, min_x, min_y = parse_shp_file(args.shp)
    print(f"地图尺寸: {map_w}x{map_h}, 建筑网格数: {buildings_location.shape}")

    # 4. 解析CSV文件（获取无人机ID、起始点、终点）
    print(f"正在解析CSV文件: {args.csv}")
    uav_ids, start_points, end_points = parse_csv_file(args.csv)
    uav_num = len(uav_ids)
    print(f"解析到 {uav_num} 架无人机")

    # 5. 初始化无人机初始状态
    # 初始状态格式：[x, y, z, vx, vy, vz, sensor_status]
    init_states = np.zeros((uav_num, 7), dtype=np.float32)
    for i in range(uav_num):
        init_states[i][:3] = start_points[i]  # 初始位置
        init_states[i][3:6] = [0.0, 0.0, 0.0] # 初始速度
        init_states[i][6] = 0.0               # 初始传感器状态

    # 6. 初始化环境和控制器
    env = UAVEnv(
        uav_num=uav_num,
        map_w=map_w,
        map_h=map_h,
        map_z=config.map_z,
        init_states=init_states,
        buildings_location=buildings_location,
        config=config
    )
    controller = MvController(
        config=config,
        map_w=map_w,
        map_h=map_h,
        map_z=config.map_z,
        buildings_location=buildings_location
    )

    # 7. 模拟主循环
    env_t = 0
    actions = np.zeros((uav_num, 4), dtype=np.float32)
    flag = [False] * uav_num  # 标记无人机是否到达目标点
    done = False

    print("\n开始无人机运动模拟...")
    while not done and env_t < args.max_steps:
        # 7.1 为每个无人机计算动作
        for i in range(uav_num):
            if flag[i]:  # 已到达目标点，停止运动
                actions[i] = [0.0, 0.0, 0.0, 0.0]
                continue

            # 获取当前无人机位置和目标点
            uav_pos = env.state[i][:3]
            aim_pos = end_points[i]

            # 计算朝向目标点的速度
            vx, vy, vz = controller.move_to(uav_pos, aim_pos)

            # 检查是否到达目标点
            if controller.is_arrive(uav_pos, aim_pos):
                flag[i] = True
                print(f"[{env_t}] 无人机 {uav_ids[i]} 到达目标点: {aim_pos}")
                actions[i] = [0.0, 0.0, 0.0, 0.0]
                continue

            # 边界检测：超出地图则停止
            if controller.is_outside_map(uav_pos, [vx, vy, vz]):
                vx, vy, vz = 0.0, 0.0, 0.0
                print(f"[{env_t}] 无人机 {uav_ids[i]} 即将出界，停止运动")

            # 避障检测：即将进入建筑则向上飞
            if controller.will_enter_buildings(uav_pos, [vx, vy, vz]):
                vx, vy, vz = controller.move_up()
                print(f"[{env_t}] 无人机 {uav_ids[i]} 检测到建筑，向上避障")

            # 保存动作
            actions[i] = [vx, vy, vz, 0.0]

        # 7.2 执行动作，更新状态
        obs, reward, _, info = env.step(actions, env_t)

        # 7.3 打印进度（每100步）
        if env_t % 100 == 0:
            print(f"[{env_t}] 模拟进度: {env_t}/{args.max_steps}, 已到达目标点: {sum(flag)}/{uav_num}")

        # 7.4 检查是否所有无人机都到达目标点
        if all(flag):
            print(f"\n所有无人机已到达目标点，模拟结束（步数: {env_t}）")
            done = True

        # 7.5 步数+1
        env_t += 1

    # 8. 输出最终结果
    print("\n===== 模拟结果 =====")
    print(f"总模拟步数: {env_t}")
    print(f"到达目标点的无人机数: {sum(flag)}/{uav_num}")
    
    # 输出每个无人机的最终位置
    for i in range(uav_num):
        final_pos = env.state[i][:3]
        aim_pos = end_points[i]
        distance = np.sqrt(
            (final_pos[0]-aim_pos[0])**2 + 
            (final_pos[1]-aim_pos[1])**2 + 
            (final_pos[2]-aim_pos[2])**2
        )
        # 网格坐标（代码当前输出的坐标）
        grid_x, grid_y, grid_z = env.state[i][:3]
        
        # 转换为原始地理坐标
        orig_x = grid_x * 1.0 + min_x
        orig_y = grid_y * 1.0 + min_y
        orig_z = grid_z  # Z轴保持不变
        
        # 输出两种坐标
        print(f"无人机 {uav_ids[i]}:")
        print(f"  网格坐标：X={grid_x:.2f}, Y={grid_y:.2f}, Z={grid_z:.2f}")
        print(f"  原始地理坐标：X={orig_x:.2f}, Y={orig_y:.2f}, Z={orig_z:.2f}")
        status = "已到达" if flag[i] else f"未到达（距离: {distance:.2f}）"
        print(f"无人机 {uav_ids[i]}: 最终位置 {final_pos}, 目标点 {aim_pos}, 状态: {status}")

if __name__ == "__main__":
    main()