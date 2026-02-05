#!/usr/bin/env bash
# file: stop_all.sh
for s in qwen3-8b qwen3-emb api celery graph_utils graph_main; do
    tmux kill-session -t "$s" 2>/dev/null || true
done
echo "All tmux sessions killed."