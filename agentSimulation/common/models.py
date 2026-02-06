from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from common.db import Base  # 使用 common/db.py 中定义的 Base

# 1. 仓储基础信息表
class WarehouseBase(Base):
    __tablename__ = "warehouse_base"

    warehouse_id = Column(Integer, primary_key=True, autoincrement=True, comment="仓储ID")
    warehouse_name = Column(String(50), nullable=False, comment="仓储名称")
    location_x = Column(DECIMAL(10, 2), nullable=False, comment="仓储X坐标")
    location_y = Column(DECIMAL(10, 2), nullable=False, comment="仓储Y坐标")
    max_capacity = Column(Integer, nullable=False, comment="最大容量")
    status = Column(Integer, default=1, comment="状态：0=停用，1=正常，2=维护")
    create_time = Column(DateTime, default=datetime.now, nullable=False)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

# 2. 货架与物品信息表
class WarehouseGoods(Base):
    __tablename__ = "warehouse_goods"

    goods_id = Column(Integer, primary_key=True, autoincrement=True, comment="物品ID")
    warehouse_id = Column(Integer, ForeignKey("warehouse_base.warehouse_id"), nullable=False, comment="关联仓储ID")
    shelf_id = Column(String(20), nullable=False, comment="货架编号")
    shelf_x = Column(DECIMAL(10, 2), nullable=False, comment="货架X坐标")
    shelf_y = Column(DECIMAL(10, 2), nullable=False, comment="货架Y坐标")
    goods_name = Column(String(100), nullable=False, comment="物品名称")
    goods_type = Column(String(30), nullable=False, comment="物品类型")
    goods_weight = Column(DECIMAL(8, 2), nullable=False, comment="物品重量")
    stock_quantity = Column(Integer, default=0, comment="库存数量")
    target_location = Column(String(50), nullable=False, comment="目标交付点")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

# 3. Agent基础信息表
class AgentBase(Base):
    __tablename__ = "agent_base"

    agent_id = Column(String(20), primary_key=True, comment="Agent唯一标识")
    agent_type = Column(Integer, nullable=False, comment="类型：1=无人机，2=地面运输机器人，3=仓储机器人")
    warehouse_id = Column(Integer, ForeignKey("warehouse_base.warehouse_id"), nullable=True, comment="关联仓储ID")
    max_load = Column(DECIMAL(8, 2), nullable=False, comment="最大载重")
    max_speed = Column(DECIMAL(8, 2), nullable=False, comment="最大速度")
    battery_capacity = Column(Integer, nullable=False, comment="电池容量")
    status = Column(Integer, default=0, comment="状态：0=离线，1=待命，2=执行中，3=故障")
    last_maintain_time = Column(DateTime, nullable=True, comment="最后维护时间")

# 4. 任务主表
class TaskMain(Base):
    __tablename__ = "task_main"

    task_id = Column(String(30), primary_key=True, comment="任务ID")
    task_type = Column(Integer, nullable=False, comment="类型：1=物流运输，2=紧急调货")
    goods_id = Column(Integer, ForeignKey("warehouse_goods.goods_id"), nullable=False, comment="关联物品ID")
    target_x = Column(DECIMAL(12, 6), nullable=False, comment="目标点X坐标")
    target_y = Column(DECIMAL(12, 6), nullable=False, comment="目标点Y坐标")
    require_time = Column(DateTime, nullable=False, comment="要求完成时间")
    status = Column(Integer, default=0, comment="状态：0=未开始，1=执行中，2=完成，3=失败")
    create_time = Column(DateTime, default=datetime.now, nullable=False)
    complete_time = Column(DateTime, nullable=True)

# 5. 任务-Agent关联表
class TaskAgentRel(Base):
    __tablename__ = "task_agent_rel"

    rel_id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(30), ForeignKey("task_main.task_id"), nullable=False)
    agent_id = Column(String(20), ForeignKey("agent_base.agent_id"), nullable=False)
    agent_role = Column(String(20), nullable=False, comment="分工")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(Integer, default=0, comment="状态：0=未开始，1=执行中，2=完成")
    feedback_info = Column(String(200), nullable=True)

# 6. 无人机传感器数据表
class AgentUavSensor(Base):
    __tablename__ = "agent_uav_sensor"

    sensor_id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(20), ForeignKey("agent_base.agent_id"), nullable=False)
    task_id = Column(String(30), ForeignKey("task_main.task_id"), nullable=False)
    gps_x = Column(DECIMAL(12, 6), nullable=False, comment="GPS经度")
    gps_y = Column(DECIMAL(12, 6), nullable=False, comment="GPS纬度")
    altitude = Column(DECIMAL(8, 2), nullable=False, comment="飞行高度")
    attitude_angle = Column(DECIMAL(6, 2), nullable=False, comment="姿态角")
    obstacle_dist = Column(DECIMAL(8, 2), nullable=False, comment="障碍物距离")
    battery_remaining = Column(Integer, nullable=False, comment="剩余电量")
    signal_strength = Column(Integer, nullable=False, comment="信号强度")
    collect_time = Column(DateTime, default=datetime.now, nullable=False)

# 7. 地面运输机器人传感器数据表
class AgentGroundSensor(Base):
    __tablename__ = "agent_ground_sensor"

    sensor_id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(20), ForeignKey("agent_base.agent_id"), nullable=False)
    task_id = Column(String(30), ForeignKey("task_main.task_id"), nullable=False)
    slam_x = Column(DECIMAL(10, 2), nullable=False, comment="SLAM X")
    slam_y = Column(DECIMAL(10, 2), nullable=False, comment="SLAM Y")
    speed = Column(DECIMAL(6, 2), nullable=False, comment="当前速度")
    obstacle_dist = Column(DECIMAL(8, 2), nullable=False, comment="障碍物距离")
    goods_status = Column(Integer, nullable=False, comment="物品状态：0=未装载，1=已装载，2=已交付")
    battery_remaining = Column(Integer, nullable=False, comment="剩余电量")
    collect_time = Column(DateTime, default=datetime.now, nullable=False)

# 8. 仓储机器人传感器数据表
class AgentWarehouseSensor(Base):
    __tablename__ = "agent_warehouse_sensor"

    sensor_id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(20), ForeignKey("agent_base.agent_id"), nullable=False)
    task_id = Column(String(30), ForeignKey("task_main.task_id"), nullable=False)
    shelf_nav_x = Column(DECIMAL(10, 2), nullable=False, comment="货架导航X")
    shelf_nav_y = Column(DECIMAL(10, 2), nullable=False, comment="货架导航Y")
    grip_force = Column(DECIMAL(6, 2), nullable=False, comment="夹持力")
    goods_weight = Column(DECIMAL(8, 2), nullable=False, comment="物品重量")
    warehouse_temp = Column(DECIMAL(4, 1), nullable=False, comment="仓储温度")
    battery_remaining = Column(Integer, nullable=False, comment="剩余电量")
    collect_time = Column(DateTime, default=datetime.now, nullable=False)

# 9. 无人机起降点信息表 (来自 sql/uav_landing_points.sql)
class UavLandingPoint(Base):
    __tablename__ = "uav_landing_points"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="起降点ID")
    name = Column(String(50), nullable=False, comment="起降点名称")
    location_x = Column(DECIMAL(12, 6), nullable=False, comment="GPS经度")
    location_y = Column(DECIMAL(12, 6), nullable=False, comment="GPS纬度")
    description = Column(String(200), nullable=True, comment="描述信息")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
