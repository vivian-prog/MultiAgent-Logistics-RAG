#!/bin/bash
# start_all_services.sh
# 一键启动所有实验依赖服务
# 使用方法: ./start_all_services.sh

set -e

# ===================== 配置 =====================
PROJECT_ROOT="/home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG"
LOG_DIR="$PROJECT_ROOT/logs"

# 服务端口配置
LLM_PORT=8080
EMBEDDING_PORT=8021
GRAPHRAG_PORT=8015
TEXT_RAG_PORT=8016
RAW_TEXT_RAG_PORT=8017
SIMULATION_PORT=8090

# 等待时间配置
WAIT_BETWEEN_SERVICES=3
WAIT_AFTER_ALL=15

# ===================== 颜色输出 =====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ===================== 工具函数 =====================
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

wait_for_service() {
    local name=$1
    local port=$2
    local max_retries=30
    local retry=0

    print_info "等待 $name (端口 $port) 启动..."

    while [ $retry -lt $max_retries ]; do
        if curl -s "http://localhost:$port/health" > /dev/null 2>&1 || \
           curl -s "http://localhost:$port/v1/models" > /dev/null 2>&1; then
            print_success "$name (端口 $port) 已就绪"
            return 0
        fi
        retry=$((retry + 1))
        sleep 1
    done

    print_error "$name (端口 $port) 启动超时"
    return 1
}

kill_service_on_port() {
    local port=$1
    local pid=$(lsof -t -i :$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        print_warning "终止端口 $port 上的进程 (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# ===================== 主函数 =====================
main() {
    echo ""
    echo "=========================================="
    echo "  多智能体物流调度系统 - 服务启动脚本"
    echo "=========================================="
    echo ""

    cd $PROJECT_ROOT

    # 创建日志目录
    mkdir -p $LOG_DIR
    print_info "日志目录: $LOG_DIR"

    # ===================== 检查基础服务 =====================
    echo ""
    print_info "========== 第一步：检查基础服务 =========="

    # 检查LLM服务
    if curl -s "http://localhost:$LLM_PORT/v1/models" > /dev/null 2>&1; then
        print_success "LLM服务 (端口 $LLM_PORT) 已运行"
    else
        print_error "LLM服务 (端口 $LLM_PORT) 未启动!"
        print_info "请先启动LLM服务，例如："
        print_info "  python -m vllm.entrypoints.openai.api_server --model Qwen3-8B --port 8080"
        exit 1
    fi

    # 检查Embedding服务
    if curl -s "http://localhost:$EMBEDDING_PORT/v1/models" > /dev/null 2>&1; then
        print_success "Embedding服务 (端口 $EMBEDDING_PORT) 已运行"
    else
        print_error "Embedding服务 (端口 $EMBEDDING_PORT) 未启动!"
        print_info "请先启动Embedding服务，例如："
        print_info "  python -m vllm.entrypoints.openai.api_server --model Qwen3-Embedding-8B --port 8021"
        exit 1
    fi

    # 检查仿真服务
    if curl -s "http://localhost:$SIMULATION_PORT/health" > /dev/null 2>&1; then
        print_success "仿真服务 (端口 $SIMULATION_PORT) 已运行"
    else
        print_error "仿真服务 (端口 $SIMULATION_PORT) 未启动!"
        print_info "请先启动仿真服务"
        exit 1
    fi

    # ===================== 启动RAG服务 =====================
    echo ""
    print_info "========== 第二步：启动RAG服务 =========="

    # 启动GraphRAG服务
    if check_port $GRAPHRAG_PORT; then
        print_warning "端口 $GRAPHRAG_PORT 已被占用，跳过GraphRAG服务"
    else
        print_info "启动GraphRAG服务 (端口 $GRAPHRAG_PORT)..."
        cd $PROJECT_ROOT/GraphRag/utils
        nohup python main.py > $LOG_DIR/graphrag.log 2>&1 &
        echo $! > $LOG_DIR/graphrag.pid
        cd $PROJECT_ROOT
        sleep $WAIT_BETWEEN_SERVICES
    fi

    # 启动Text RAG服务
    if check_port $TEXT_RAG_PORT; then
        print_warning "端口 $TEXT_RAG_PORT 已被占用，跳过Text RAG服务"
    else
        print_info "启动Text RAG服务 (端口 $TEXT_RAG_PORT)..."
        cd $PROJECT_ROOT/TextRAG
        nohup python faiss_service.py > $LOG_DIR/faiss_textrag.log 2>&1 &
        echo $! > $LOG_DIR/faiss_textrag.pid
        cd $PROJECT_ROOT
        sleep $WAIT_BETWEEN_SERVICES
    fi

    # 启动Raw Text RAG服务
    if check_port $RAW_TEXT_RAG_PORT; then
        print_warning "端口 $RAW_TEXT_RAG_PORT 已被占用，跳过Raw Text RAG服务"
    else
        print_info "启动Raw Text RAG服务 (端口 $RAW_TEXT_RAG_PORT)..."
        print_info "(首次启动可能需要1-3分钟构建索引)"
        cd $PROJECT_ROOT/TextRAG
        nohup python faiss_service_raw.py > $LOG_DIR/faiss_raw_textrag.log 2>&1 &
        echo $! > $LOG_DIR/faiss_raw_textrag.pid
        cd $PROJECT_ROOT
        sleep $WAIT_BETWEEN_SERVICES
    fi

    # ===================== 等待所有服务就绪 =====================
    echo ""
    print_info "========== 第三步：等待所有服务就绪 =========="
    sleep $WAIT_AFTER_ALL

    # ===================== 验证服务状态 =====================
    echo ""
    print_info "========== 第四步：验证服务状态 =========="
    echo ""

    all_ok=true

    # 检查LLM
    if curl -s "http://localhost:$LLM_PORT/v1/models" > /dev/null 2>&1; then
        print_success "✅ LLM服务 (端口 $LLM_PORT) 正常"
    else
        print_error "❌ LLM服务 (端口 $LLM_PORT) 异常"
        all_ok=false
    fi

    # 检查Embedding
    if curl -s "http://localhost:$EMBEDDING_PORT/v1/models" > /dev/null 2>&1; then
        print_success "✅ Embedding服务 (端口 $EMBEDDING_PORT) 正常"
    else
        print_error "❌ Embedding服务 (端口 $EMBEDDING_PORT) 异常"
        all_ok=false
    fi

    # 检查GraphRAG
    if curl -s "http://localhost:$GRAPHRAG_PORT/v1/models" > /dev/null 2>&1; then
        print_success "✅ GraphRAG服务 (端口 $GRAPHRAG_PORT) 正常"
    else
        print_error "❌ GraphRAG服务 (端口 $GRAPHRAG_PORT) 异常"
        all_ok=false
    fi

    # 检查Text RAG
    if curl -s "http://localhost:$TEXT_RAG_PORT/health" > /dev/null 2>&1; then
        print_success "✅ Text RAG服务 (端口 $TEXT_RAG_PORT) 正常"
    else
        print_error "❌ Text RAG服务 (端口 $TEXT_RAG_PORT) 异常"
        all_ok=false
    fi

    # 检查Raw Text RAG
    if curl -s "http://localhost:$RAW_TEXT_RAG_PORT/health" > /dev/null 2>&1; then
        print_success "✅ Raw Text RAG服务 (端口 $RAW_TEXT_RAG_PORT) 正常"
    else
        print_error "❌ Raw Text RAG服务 (端口 $RAW_TEXT_RAG_PORT) 异常"
        all_ok=false
    fi

    # 检查仿真服务
    if curl -s "http://localhost:$SIMULATION_PORT/health" > /dev/null 2>&1; then
        print_success "✅ 仿真服务 (端口 $SIMULATION_PORT) 正常"
    else
        print_error "❌ 仿真服务 (端口 $SIMULATION_PORT) 异常"
        all_ok=false
    fi

    # ===================== 输出结果 =====================
    echo ""
    echo "=========================================="

    if [ "$all_ok" = true ]; then
        print_success "所有服务已启动并正常运行!"
        echo ""
        echo "现在可以运行实验："
        echo "  python ex_main.py --all          # 运行所有实验"
        echo "  python ex_main.py --ablation     # 仅消融实验"
        echo "  python ex_main.py --baseline     # 仅基线实验"
        echo "  python ex_main.py --robustness   # 仅鲁棒性实验"
        echo ""
        echo "查看日志："
        echo "  tail -f $LOG_DIR/graphrag.log"
        echo "  tail -f $LOG_DIR/faiss_textrag.log"
        echo "  tail -f $LOG_DIR/faiss_raw_textrag.log"
        echo ""
        exit 0
    else
        print_error "部分服务启动失败，请检查日志"
        echo ""
        echo "查看日志："
        echo "  tail -f $LOG_DIR/graphrag.log"
        echo "  tail -f $LOG_DIR/faiss_textrag.log"
        echo "  tail -f $LOG_DIR/faiss_raw_textrag.log"
        exit 1
    fi
}

# ===================== 停止所有服务 =====================
stop_all() {
    echo ""
    print_info "停止所有RAG服务..."

    for pid_file in $LOG_DIR/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat $pid_file)
            if kill -0 $pid 2>/dev/null; then
                kill $pid
                print_info "已停止进程 $pid"
            fi
            rm $pid_file
        fi
    done

    print_success "所有RAG服务已停止"
}

# ===================== 命令行参数处理 =====================
case "${1:-start}" in
    start)
        main
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        main
        ;;
    status)
        echo "检查服务状态..."
        curl -s "http://localhost:$LLM_PORT/v1/models" > /dev/null 2>&1 && echo "✅ LLM服务正常" || echo "❌ LLM服务未启动"
        curl -s "http://localhost:$EMBEDDING_PORT/v1/models" > /dev/null 2>&1 && echo "✅ Embedding服务正常" || echo "❌ Embedding服务未启动"
        curl -s "http://localhost:$GRAPHRAG_PORT/v1/models" > /dev/null 2>&1 && echo "✅ GraphRAG服务正常" || echo "❌ GraphRAG服务未启动"
        curl -s "http://localhost:$TEXT_RAG_PORT/health" > /dev/null 2>&1 && echo "✅ Text RAG服务正常" || echo "❌ Text RAG服务未启动"
        curl -s "http://localhost:$RAW_TEXT_RAG_PORT/health" > /dev/null 2>&1 && echo "✅ Raw Text RAG服务正常" || echo "❌ Raw Text RAG服务未启动"
        curl -s "http://localhost:$SIMULATION_PORT/health" > /dev/null 2>&1 && echo "✅ 仿真服务正常" || echo "❌ 仿真服务未启动"
        ;;
    *)
        echo "使用方法: $0 {start|stop|restart|status}"
        echo ""
        echo "  start   - 启动所有RAG服务 (默认)"
        echo "  stop    - 停止所有RAG服务"
        echo "  restart - 重启所有RAG服务"
        echo "  status  - 检查所有服务状态"
        exit 1
        ;;
esac
