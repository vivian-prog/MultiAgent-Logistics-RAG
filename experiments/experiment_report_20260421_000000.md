# `experiment_details.csv` 实验报告

生成时间：2026-04-21  
数据来源：[experiment_details.csv](/home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/experiments/results/experiment_details.csv)

## 1. 报告目的

本报告基于 `MultiAgent-Logistics-RAG/experiments/results/experiment_details.csv` 中记录的实验数据，对当前实验结果进行整理，重点说明：

- 本次数据包含了哪些实验类型
- 各实验类型的记录数量
- 该数据是否覆盖 `ex_main.py` 默认配置下的全部实验
- 数据使用时需要注意的边界与局限

## 2. 数据概况

根据当前 `experiment_details.csv` 的已统计结果，本文件共记录 **30 条实验明细**，包含以下三类实验：

| 实验类型 | 记录数 |
|---|---:|
| `ablation` | 4 |
| `robustness` | 23 |
| `comparison` | 3 |
| `baseline` | 0 |
| **合计** | **30** |

从数据结构上看，这份 CSV 已覆盖：

- 消融实验 `ablation`
- 鲁棒性实验 `robustness`
- 对比实验 `comparison`

但**没有包含基础实验 `baseline`**。

## 3. 与 `ex_main.py` 默认实验配置的对应关系

结合当前 [ex_main.py](/home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/ex_main.py) 中的默认设置，可以得到默认一轮全量实验的理论规模：

| 实验类型 | 默认数量 |
|---|---:|
| `baseline` | 1 |
| `ablation` | 4 |
| `robustness` | 23 |
| `comparison` | 3 |
| **合计** | **31** |

因此，当前 `experiment_details.csv` 与默认全量实验相比，**缺少 1 条 `baseline` 实验记录**。

结论是：

- 这份 `experiment_details.csv` **不是** `ex_main.py --all` 的完整实验输出
- 它更像是一次“缺少 baseline 组”的实验结果快照
- 如果要作为“全量实验报告”直接引用，还需要补齐 `baseline` 结果

## 4. 当前数据的可用性分析

尽管当前数据并不完整，但它仍然具有较高的分析价值，特别适用于以下任务：

- 分析不同 RAG 配置下的消融实验表现
- 观察鲁棒性实验在参数扰动下的响应情况
- 比较 `baseline / ACO / GA` 三类调度策略中的后两类结果表现

不适合直接用于以下结论：

- “本轮已经完成全部实验”
- “包含了当前 `ex_main.py` 的所有实验类型”
- “可以直接作为完整的 `--all` 实验归档”

## 5. 结果解读建议

对于这份数据，建议按以下方式解读：

1. 将其视为一次**部分实验结果集**，而不是完整归档。
2. 在论文、汇报或周报中引用时，应明确说明：**基础实验组未包含在该 CSV 中**。
3. 若需要完整实验闭环，应补充一份包含 `baseline` 的明细文件，再统一汇总。

## 6. 建议的后续处理

为了形成一份可直接归档或写论文的完整实验结果，建议执行以下步骤：

1. 重新运行 `baseline` 实验，生成对应的明细记录。
2. 将补齐后的 `baseline` 与当前 `experiment_details.csv` 统一合并。
3. 生成一份新的总表，确保实验类型覆盖：
   `baseline + ablation + robustness + comparison`
4. 在最终报告中区分：
   - 实验是否“已运行”
   - 实验是否“完全成功”
   - 实验结果是否“可用于统计分析”

## 7. 总结

基于 `experiment_details.csv` 当前内容，可以明确得出以下结论：

- 该文件记录了 **30 条实验数据**
- 已包含 `ablation`、`robustness`、`comparison` 三类实验
- **未包含 `baseline`**
- 因而**尚未覆盖 `ex_main.py` 默认配置下的全部实验**

如果后续需要，我建议再基于：

- `experiment_details.csv`
- `0418experiment_details.csv`
- 各类时间戳 CSV

进一步生成一份“完整实验总报告”，把覆盖情况、成功率、失败原因和关键耗时指标统一整理出来。
