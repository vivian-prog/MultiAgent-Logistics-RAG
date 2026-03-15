# Figure 8 用户研究结果图表说明

## 图表概述

Figure 8 展示了用户研究的量化评估结果，采用分组条形图形式，按照三个评估维度展示12个问题的评分情况。

---

## 图表结构说明

### 1. 坐标轴

| 元素 | 说明 |
|------|------|
| **X轴** | 评估项目（Evaluation Items），包含12个问题（Q1-Q12），按维度分组排列 |
| **Y轴** | 7点Likert量表得分（Mean Score），范围0-7分 |

### 2. 分数含义

| 分数范围 | 评价等级 | 含义 |
|----------|----------|------|
| 6.0-7.0 | 非常好 | 用户非常满意，完全符合预期 |
| 5.0-5.9 | 良好 | 用户较为满意，基本符合预期 |
| 4.0-4.9 | 中等 | 用户评价一般，存在改进空间 |
| 3.0-3.9 | 较低 | 用户不太满意，需要改进 |
| 1.0-2.9 | 较差 | 用户不满意，问题严重 |

### 3. 参考线

- **虚线 (y=4)**: 中性评价线，表示"一般"
- **点线 (y=5)**: 良好评价线，表示"良好"

---

## 维度分组说明

### 维度一：System Workflow（系统工作流程）- 蓝色

| 问题编号 | 问题描述 | 均值 | 标准差 | 评价 |
|----------|----------|------|--------|------|
| Q1 | I can quickly locate candidate clusters and use multi-dimensional data for site selection | 5.2 | 0.60 | 良好 |
| Q2 | I can use 3D analysis to identify and avoid potential safety risks | 5.1 | 0.54 | 良好 |
| Q3 | I can explore how candidate scores change after adjusting weights | 5.0 | 0.89 | 中等 |
| Q4 | The system generates diverse site selection solutions for comparison | 5.2 | 0.60 | 良好 |
| Q5 | I can understand how the ranking algorithm determines candidate priorities | 4.9 | 0.70 | 较低 |

**维度整体表现**:
- 整体均值: **5.08**
- 均值范围: 4.9 - 5.2
- 标准差范围: 0.54 - 0.89
- 主要短板: Q5（算法可解释性）得分最低，Q3（权重调整反馈）标准差最大

---

### 维度二：Visual Design（视觉设计与交互）- 橙色

| 问题编号 | 问题描述 | 均值 | 标准差 | 评价 |
|----------|----------|------|--------|------|
| Q6 | Spatial view provides good design for global, cluster, and candidate data | 5.4 | 0.80 | 良好 |
| Q7 | 3D view provides good design for checking candidate safety | 5.2 | 0.60 | 良好 |
| Q8 | Ranking and change views help me adjust rankings and observe changes | 6.0 | 0.77 | 非常好 |
| Q9 | The six views are intuitive and easy to use | 5.5 | 0.81 | 良好 |

**维度整体表现**:
- 整体均值: **5.53**（三个维度中最高）
- 均值范围: 5.2 - 6.0
- 标准差范围: 0.60 - 0.81
- 亮点: Q8（排序视图和变化视图）获得最高分6.0

---

### 维度三：System Usability（系统可用性）- 绿色

| 问题编号 | 问题描述 | 均值 | 标准差 | 评价 |
|----------|----------|------|--------|------|
| Q10 | The system provides sufficient information and tools for site selection | 5.2 | 0.75 | 良好 |
| Q11 | The interaction and operation logic matches my expectations | 5.0 | 0.63 | 中等 |
| Q12 | The system is beginner-friendly and easy to use | 5.3 | 0.64 | 良好 |

**维度整体表现**:
- 整体均值: **5.17**
- 均值范围: 5.0 - 5.3
- 标准差范围: 0.63 - 0.75
- 主要短板: Q11（交互逻辑合理性）得分最低

---

## 图表元素详解

### 条形图（Bar）
- **高度**: 表示该问题的平均得分
- **颜色**: 区分不同维度（蓝色=工作流程，橙色=视觉设计，绿色=可用性）
- **宽度**: 统一为0.7，保证视觉一致性

### 误差条（Error Bar）
- **位置**: 条形顶部
- **长度**: 表示标准差（Standard Deviation）
- **含义**: 反映用户评分的离散程度
  - 误差条越长 → 用户评价差异越大
  - 误差条越短 → 用户评价越一致
- **示例**: Q3的标准差最大(0.89)，说明用户对该功能的体验差异显著

### 数值标签（Value Label）
- **位置**: 误差条上方
- **格式**: 保留一位小数（如 5.2、6.0）
- **作用**: 便于精确读取数值

---

## 关键发现

### 高分项目（均值 ≥ 5.5）

| 排名 | 问题 | 均值 | 分析 |
|------|------|------|------|
| 1 | Q8: Ranking and change views help me adjust rankings and observe changes | 6.0 | 用户最满意的功能，视图设计有效支持排名调整和变化观察 |
| 2 | Q9: The six views are intuitive and easy to use | 5.5 | 整体视图设计获得良好评价 |
| 3 | Q6: Spatial view provides good design for global, cluster, and candidate data | 5.4 | 空间视图的数据展现效果良好 |

### 低分项目（均值 < 5.1）

| 排名 | 问题 | 均值 | 标准差 | 问题分析 |
|------|------|------|--------|----------|
| 1 | Q5: I can understand how the ranking algorithm determines candidate priorities | 4.9 | 0.70 | LambdaMART算法复杂，缺乏可视化解释，用户难以理解排名逻辑 |
| 2 | Q3: I can explore how candidate scores change after adjusting weights | 5.0 | 0.89 | 反馈延迟、操作路径不直观，用户评价差异大 |
| 3 | Q12: The system is beginner-friendly and easy to use | 5.0 | 0.63 | 系统对新手的学习成本较高 |

### 标准差异常高项目

| 问题 | 标准差 | 分析 |
|------|--------|------|
| Q3: I can explore how candidate scores change after adjusting weights | 0.89 | 部分用户能顺利完成操作，部分用户遇到困难，体验不一致 |
| Q9: The six views are intuitive and easy to use | 0.81 | 用户对多视图系统的接受度存在差异 |
| Q10: The system provides sufficient information and tools for site selection | 0.75 | 不同背景用户对工具需求不同 |

---

## 维度汇总图说明

Figure 8 (Summary) 展示三个维度的整体表现：

```
维度                均值±标准差
─────────────────────────────
System Workflow     5.08±0.12
Visual Design       5.53±0.29  ← 表现最佳
System Usability    5.17±0.12
```

### 解读

1. **Visual Design 维度表现最佳** (5.53分)
   - 用户对视图设计和视觉呈现最为满意
   - 排序视图和变化视图设计效果显著

2. **System Workflow 维度表现中等** (5.08分)
   - 核心功能基本可用
   - 算法可解释性和权重反馈是主要短板

3. **System Usability 维度表现中等** (5.17分)
   - 工具完备性较好
   - 交互逻辑和新手友好性需改进

---

## 改进建议

基于图表分析，优先改进方向：

1. **算法可解释性** (Q5, 均值4.9)
   - 问题: I can understand how the ranking algorithm determines candidate priorities
   - 建议: 添加动态权重影响热力图、提供特征贡献度可视化、增加算法原理说明文档

2. **权重调整反馈** (Q3, 标准差0.89)
   - 问题: I can explore how candidate scores change after adjusting weights
   - 建议: 优化异步计算与实时渲染、实现跨视图自动跳转、简化操作路径

3. **交互逻辑合理性** (Q11, 均值5.0)
   - 问题: The interaction and operation logic matches my expectations
   - 建议: 扁平化菜单层级、统一功能入口设计、增强新手引导

---

## 数据来源

- 数据文件: `userstudy.xlsx`
- 样本量: 10名用户
- 评分标准: 7点Likert量表（1=完全不同意，7=完全同意）
- 分析文档: `userstudy补充分析.docx`
