# celery_worker/__init__.py
import os, sys

# 把项目根（agentSimulation/）塞进 PATH
proj_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)
# celery_worker/__init__.py
import os
from celery import Celery
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 初始化Celery实例
app = Celery(
    "agent_sim",  # Celery实例名称
    # 消息队列（broker）：用于接收任务（推荐Redis/RabbitMQ）
    broker=os.getenv("CELERY_BROKER_URL", "redis://:redis307@localhost:6379/0"),
    # 结果存储（backend）：用于保存任务状态/结果
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://:redis307@localhost:6379/1")
)


# 自动发现任务（会扫描tasks.py中的@app.task装饰的函数）
app.autodiscover_tasks(["celery_worker"])