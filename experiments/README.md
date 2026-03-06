# 实验模块使用指南

## 目录结构

```
experiments/
├── __init__.py              # 模块入口
├── recorder.py              # 实验结果持久化
├── metrics.py               # 指标计算
├── run_ablation.py          # 消融实验脚本
├── run_robustness.py        # 鲁棒性实验脚本
├── benchmark_data.json      # 真实配送时间基准数据
└── results/                 # 实验结果存储目录
```

## 1. 消融实验

比较三种模式：无RAG、文本RAG、GraphRAG

### 运行方式

```bash
# 使用默认prompts运行
python experiments/run_ablation.py

# 自定义prompts
python experiments/run_ablation.py --prompts "prompt1" "prompt2" "prompt3"

# 从文件加载prompts
python experiments/run_ablation.py --config prompts.json

# 指定输出目录
python experiments/run_ablation.py --output ./my_results

# 每个配置重复3次
python experiments/run_ablation.py --repeat 3
```

### 输出文件

- `{experiment_id}.json` - 单次实验详细结果
- `experiments_summary.csv` - 所有实验汇总表
- `ablation_summary.json` - 批量实验汇总

## 2. 鲁棒性实验

修改Agent参数，观察指标变化

### 运行方式

```bash
# 测试所有Agent
python experiments/run_robustness.py

# 只测试UAV
python experiments/run_robustness.py --agents uav

# 测试UAV和Truck
python experiments/run_robustness.py --agents uav truck

# 自定义prompt
python experiments/run_robustness.py --prompt "你的测试prompt"

# 使用自定义参数配置
python experiments/run_robustness.py --config custom_variations.yaml
```

### 参数扰动范围

| Agent | 参数 | 默认变化范围 |
|-------|------|-------------|
| UAV | max_speed | -50% ~ +50% |
| UAV | volatility | -50% ~ +100% |
| Truck | base_fuel_per_100km | -30% ~ +30% |
| Truck | economic_speed | -30% ~ +30% |
| Robot | speed_m_per_sec | -50% ~ +50% |
| Robot | battery_drain_per_sec | -50% ~ +100% |

## 3. 配置文件说明

### configs/agent_params.yaml

```yaml
uav:
  max_speed: 0.3        # 无人机最大速度
  volatility: 0.02      # 速度波动
  radius: 0.3           # 无人机半径
  tolerance: 0.1        # 到达容差

truck:
  base_fuel_per_100km: 30  # 基础油耗
  economic_speed: 60       # 经济时速
  fuel_price: 7.5          # 油价

robot:
  speed_m_per_sec: 1.0     # 移动速度
  battery_drain_per_sec: 0.02  # 电量消耗率
```

## 4. 基准数据

编辑 `benchmark_data.json` 填入真实配送时间数据：

```json
{
  "benchmark_cases": [
    {
      "case_id": "case_001",
      "真实配送信息": {
        "time_breakdown": {
          "total_delivery_hours": 2.5
        }
      }
    }
  ]
}
```

## 5. 代码示例

### 使用实验记录器

```python
from experiments import ExperimentRecorder

recorder = ExperimentRecorder()
recorder.start_experiment("ablation", {"enable_rag": True, "rag_type": "graphrag"})
recorder.record_rag_metrics(True, "graphrag", 1.5, 2.0, "context", "answer")
recorder.record_agent_result("agentrobot", "task_001", 30.5, True)
recorder.end_experiment("completed")
recorder.save_to_json()
```

### 计算指标

```python
from experiments import MetricsCalculator, calculate_all_metrics

# 计算时间误差
error = MetricsCalculator.calculate_time_error(
    simulated_time=2.0,  # 小时
    real_time=2.5        # 小时
)
# {'absolute_error': 0.5, 'relative_error': 0.2, 'accuracy': 0.8}

# 计算RAG性能
perf = MetricsCalculator.calculate_rag_performance(
    rag_search_time=1.5,
    llm_inference_time=2.0
)
```

## 6. 注意事项

1. **服务依赖**：运行实验前确保以下服务已启动：
   - LLM服务 (localhost:8080)
   - RAG服务 (localhost:8015)
   - 仿真API (localhost:8090)
   - GraphHopper (localhost:8989)
   - MySQL数据库

2. **数据准备**：
   - 数据库中需要有测试数据（仓库、货物、Agent等）
   - 地图数据 `map1_buildings.npy` 需要存在

3. **并发运行**：建议避免同时运行多个实验，可能导致资源竞争
