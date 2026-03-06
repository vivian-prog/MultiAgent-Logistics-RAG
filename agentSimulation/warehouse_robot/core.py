# warehouse_robot/core.py
import pymysql
import datetime
import math
import random
import sys
import time
import csv
import os
from typing import List, Tuple

# 添加项目根目录到路径，以便导入配置模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from configs.loader import get_robot_config

# ---------------- 配置 ----------------
MYSQL_CFG = {
    "host": "localhost",
    "user": "huangw293",
    "password": "Huangw293!@#",
    "database": "hma_llm",
    "charset": "utf8mb4",
}

# 从配置文件读取Robot参数
_robot_config = get_robot_config()
SPEED_M_PER_SEC = _robot_config.get("speed_m_per_sec", 1.0)
GRIP_RATIO = _robot_config.get("grip_ratio", 10.0)
BATTERY_DRAIN_PER_SEC = _robot_config.get("battery_drain_per_sec", 0.02)
TIME_SCALE = _robot_config.get("time_scale", 10.0)  # 时间加速因子（10倍速），避免仿真过慢导致超时
# -------------------------------------

# ---------- 数据库连接 ----------
def get_conn():
    return pymysql.connect(**MYSQL_CFG)

# ---------- 查询仓储中心 ----------
def get_home_location() -> Tuple[float, float]: 
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT location_x, location_y FROM warehouse_base WHERE status = 1 LIMIT 1")
            row = cur.fetchone()
    if not row:
        raise Exception("没有状态正常的仓储中心")
    return float(row[0]), float(row[1])

# ---------- 查询商品 ----------
def query_goods(goods_name: str):
    """返回 (shelf_x, shelf_y, goods_weight, target_location, stock_quantity, warehouse_id)"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT shelf_x, shelf_y, goods_weight, target_location, stock_quantity, warehouse_id "
                "FROM warehouse_goods WHERE goods_name = %s LIMIT 1",
                (goods_name,))
            row = cur.fetchone()
    if not row:
        raise Exception(f"未找到物品：{goods_name}")
    if row[4] <= 0:
        raise Exception(f"商品 {goods_name} 库存为 0")
    return float(row[0]), float(row[1]), float(row[2]), row[3], int(row[4]), int(row[5])

# ---------- 库存扣减 ----------
def grab_goods(goods_name: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE warehouse_goods SET stock_quantity = stock_quantity - 1 "
                "WHERE goods_name = %s AND stock_quantity > 0",
                (goods_name,))
            conn.commit()
            return cur.rowcount

# ---------- 挪货到交付点 ----------
def move_to_delivered(goods_name: str, target_x: float, target_y: float):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE warehouse_goods "
                "SET shelf_x = %s, shelf_y = %s, shelf_id = 'DELIVERED' "
                "WHERE goods_name = %s",
                (target_x, target_y, goods_name))
            conn.commit()

# ---------- 传感器落库 ----------
def log_sensor(rec: dict):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO agent_warehouse_sensor "
                "(agent_id, task_id, shelf_nav_x, shelf_nav_y, grip_force, goods_weight, "
                "battery_remaining, collect_time, warehouse_temp) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (rec['agent_id'], rec['task_id'], rec['shelf_nav_x'], rec['shelf_nav_y'],
                 rec['grip_force'], rec['goods_weight'], rec['battery_remaining'],
                 rec['collect_time'], 0.0))
            conn.commit()

# ---------- 机器人类 ----------
class Robot:
    def __init__(self, agent_id: str, task_id: str, home_x: float, home_y: float):
        self.agent_id = agent_id
        self.task_id = task_id
        self.x = home_x
        self.y = home_y
        self.battery = 100.0
        self.grip_force = 0.0
        self.goods_weight = 0.0

    def move_toward(self, target_x, target_y, step_sec=1):
        dx = target_x - self.x
        dy = target_y - self.y
        dist = math.hypot(dx, dy)
        if dist < 0.1:
            return 0
        move_sec = min(step_sec, dist / SPEED_M_PER_SEC)
        ratio = (SPEED_M_PER_SEC * move_sec) / dist
        self.x += dx * ratio
        self.y += dy * ratio
        return move_sec

    def sense(self) -> dict:
        return dict(
            agent_id=self.agent_id,
            task_id=self.task_id,
            shelf_nav_x=round(self.x, 2),
            shelf_nav_y=round(self.y, 2),
            grip_force=round(self.grip_force, 2),
            goods_weight=round(self.goods_weight, 2),
            battery_remaining=int(self.battery),
            collect_time=datetime.datetime.now()
        )

# ---------- 解析CSV文件 ----------
def parse_task_csv(csv_path: str) -> List[Tuple[str, str]]:
    """
    解析任务CSV文件，格式：agent_id,goods_name（多行）
    :param csv_path: CSV文件路径
    :return: 任务列表 [(agent_id, goods_name), ...]
    """
    tasks = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            # 跳过表头（如果有）
            header = next(reader, None)
            if header and ('agent_id' in header[0].lower() or '机器人' in header[0]):
                pass  # 跳过表头行
            else:
                # 表头不存在，把第一行加入任务
                if header:
                    tasks.append((header[0].strip(), header[1].strip()))
            
            # 读取剩余行
            for row in reader:
                if len(row) < 2:
                    print(f"[WARN] 无效行：{row}，跳过")
                    continue
                agent_id = row[0].strip()
                goods_name = row[1].strip()
                tasks.append((agent_id, goods_name))
        
        if not tasks:
            raise Exception("CSV文件中无有效任务")
        return tasks

    except FileNotFoundError:
        raise Exception(f"CSV文件不存在：{csv_path}")
    except Exception as e:
        raise Exception(f"解析CSV失败：{str(e)}")

# ---------- 单任务仿真核心函数 ----------
def simulate_single_task(agent_id: str, goods_name: str, task_context=None, task_id=None) -> dict:
    """
    执行单个仓储机器人仿真任务
    :param agent_id: 机器人ID
    :param goods_name: 商品名称
    :param task_context: Celery任务上下文（用于更新进度）
    :param task_id: 指定任务ID（可选，若不传则自动生成）
    :return: 仿真结果字典
    """
    try:
        # 1. 初始化进度
        if task_context:
            task_context.update_state(state="STARTED", meta={"progress": 10})

        # 2. 获取基础数据
        home_x, home_y = get_home_location()
        shelf_x, shelf_y, weight, target_str, old_qty, wh_id = query_goods(goods_name)

        # 使用传入的task_id或自动生成
        if not task_id:
            task_id = f"T{datetime.datetime.now():%Y%m%d%H%M%S}"

        robot = Robot(agent_id, task_id, home_x, home_y)
        
        # 记录任务基础信息
        task_info = {
            "task_id": task_id,
            "agent_id": agent_id,
            "goods_name": goods_name,
            "home_location": (home_x, home_y),
            "shelf_location": (shelf_x, shelf_y),
            "target_location": (shelf_x + 20, shelf_y + 20),
            "goods_weight": weight,
            "initial_stock": old_qty,
            "warehouse_id": wh_id
        }

        # 3. 空载巡航去货架（进度10%→40%）
        if task_context:
            task_context.update_state(state="STARTED", meta={"progress": 20})
        print(f"[INFO] 空载巡航中：{agent_id} → 货架({shelf_x},{shelf_y})")
        step_count = 0
        max_steps = int(math.hypot(shelf_x - home_x, shelf_y - home_y) / SPEED_M_PER_SEC) + 1
        while math.hypot(robot.x - shelf_x, robot.y - shelf_y) > 0.1:
            sec = robot.move_toward(shelf_x, shelf_y)
            robot.battery -= BATTERY_DRAIN_PER_SEC * sec
            log_sensor(robot.sense())
            step_count += 1
            # 更新进度
            if task_context and max_steps > 0:
                progress = 10 + int((step_count / max_steps) * 30)
                task_context.update_state(state="STARTED", meta={"progress": min(progress, 40)})
            time.sleep(sec / TIME_SCALE) # 加速仿真

        # 4. 抓取商品（进度40%→50%）
        if task_context:
            task_context.update_state(state="STARTED", meta={"progress": 50})
        print(f"[INFO] 到达货架，抓取商品 {goods_name}")
        if grab_goods(goods_name) == 0:
            raise Exception("库存扣减失败")
        robot.goods_weight = weight
        robot.grip_force = weight * GRIP_RATIO
        log_sensor(robot.sense())

        # 5. 运输到交付点（进度50%→80%）
        if task_context:
            task_context.update_state(state="STARTED", meta={"progress": 60})
        target_x, target_y = shelf_x + 20, shelf_y + 20
        print(f"[INFO] 运输到交付点({target_x},{target_y})")
        step_count = 0
        max_steps = int(math.hypot(target_x - shelf_x, target_y - shelf_y) / SPEED_M_PER_SEC) + 1
        while math.hypot(robot.x - target_x, robot.y - target_y) > 0.1:
            sec = robot.move_toward(target_x, target_y)
            robot.battery -= BATTERY_DRAIN_PER_SEC * sec
            log_sensor(robot.sense())
            step_count += 1
            # 更新进度
            if task_context and max_steps > 0:
                progress = 50 + int((step_count / max_steps) * 30)
                task_context.update_state(state="STARTED", meta={"progress": min(progress, 80)})
            time.sleep(sec / TIME_SCALE) # 加速仿真

        # 6. 卸货并更新货位（进度80%→100%）
        if task_context:
            task_context.update_state(state="STARTED", meta={"progress": 90})
        print(f"[INFO] 到达交付点，卸货 {goods_name}")
        robot.goods_weight = 0
        robot.grip_force = 0
        log_sensor(robot.sense())
        move_to_delivered(goods_name, target_x, target_y)
        
        # 7. 整理结果
        if task_context:
            task_context.update_state(state="STARTED", meta={"progress": 100})
        
        result = {
            **task_info,
            "final_battery": round(robot.battery, 2),
            "final_stock": old_qty - 1,
            "delivery_location": (target_x, target_y),
            "status": "SUCCESS",
            "error": None
        }
        print(f"[INFO] 任务 {task_id} 完成，剩余电量 {robot.battery:.1f}%")
        return result

    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] 单任务仿真失败：{error_msg}")
        return {
            "agent_id": agent_id,
            "goods_name": goods_name,
            "status": "FAILURE",
            "error": error_msg,
            "final_battery": None,
            "task_id": None
        }

# ---------- 批量任务仿真核心函数 ----------
def simulate_batch_tasks(csv_path: str, task_context=None) -> dict:
    """
    执行CSV批量仓储机器人仿真任务
    :param csv_path: CSV文件路径
    :param task_context: Celery任务上下文（用于更新进度）
    :return: 批量仿真结果字典
    """
    try:
        # 1. 解析CSV
        if task_context:
            task_context.update_state(state="STARTED", meta={"progress": 5})
        tasks = parse_task_csv(csv_path)
        total_tasks = len(tasks)
        success_count = 0
        task_results = []

        # 2. 执行每个任务
        for idx, (agent_id, goods_name) in enumerate(tasks, 1):
            print(f"\n========== 执行任务 {idx}/{total_tasks} ==========")
            # 更新批量进度
            if task_context:
                batch_progress = 5 + int((idx / total_tasks) * 95)
                task_context.update_state(
                    state="STARTED", 
                    meta={
                        "progress": batch_progress,
                        "current_task": f"{idx}/{total_tasks}",
                        "agent_id": agent_id,
                        "goods_name": goods_name
                    }
                )
            # 执行单任务
            task_result = simulate_single_task(agent_id, goods_name)
            task_results.append(task_result)
            if task_result["status"] == "SUCCESS":
                success_count += 1

        # 3. 整理批量结果
        result = {
            "batch_task_count": total_tasks,
            "success_count": success_count,
            "failure_count": total_tasks - success_count,
            "task_results": task_results,
            "status": "SUCCESS" if success_count == total_tasks else "PARTIAL_SUCCESS",
            "error": None
        }
        print(f"\n[INFO] 批量任务执行完成：成功 {success_count}/{total_tasks}")
        return result

    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] 批量任务仿真失败：{error_msg}")
        return {
            "batch_task_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "task_results": [],
            "status": "FAILURE",
            "error": error_msg
        }