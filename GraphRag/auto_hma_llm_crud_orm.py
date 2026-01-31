from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base  # 修复：2.0版本正确导入路径
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv
import os
from datetime import datetime

# 加载环境变量
load_dotenv()

# -------------------------- 1. 数据库连接配置 --------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "huangw293"),
    "password": os.getenv("DB_PASSWORD", "Huangw293!@#"),
    "database": os.getenv("DB_NAME", "hma_llm"),
    "charset": "utf8mb4"
}

# 构建数据库连接URL（MySQL+pymysql）
# DB_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"
import urllib.parse
encoded_password = urllib.parse.quote_plus(DB_CONFIG['password'])  # 自动编码所有特殊字符

# 构建正确的连接URL（使用编码后的密码）
DB_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{encoded_password}@{DB_CONFIG['host']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"


# 创建引擎（echo=True可打印SQL日志，生产环境关闭）
engine = create_engine(DB_URL, echo=False)
# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# 基类（修复：2.0版本正确写法）
Base = declarative_base()

# -------------------------- 2. 数据模型定义（对应原数据表） --------------------------
class WarehouseBase(Base):
    """仓储基础信息表（对应原warehouse_base）"""
    __tablename__ = "warehouse_base"
    
    warehouse_id = Column(Integer, primary_key=True, autoincrement=True, comment="仓储ID")
    warehouse_name = Column(String(50), nullable=False, comment="仓储名称")
    location_x = Column(Float, nullable=False, comment="仓储X坐标")
    location_y = Column(Float, nullable=False, comment="仓储Y坐标")
    max_capacity = Column(Integer, nullable=False, comment="最大容量")
    status = Column(Integer, default=1, comment="状态：1-可用，0-不可用")
    
    # 关联：一个仓储对应多个物品
    goods = relationship("WarehouseGoods", back_populates="warehouse", cascade="all, delete-orphan")

class WarehouseGoods(Base):
    """货架与物品信息表（对应原warehouse_goods）"""
    __tablename__ = "warehouse_goods"
    
    goods_id = Column(Integer, primary_key=True, autoincrement=True, comment="物品ID")
    warehouse_id = Column(Integer, ForeignKey("warehouse_base.warehouse_id"), nullable=False, comment="关联仓储ID")
    shelf_id = Column(String(20), nullable=False, comment="货架ID")
    shelf_x = Column(Float, nullable=False, comment="货架X坐标")
    shelf_y = Column(Float, nullable=False, comment="货架Y坐标")
    goods_name = Column(String(50), nullable=False, comment="物品名称")
    goods_type = Column(String(30), nullable=False, comment="物品类型")
    goods_weight = Column(Float, nullable=False, comment="物品重量")
    stock_quantity = Column(Integer, default=0, comment="库存数量")
    target_location = Column(String(100), nullable=False, comment="目标位置")
    
    # 关联：物品属于一个仓储
    warehouse = relationship("WarehouseBase", back_populates="goods")
    # 关联：一个物品对应多个任务
    tasks = relationship("TaskMain", back_populates="goods", cascade="all, delete-orphan")

class AgentBase(Base):
    """Agent基础信息表（对应原agent_base）"""
    __tablename__ = "agent_base"
    
    agent_id = Column(String(20), primary_key=True, comment="AgentID（自定义，非自增）")
    agent_type = Column(String(30), nullable=False, comment="Agent类型：无人机/卡车/机器人等")
    warehouse_id = Column(Integer, ForeignKey("warehouse_base.warehouse_id"), nullable=True, comment="关联仓储ID")
    max_load = Column(Float, nullable=False, comment="最大载重")
    max_speed = Column(Float, nullable=False, comment="最大速度")
    battery_capacity = Column(Float, nullable=False, comment="电池容量")
    status = Column(Integer, default=0, comment="状态：0-空闲，1-忙碌，2-故障")
    last_maintain_time = Column(DateTime, nullable=True, comment="最后维护时间")
    
    # 关联：一个Agent对应多个任务关联记录
    task_rels = relationship("TaskAgentRel", back_populates="agent", cascade="all, delete-orphan")

class TaskMain(Base):
    """任务主表（对应原task_main）"""
    __tablename__ = "task_main"
    
    task_id = Column(String(20), primary_key=True, comment="任务ID（自定义，非自增）")
    task_type = Column(String(30), nullable=False, comment="任务类型：配送/搬运等")
    goods_id = Column(Integer, ForeignKey("warehouse_goods.goods_id"), nullable=False, comment="关联物品ID")
    target_x = Column(Float, nullable=False, comment="目标X坐标")
    target_y = Column(Float, nullable=False, comment="目标Y坐标")
    require_time = Column(DateTime, nullable=False, comment="要求完成时间")
    status = Column(Integer, default=0, comment="状态：0-待执行，1-执行中，2-已完成，3-失败")
    complete_time = Column(DateTime, nullable=True, comment="实际完成时间")
    
    # 关联：一个任务对应一个物品
    goods = relationship("WarehouseGoods", back_populates="tasks")
    # 关联：一个任务对应多个Agent关联记录
    agent_rels = relationship("TaskAgentRel", back_populates="task", cascade="all, delete-orphan")

class TaskAgentRel(Base):
    """任务-Agent关联表（对应原task_agent_rel）"""
    __tablename__ = "task_agent_rel"
    
    rel_id = Column(Integer, primary_key=True, autoincrement=True, comment="关联ID")
    task_id = Column(String(20), ForeignKey("task_main.task_id"), nullable=False, comment="关联任务ID")
    agent_id = Column(String(20), ForeignKey("agent_base.agent_id"), nullable=False, comment="关联AgentID")
    agent_role = Column(String(30), nullable=False, comment="Agent角色：主执行/辅助等")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    status = Column(Integer, default=0, comment="状态：0-执行中，1-完成，2-失败")
    feedback_info = Column(Text, nullable=True, comment="反馈信息")
    
    # 关联：一个关联记录对应一个任务/一个Agent
    task = relationship("TaskMain", back_populates="agent_rels")
    agent = relationship("AgentBase", back_populates="task_rels")
# -------------------------- 3. 工具函数：格式化SQLAlchemy对象输出 --------------------------
def format_sqlalchemy_obj(obj):
    """
    格式化SQLAlchemy模型对象，只保留字段和值，剔除私有属性
    """
    if not obj:
        return None
    # 过滤掉_sa_instance_state等私有属性
    return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
# -------------------------- 4. 基础CRUD基类（修复会话获取逻辑） --------------------------
class BaseCRUD:
    def __init__(self, model):
        self.model = model  # 传入具体模型类（如WarehouseBase）
    
    def get_db(self):
        """获取数据库会话（适用于Web框架依赖注入，普通使用直接实例化）"""
        db = SessionLocal()
        try:
            return db
        finally:
            db.close()
    
    def create(self, db, **kwargs):
        """新增数据"""
        try:
            obj = self.model(**kwargs)
            db.add(obj)
            db.commit()
            db.refresh(obj)  # 刷新获取自增ID等字段
            # 修复：动态获取主键值
            primary_key = [col.name for col in self.model.__table__.primary_key.columns][0]
            print(f"{self.model.__tablename__} 新增成功，ID：{getattr(obj, primary_key)}")
            return obj
        except Exception as e:
            db.rollback()
            print(f"{self.model.__tablename__} 新增失败：{str(e)}")
            return False
    
    def read(self, db, **filters):
        """查询单条数据（按筛选条件）"""
        try:
            obj = db.query(self.model).filter_by(**filters).first()
            formatted_obj = format_sqlalchemy_obj(obj)
            if obj:
                print(f"✅ {self.model.__tablename__} 查询成功 | 结果：{formatted_obj}")
            else:
                print(f"⚠️ {self.model.__tablename__} 查询失败 | 原因：未找到符合条件的数据")
            
            return obj if obj else f"未找到{self.model.__tablename__}符合条件的数据"
        except Exception as e:
            print(f"{self.model.__tablename__} 查询失败：{str(e)}")
            return None
    
    def update(self, db, filters, **kwargs):
        """更新数据（先筛选，后更新）"""
        if not kwargs:
            return False
        try:
            obj = db.query(self.model).filter_by(**filters)
            rowcount = obj.update(kwargs, synchronize_session=False)
            db.commit()
            print(f"{self.model.__tablename__} 更新成功，影响行数：{rowcount}")
            return True if rowcount > 0 else False
        except Exception as e:
            db.rollback()
            print(f"{self.model.__tablename__} 更新失败：{str(e)}")
            return False
    
    def delete(self, db, **filters):
        """删除数据"""
        try:
            rowcount = db.query(self.model).filter_by(**filters).delete(synchronize_session=False)
            db.commit()
            print(f"{self.model.__tablename__} 删除成功，影响行数：{rowcount}")
            return True if rowcount > 0 else False
        except Exception as e:
            db.rollback()
            print(f"{self.model.__tablename__} 删除失败：{str(e)}")
            return False
    
    def query_all(self, db, **filters):
        """查询所有数据（可选筛选）"""
        try:
            query = db.query(self.model)
            if filters:
                query = query.filter_by(**filters)
            results = query.all()
            if results:
                print(f"✅ {self.model.__tablename__} 批量查询成功 | 总条数：{len(results)}")
                for idx, res in enumerate(results):
                    print(f"   第{idx+1}条：{format_sqlalchemy_obj(res)}")
            else:
                print(f"⚠️ {self.model.__tablename__} 批量查询 | 结果：无数据")
            return results if results else f"{self.model.__tablename__} 无数据"
        except Exception as e:
            print(f"{self.model.__tablename__} 批量查询失败：{str(e)}")
            return None

# -------------------------- 4. 各表CRUD实现类（对齐原功能） --------------------------
class WarehouseBaseCRUD(BaseCRUD):
    def __init__(self):
        super().__init__(WarehouseBase)
    
    # 重载create，适配原参数顺序
    def create_warehouse(self, db, warehouse_name, location_x, location_y, max_capacity, status=1):
        return self.create(db, 
                          warehouse_name=warehouse_name,
                          location_x=location_x,
                          location_y=location_y,
                          max_capacity=max_capacity,
                          status=status)

class WarehouseGoodsCRUD(BaseCRUD):
    def __init__(self):
        super().__init__(WarehouseGoods)
    
    def create_goods(self, db, warehouse_id, shelf_id, shelf_x, shelf_y, goods_name, goods_type, goods_weight, target_location, stock_quantity=0):
        return self.create(db,
                          warehouse_id=warehouse_id,
                          shelf_id=shelf_id,
                          shelf_x=shelf_x,
                          shelf_y=shelf_y,
                          goods_name=goods_name,
                          goods_type=goods_type,
                          goods_weight=goods_weight,
                          stock_quantity=stock_quantity,
                          target_location=target_location)

class AgentBaseCRUD(BaseCRUD):
    def __init__(self):
        super().__init__(AgentBase)
    
    def create_agent(self, db, agent_id, agent_type, max_load, max_speed, battery_capacity, warehouse_id=None, status=0, last_maintain_time=None):
        return self.create(db,
                          agent_id=agent_id,
                          agent_type=agent_type,
                          max_load=max_load,
                          max_speed=max_speed,
                          battery_capacity=battery_capacity,
                          warehouse_id=warehouse_id,
                          status=status,
                          last_maintain_time=last_maintain_time)

class TaskMainCRUD(BaseCRUD):
    def __init__(self):
        super().__init__(TaskMain)
    
    def create_task(self, db, task_id, task_type, goods_id, target_x, target_y, require_time, status=0, complete_time=None):
        return self.create(db,
                          task_id=task_id,
                          task_type=task_type,
                          goods_id=goods_id,
                          target_x=target_x,
                          target_y=target_y,
                          require_time=require_time,
                          status=status,
                          complete_time=complete_time)

class TaskAgentRelCRUD(BaseCRUD):
    def __init__(self):
        super().__init__(TaskAgentRel)
    
    def create_rel(self, db, task_id, agent_id, agent_role, start_time, end_time=None, status=0, feedback_info=None):
        return self.create(db,
                          task_id=task_id,
                          agent_id=agent_id,
                          agent_role=agent_role,
                          start_time=start_time,
                          end_time=end_time,
                          status=status,
                          feedback_info=feedback_info)

# # -------------------------- 5. 使用示例（修复会话获取方式） --------------------------
# if __name__ == "__main__":
#     # 1. 创建数据表（首次运行执行，后续注释）
#     # Base.metadata.create_all(bind=engine)
#     # print("数据表创建成功")
    
#     # 2. 获取数据库会话（修复：正确的实例化方式）
#     db = SessionLocal()
    
#     # 3. 仓储操作示例
#     warehouse_crud = WarehouseBaseCRUD()
#     # 新增仓储（示例：传入具体参数）
#     warehouse_obj = warehouse_crud.create_warehouse(db, "主仓库A", 100.0, 200.0, 5000)
#     if warehouse_obj:
#         print(f"新增仓储ID：{warehouse_obj.warehouse_id}")
    
#     # 查询单个仓储
#     warehouse = warehouse_crud.read(db, warehouse_id=1)
#     if warehouse and not isinstance(warehouse, str):
#         print(f"仓储名称：{warehouse.warehouse_name}，最大容量：{warehouse.max_capacity}")
#     else:
#         print(warehouse)
    
#     # 更新仓储
#     update_result = warehouse_crud.update(db, {"warehouse_id":1}, max_capacity=6000)
#     print(f"更新结果：{update_result}")
    
#     # 查询所有可用仓储
#     all_warehouses = warehouse_crud.query_all(db, status=1)
#     if all_warehouses and not isinstance(all_warehouses, str):
#         for wh in all_warehouses:
#             print(f"仓储ID：{wh.warehouse_id}，名称：{wh.warehouse_name}")
#     else:
#         print(all_warehouses)
    
#     # 删除仓储
#     delete_result = warehouse_crud.delete(db, warehouse_id=1)
#     print(f"删除结果：{delete_result}")
    
#     # 4. 关闭会话
#     db.close()


# -------------------------- 4. 测试类（继承BaseCRUD） --------------------------
class WarehouseBaseCRUD(BaseCRUD):
    def __init__(self):
        super().__init__(WarehouseBase)

# -------------------------- 5. 主测试函数 --------------------------
def main():
    # 1. 初始化数据表（首次运行必须执行）
    print("===== 1. 初始化数据表 =====")
    Base.metadata.create_all(bind=engine)
    print("✅ 数据表初始化完成（若已存在则忽略）")

    # 2. 获取数据库会话
    db = SessionLocal()
    try:
        # 3. 初始化CRUD实例
        warehouse_crud = WarehouseBaseCRUD()

        # 4. 测试create（新增仓储）
        print("\n===== 2. 测试create（新增数据） =====")
        # 新增测试数据
        warehouse_obj = warehouse_crud.create(
            db,
            warehouse_name="测试仓储001",
            location_x=100.5,
            location_y=200.8,
            max_capacity=5000,
            status=1
        )
        # 记录新增的ID，用于后续测试
        test_warehouse_id = warehouse_obj.warehouse_id if warehouse_obj else None

        # 5. 测试read（单条查询）
        print("\n===== 3. 测试read（单条查询） =====")
        if test_warehouse_id:
            # 按ID查询
            warehouse_crud.read(db, warehouse_id=test_warehouse_id)
            # 测试查询不存在的数据
            warehouse_crud.read(db, warehouse_id=9999)

        # 6. 测试update（更新数据）
        print("\n===== 4. 测试update（更新数据） =====")
        if test_warehouse_id:
            # 更新最大容量和状态
            warehouse_crud.update(
                db,
                filters={"warehouse_id": test_warehouse_id},
                max_capacity=6000,
                status=0
            )
            # 验证更新结果
            warehouse_crud.read(db, warehouse_id=test_warehouse_id)
            # 测试更新不存在的数据
            warehouse_crud.update(
                db,
                filters={"warehouse_id": 9999},
                max_capacity=7000
            )

        # 7. 测试query_all（批量查询）
        print("\n===== 5. 测试query_all（批量查询） =====")
        # 查询所有数据
        warehouse_crud.query_all(db)
        # 按状态筛选查询
        warehouse_crud.query_all(db, status=0)

        # 8. 测试delete（删除数据）
        print("\n===== 6. 测试delete（删除数据） =====")
        if test_warehouse_id:
            # 删除新增的测试数据
            warehouse_crud.delete(db, warehouse_id=test_warehouse_id)
            # 验证删除结果
            warehouse_crud.read(db, warehouse_id=test_warehouse_id)
            # 测试删除不存在的数据
            warehouse_crud.delete(db, warehouse_id=9999)

        # 9. 最终批量查询（验证数据清理）
        print("\n===== 7. 最终批量查询（验证清理） =====")
        warehouse_crud.query_all(db)

    except Exception as e:
        print(f"\n❌ 测试过程出错：{str(e)}")
        db.rollback()
    finally:
        # 10. 关闭会话
        db.close()
        print("\n===== 测试完成 =====")

# -------------------------- 6. 执行测试 --------------------------
if __name__ == "__main__":
    main()