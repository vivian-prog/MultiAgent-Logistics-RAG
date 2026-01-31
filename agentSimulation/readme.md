# 进入虚拟环境
conda activate gym_py38
# 运行FastAPI服务
uvicorn main:app --host 127.0.0.1 --port 8090 --reload
# 带资源限制的启动命令（推荐生产环境使用）
celery -A celery_worker.app worker --concurrency=10 --max-memory-per-child=2048 --max-tasks-per-child=100 --loglevel=info
