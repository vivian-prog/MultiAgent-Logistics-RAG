# 多智能体物流调度系统 - 实验框架使用指南

## 概述

`ex_main.py` 是多智能体物流调度系统的综合实验主程序，支持多种实验类型的自动化执行和指标收集。

## 实验指标

### 核心指标说明

| 指标类别 | 指标名称 | 说明 | 单位 |
|---------|---------|------|------|
| **RAG指标** | `rag_search_time` | RAG检索耗时 | 秒 |
| | `rag_query_generation_time` | RAG查询生成耗时 | 秒 |
| **LLM指标** | `llm_total_time` | LLM总思考耗时 | 秒 |
| | `llm_query_gen_time` | LLM生成RAG查询耗时 | 秒 |
| | `llm_command_gen_time` | LLM生成指令耗时 | 秒 |
| **Agent仿真指标** | `robot_simulation_time` | Robot仿真物理世界运行时间 | 秒 |
| | `truck_simulation_time` | Truck仿真物理世界运行时间 | 秒 |
| | `uav_simulation_time` | UAV仿真物理世界运行时间 | 秒 |
| **总体指标** | `total_time` | 全流程总耗时 | 秒 |

---

## 实验类型

### 1. 基础实验组 (Baseline)

收集系统在标准配置下的所有核心指标，建立性能基准。

**配置**: GraphRAG + LLM

**执行命令**:
```bash
python ex_main.py --baseline
```

---

### 2. 消融实验 (Ablation)

对比不同RAG模式对系统性能的影响，特别关注语料来源（预处理文本 vs 原始文本）对检索效果的影响。

| 配置名称 | RAG模式 | 服务端口 | 语料来源 | 说明 |
|---------|--------|---------|---------|------|
| `no_rag` | 无RAG | - | - | 仅使用LLM，无检索增强 |
| `text_rag` | Text RAG | 8016 | GraphRAG预处理的text_units | 基于FAISS向量检索的预处理文本RAG |
| `raw_text_rag` | Raw Text RAG | 8017 | 原始txt文件 | 基于FAISS向量检索的原始文本RAG |
| `graphrag` | GraphRAG | 8015 | 知识图谱 | 基于知识图谱的RAG |

**语料来源对比**：
- **text_rag**: 使用GraphRAG预处理生成的文本单元，经过实体识别和关系抽取，语义单元完整
- **raw_text_rag**: 使用原始txt文件，仅经过简单分块，包含表结构和数据记录

**执行命令**:
```bash
# 运行消融实验 (需要先启动所有RAG服务)
python ex_main.py --ablation
```

---

### 3. 鲁棒性实验 (Robustness)

通过修改Agent参数，测试系统的稳定性和敏感度。

#### 可调节参数

| Agent | 参数名称 | 基准值 | 说明 |
|-------|---------|-------|------|
| **UAV** | `battery_drain_rate` | 0.5 | 无人机耗电速率 |
| | `max_speed` | 0.3 | 无人机最大速度 |
| **Robot** | `battery_drain_per_sec` | 0.02 | 机器人耗电速率 |
| | `speed_m_per_sec` | 1.0 | 机器人移动速度 |
| **Truck** | `base_fuel_per_100km` | 30 | 卡车基础油耗 |

**执行命令**:
```bash
# 默认测试 UAV 和 Robot
python ex_main.py --robustness

# 指定测试的 Agent 类型
python ex_main.py --robustness --agents uav truck robot
```

---

### 4. 对比实验 (Comparison)

对比不同算法策略的性能差异。

| 算法名称 | 说明 | 预期效果 |
|---------|------|---------|
| `baseline` | 基线方案 (GraphRAG + LLM) | 标准性能 |
| `optimized_routing` | 优化路径规划 | 仿真时间减少约10-15% |
| `multi_stage` | 多阶段决策 | LLM时间增加，仿真更准确 |

**执行命令**:
```bash
python ex_main.py --comparison
```

---

## 使用方法

### 运行所有实验

```bash
python ex_main.py --all
```

### 运行单个实验

```bash
# 基础实验组
python ex_main.py --baseline

# 消融实验
python ex_main.py --ablation

# 鲁棒性实验
python ex_main.py --robustness

# 对比实验
python ex_main.py --comparison
```

### 自定义测试Prompts

#### 命令行直接指定
```bash
python ex_main.py --baseline --prompts "请指挥无人机运送药品到深圳市人民医院" "安排卡车运送生鲜到南山配送站"
```

#### 从JSON文件加载
```bash
python ex_main.py --all --prompts-file my_prompts.json
```

JSON文件格式示例 (`my_prompts.json`):
```json
{
  "prompts": [
    "请指挥各个agent把干粉灭火器从所在仓库运到深圳市中山大学深圳校区",
    "请调度无人机把急救药品从深圳仓库运到深圳市光明区人民医院",
    "安排卡车运送500公斤生鲜从龙华仓储中心到南山配送站"
  ]
}
```

### 指定输出目录

```bash
python ex_main.py --all --output ./experiment_results
```

### 设置重复次数

```bash
python ex_main.py --baseline --repeat 3
```

---

## 命令行参数完整列表

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `--all` | flag | - | 运行所有实验 |
| `--baseline` | flag | - | 运行基础实验组 |
| `--ablation` | flag | - | 运行消融实验 |
| `--robustness` | flag | - | 运行鲁棒性实验 |
| `--comparison` | flag | - | 运行对比实验 |
| `--output` | string | `experiments/results` | 结果输出目录 |
| `--prompts` | list | 内置prompts | 自定义测试prompts |
| `--prompts-file` | string | - | JSON格式的prompts文件 |
| `--repeat` | int | 1 | 每配置重复次数 |
| `--agents` | list | `["uav", "robot"]` | 鲁棒性实验的Agent类型 |

---

## 输出文件

实验结果保存在 `experiments/results/` 目录下：

### CSV文件

| 文件名 | 内容 |
|-------|------|
| `baseline_metrics.csv` | 基础实验组指标 |
| `ablation_no_rag_metrics.csv` | 无RAG配置指标 |
| `ablation_text_rag_metrics.csv` | Text RAG配置指标 (预处理文本) |
| `ablation_raw_text_rag_metrics.csv` | Raw Text RAG配置指标 (原始文本) |
| `ablation_graphrag_metrics.csv` | GraphRAG配置指标 |
| `robustness_uav_battery_drain_rate_metrics.csv` | UAV耗电速率鲁棒性指标 |
| `robustness_robot_battery_drain_per_sec_metrics.csv` | Robot耗电速率鲁棒性指标 |
| `comparison_baseline_metrics.csv` | 基线算法指标 |
| `comparison_optimized_routing_metrics.csv` | 优化路径算法指标 |
| `comparison_multi_stage_metrics.csv` | 多阶段算法指标 |

### 汇总报告

| 文件名 | 内容 |
|-------|------|
| `experiment_summary.txt` | 所有实验的汇总统计报告 |

---

## 默认测试Prompts

系统内置5个测试prompt：

1. `请指挥各个agent把干粉灭火器从所在仓库运到深圳市中山大学深圳校区(北纬 22.800884948488687°，东经 113.95443173232752°)`
2. `请调度无人机把急救药品从深圳仓库运到深圳市光明区人民医院`
3. `安排卡车运送500公斤生鲜从龙华仓储中心到南山配送站`
4. `协调机器人、卡车和无人机完成从福田仓库到宝安机场的快递配送`
5. `指挥仓储机器人分拣锂电池，并通过卡车运往龙岗区配送中心`

---

## 实验结果示例

### 基础实验组输出示例

```
============================================================
基础实验组 - 汇总统计
============================================================

【RAG指标】
  平均RAG检索耗时: 2.35s

【LLM指标】
  平均LLM总思考耗时: 5.82s

【Agent仿真指标】
  平均Robot仿真时间: 12.50s (成功率: 100.0%)
  平均Truck仿真时间: 1850.00s (成功率: 100.0%)
  平均UAV仿真时间: 156.00s (成功率: 100.0%)

【总体指标】
  平均总耗时: 45.32s
```

### 消融实验对比输出示例

```
============================================================
消融实验对比结果
============================================================

配置                 RAG耗时(s)      LLM耗时(s)      总耗时(s)
-----------------------------------------------------------------
no_rag              0.00            4.25            35.20
text_rag            1.85            5.50            42.15
raw_text_rag        2.10            5.35            43.50
graphrag            2.35            5.82            45.32
```

---

## 依赖服务

### ⚠️ 重要提示

**运行 `python ex_main.py --all` 或任何实验命令前，必须先启动所有依赖服务！**

如果服务未启动，实验将失败并报错。

### 服务列表

| 服务 | 地址 | 必需性 | 说明 |
|-----|------|-------|------|
| LLM服务 | `http://localhost:8080` | **必需** | Qwen3-8B模型，所有实验依赖 |
| Embedding服务 | `http://localhost:8021` | **必需** | Qwen3-Embedding-8B，FAISS服务依赖 |
| GraphRAG服务 | `http://localhost:8015` | **必需** | 知识图谱检索，graphrag配置使用 |
| Text RAG服务 | `http://localhost:8016` | **必需** | 预处理文本向量检索，text_rag配置使用 |
| Raw Text RAG服务 | `http://localhost:8017` | **必需** | 原始文本向量检索，raw_text_rag配置使用 |
| 仿真服务 | `http://localhost:8090` | **必需** | Agent仿真API，验证调度方案 |

### 服务依赖关系

```
LLM服务 (8080) ←──────────────────────────────────── 所有实验
     │
     ↓
Embedding服务 (8021) ←── FAISS服务依赖
     │
     ├──→ Text RAG服务 (8016) ←── text_rag配置
     │
     └──→ Raw Text RAG服务 (8017) ←── raw_text_rag配置

GraphRAG服务 (8015) ←── graphrag配置

仿真服务 (8090) ←── 所有实验的仿真验证
```

### 服务启动顺序

**必须按以下顺序启动服务**：

```bash
# ========== 第一步：启动基础服务 ==========

# 1. 启动LLM服务 (端口8080) - 所有实验的核心依赖
# 根据你的LLM部署方式启动，例如：
# python -m vllm.entrypoints.openai.api_server --model Qwen3-8B --port 8080

# 2. 启动Embedding服务 (端口8021) - FAISS服务的前置依赖
# 根据你的Embedding模型部署方式启动，例如：
# python -m vllm.entrypoints.openai.api_server --model Qwen3-Embedding-8B --port 8021

# ========== 第二步：等待基础服务就绪 ==========
sleep 10

# ========== 第三步：启动RAG服务 ==========

# 3. 启动GraphRAG服务 (端口8015) - graphrag配置使用
cd GraphRag/utils
python main.py &

# 4. 启动Text RAG服务 (端口8016) - text_rag配置使用
cd ../../TextRAG
python faiss_service.py &

# 5. 启动Raw Text RAG服务 (端口8017) - raw_text_rag配置使用
python faiss_service_raw.py &

# ========== 第四步：启动仿真服务 ==========

# 6. 启动仿真服务 (端口8090)
# 根据你的仿真服务部署方式启动

# ========== 第五步：等待所有服务就绪 ==========
sleep 15

# ========== 第六步：运行实验 ==========
cd ..
python ex_main.py --all
```

### 服务状态检查

运行实验前，可以使用以下命令检查服务是否正常：

```bash
# 检查所有服务状态
curl -s http://localhost:8080/v1/models && echo "✅ LLM服务正常" || echo "❌ LLM服务未启动"
curl -s http://localhost:8021/v1/models && echo "✅ Embedding服务正常" || echo "❌ Embedding服务未启动"
curl -s http://localhost:8015/v1/models && echo "✅ GraphRAG服务正常" || echo "❌ GraphRAG服务未启动"
curl -s http://localhost:8016/health && echo "✅ Text RAG服务正常" || echo "❌ Text RAG服务未启动"
curl -s http://localhost:8017/health && echo "✅ Raw Text RAG服务正常" || echo "❌ Raw Text RAG服务未启动"
curl -s http://localhost:8090/health && echo "✅ 仿真服务正常" || echo "❌ 仿真服务未启动"
```

### 快速启动命令

```bash
#!/bin/bash
# 一键启动所有RAG服务（假设LLM和Embedding服务已启动）

cd /Users/bytedance/PycharmProjects/MultiAgent-Logistics-RAG

# 创建日志目录
mkdir -p logs

# 启动GraphRAG (端口8015)
nohup python GraphRag/utils/main.py > logs/graphrag.log 2>&1 &
echo "GraphRAG服务启动中..."

# 启动Text RAG (端口8016) - 预处理文本
nohup python TextRAG/faiss_service.py > logs/faiss_textrag.log 2>&1 &
echo "Text RAG服务启动中..."

# 启动Raw Text RAG (端口8017) - 原始文本
nohup python TextRAG/faiss_service_raw.py > logs/faiss_raw_textrag.log 2>&1 &
echo "Raw Text RAG服务启动中..."

# 等待服务启动
echo "等待服务启动..."
sleep 15

# 检查服务状态
echo "检查服务状态..."
curl -s http://localhost:8015/v1/models > /dev/null && echo "✅ GraphRAG (8015) 正常" || echo "❌ GraphRAG (8015) 异常"
curl -s http://localhost:8016/health > /dev/null && echo "✅ Text RAG (8016) 正常" || echo "❌ Text RAG (8016) 异常"
curl -s http://localhost:8017/health > /dev/null && echo "✅ Raw Text RAG (8017) 正常" || echo "❌ Raw Text RAG (8017) 异常"

echo "所有服务已启动，可以运行实验"
```

### 首次启动注意事项

1. **Raw Text RAG服务首次启动**：
   - 会自动从 `GraphRag/input/` 目录读取原始txt文件
   - 首次启动会构建FAISS索引，需要额外等待时间（约1-3分钟）
   - 索引构建完成后会缓存到 `TextRAG/faiss_index_raw/` 目录

2. **Text RAG服务**：
   - 需要先运行GraphRAG预处理，生成 `GraphRag/inputs/artifacts/create_final_text_units.parquet`
   - 如果该文件不存在，text_rag配置会报错

3. **服务端口冲突**：
   - 确保端口 8015/8016/8017 未被其他服务占用
   - 可以使用 `lsof -i :8015` 检查端口占用情况

---

## 注意事项

1. **服务状态**: 运行实验前请确保所有依赖服务正常运行
2. **网络延迟**: 实际耗时可能因网络状况有所波动
3. **重复次数**: 建议设置 `--repeat 3` 以获得更稳定的统计结果
4. **参数扰动**: 鲁棒性实验会修改内存中的配置，不影响配置文件

---

## 文件结构

```
MultiAgent-Logistics-RAG/
├── ex_main.py                    # 实验主程序
├── main.py                       # 原始主程序
├── experiments/
│   ├── __init__.py
│   ├── recorder.py               # 实验记录器
│   ├── metrics.py                # 指标计算
│   ├── run_ablation.py           # 消融实验脚本
│   ├── run_robustness.py         # 鲁棒性实验脚本
│   └── results/                  # 实验结果输出目录
│       ├── baseline_metrics.csv
│       ├── ablation_no_rag_metrics.csv
│       ├── ablation_text_rag_metrics.csv
│       ├── ablation_raw_text_rag_metrics.csv
│       ├── ablation_graphrag_metrics.csv
│       ├── robustness_*.csv
│       ├── comparison_*.csv
│       └── experiment_summary.txt
├── TextRAG/                      # FAISS文本RAG服务
│   ├── faiss_service.py          # Text RAG服务 (端口8016, 预处理文本)
│   ├── faiss_service_raw.py      # Raw Text RAG服务 (端口8017, 原始文本)
│   ├── faiss_index/              # Text RAG索引存储
│   ├── faiss_index_raw/          # Raw Text RAG索引存储
│   └── README.md                 # TextRAG说明文档
├── GraphRag/                     # GraphRAG服务
│   ├── utils/
│   │   └── main.py               # GraphRAG服务主程序 (端口8015)
│   ├── input/                    # 原始输入文本 (raw_text_rag使用)
│   └── inputs/artifacts/         # GraphRAG预处理数据 (text_rag使用)
├── prompts/
│   └── prompts.py                # Prompt模板
├── configs/
│   ├── loader.py                 # 配置加载器
│   └── agent_params.yaml         # Agent参数配置
└── EX_MAIN_README.md             # 本说明文件
```
