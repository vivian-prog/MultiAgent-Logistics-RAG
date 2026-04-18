# uav_simulation/core.py
import random
import sys
import gym
from gym import spaces
import numpy as np
import math
import os
import shapefile  # 需安装: pip install pyshp
from typing import Tuple, List

# -------------------------- SHP 解析工具 (从 uav_simulation_shp.py移植) --------------------------
def parse_shp_file(shp_path: str, grid_resolution: float = 1.0) -> Tuple[np.ndarray, int, int, float, float]:
    """
    解析Shp文件，将地理坐标映射到网格坐标
    Args:
        shp_path: Shp文件路径
        grid_resolution: 网格分辨率（米/网格）
    Returns:
        buildings_location: 2D数组 [grid_w, grid_h]
        grid_w, grid_h: 网格宽高
        min_x, min_y: 地理坐标偏移量原点
    """
    if not os.path.exists(shp_path):
        raise FileNotFoundError(f"SHP file not found: {shp_path}")

    sf = shapefile.Reader(shp_path)
    shapes = sf.shapes()
    records = sf.records()
    
    if len(shapes) == 0 or len(records) == 0:
        # 如果SHP为空，返回一个小的空地图，避免崩溃
        return np.zeros((50, 50)), 50, 50, 0.0, 0.0
    
    # 1. 提取地理坐标范围
    all_x = []
    all_y = []
    for shape in shapes:
        x = [p[0] for p in shape.points]
        y = [p[1] for p in shape.points]
        all_x.extend(x)
        all_y.extend(y)
    
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    # 2. 计算网格尺寸
    grid_w = int((max_x - min_x) / grid_resolution) + 1
    grid_h = int((max_y - min_y) / grid_resolution) + 1
    
    # 限制最大尺寸防止内存溢出
    max_grid_size = 2000 
    if grid_w > max_grid_size or grid_h > max_grid_size:
        print(f"Warning: Grid size too large ({grid_w}x{grid_h}). Limiting to {max_grid_size}.")
        # 这里简单截断，实际生产环境可能需要更复杂的缩放逻辑
        grid_w = min(grid_w, max_grid_size)
        grid_h = min(grid_h, max_grid_size)

    buildings_location = np.zeros((grid_w, grid_h), dtype=np.float32)
    
    # 3. 查找高度字段
    field_names = [f[0].lower() for f in sf.fields[1:]]
    height_field_idx = -1
    for idx, name in enumerate(field_names):
        if name in ["height", "高度", "h", "elev", "z"]:
            height_field_idx = idx
            break
            
    # 4. 填充建筑高度
    for shape, record in zip(shapes, records):
        try:
            # 尝试获取高度，如果没有高度字段或解析失败，默认为0或一个基础高度
            height = 0.0
            if height_field_idx != -1 and height_field_idx < len(record):
                h_val = record[height_field_idx]
                if h_val is not None:
                    height = float(h_val)
            if height < 0: height = 0.0
        except (ValueError, IndexError, TypeError):
            continue
        
        bbox = shape.bbox # (xmin, ymin, xmax, ymax)
        xmin, ymin, xmax, ymax = bbox
        
        # 转换为网格坐标
        grid_xmin = int((xmin - min_x) / grid_resolution)
        grid_ymin = int((ymin - min_y) / grid_resolution)
        grid_xmax = int((xmax - min_x) / grid_resolution)
        grid_ymax = int((ymax - min_y) / grid_resolution)
        
        # 边界裁剪
        grid_xmin = max(0, min(grid_xmin, grid_w-1))
        grid_ymin = max(0, min(grid_ymin, grid_h-1))
        grid_xmax = max(0, min(grid_xmax, grid_w-1))
        grid_ymax = max(0, min(grid_ymax, grid_h-1))
        
        # 填充
        for x in range(grid_xmin, grid_xmax + 1):
            for y in range(grid_ymin, grid_ymax + 1):
                buildings_location[x][y] = max(buildings_location[x][y], height)
                
    return buildings_location, grid_w, grid_h, min_x, min_y

# -------------------------- 配置常量 --------------------------
# 固定 SHP 文件路径
SHP_FILE_PATH = os.path.join(os.path.dirname(__file__), "shpsimulation", "gis", "gis数据", "selection_SZ_building_for_UAV_test.shp")
GRID_RESOLUTION = 1.0  # 1米对应1个网格单位，或者根据SHP实际单位调整（如果是经纬度需要投影转换，这里假设SHP已是投影坐标或简化处理）

# UAV 物理参数
UAV_MAX_SPEED = 0.3    # 网格单位/步
UAV_VOLATILITY = 0.02
UAV_RADIUS = 0.3
UAV_TOLERANCE = 0.1
MAP_Z = 20             # 默认最大飞行高度

# -------------------------- 无人机环境类 --------------------------
class UAVEnv(gym.Env):
    def __init__(self, uav_num, map_w, map_h, map_z, Init_state, buildings_location):
        super(UAVEnv, self).__init__()
        self.uav_num = uav_num
        self.map_w = map_w
        self.map_h = map_h
        self.map_z = map_z
        self.buildings_location = buildings_location
        self.position_pool = [[] for _ in range(self.uav_num)]
        self.state = Init_state.copy() # 确保复制
        
        # 动作空间: [vx, vy, vz, sensor]
        self.action_space = spaces.Box(
            low=np.array([-UAV_MAX_SPEED, -UAV_MAX_SPEED, -UAV_MAX_SPEED, 0] * self.uav_num),
            high=np.array([UAV_MAX_SPEED, UAV_MAX_SPEED, UAV_MAX_SPEED, 1] * self.uav_num), 
            dtype=np.float32
        )
        # 观测空间
        self.observation_space = spaces.Box(
            low=np.array([0, 0, 0, -UAV_MAX_SPEED, -UAV_MAX_SPEED, -UAV_MAX_SPEED, 0] * self.uav_num),
            high=np.array([self.map_w, self.map_h, self.map_z, UAV_MAX_SPEED, UAV_MAX_SPEED, UAV_MAX_SPEED, 1] * self.uav_num),
            dtype=np.float32
        )

    def recorder(self, env_t):
        if env_t % 2 == 0:
            for i in range(self.uav_num):
                x, y, z = self.state[i][:3]
                position = [float(round(x, 2)), float(round(y, 2)), float(round(z, 2)), int(env_t)]
                self.position_pool[i].append(position)

    def step(self, actions, env_t):
        actions = np.array(actions).reshape(self.uav_num, 4)
        for i in range(self.uav_num):
            self.state[i][0] += actions[i][0]
            self.state[i][1] += actions[i][1]
            self.state[i][2] += actions[i][2]
            self.state[i][3:6] = actions[i][:3]
            self.state[i][6] = actions[i][3]
        return self.state, 0, False, {}

    def reset(self):
        # 注意：在单次任务中通常不需要reset，除非重用env
        self.state = np.zeros((self.uav_num, 7), dtype=np.float32)
        return self.state

# -------------------------- 运动控制器类 --------------------------
class MvController:
    def __init__(self, map_w, map_h, map_z, buildings_location):
        self.map_w = map_w
        self.map_h = map_h
        self.map_z = map_z
        self.buildings_location = buildings_location

    def Move_up(self):
        return 0, 0, 0.2

    def Move_to(self, uav, aim):
        x_diff = aim[0] - uav[0]
        y_diff = aim[1] - uav[1]
        z_diff = aim[2] - uav[2]
        distance = np.sqrt(x_diff ** 2 + y_diff ** 2 + z_diff ** 2)
        
        if distance < 1e-6:
            return 0, 0, 0

        vx_normalized = x_diff / distance
        vy_normalized = y_diff / distance
        vz_normalized = z_diff / distance
        
        vx = vx_normalized * UAV_MAX_SPEED + random.gauss(0, UAV_VOLATILITY)
        vy = vy_normalized * UAV_MAX_SPEED + random.gauss(0, UAV_VOLATILITY)
        vz = vz_normalized * UAV_MAX_SPEED + random.gauss(0, UAV_VOLATILITY)
        
        return vx, vy, vz

    def Is_arrive(self, uav, aim):
        x_error = abs(uav[0] - aim[0])
        y_error = abs(uav[1] - aim[1])
        z_error = abs(uav[2] - aim[2])
        return x_error < UAV_TOLERANCE and y_error < UAV_TOLERANCE and z_error < UAV_TOLERANCE

    def Will_enter_buildings(self, uav, action, uav_r):
        next_x = uav[0] + action[0]
        next_y = uav[1] + action[1]
        next_z = uav[2] + action[2]
        
        grid_x = int(round(next_x))
        grid_y = int(round(next_y))
        
        # 边界检查
        if grid_x < 0 or grid_x >= self.map_w or grid_y < 0 or grid_y >= self.map_h:
            return False # 出界由 Is_outside_map 处理，这里只关心建筑碰撞
            
        height = self.buildings_location[grid_x][grid_y]
        
        # 如果下一步高度低于建筑高度+半径，则判定为碰撞
        if next_z - uav_r <= height:
            return True
        return False

    def Is_outside_map(self, uav, action):
        next_x = uav[0] + action[0]
        next_y = uav[1] + action[1]
        next_z = uav[2] + action[2]
        if next_x < 0 or next_x >= self.map_w or next_y < 0 or next_y >= self.map_h or next_z < 0 or next_z >= self.map_z:
            return True
        return False

# -------------------------- 封装仿真核心函数 --------------------------
def run_uav_simulation_core(params: dict, task_context):
    """
    无人机仿真核心函数（基于SHP地图）
    """
    # 1. 解析参数
    max_steps = params.get("max_steps", 1000)
    
    # 2. 加载 SHP 地图 (固定路径)
    task_context.update_state(state="STARTED", meta={"progress": 5})
    print(f"Loading SHP map from: {SHP_FILE_PATH}")
    try:
        buildings_location, map_w, map_h, min_x, min_y = parse_shp_file(SHP_FILE_PATH, GRID_RESOLUTION)
        print(f"Map loaded: Size {map_w}x{map_h}, Origin ({min_x}, {min_y})")
    except Exception as e:
        print(f"Error loading SHP: {e}. Using empty map.")
        buildings_location = np.zeros((50, 50))
        map_w, map_h, min_x, min_y = 50, 50, 0, 0

    map_z = MAP_Z
    uav_r = UAV_RADIUS

    # 3. 确定任务类型：动态单机 vs 批量随机
    raw_start_lng = params.get("start_lng") or params.get("start_x")
    raw_start_lat = params.get("start_lat") or params.get("start_y")
    raw_end_lng = params.get("end_lng") or params.get("end_x")
    raw_end_lat = params.get("end_lat") or params.get("end_y")

    init_states = []
    match_pairs = []
    
    # 坐标转换辅助函数 (假设 SHP 是投影坐标，或者这里简化处理直接作为Grid坐标)
    # 注意：如果 SHP 是经纬度，parse_shp_file 内部已经做了归一化到 0-start 的网格映射。
    # 这里的 start/end 如果是前端传来的经纬度，需要同样的映射逻辑。
    # 为简化，假设前端传入的 start/end 已经是相对于 SHP 原点的网格坐标，或者 SHP 解析后的坐标系就是 Grid 系。
    # 如果前端传的是真实经纬度，需要在这里减去 min_x/min_y 并除以 resolution。
    
    is_single_task = all(v is not None for v in [raw_start_lng, raw_start_lat, raw_end_lng, raw_end_lat])

    if is_single_task:
        # --- 单机任务模式 ---
        # 假设传入的是 Grid 坐标 (如果传入的是经纬度，需在此处转换: (lng - min_x)/res)
        # 这里为了兼容之前的逻辑，假设传入值可以直接使用，或者需要根据 min_x/min_y 偏移
        # 修正：通常前端传经纬度，SHP解析后 min_x/min_y 是原始地理坐标最小值。
        # 如果 SHP 是投影坐标(如UTM)，则直接减。如果是经纬度，这种线性映射误差大，但暂按线性处理。
        
        try:
            s_x = float(raw_start_lng)
            s_y = float(raw_start_lat)
            e_x = float(raw_end_lng)
            e_y = float(raw_end_lat)
            
            # 如果传入的是地理坐标，需要转换为网格坐标
            # 假设 parse_shp_file 中的 min_x/min_y 是地理坐标下限
            # grid_x = (geo_x - min_x) / resolution
            
            # 检测数值大小，如果很大(如113.xxx)，则是经纬度，需要转换
            if s_x > 100: 
                start_x = (s_x - min_x) / GRID_RESOLUTION
                start_y = (s_y - min_y) / GRID_RESOLUTION
                end_x = (e_x - min_x) / GRID_RESOLUTION
                end_y = (e_y - min_y) / GRID_RESOLUTION
            else:
                # 假设已经是网格坐标
                start_x, start_y = s_x, s_y
                end_x, end_y = e_x, e_y

            print(f"Single Task: Start({start_x:.2f}, {start_y:.2f}) -> End({end_x:.2f}, {end_y:.2f})")
            
            # 动态扩展地图如果需要
            curr_max_w = max(map_w, int(max(start_x, end_x) + 10))
            curr_max_h = max(map_h, int(max(start_y, end_y) + 10))
            
            if curr_max_w > map_w or curr_max_h > map_h:
                new_bl = np.zeros((curr_max_w, curr_max_h))
                new_bl[:map_w, :map_h] = buildings_location
                buildings_location = new_bl
                map_w, map_h = curr_max_w, curr_max_h
                print(f"Map expanded to {map_w}x{map_h}")

            uav_num = 1
            init_state = np.zeros((1, 7))
            init_state[0] = [start_x, start_y, 5.0, 0, 0, 0, 0] # 初始高度5
            init_states.append(init_state)
            
            target_z = 5.0 # 目标高度
            match_pairs.append([0, [0,0,0], [end_x, end_y, target_z]])
            
        except Exception as e:
            print(f"Error parsing single task coords: {e}")
            #  fallback to random if error
            is_single_task = False

    if not is_single_task:
        # --- 批量/随机任务模式 (Map1 逻辑) ---
        uav_num = 10 # 默认少量无人机测试，避免过多
        print(f"Batch Mode: Generating {uav_num} random UAVs")
        
        # 在地图范围内随机生成
        safe_w = max(1, map_w - 2)
        safe_h = max(1, map_h - 2)
        
        init_state = np.random.uniform(2, safe_w, (uav_num, 7)) # X
        init_state[:, 1] = np.random.uniform(2, safe_h, uav_num) # Y
        init_state[:, 2] = 5.0 # Z
        init_states.append(init_state)
        
        for i in range(uav_num):
            tx = np.random.uniform(2, safe_w)
            ty = np.random.uniform(2, safe_h)
            tz = 5.0
            match_pairs.append([i, [0,0,0], [tx, ty, tz]])

    # 合并初始状态
    final_init_state = np.vstack(init_states) if init_states else np.zeros((0,7))
    uav_num = len(match_pairs)

    if uav_num == 0:
        return {"error": "No UAVs generated"}

    # 4. 初始化环境与控制器
    task_context.update_state(state="STARTED", meta={"progress": 20})
    env = UAVEnv(uav_num, map_w, map_h, map_z, final_init_state, buildings_location)
    controller = MvController(map_w, map_h, map_z, buildings_location)

    # 5. 仿真循环
    task_context.update_state(state="STARTED", meta={"progress": 30})
    env_t = 0
    flag = [False] * uav_num
    done = False
    
    # 用于记录详细状态
    uav_status_log = {i: {"status": "pending", "reason": "Started"} for i in range(uav_num)}

    while not done and env_t < max_steps:
        progress = 30 + int((env_t / max_steps) * 70)
        if env_t % 10 == 0: # 降低更新频率
            task_context.update_state(state="STARTED", meta={"progress": progress})

        actions = np.zeros((uav_num, 4))
        
        for i in range(uav_num):
            if flag[i]:
                continue
                
            uav_pos = env.state[i][:3]
            aim_pos = np.array(match_pairs[i][2])
            
            # 记录最后位置用于诊断
            uav_status_log[i]["last_pos"] = uav_pos.tolist()
            uav_status_log[i]["target_pos"] = aim_pos.tolist()

            # 计算动作
            vx, vy, vz = controller.Move_to(uav_pos, aim_pos)
            
            # 避障与边界检查
            if controller.Is_outside_map(uav_pos, [vx, vy, vz]):
                vx, vy, vz = 0, 0, 0
                uav_status_log[i]["reason"] = "Stopped: Out of bounds"
            
            if controller.Will_enter_buildings(uav_pos, [vx, vy, vz], uav_r):
                vx, vy, vz = controller.Move_up()
                # 如果一直向上飞也出界，会在下一轮被 Is_outside_map 捕获
            
            actions[i] = [vx, vy, vz, 0]
            
            # 到达检查
            if controller.Is_arrive(uav_pos, aim_pos):
                flag[i] = True
                uav_status_log[i]["status"] = "arrived"
                uav_status_log[i]["reason"] = "Success"

        env.step(actions, env_t)
        env.recorder(env_t)
        
        if all(flag):
            done = True
        env_t += 1

    # 6. 整理结果
    task_context.update_state(state="STARTED", meta={"progress": 100})
    
    # 补充未到达的原因
    for i in range(uav_num):
        if not flag[i]:
            uav_status_log[i]["status"] = "failed"
            last_pos = uav_status_log[i].get("last_pos", [0,0,0])
            target = uav_status_log[i].get("target_pos", [0,0,0])
            dist = np.linalg.norm(np.array(last_pos) - np.array(target))
            if "Out of bounds" in uav_status_log[i].get("reason", ""):
                pass # 已有原因
            elif dist > 5.0:
                uav_status_log[i]["reason"] = f"Timeout: Too far ({dist:.2f})"
            else:
                uav_status_log[i]["reason"] = f"Timeout: Stuck near target ({dist:.2f})"

    uav_trajectories = {f"uav_{i}": env.position_pool[i] for i in range(uav_num)}
    arrived_count = sum(flag)

    return {
        "map_name": "SHP_Map",
        "uav_num": int(uav_num),
        "total_steps": int(env_t),
        "max_steps": int(max_steps),
        "arrived_uav_count": int(arrived_count),
        "arrived_uav_ratio": round(arrived_count / uav_num, 2) if uav_num > 0 else 0,
        "uav_trajectories": uav_trajectories,
        "uav_arrived_status": [bool(f) for f in flag],
        "detailed_uav_status": list(uav_status_log.values()),
        "map_info": {"map_w": float(map_w), "map_h": float(map_h), "map_z": float(map_z)}
    }