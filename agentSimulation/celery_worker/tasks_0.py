
# celery_worker/__init__.py
import os, sys

# 把项目根（agentSimulation/）塞进 PATH
proj_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)
# celery_worker/tasks.py
import time
from celery_worker import app  # 导入上面初始化的Celery实例
from common.db import get_sync_db  # 若需要数据库操作，需用同步DB（Celery不支持异步Session）
from common.schema import SimulationResultSchema
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
    

# 核心：用@app.task装饰，将普通函数转为Celery异步任务
@app.task(bind=True, name="run_simulation_task_agent1")  # name可选，指定任务名（方便查询）
def run_simulation_task_Agent1(self, params: dict):

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
                 "agent_type": 1,

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
    


# 核心：用@app.task装饰，将普通函数转为Celery异步任务
@app.task(bind=True, name="run_simulation_task_agent2")  # name可选，指定任务名（方便查询）
def run_simulation_task_Agent2(self, params: dict):

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
                 "agent_type": 2,

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
    

# 核心：用@app.task装饰，将普通函数转为Celery异步任务
@app.task(bind=True, name="run_simulation_task_agent3")  # name可选，指定任务名（方便查询）
def run_simulation_task_Agent3(self, params: dict):

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
                 "agent_type": 3,

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
    