#!/usr/bin/env bash
# file: start_all.sh
set -euo pipefail

##############################
# 0. 基础配置
##############################
# CONDA_BASE="$HOME/miniconda3"          # 改成你的 conda 安装目录
# export PATH="$CONDA_BASE/bin:$PATH"
# source "$CONDA_BASE/etc/profile.d/conda.sh"

##############################
# 1. 启动函数：run_in_tmux <session> <conda_env> <work_dir> <command...>
##############################
run_in_tmux(){
    local session=$1; shift
    local env=$1;     shift
    local workdir=$1; shift
    # 如果会话已存在，先杀掉
    tmux kill-session -t "$session" 2>/dev/null || true
    tmux new-session -d -s "$session" -n main -c "$workdir"
    tmux send-keys -t "$session:main" "conda activate $env" C-m
    tmux send-keys -t "$session:main" "exec $*" C-m
}

##############################
# 2. 依次启动 6 个服务
##############################
# ① Qwen3-8B 生成模型
run_in_tmux qwen3-8b  vllmModel  /home/sysuvis/program/huangw293/model \
  bash -c 'CUDA_VISIBLE_DEVICES=2,3 vllm serve /home/sysuvis/huangw293/model/qwen3-8b/tmp/Qwen/Qwen3-8B --served-model-name Qwen3-8B --max_model_len 8192 --port 8080 --trust-remote-code --gpu-memory-utilization 0.5 --tensor-parallel-size 2'

# ② Qwen3-Embedding-8B 向量模型
run_in_tmux qwen3-emb vllmModel  /home/sysuvis/program/huangw293/model \
  bash -c 'CUDA_VISIBLE_DEVICES=2,3 \
VLLM_USE_MODELSCOPE=true \
vllm serve Qwen/Qwen3-Embedding-8B \
  --served-model-name Qwen3-Embedding-8B \
  --port 8021 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.3 \
  --tensor-parallel-size 2'

# ③ FastAPI 主服务
run_in_tmux api  gym_py38  /home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/agentSimulation \
  uvicorn main:app --host 127.0.0.1 --port 8090 --reload

# ④ Celery 异步任务
run_in_tmux celery  gym_py38  /home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/agentSimulation \
  celery -A celery_worker.app worker \
  --concurrency=10 --max-memory-per-child=2048 --max-tasks-per-child=100 --loglevel=info

# ⑤ GraphRag utils
run_in_tmux graph_utils  GraphragTest  /home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/GraphRag \
  python utils/main.py

# ⑥ GraphRag 主程序
run_in_tmux graph_main  GraphragTest  /home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG \
  python main.py

##############################
# 3. 查看命令提示
##############################
echo "All services are starting in tmux sessions:"
echo "  tmux ls               # 查看会话列表"
echo "  tmux attach -t api    # 举例：attach 到 FastAPI 窗口"
echo "  ./stop_all.sh         # 需要的话再写一个一次性 kill 的脚本"