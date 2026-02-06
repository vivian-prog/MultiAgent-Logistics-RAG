
# celery_worker/__init__.py
import os, sys
from typing import Optional  # 关键：导入Optional
# 把项目根（agentSimulation/）塞进 PATH
proj_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)
# celery_worker/tasks.py
import time
import math  # 补充导入 math
from celery_worker import app  # 导入上面初始化的Celery实例
from common.db import get_sync_db  # 若需要数据库操作，需用同步DB（Celery不支持异步Session）
from common.schema import SimulationResultSchema
from uav_simulation.core import run_uav_simulation_core
from warehouse_robot.core import simulate_single_task, simulate_batch_tasks
# 核心：用@app.task装饰，将普通函数转为Celery异步任务
@app.task(bind=True, name="run_simulation_task")  # name可选，指定任务名（方便查询）
def run_simulation_task(self, params: dict):

    """
    仿真任务的核心逻辑（Agent仿真、计算等耗时操作）
    :param self: 任务上下文（可用于更新任务状态、记录日志）
    :param params: 前端传入的仿真参数（如Agent配置、任务参数）
    :return: 仿真结果（会被Celery保存到backend）
    """
    try:
        # 1. （可选）更新任务状态为"STARTED"（前端查询时能看到执行中）
        self.update_state(state="STARTED", meta={"progress": 0})

        # 2. 模拟耗时的仿真计算（替换为你的实际业务逻辑）
        print(f"开始执行仿真任务，参数：{params}")
        time.sleep(5)  # 代表耗时操作（如Agent路径规划、任务调度）

        # 3. （可选）数据库操作（注意：Celery任务是同步的，需用同步DB会话）
        db = next(get_sync_db())  # 替换为你的同步DB获取函数
        # 示例：将参数存入数据库 / 读取基础数据
        # task_record = TaskRecord(params=params, status="SUCCESS")
        # db.add(task_record)
        # db.commit()

        # 4. 构造仿真结果（符合SimulationResultSchema模型）
        result = {
            "task_id": self.request.id,
            "params": {
                 "agent_count": 1,
                "task_type": '0',
                "warehouse_id": 1,
            },
            "simulation_data": {
                 "agent_count": 0,
                "task_type": 0,
                "warehouse_id": 0,
            },
            "progress": 100,
            "status": "SUCCESS",
            "error": None,
            "finish_time": "2025-12-19T14:30:00"

        }


        # 5. 返回结果（会自动保存到Celery backend）
        return SimulationResultSchema(**result).dict()  # 标准化结果格式

    except Exception as e:
        # 捕获异常，更新状态为FAILURE，返回错误信息
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise e  # 让Celery记录异常，前端查询时能看到


# # 核心：用@app.task装饰，将普通函数转为Celery异步任务
# @app.task(bind=True, name="run_simulation_task_agent1")  # name可选，指定任务名（方便查询）
# def run_simulation_task_Agent1(self, params: dict):

#     """
#     仿真任务的核心逻辑（Agent仿真、计算等耗时操作）
#     :param self: 任务上下文（可用于更新任务状态、记录日志）
#     :param params: 前端传入的仿真参数（如Agent配置、任务参数）
#     :return: 仿真结果（会被Celery保存到backend）
#     """
#     try:
#         # 1. （可选）更新任务状态为"STARTED"（前端查询时能看到执行中）
#         self.update_state(state="STARTED", meta={"progress": 0})
#
#         # 2. 模拟耗时的仿真计算（替换为你的实际业务逻辑）
#         print(f"开始执行仿真任务，参数：{params}")
#         time.sleep(5)  # 代表耗时操作（如Agent路径规划、任务调度）
#
#         # 3. （可选）数据库操作（注意：Celery任务是同步的，需用同步DB会话）
#         db = next(get_sync_db())  # 替换为你的同步DB获取函数
#         # 示例：将参数存入数据库 / 读取基础数据
#         # task_record = TaskRecord(params=params, status="SUCCESS")
#         # db.add(task_record)
#         # db.commit()
#
#         # 4. 构造仿真结果（符合SimulationResultSchema模型）
#         result = {
#             "task_id": self.request.id,
#             "params": {
#                  "agent_type": 1,
#
#             },
#             "simulation_data": {
#                  "agent_count": 0,
#                 "task_type": 0,
#                 "warehouse_id": 0,
#             },
#             "progress": 100,
#             "status": "SUCCESS",
#             "error": None,
#             "finish_time": "2025-12-19T14:30:00"
#
#         }
#
#
#         # 5. 返回结果（会自动保存到Celery backend）
#         return SimulationResultSchema(**result).dict()  # 标准化结果格式
#
#     except Exception as e:
#         # 捕获异常，更新状态为FAILURE，返回错误信息
#         self.update_state(state="FAILURE", meta={"error": str(e)})
#         raise e  # 让Celery记录异常，前端查询时能看到
#

from datetime import datetime
import requests  # 用于调用GraphHopper API（也可改用GraphHopper Python客户端）

from pydantic import BaseModel  # 假设SimulationResultSchema基于BaseModel

# 定义结果模型（如果未定义，补充这部分）
class SimulationResultSchema(BaseModel):
    task_id: str
    params: dict
    simulation_data: dict
    progress: int
    status: str
    error: Optional[str]
    finish_time: str

    class Config:
        arbitrary_types_allowed = True

# 模拟获取同步数据库会话的函数（替换为你实际的DB逻辑）
def get_sync_db():
    """模拟生成同步数据库会话，需替换为你的真实实现"""
    yield None

# GraphHopper配置（根据你的部署地址/密钥调整）
GRAPH_HOPPER_BASE_URL = "http://localhost:8989/route"
GRAPH_HOPPER_API_KEY = "your_api_key"  # 本地部署可留空，云端需填密钥

def calculate_truck_minute_positions(route_points, route_times):
    """
    核心：根据GraphHopper返回的路线点和分段时间，计算每分钟应到达的位置
    :param route_points: 路线GPS点列表 [(lat1, lng1), (lat2, lng2), ...]
    :param route_times: 各分段耗时（秒）列表 [t1, t2, t3, ...]
    :return: 每分钟位置字典 {分钟数: (纬度, 经度), ...}
    """
    minute_positions = {}
    accumulated_time = 0.0  # 累计耗时（秒）
    point_index = 0  # 当前遍历的路线点索引

    # 遍历每一分钟，计算对应位置
    for minute in range(0, int(sum(route_times) // 60) + 2):  # 覆盖所有耗时分钟
        target_time = minute * 60  # 目标时间（秒）

        # 找到目标时间所在的路段
        while point_index < len(route_times) - 1:
            seg_time = route_times[point_index]
            if accumulated_time + seg_time >= target_time:
                break
            accumulated_time += seg_time
            point_index += 1

        # 计算在当前路段的时间占比
        seg_time = route_times[point_index] if point_index < len(route_times) else 0
        if seg_time == 0:
            # 已到终点，后续分钟都停在最后一个点
            lat, lng = route_points[-1]
        else:
            ratio = (target_time - accumulated_time) / seg_time
            # 线性插值计算GPS坐标
            lat1, lng1 = route_points[point_index]
            lat2, lng2 = route_points[point_index + 1] if (point_index + 1) < len(route_points) else (lat1, lng1)
            lat = lat1 + (lat2 - lat1) * ratio
            lng = lng1 + (lng2 - lng1) * ratio

        minute_positions[minute] = (round(lat, 6), round(lng, 6))  # 保留6位小数，符合GPS精度

    return minute_positions


def calculate_truck_fuel_consumption(route_data, truck_params):
    """
    核心新增：计算卡车全程油耗（基于行业通用油耗模型）
    :param route_data: GraphHopper返回的路线数据（距离、分段速度、道路类型）
    :param truck_params: 卡车参数（载重、车型、基础油耗等）
    :return: 油耗结果字典（总油耗、单位油耗、分段油耗等）
    """
    # 1. 基础参数（可根据实际车型调整，或从truck_params传入）
    base_fuel_per_100km = truck_params.get("base_fuel", 30)  # 空车百公里油耗（升），默认30L/100km
    load_factor = truck_params.get("load_factor", 0.3)       # 载重油耗系数（载重每增加1吨，油耗增加30%）
    road_type_factors = {                                    # 不同道路类型油耗系数
        "motorway": 1.0,    # 高速路
        "trunk": 1.1,       # 主干道
        "primary": 1.2,     # 一级公路
        "secondary": 1.3,   # 二级公路
        "tertiary": 1.4,    # 三级公路
        "residential": 1.5, # 居民区道路
        "unclassified": 1.4 # 未分类道路
    }
    speed_factor = truck_params.get("speed_factor", 0.005)   # 速度影响系数（速度偏离经济时速的油耗增量）
    economic_speed = 60                                      # 经济时速（km/h）

    # 2. 提取路线核心数据
    total_distance_km = route_data["distance"] / 1000  # 总距离（公里）
    total_fuel = 0.0                                   # 总油耗（升）
    segment_fuel_details = []                          # 分段油耗明细

    # 3. 计算载重影响后的基础油耗
    load_weight = truck_params.get("load_weight", 0)   # 载重（吨）
    load_impacted_fuel = base_fuel_per_100km * (1 + load_weight * load_factor)

    # 4. 遍历路线分段计算油耗（若有分段数据）
    if "segments" in route_data and len(route_data["segments"]) > 0:
        for seg in route_data["segments"][0].get("edges", []):
            # 分段距离（公里）
            seg_distance_km = seg.get("distance", 0) / 1000
            if seg_distance_km <= 0:
                continue

            # 分段平均速度（km/h）
            seg_time_h = seg.get("time", 0) / 3600000  # GraphHopper time是毫秒，转小时
            seg_speed = seg_distance_km / seg_time_h if seg_time_h > 0 else economic_speed

            # 道路类型系数（默认1.2）
            road_type = seg.get("road_type", "unclassified")
            road_factor = road_type_factors.get(road_type, 1.2)

            # 速度影响系数（偏离经济时速越多，油耗越高）
            speed_deviation = abs(seg_speed - economic_speed)
            speed_impact = 1 + (speed_deviation * speed_factor)

            # 分段油耗 = 基础油耗 * 距离 * 道路系数 * 速度系数 / 100
            seg_fuel = load_impacted_fuel * seg_distance_km * road_factor * speed_impact / 100
            total_fuel += seg_fuel

            # 记录分段油耗明细
            segment_fuel_details.append({
                "distance_km": round(seg_distance_km, 2),
                "speed_kmh": round(seg_speed, 1),
                "road_type": road_type,
                "fuel_liter": round(seg_fuel, 3)
            })
    else:
        # 无分段数据时，按总距离和平均速度计算
        total_time_h = route_data["time"] / 3600000
        avg_speed = total_distance_km / total_time_h if total_time_h > 0 else economic_speed
        speed_deviation = abs(avg_speed - economic_speed)
        speed_impact = 1 + (speed_deviation * speed_factor)
        total_fuel = load_impacted_fuel * total_distance_km * speed_impact / 100

    # 5. 计算单位油耗（升/公里）、费用（可选）
    fuel_price = truck_params.get("fuel_price", 7.5)  # 油价（元/升），默认7.5元
    total_fuel_cost = total_fuel * fuel_price         # 总油费（元）
    fuel_per_km = total_fuel / total_distance_km if total_distance_km > 0 else 0  # 升/公里

    return {
        "total_fuel_liter": round(total_fuel, 2),          # 总油耗（升）
        "fuel_per_100km": round(total_fuel / total_distance_km * 100, 2),  # 百公里油耗（升）
        "fuel_per_km": round(fuel_per_km, 4),              # 每公里油耗（升）
        "total_fuel_cost": round(total_fuel_cost, 2),      # 总油费（元）
        "fuel_price": fuel_price,                          # 油价（元/升）
        "segment_fuel_details": segment_fuel_details       # 分段油耗明细
    }


# ---------------------- 生成传感器数据并写入数据库 ----------------------
def save_agent_sensor_data(db, task_id, agent_id, minute_positions, route_data, params):
    """
    批量保存Agent传感器数据到数据库
    :param db: ORM数据库会话
    :param task_id: 任务ID
    :param agent_id: AgentID
    :param minute_positions: 每分钟位置字典 {分钟数: (lat/lng)}
    :param route_data: GraphHopper路线数据
    :param params: 前端传入参数（含货物状态、电量等）
    """
    # 1. 基础参数提取
    total_distance_m = route_data["distance"]  # 总距离（米）
    total_time_s = route_data["time"] / 1000   # 总耗时（秒）
    avg_speed_m_s = total_distance_m / total_time_s if total_time_s > 0 else 0  # 平均速度（m/s）
    goods_status = params.get("goods_status", 1)  # 默认已装载
    battery_remaining = params.get("battery_remaining", 100)  # 默认满电
    obstacle_dist = params.get("obstacle_dist", 100.0)  # 默认前方无障碍物（100米）

    # 2. 转换GPS坐标为SLAM X/Y（若需坐标系转换，可在此补充）
    # 简化处理：直接将纬度作为Y，经度作为X（乘以100000转换为米级坐标，适配SLAM）
    def gps_to_slam(lat, lng):
        slam_x = round(lng * 100000, 2)
        slam_y = round(lat * 100000, 2)
        return slam_x, slam_y

    # 3. 批量生成每分钟的传感器数据
    sensor_data_list = []
    start_time = datetime.now()
    for minute, (lat, lng) in minute_positions.items():
        # 计算当前分钟的速度（m/s）：模拟速度随路段变化
        current_speed = avg_speed_m_s * (0.8 + (minute % 5) * 0.04)  # 模拟速度波动
        current_speed = round(current_speed, 2)

        # 电量衰减（每分钟减少1%）
        current_battery = max(0, battery_remaining - minute)

        # 坐标转换
        slam_x, slam_y = gps_to_slam(lat, lng)

        # 构建传感器数据对象
        sensor_data = AgentGroundSensor(
            agent_id=agent_id,
            task_id=task_id,
            slam_x=slam_x,
            slam_y=slam_y,
            speed=current_speed,
            obstacle_dist=obstacle_dist,
            goods_status=goods_status,
            battery_remaining=current_battery,
            collect_time=start_time + timedelta(minutes=minute)  # 按分钟递增采集时间
        )
        sensor_data_list.append(sensor_data)

    # 4. 批量插入数据库（高效批量操作）
    db.add_all(sensor_data_list)
    db.commit()
    print(f"成功写入{len(sensor_data_list)}条Agent传感器数据，任务ID：{task_id}，AgentID：{agent_id}")

@app.task(bind=True, name="run_simulation_task_agent_uav")
def run_simulation_task_agent_uav(self, params: dict):
    """
    仿真任务的核心逻辑（调用无人机仿真代码）
    :param self: 任务上下文
    :param params: 前端传入参数（Map_name、max_steps等）
    :return: 标准化仿真结果
    """
    try:
        # 1. 更新任务初始状态
        self.update_state(state="STARTED", meta={"progress": 0})
        print(f"开始执行无人机仿真任务，参数：{params}")

        # 2. （可选）数据库操作
        db = next(get_sync_db())
        # 示例：保存任务记录
        # task_record = TaskRecord(task_id=self.request.id, params=params, status="STARTED")
        # db.add(task_record)
        # db.commit()

        # 3. 关键：调用导入的无人机仿真核心函数
        uav_sim_result = run_uav_simulation_core(params, self)

        # 4. 构造标准化结果
        result = {
            "task_id": self.request.id,
            "params": {
                "agent_type": 1,  # 标记为无人机仿真
                **params  # 透传前端参数
            },
            "simulation_data": {
                "agent_count": uav_sim_result["uav_num"],
                "task_type": 1,  # 无人机路径仿真
                "warehouse_id": params.get("warehouse_id", 0),
                **uav_sim_result  # 合并仿真结果
            },
            "progress": 100,
            "status": "SUCCESS",
            "error": None,
            "finish_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }

        # 5. 返回标准化结果
        return SimulationResultSchema(**result).dict()

    except Exception as e:
        # 异常处理
        try:
            db = next(get_sync_db())
            if db:
                db.rollback()
        except:
            pass
        self.update_state(state="FAILURE", meta={"error": str(e), "progress": 0})
        raise e


#进行卡车的仿真路线规划，更新数据库的卡车传感器数据
@app.task(bind=True, name="run_simulation_task_agent_truck")
def run_simulation_task_agent_truck(self, params: dict):
    """
    最终版：路线规划 + 分钟级位置 + 油耗计算 + 传感器数据写入数据库
    """
    db = None  # 初始化数据库会话
    try:
        # 1. 初始化任务状态
        self.update_state(state="STARTED", meta={"progress": 0})
        task_id = self.request.id  # Celery任务ID（关联task_main表的task_id）
        agent_id = params.get("agent_id", "truck_001")  # 前端传入AgentID，默认truck_001
        print(f"开始执行卡车仿真任务，AgentID：{agent_id}，任务ID：{task_id}")

        # 2. 校验核心参数
        required_params = ["start_lat", "start_lng", "end_lat", "end_lng"]
        for param in required_params:
            if param not in params:
                raise ValueError(f"缺少GPS参数：{param}")
        truck_params = params.get("truck_params", {})

        # 3. 调用GraphHopper规划路线（进度20%）
        self.update_state(state="STARTED", meta={"progress": 20})

        # 修正：根据 debug/test_graphhopper.py 的成功经验调整参数
        # 1. 坐标顺序应为 lat,lng
        # 2. 使用 profile=car (或 truck) 替代 vehicle/weighting
        # 3. 添加 layer=OpenStreetMap (如果服务端需要)
        gh_params = {
            "point": [f"{params['start_lat']},{params['start_lng']}", f"{params['end_lat']},{params['end_lng']}"],
            "profile": "car",  # 优先使用测试通过的 profile
            "layer": "OpenStreetMap",
            "points_encoded": False,
            "details": ["road_type", "distance", "time", "speed"] # details 需要是列表或多次重复的键，requests params支持列表
        }

        try:
            print(f"正在请求 GraphHopper: {GRAPH_HOPPER_BASE_URL} 参数: {gh_params}")
            # 使用 params 字典传参，requests 会自动处理 url 编码和格式
            response = requests.get(GRAPH_HOPPER_BASE_URL, params=gh_params, timeout=10)

            # 如果 profile=car 失败，尝试回退到 profile=truck (可选优化，暂不加，保持简单)
            response.raise_for_status()

            gh_data = response.json()
            if "paths" not in gh_data:
                raise ValueError(f"GraphHopper 响应缺少 'paths' 字段: {gh_data}")

            best_route = gh_data["paths"][0]
            print("GraphHopper 请求成功")

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError, ValueError) as e:
            print(f"GraphHopper 连接失败或超时 ({e})，切换至 Mock 模式...")

            # --- Mock 兜底逻辑 ---
            # 1. 计算直线距离 (Haversine公式简化版)
            lat1, lng1 = float(params['start_lat']), float(params['start_lng'])
            lat2, lng2 = float(params['end_lat']), float(params['end_lng'])
            R = 6371  # 地球半径 km
            dlat = math.radians(lat2 - lat1)
            dlng = math.radians(lng2 - lng1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            straight_dist_km = R * c

            # 模拟路网弯曲系数 1.4
            mock_distance_m = straight_dist_km * 1.4 * 1000

            # 2. 估算时间 (假设平均时速 60km/h)
            mock_speed_mps = 60 / 3.6  # 16.6 m/s
            mock_time_ms = (mock_distance_m / mock_speed_mps) * 1000

            # 3. 构造 Mock 响应结构 (模仿 GraphHopper)
            best_route = {
                "distance": mock_distance_m,
                "time": mock_time_ms,
                "points": {"coordinates": [[lng1, lat1], [lng2, lat2]]}, # 仅起点终点
                "segments": [{"distance_time": {"times": [mock_time_ms]}}] # 简化的分段
            }
            # --------------------

        # 4. 解析路线数据（进度50%）
        self.update_state(state="STARTED", meta={"progress": 50})
        route_points = [(p[0], p[1]) for p in best_route["points"]["coordinates"]]
        route_times = [t / 1000 for t in best_route["segments"][0]["distance_time"]["times"]] if "segments" in best_route else []
        if not route_times or len(route_times) != len(route_points) - 1:
            total_time = best_route["time"] / 1000
            route_times = [total_time / (len(route_points) - 1)] * (len(route_points) - 1) if len(route_points) > 1 else []

        # 5. 计算每分钟位置（进度70%）
        self.update_state(state="STARTED", meta={"progress": 70})
        minute_positions = calculate_truck_minute_positions(route_points, route_times)

        # 6. 计算油耗（进度85%）
        self.update_state(state="STARTED", meta={"progress": 85})
        fuel_result = calculate_truck_fuel_consumption(best_route, truck_params)

        # 7. 新增：写入传感器数据到数据库（进度90%）
        self.update_state(state="STARTED", meta={"progress": 90})
        db = next(get_sync_db())  # 获取ORM会话
        save_agent_sensor_data(db, task_id, agent_id, minute_positions, best_route, params)

        # 8. 构造最终结果
        result = {
            "task_id": task_id,
            "params": {"agent_type": 1, **params},
            "simulation_data": {
                "agent_count": 1,
                "task_type": 1,
                "warehouse_id": params.get("warehouse_id", 0),
                "total_distance": round(best_route["distance"] / 1000, 2),
                "total_time": round(best_route["time"] / 3600000, 2),
                "route_points": route_points,
                "minute_positions": minute_positions,
                "fuel_consumption": fuel_result
            },
            "progress": 100,
            "status": "SUCCESS",
            "error": None,
            "finish_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }

        return SimulationResultSchema(**result).dict()

    except Exception as e:
        # 异常时回滚数据库
        if db:
            db.rollback()
        self.update_state(state="FAILURE", meta={"error": str(e), "progress": 0})
        raise e
    finally:
        # 确保数据库会话关闭
        if db:
            db.close()




# ---------------- Celery异步任务（核心） ----------------
@app.task(bind=True, name="run_simulation_task_agent_robot")
def run_simulation_task_agent_robot(self, params: dict):
    """
    仓储机器人仿真Celery异步任务
    支持两种参数模式：
    1. 单任务：params = {"agent_id": "robot001", "goods_name": "手机"}
    2. 批量任务：params = {"csv_path": "/path/to/tasks.csv"}
    :param self: Celery任务上下文
    :param params: 前端传入参数
    :return: 标准化仿真结果
    """
    try:
        # 1. 初始化任务状态
        self.update_state(state="STARTED", meta={"progress": 0})
        print(f"开始执行仓储机器人仿真任务，参数：{params}")

        # 2. （可选）数据库操作（保存任务记录）
        db = next(get_sync_db())
        # 示例：task_record = TaskRecord(task_id=self.request.id, params=params, status="STARTED")
        # db.add(task_record)
        # db.commit()

        # 3. 执行仿真任务（区分单任务/批量任务）
        if "csv_path" in params:
            # 批量任务模式
            sim_result = simulate_batch_tasks(params["csv_path"], self)
        elif "agent_id" in params and "goods_name" in params:
            # 单任务模式
            sim_result = simulate_single_task(params["agent_id"], params["goods_name"], self)
        else:
            raise Exception("参数错误：必须提供 csv_path 或 agent_id+goods_name")

        # 4. 构造标准化结果
        result = {
            "task_id": self.request.id,
            "params": {
                "agent_type": 3,  # 标记为仓储机器人仿真
                **params  # 透传前端参数
            },
            "simulation_data": {
                "agent_count": 1 if "agent_id" in params else sim_result.get("batch_task_count", 0),
                "task_type": 2,  # 标记为仓储机器人任务
                "warehouse_id": sim_result.get("warehouse_id", 0),
                **sim_result  # 合并仿真结果
            },
            "progress": 100,
            "status": sim_result["status"],
            "error": sim_result["error"],
            "finish_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }

        # 5. 返回标准化结果
        return SimulationResultSchema(**result).dict()

    except Exception as e:
        # 异常处理：回滚数据库、更新状态
        error_msg = str(e)
        try:
            db = next(get_sync_db())
            if db:
                db.rollback()
        except:
            pass
        self.update_state(state="FAILURE", meta={"error": error_msg, "progress": 0})
        # 构造失败结果
        fail_result = {
            "task_id": self.request.id,
            "params": {"agent_type": 3, **params},
            "simulation_data": {"agent_count": 0, "task_type": 2, "warehouse_id": 0},
            "progress": 0,
            "status": "FAILURE",
            "error": error_msg,
            "finish_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }
        raise e  # 让Celery记录异常
