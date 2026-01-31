# common/schema.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime

# -------------------------- 基础模型（所有模型继承） --------------------------
class BaseSchema(BaseModel):
    """基础模型，提供配置"""
    class Config:
        orm_mode = True  # 支持从SQLAlchemy对象序列化
        arbitrary_types_allowed = True  # 允许任意类型（如datetime）

# -------------------------- 仓储模型（对应warehouse_base表） --------------------------
class WarehouseBaseSchema(BaseSchema):
    """仓储基础信息模型（入参/出参通用）"""
    warehouse_name: str = Field(..., min_length=1, max_length=50, description="仓储名称")
    location_x: float = Field(..., description="仓储X坐标")
    location_y: float = Field(..., description="仓储Y坐标")
    max_capacity: int = Field(..., gt=0, description="最大容量（大于0）")
    status: Optional[int] = Field(1, ge=0, le=1, description="状态：1-可用，0-不可用")

class WarehouseCreateSchema(WarehouseBaseSchema):
    """仓储创建模型（入参）"""
    pass  # 继承WarehouseBaseSchema即可

class WarehouseResponseSchema(WarehouseBaseSchema):
    """仓储响应模型（出参）"""
    warehouse_id: int = Field(..., description="仓储ID")
    create_time: Optional[datetime] = Field(None, description="创建时间")

# -------------------------- 仿真任务模型 --------------------------
class SimulationTaskParamsSchema(BaseSchema):
    """仿真任务参数模型（前端传入）"""
    # 示例：根据你的Agent仿真业务定义参数
    agent_count: int = Field(..., gt=0, description="Agent数量")
    task_type: str = Field(..., pattern=r"^[a-zA-Z0-9_]+$", description="任务类型")
    warehouse_id: int = Field(..., gt=0, description="关联仓储ID")
    config: Optional[Dict[str, Any]] = Field({}, description="仿真配置（自定义）")

class SimulationResultSchema(BaseSchema):
    """仿真任务结果模型（Celery返回）"""
    task_id: str = Field(..., description="Celery任务ID")
    params: SimulationTaskParamsSchema = Field(..., description="任务参数")
    simulation_data: Dict[str, Any] = Field(..., description="仿真结果数据")
    progress: int = Field(..., ge=0, le=100, description="任务进度（0-100）")
    status: Optional[str] = Field("SUCCESS", description="任务状态")
    error: Optional[str] = Field(None, description="错误信息（失败时）")
    finish_time: Optional[datetime] = Field(None, description="完成时间")

# -------------------------- 任务查询响应模型 --------------------------
class TaskStatusResponseSchema(BaseSchema):
    """任务状态查询响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态：PENDING/STARTED/SUCCESS/FAILURE")
    result: Optional[SimulationResultSchema] = Field(None, description="任务结果（成功时）")
    error: Optional[str] = Field(None, description="错误信息（失败时）")