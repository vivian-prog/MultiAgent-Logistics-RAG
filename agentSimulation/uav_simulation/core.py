# uav_simulation/core.py
import random
import sys
import gym
from gym import spaces
import numpy as np
import math

# -------------------------- 模拟外部数据导入（替换为你的真实数据） --------------------------
# 注：请将你的 array_data_zhuanyi.py、WH_test.py 等文件中的变量导入到这里
# 示例模拟数据（实际使用时删除并替换为真实数据）
buildings_location_WH = np.zeros((50, 50))
buildings_WH = []
match_pairs_WH = [[i, [0,0,0], [random.uniform(10,40), random.uniform(10,40), random.uniform(1,5)]] for i in range(50)]
uav_init_pos_WH = np.random.uniform(0, 50, (50,7))

buildings_location_zhuanyi = np.zeros((50, 50))
buildings_zhuanyi = []
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
                position = [round(x, 2), round(y, 2), round(z, 2), env_t]
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
        self.uav_r = 0.3
        self.map_w, self.map_h, self.map_z = 0, 0, 0
        self.buildings_location = []
        self.buildings = []
        self.match_pairs = []
        self.Init_state = []

    def Setting(self):
        if self.name == 'Map1':
            self.uav_num = 50
            self.map_w, self.map_h, self.map_z = 50, 50, 5
            self.buildings_location = buildings_location_WH
            self.buildings = buildings_WH
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
            self.uav_num = 50
            self.map_w, self.map_h, self.map_z = 50, 50, 5
            self.buildings_location = buildings_location_WH
            self.buildings = buildings_WH
            self.match_pairs = match_pairs_WH
            self.Init_state = uav_init_pos_WH

        return self.uav_num, self.map_w, self.map_h, self.map_z, self.buildings_location, self.buildings, self.match_pairs, self.uav_r, self.Init_state

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
        max_speed = 0.3
        volatility = 0.02
        x_diff = aim[0] - uav[0]
        y_diff = aim[1] - uav[1]
        z_diff = aim[2] - uav[2]
        distance = np.sqrt(x_diff ** 2 + y_diff ** 2 + z_diff ** 2)
        if abs(x_diff) < 0.1:
            vx = 0
        else:
            vx_normalized = x_diff / distance
            vx = vx_normalized * max_speed + random.gauss(0, volatility)
        if abs(y_diff) < 0.1:
            vy = 0
        else:
            vy_normalized = y_diff / distance
            vy = vy_normalized * max_speed + random.gauss(0, volatility)
        if abs(z_diff) < 0.1:
            vz = 0
        else:
            vz_normalized = z_diff / distance
            vz = vz_normalized * max_speed + random.gauss(0, volatility)
        return vx, vy, vz

    def Is_arrive(self, uav, aim):
        tolerance = 0.1
        x_error = abs(uav[0] - aim[0])
        y_error = abs(uav[1] - aim[1])
        z_error = abs(uav[2] - aim[2])
        return x_error < tolerance and y_error < tolerance and z_error < tolerance

    def Will_enter_buildings(self, uav, action, uav_r):
        next_x = uav[0] + action[0]
        next_y = uav[1] + action[1]
        next_z = uav[2] + action[2]
        grid_x = int(next_x)
        grid_y = int(next_y)
        if 0 <= grid_x < len(self.buildings_location) and 0 <= grid_y < len(self.buildings_location[0]):
            height = self.buildings_location[grid_x][grid_y]
        else:
            height = 0
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
    :param params: 仿真参数（Map_name、max_steps）
    :param task_context: Celery任务上下文（self）
    :return: 仿真结果字典
    """
    # 1. 解析参数
    map_name = params.get("Map_name", "Map1")
    max_steps = params.get("max_steps", 1000)

    # 2. 初始化配置
    task_context.update_state(state="STARTED", meta={"progress": 10})
    MAP = SetConfig(map_name)
    uav_num, map_w, map_h, map_z, buildings_location, buildings, match_pairs, uav_r, Init_state = MAP.Setting()

    # ================= 核心修改：支持动态单机任务（深圳坐标系映射） =================
    # 检查是否传入了特定的起终点坐标 (GPS 经纬度)
    # 兼容 LLM 可能生成的 start_lat/lng 格式
    raw_start_lng = params.get("start_lng") or params.get("start_x")
    raw_start_lat = params.get("start_lat") or params.get("start_y")
    raw_end_lng = params.get("end_lng") or params.get("end_x")
    raw_end_lat = params.get("end_lat") or params.get("end_y")

    if all(v is not None for v in [raw_start_lng, raw_start_lat, raw_end_lng, raw_end_lat]):
        # 1. 定义深圳区域的参考原点 (左下角近似值：宝安机场西南侧)
        # 这样可以将 GPS (113.x, 22.x) 映射为相对较小的正数
        ORIGIN_LNG = 113.70
        ORIGIN_LAT = 22.40

        # 2. 定义缩放比例 (将经纬度差值放大为 Grid 坐标)
        # 假设 0.01 度 (约1km) 对应 10 个 Grid 单位 -> 1 Grid ≈ 100米
        SCALE_FACTOR = 1000.0

        def gps_to_grid(lng, lat):
            grid_x = (float(lng) - ORIGIN_LNG) * SCALE_FACTOR
            grid_y = (float(lat) - ORIGIN_LAT) * SCALE_FACTOR
            return grid_x, grid_y

        # 3. 转换坐标
        start_x, start_y = gps_to_grid(raw_start_lng, raw_start_lat)
        end_x, end_y = gps_to_grid(raw_end_lng, raw_end_lat)

        print(f"检测到动态单机任务。GPS映射: 起点({raw_start_lng},{raw_start_lat})->({start_x:.2f},{start_y:.2f})")

        # 4. 强制设为单机
        uav_num = 1

        # 5. 覆盖初始状态
        Init_state = np.zeros((1, 7), dtype=np.float32)
        Init_state[0] = [start_x, start_y, 0, 0, 0, 0, 0]

        # 6. 覆盖目标配对
        target_z = min(5.0, map_z)
        match_pairs = [[0, [0,0,0], [end_x, end_y, target_z]]]

        # 7. 动态调整地图边界 (确保转换后的坐标在地图内)
        # 找出最大 Grid 坐标，并留出缓冲
        max_grid_x = max(start_x, end_x, map_w)
        max_grid_y = max(start_y, end_y, map_h)

        if max_grid_x >= map_w or max_grid_y >= map_h:
            map_w = math.ceil(max_grid_x + 20)
            map_h = math.ceil(max_grid_y + 20)
            # 重置建筑物 (清空避障，因为真实地图太复杂，此处仅演示轨迹)
            buildings_location = np.zeros((map_w, map_h))
            print(f"地图尺寸已根据深圳坐标动态扩展为: {map_w} x {map_h}")

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
        "uav_num": uav_num,
        "total_steps": env_t,
        "max_steps": max_steps,
        "arrived_uav_count": arrived_count,
        "arrived_uav_ratio": round(arrived_count / uav_num, 2) if uav_num > 0 else 0,
        "uav_trajectories": uav_trajectories,
        "uav_arrived_status": flag,
        "map_info": {"map_w": map_w, "map_h": map_h, "map_z": map_z}
    }
