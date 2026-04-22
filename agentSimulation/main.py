# main.py（FastAPI主文件）
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from common.db import get_db
import time
# 关键：从celery_worker.tasks导入定义好的任务函数
from celery_worker.tasks import run_simulation_task, run_simulation_task_agent_uav, run_simulation_task_agent_truck, run_simulation_task_agent_robot
from celery.result import AsyncResult 
from celery_worker.tasks import app as celery_app
app = FastAPI(title="AgentSim-Service")
@app.get("/")                    # ← 新增
def root():
    return {"message": "AgentSimulation API 已启动，请访问 /docs 查看接口"}
@app.post("/api/v1/run_simulation")
async def run_sim(params: dict, db: AsyncSession = Depends(get_db)):
    task = run_simulation_task.delay(params)  # 提交任务到Celery队列
    return {"task_id": task.id}

# Agent1仿真接口
@app.post("/api/v1/simulation/agentuav")
async def simulate_agent_uav(params: dict):
    task = run_simulation_task_agent_uav.delay(params)
    return {"task_id": task.id, "agent_type": "uav"}

# Agent2仿真接口
@app.post("/api/v1/simulation/agenttruck")
async def simulate_agent_truck(params: dict):
    task = run_simulation_task_agent_truck.delay(params)
    return {"task_id": task.id, "agent_type": "truck"}

# Agent3仿真接口
@app.post("/api/v1/simulation/agentrobot")
async def simulate_agent_robot(params: dict):
    task = run_simulation_task_agent_robot.delay(params)
    return {"task_id": task.id, "agent_type": "robot"}

@app.get("/api/v1/task/{task_id}")
async def get_result(task_id: str):
    # 通过任务函数的AsyncResult获取结果
    res = celery_app.AsyncResult(task_id)
    return {"status": res.status, "result": res.result}

# 1. 提交任务接口（原有逻辑，新增返回 task_id + 查询地址）
@app.post("/api/agent1/simulation")
async def submit_agent1_task(params: dict):
    """接收参数，提交 Celery 任务，返回 task_id 和结果查询地址"""
    try:
        # 提交 Celery 任务
        task = run_simulation_task_agent_uav.delay(params)
        # 返回：task_id + 结果查询接口地址
        return {
            "task_id": task.id,
            "result_url": f"/api/agent1/result/{task.id}",  # 结果查询地址
            "status": "submitted"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"任务提交失败：{str(e)}")

# 2. 新增：查询任务结果接口
@app.get("/api/agent1/result/{task_id}")
async def get_agent1_task_result(task_id: str):
    """根据 task_id 查询 Celery 任务的完整结果"""
    # 获取 Celery 任务结果对象
    task_result = run_simulation_task_agent_uav.AsyncResult(task_id, app=run_simulation_task_agent_uav.app)
    
    if task_result.ready():  # 任务已完成（成功/失败）
        if task_result.successful():
            return {
                "task_id": task_id,
                "status": "success",
                "result": task_result.result,
                "finished_at": task_result.date_done.strftime("%Y-%m-%dT%H:%M:%S") if task_result.date_done else None
            }
        else:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(task_result.result),
                "finished_at": task_result.date_done.strftime("%Y-%m-%dT%H:%M:%S") if task_result.date_done else None
            }
    else:
        # 核心修复：适配所有 Celery 版本的进度获取逻辑
        progress = 0
        # 方案1：优先尝试 info（Celery 4.x+/5.x 通用）
        if hasattr(task_result, 'info') and isinstance(task_result.info, dict):
            progress = task_result.info.get("progress", 0)
        # 方案2：兼容旧版本的 state 字典（任务 update_state 时的自定义数据）
        elif not isinstance(task_result.state, str) and isinstance(task_result.state, dict):
            progress = task_result.state.get("meta", {}).get("progress", 0)
        
        return {
            "task_id": task_id,
            "status": "running",
            "progress": progress,
            "result": None
        }
        