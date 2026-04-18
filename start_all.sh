#!/usr/bin/env bash
# file: start_all.sh
set -euo pipefail
# /home/sysuvis/huangw293/MultiAgent-Logistics-RAG/start_all.sh
# 等待几十秒
# tmux attach -t graph_main
# 想退回主界面时，按 Ctrl + b 松开，再按 d
# 关闭系统：tmux kill-server
##############################
# 0. 基础配置
##############################
CONDA_BASE="/home/sysuvis/program/miniconda"
export PATH="$CONDA_BASE/bin:$PATH"
source "$CONDA_BASE/etc/profile.d/conda.sh"

##############################
# 1. 启动函数 (已修复)
##############################
run_in_tmux(){
    local session=$1; shift
    local env=$1;     shift
    local workdir=$1; shift
    # 如果会话已存在，先杀掉
    tmux kill-session -t "$session" 2>/dev/null || true
    tmux new-session -d -s "$session" -n main -c "$workdir"
    tmux send-keys -t "$session:main" "conda activate $env" C-m
    # 【修改点】移除了 exec，这样发生报错时窗口不会闪退，你能直接看到 Error
    tmux send-keys -t "$session:main" "$*" C-m
}

##############################
# 2. 依次启动 6 个服务 (已修复)
##############################
# ① Qwen3-8B 生成模型
run_in_tmux qwen3-8b  vllmModel  /home/sysuvis/program/huangw293/model \
  "env CUDA_VISIBLE_DEVICES=2,3 vllm serve /home/sysuvis/huangw293/model/qwen3-8b/tmp/Qwen/Qwen3-8B --served-model-name Qwen3-8B --max_model_len 8192 --port 8080 --trust-remote-code --gpu-memory-utilization 0.5 --tensor-parallel-size 2"

# ② Qwen3-Embedding-8B 向量模型
run_in_tmux qwen3-emb vllmModel  /home/sysuvis/program/huangw293/model \
  "env CUDA_VISIBLE_DEVICES=2,3 VLLM_USE_MODELSCOPE=true vllm serve Qwen/Qwen3-Embedding-8B --served-model-name Qwen3-Embedding-8B --port 8021 --max-model-len 8192 --gpu-memory-utilization 0.3 --tensor-parallel-size 2"

# ③ FastAPI 主服务
run_in_tmux api  gym_py38  /home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/agentSimulation \
  "uvicorn main:app --host 127.0.0.1 --port 8090 --reload"

# ④ Celery 异步任务
run_in_tmux celery  gym_py38  /home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/agentSimulation \
  "celery -A celery_worker.app worker --concurrency=10 --max-memory-per-child=2048 --max-tasks-per-child=100 --loglevel=info"

# ⑤ GraphRag utils
run_in_tmux graph_utils  GraphragTest  /home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/GraphRag \
  "python utils/main.py"

# ⑥ GraphRag 主程序 【修改点】延迟 45 秒启动，等待大模型加载完毕
run_in_tmux graph_main  GraphragTest  /home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG \
  "sleep 45 && python main.py"

##############################
# 3. 查看命令提示
##############################
echo "All services are starting in tmux sessions:"
echo "  tmux ls               # 查看会话列表"
echo "  tmux attach -t api    # 举例：attach 到 FastAPI 窗口"