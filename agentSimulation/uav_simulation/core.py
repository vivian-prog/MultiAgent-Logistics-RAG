# uav_simulation/core.py
import random
import sys
import gym
from gym import spaces
import numpy as np
import math
import os
import sys
# 添加项目根目录到路径，以便导入配置模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from configs.loader import get_uav_config, get_simulation_config

# 深圳参考原点 (用于 Grid 映射 - 必须与预处理脚本保持一致)
# 现在从配置文件读取
_sim_config = get_simulation_config()
ORIGIN_LNG = _sim_config.get("origin_lng", 113.70)
ORIGIN_LAT = _sim_config.get("origin_lat", 22.40)
SCALE_FACTOR = _sim_config.get("scale_factor", 1000.0)  # 0.001度 ≈ 1个Grid单位 ≈ 100米

# UAV配置参数（从配置文件读取）
_uav_config = get_uav_config()
UAV_MAX_SPEED = _uav_config.get("max_speed", 0.3)
UAV_VOLATILITY = _uav_config.get("volatility", 0.02)
UAV_RADIUS = _uav_config.get("radius", 0.3)
UAV_TOLERANCE = _uav_config.get("tolerance", 0.1)

def gps_to_grid(lng, lat):
    grid_x = (float(lng) - ORIGIN_LNG) * SCALE_FACTOR
    grid_y = (float(lat) - ORIGIN_LAT) * SCALE_FACTOR
    return grid_x, grid_y

# -------------------------- 模拟外部数据导入 --------------------------
# 预先定义变量，稍后在 SetConfig 中初始化
buildings_location_WH = None
uav_init_pos_WH = None
match_pairs_WH = None

buildings_location_zhuanyi = np.zeros((50, 50))
match_pairs_zhuanyi = [[i, [0,0,0], [random.uniform(10,40), random.uniform(10,40), random.uniform(1,5)]] for i in range(32)]
uav_init_state_zhuanyi = np.random.uniform(0, 50, (32,7))

# -------------------------- 无人机环境类 --------------------------
class UAVEnv(gym.Env):
    def __init__(self, uav_num, map_w, map_h, map_z, Init_state):
        super(UAVEnv, self).__init__()
        self.uav_num = uav_num
        self.map_w = map_w
        self.map_h = map_h
        self.map_z = map_z
        self.position_pool = [[] for _ in range(self.uav_num)]
        self.state = Init_state
        self.action_space = spaces.Box(low=np.array([-0.35, -0.35, -0.35, 0] * self.uav_num),
                                       high=np.array([0.35, 0.35, 0.35, 1] * self.uav_num), dtype=np.float32)
        self.observation_space = spaces.Box(low=np.array([0, 0, 0, -1, -1, -1, 0] * self.uav_num),
                                            high=np.array([self.map_w, self.map_h, self.map_z, 1, 1, 1, 1] *
                                                          self.uav_num), dtype=np.float32)

    def recorder(self, env_t):
        if env_t % 2 == 0:
            for i in range(self.uav_num):
                x, y, z = self.state[i][:3]
                # 显式转换为原生 float，避免 JSON 序列化错误
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
        self.state = np.zeros((self.uav_num, 7), dtype=np.float32)
        return self.state

# -------------------------- 参数配置类 --------------------------
class SetConfig:
    def __init__(self, name):
        self.name = name
        self.uav_num = 0
        self.uav_r = UAV_RADIUS  # 从配置文件读取
        self.map_w, self.map_h, self.map_z = 0, 0, 0
        self.buildings_location = []
        self.buildings = []
        self.match_pairs = []
        self.Init_state = []

    def Setting(self):
        global buildings_location_WH, uav_init_pos_WH, match_pairs_WH

        if self.name == 'Map1':
            # 加载预处理的地图数据 (.npy)
            if buildings_location_WH is None:
                npy_path = os.path.join(os.path.dirname(__file__), "map1_buildings.npy")
                if os.path.exists(npy_path):
                    print(f"Loading cached map: {npy_path}")
                    buildings_location_WH = np.load(npy_path)
                else:
                    print(f"Warning: Map cache not found ({npy_path}), using empty map.")
                    buildings_location_WH = np.zeros((50, 50))

                w, h = buildings_location_WH.shape
                # 初始化匹配对和状态 (随机分布在地图范围内)
                uav_init_pos_WH = np.random.uniform(0, min(w, h), (50, 7))
                match_pairs_WH = [[i, [0,0,0], [random.uniform(0,w), random.uniform(0,h), random.uniform(5,10)]] for i in range(50)]

            self.uav_num = 50
            self.map_w = buildings_location_WH.shape[0]
            self.map_h = buildings_location_WH.shape[1]
            self.map_z = 20
            self.buildings_location = buildings_location_WH
            self.match_pairs = match_pairs_WH
            self.Init_state = uav_init_pos_WH

        elif self.name == 'Map2':
            self.uav_num = 32
            self.map_w, self.map_h, self.map_z = 50, 50, 5
            self.buildings_location = buildings_location_zhuanyi
            self.buildings = buildings_zhuanyi
            self.match_pairs = match_pairs_zhuanyi
            self.Init_state = uav_init_state_zhuanyi
        else:
            # 默认兜底
            print(f"Warning: Unknown Map_name '{self.name}', defaulting to Map1 config.")
            return self.Setting() # 递归调用 Map1

        return self.uav_num, self.map_w, self.map_h, self.map_z, self.buildings_location, self.buildings, self.match_pairs, self.uav_r, self.Init_state

# -------------------------- 运动控制器类 --------------------------
class MvController:
    def __init__(self, map_w, map_h, map_z, buildings_location):
        self.map_w = map_w
        self.map_h = map_h
        self.map_z = map_z
        self.buildings_location = buildings_location
        # 从配置文件读取运动参数
        self.max_speed = UAV_MAX_SPEED
        self.volatility = UAV_VOLATILITY
        self.tolerance = UAV_TOLERANCE

    def Move_up(self):
        return 0, 0, 0.2

    def Move_to(self, uav, aim):
        x_diff = aim[0] - uav[0]
        y_diff = aim[1] - uav[1]
        z_diff = aim[2] - uav[2]
        distance = np.sqrt(x_diff ** 2 + y_diff ** 2 + z_diff ** 2)
        if abs(x_diff) < 0.1:
            vx = 0
        else:
            vx_normalized = x_diff / distance
            vx = vx_normalized * self.max_speed + random.gauss(0, self.volatility)
        if abs(y_diff) < 0.1:
            vy = 0
        else:
            vy_normalized = y_diff / distance
            vy = vy_normalized * self.max_speed + random.gauss(0, self.volatility)
        if abs(z_diff) < 0.1:
            vz = 0
        else:
            vz_normalized = z_diff / distance
            vz = vz_normalized * self.max_speed + random.gauss(0, self.volatility)
        return vx, vy, vz

    def Is_arrive(self, uav, aim):
        x_error = abs(uav[0] - aim[0])
        y_error = abs(uav[1] - aim[1])
        z_error = abs(uav[2] - aim[2])
        return x_error < self.tolerance and y_error < self.tolerance and z_error < self.tolerance

    def Will_enter_buildings(self, uav, action, uav_r):
        next_x = uav[0] + action[0]
        next_y = uav[1] + action[1]
        next_z = uav[2] + action[2]
        grid_x = int(next_x)
        grid_y = int(next_y)
        # 边界检查
        if grid_x < 0 or grid_x >= len(self.buildings_location) or grid_y < 0 or grid_y >= len(self.buildings_location[0]):
            return False

        height = self.buildings_location[grid_x][grid_y]

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

# -------------------------- 封装仿真核心函数（供外部导入调用） --------------------------
def run_uav_simulation_core(params: dict, task_context):
    """
    无人机仿真核心函数（供Celery任务调用）
    """
    # 1. 解析参数
    map_name = params.get("Map_name", "Map1")
    max_steps = params.get("max_steps", 1000)

    # 2. 初始化配置
    task_context.update_state(state="STARTED", meta={"progress": 10})
    MAP = SetConfig(map_name)
    uav_num, map_w, map_h, map_z, buildings_location, buildings, match_pairs, uav_r, Init_state = MAP.Setting()

    # ================= 核心修改：支持动态单机任务（深圳坐标系映射） =================
    raw_start_lng = params.get("start_lng") or params.get("start_x")
    raw_start_lat = params.get("start_lat") or params.get("start_y")
    raw_end_lng = params.get("end_lng") or params.get("end_x")
    raw_end_lat = params.get("end_lat") or params.get("end_y")

    if all(v is not None for v in [raw_start_lng, raw_start_lat, raw_end_lng, raw_end_lat]):
        # 3. 转换坐标 (复用全局定义的转换逻辑)
        start_x, start_y = gps_to_grid(raw_start_lng, raw_start_lat)
        end_x, end_y = gps_to_grid(raw_end_lng, raw_end_lat)

        print(f"检测到动态单机任务。GPS映射: 起点({raw_start_lng},{raw_start_lat})->({start_x:.2f},{start_y:.2f})")

        # 4. 强制设为单机
        uav_num = 1

        # 5. 覆盖初始状态
        Init_state = np.zeros((1, 7), dtype=np.float32)
        Init_state[0] = [start_x, start_y, 0, 0, 0, 0, 0]

        # 6. 覆盖目标配对
        target_z = min(15.0, map_z) # 目标高度设高一点
        match_pairs = [[0, [0,0,0], [end_x, end_y, target_z]]]

        # 7. 动态调整地图边界 (确保转换后的坐标在地图内)
        max_grid_x = max(start_x, end_x, map_w)
        max_grid_y = max(start_y, end_y, map_h)

        if max_grid_x >= map_w or max_grid_y >= map_h:
            new_w = math.ceil(max_grid_x + 20)
            new_h = math.ceil(max_grid_y + 20)

            # 创建新的扩展地图
            new_buildings = np.zeros((new_w, new_h))
            # 将旧地图数据复制进去 (左下角对齐)
            old_w, old_h = buildings_location.shape
            new_buildings[0:old_w, 0:old_h] = buildings_location

            buildings_location = new_buildings
            map_w, map_h = new_w, new_h
            print(f"地图尺寸已根据深圳坐标动态扩展为: {map_w} x {map_h} (保留了SHP数据)")

    # ==========================================================

    # 3. 初始化模块
    task_context.update_state(state="STARTED", meta={"progress": 20})
    env = UAVEnv(uav_num, map_w, map_h, map_z, Init_state)
    mvcontroller = MvController(map_w, map_h, map_z, buildings_location)

    # 4. 仿真循环
    task_context.update_state(state="STARTED", meta={"progress": 30})
    env_t = 0
    actions = [[0, 0, 0, 0] for _ in range(uav_num)]
    flag = [False] * uav_num
    done = False

    while not done and env_t < max_steps:
        # 更新进度
        progress = 30 + int((env_t / max_steps) * 70)
        task_context.update_state(state="STARTED", meta={"progress": progress})

        # 计算每个无人机动作
        for pair in match_pairs:
            index = pair[0]
            uav_state = env.state[index][:3]
            aim = pair[2]
            vx, vy, vz = mvcontroller.Move_to(uav_state, aim)

            if mvcontroller.Is_arrive(uav_state, aim):
                if not flag[index]:
                    flag[index] = True
            if mvcontroller.Is_outside_map(uav_state, [vx, vy, vz]):
                vx, vy, vz = 0, 0, 0
            if mvcontroller.Will_enter_buildings(uav_state, [vx, vy, vz], uav_r):
                vx, vy, vz = mvcontroller.Move_up()
            actions[index] = [vx, vy, vz, 0]

        env.step(actions, env_t)
        env.recorder(env_t)
        if all(flag):
            done = True
        env_t += 1

    # 5. 整理结果
    task_context.update_state(state="STARTED", meta={"progress": 100})
    uav_trajectories = {f"uav_{i}": env.position_pool[i] for i in range(uav_num)}
    arrived_count = sum(flag)

    return {
        "map_name": map_name,
        "uav_num": int(uav_num),
        "total_steps": int(env_t),
        "max_steps": int(max_steps),
        "arrived_uav_count": int(arrived_count),
        "arrived_uav_ratio": round(arrived_count / uav_num, 2) if uav_num > 0 else 0,
        "uav_trajectories": uav_trajectories,
        "uav_arrived_status": [bool(f) for f in flag],
        "map_info": {"map_w": float(map_w), "map_h": float(map_h), "map_z": float(map_z)}
    }
