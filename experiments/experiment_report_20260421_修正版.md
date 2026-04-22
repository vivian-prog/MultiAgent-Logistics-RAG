# `experiment_details.csv` 实验报告（修正版）

生成时间：2026-04-21  
数据来源：[experiment_details.csv](/home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/experiments/results/experiment_details.csv)

## 1. 报告目的

本报告基于 `MultiAgent-Logistics-RAG/experiments/results/experiment_details.csv` 中记录的实验数据，对当前实验结果进行整理，重点说明：

- 本次数据包含了哪些实验类型
- 各实验类型的记录数量
- 该数据是否覆盖 `ex_main.py` 默认配置下的全部实验
- 数据使用时需要注意的边界与局限

## 2. 数据概况

根据当前 `experiment_details.csv` 的统计结果，本文件共记录 **30 条实验明细**，包含以下实验类型：

| 实验类型 | 记录数 |
|---|---:|
| `baseline` | 1 |
| `ablation` | 4 |
| `robustness` | 23 |
| `comparison` | 3 |
| **合计** | **30** |

其中，`baseline_p1_r1` 本身就是 `baseline` 实验在默认参数下的一次具体运行记录：

- `baseline` 表示实验类型
- `p1` 表示第 1 个 prompt
- `r1` 表示第 1 次重复

因此，这份 CSV **已经包含 baseline 实验**。

## 3. 与 `ex_main.py` 默认实验配置的对应关系

结合当前 [ex_main.py](/home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/ex_main.py) 中的默认设置，可以得到默认一轮全量实验的理论规模：

| 实验类型 | 默认数量 |
|---|---:|
| `baseline` | 1 |
| `ablation` | 4 |
| `robustness` | 23 |
| `comparison` | 3 |
| **合计** | **30** |

因此，当前 `experiment_details.csv` 与默认全量实验规模是**一致的**。

结论是：

- 这份 `experiment_details.csv` **已经覆盖** `ex_main.py --all` 在当前默认配置下的一轮完整实验输出
- 它包含了 `baseline`、`ablation`、`robustness`、`comparison` 四类实验
- 可以作为当前默认参数下的一份完整实验结果快照使用

## 4. 当前数据的可用性分析

当前数据具备较高的分析价值，特别适用于以下任务：

- 分析基础实验 `baseline` 的基准表现
- 分析不同 RAG 配置下的消融实验表现
- 观察鲁棒性实验在参数扰动下的响应情况
- 比较 `baseline / ACO / GA` 三类调度策略的结果表现

但不应直接推出以下结论：

- 所有实验都运行成功
- 所有实验结果都可直接用于统计对比
- 所有记录都已通过完整成功校验

原因在于，“实验已执行完成”和“实验完全成功”是两个不同层面的判断。  
即使实验类型覆盖完整，仍可能存在部分记录失败、部分 Agent 未成功完成任务，或结果虽落盘但不适合直接纳入最终统计。

## 5. 结果解读建议

对于这份数据，建议按以下方式解读：

1. 将其视为一次**默认参数下的完整实验结果集**。
2. 在论文、汇报或周报中引用时，可以将其作为一轮 `--all` 实验的完整记录来源。
3. 在后续分析中，应继续区分：
   - 实验是否“已运行”
   - 实验是否“完全成功”
   - 实验结果是否“可用于统计分析”

## 6. 建议的后续处理

为了形成一份更适合归档或写论文的实验结果，建议执行以下步骤：

1. 对失败或部分失败的实验单独做错误原因归档。
2. 对时间指标进一步做均值、方差、最大值、最小值统计。
3. 将 `experiment_details.csv` 与各类时间戳 CSV 交叉核验，确保后续复现实验时数据一致。
4. 在最终报告中同时呈现：
   - 覆盖情况
   - 成功率
   - 失败原因
   - 关键耗时指标

## 7. 总结

基于 `experiment_details.csv` 当前内容，可以明确得出以下结论：

- 该文件记录了 **30 条实验数据**
- 已包含 `baseline`、`ablation`、`robustness`、`comparison` 四类实验
- 其中 `baseline_p1_r1` 即为默认配置下的基础实验记录
- 因而**已经覆盖 `ex_main.py` 默认配置下的全部实验类型和默认实验规模**

如果后续需要，可以再基于：

- `experiment_details.csv`
- `0418experiment_details.csv`
- 各类时间戳 CSV

进一步生成一份“完整实验总报告”，把覆盖情况、成功率、失败原因和关键耗时指标统一整理出来。
