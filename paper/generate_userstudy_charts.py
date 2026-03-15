"""
用户研究图表生成脚本
根据 userstudy.xlsx 和 userstudy补充分析.docx 的数据生成 Figure 8 分组条形图
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 设置字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'STHeiti']
plt.rcParams['axes.unicode_minus'] = False


def load_data(filepath='paper/userstudy.xlsx'):
    """加载用户研究数据"""
    df = pd.read_excel(filepath)
    return df


def create_grouped_bar_chart(df, output_path='paper/figure8_grouped_bar.png'):
    """
    创建 Figure 8 分组条形图
    展示各评估维度的详细问题得分
    """
    # 定义维度和对应的问题
    dimensions = {
        'System Workflow': [1, 2, 3, 4, 5],
        'Visual Design': [6, 7, 8, 9],
        'System Usability': [10, 11, 12]
    }

    # 定义每个问题的完整描述标签
    question_labels = {
        1: 'Q1: I can quickly locate candidate\nclusters and use multi-dimensional\ndata for site selection',
        2: 'Q2: I can use 3D analysis to\nidentify and avoid potential\nsafety risks',
        3: 'Q3: I can explore how candidate\nscores change after adjusting\nweights',
        4: 'Q4: The system generates diverse\nsite selection solutions for\ncomparison',
        5: 'Q5: I can understand how the\nranking algorithm determines\ncandidate priorities',
        6: 'Q6: Spatial view provides good\ndesign for global, cluster, and\ncandidate data',
        7: 'Q7: 3D view provides good\ndesign for checking candidate\nsafety',
        8: 'Q8: Ranking and change views help\nme adjust rankings and observe\nchanges',
        9: 'Q9: The six views are intuitive\nand easy to use',
        10: 'Q10: The system provides sufficient\ninformation and tools for site\nselection',
        11: 'Q11: The interaction and operation\nlogic matches my expectations',
        12: 'Q12: The system is beginner-friendly\nand easy to use'
    }

    # 提取每个问题的均值和标准差
    means = df['均值'].values
    stds = df['标准差'].values

    # 创建图表 - 使用更宽的画布以容纳完整问题标签
    fig, ax = plt.subplots(figsize=(30, 9))

    # 定义颜色
    colors = {
        'System Workflow': '#4472C4',      # 蓝色
        'Visual Design': '#ED7D31',         # 橙色
        'System Usability': '#70AD47'       # 绿色
    }

    x_positions = []
    x_labels = []
    bar_colors = []
    bar_heights = []
    bar_errors = []

    x_pos = 0
    for dim_name, questions in dimensions.items():
        for q in questions:
            idx = q - 1  # 索引从0开始
            x_positions.append(x_pos)
            x_labels.append(question_labels[q])
            bar_colors.append(colors[dim_name])
            bar_heights.append(means[idx])
            bar_errors.append(stds[idx])
            x_pos += 1
        x_pos += 0.5  # 维度之间增加间隔

    # 绘制条形图
    bars = ax.bar(x_positions, bar_heights, color=bar_colors, width=0.7,
                  yerr=bar_errors, capsize=4, error_kw={'elinewidth': 1.5, 'ecolor': '#333333'})

    # 添加数值标签
    for i, (pos, height, err) in enumerate(zip(x_positions, bar_heights, bar_errors)):
        ax.annotate(f'{height:.1f}',
                    xy=(pos, height + err + 0.15),
                    ha='center', va='bottom',
                    fontsize=10, fontweight='bold')

    # 设置X轴
    ax.set_xticks(x_positions)
    ax.set_xticklabels(x_labels, fontsize=8, rotation=0)

    # 设置Y轴
    ax.set_ylim(0, 7.5)
    ax.set_ylabel('Mean Score (7-point Likert Scale)', fontsize=12)
    ax.set_xlabel('Evaluation Items', fontsize=12)

    # 添加水平参考线
    ax.axhline(y=4, color='gray', linestyle='--', alpha=0.5, label='Neutral (4)')
    ax.axhline(y=5, color='gray', linestyle=':', alpha=0.5, label='Good (5)')

    # 添加维度分组标签
    dim_positions = [2, 6.5, 10]  # 各维度的中心位置
    dim_labels = ['System Workflow', 'Visual Design', 'System Usability']

    for pos, label in zip(dim_positions, dim_labels):
        ax.annotate('', xy=(pos-2.5, -1.0), xytext=(pos+2, -1.0),
                    xycoords='data', textcoords='data',
                    arrowprops=dict(arrowstyle='-', color=colors[label], lw=2))
        ax.text(pos, -1.5, label, ha='center', va='top', fontsize=11,
                fontweight='bold', color=colors[label])

    # 添加图例
    legend_elements = [plt.Rectangle((0,0),1,1, facecolor=colors['System Workflow'], label='System Workflow'),
                       plt.Rectangle((0,0),1,1, facecolor=colors['Visual Design'], label='Visual Design'),
                       plt.Rectangle((0,0),1,1, facecolor=colors['System Usability'], label='System Usability')]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)

    ax.set_title('Figure 8: User Study Results by Evaluation Dimension', fontsize=14, fontweight='bold', pad=20)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"图表已保存到: {output_path}")


def create_dimension_summary_chart(df, output_path='paper/figure8_dimension_summary.png'):
    """
    创建维度汇总图表
    展示各维度的整体均值和标准差
    """
    means = df['均值'].values
    stds = df['标准差'].values

    fig, ax = plt.subplots(figsize=(10, 6))

    # 计算各维度的整体均值和标准差
    dim_means = []
    dim_stds = []
    dim_names = ['System\nWorkflow', 'Visual\nDesign', 'System\nUsability']

    # 系统工作流程 (Q1-Q5)
    workflow_means = means[0:5]
    dim_means.append(np.mean(workflow_means))
    dim_stds.append(np.std(workflow_means))

    # 视觉设计与交互 (Q6-Q9)
    design_means = means[5:9]
    dim_means.append(np.mean(design_means))
    dim_stds.append(np.std(design_means))

    # 系统可用性 (Q10-Q12)
    usability_means = means[9:12]
    dim_means.append(np.mean(usability_means))
    dim_stds.append(np.std(usability_means))

    x = np.arange(len(dim_names))
    colors_summary = ['#4472C4', '#ED7D31', '#70AD47']

    bars = ax.bar(x, dim_means, color=colors_summary, width=0.6,
                  yerr=dim_stds, capsize=6, error_kw={'elinewidth': 2, 'ecolor': '#333333'})

    # 添加数值标签
    for i, (bar, mean, std) in enumerate(zip(bars, dim_means, dim_stds)):
        ax.annotate(f'{mean:.2f}±{std:.2f}',
                    xy=(bar.get_x() + bar.get_width()/2, bar.get_height() + std + 0.15),
                    ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(dim_names, fontsize=12)
    ax.set_ylim(0, 7.5)
    ax.set_ylabel('Mean Score (7-point Likert Scale)', fontsize=12)
    ax.set_xlabel('Evaluation Dimension', fontsize=12)
    ax.axhline(y=4, color='gray', linestyle='--', alpha=0.5)
    ax.axhline(y=5, color='gray', linestyle=':', alpha=0.5)

    ax.set_title('Figure 8 (Summary): User Study Results by Dimension', fontsize=14, fontweight='bold', pad=15)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"图表已保存到: {output_path}")

    return dim_means, dim_stds


def print_statistics(df):
    """打印统计汇总"""
    means = df['均值'].values
    stds = df['标准差'].values

    print("\n" + "="*60)
    print("用户研究统计汇总")
    print("="*60)

    # 各问题统计
    print("\n【各问题详细统计】")
    print("-"*60)
    print(f"{'问题':<6} {'均值':>8} {'标准差':>10} {'中位数':>10}")
    print("-"*60)

    for i in range(12):
        dim_name = df.iloc[i, 0] if pd.notna(df.iloc[i, 0]) else ""
        print(f"Q{i+1:<5} {means[i]:>8.2f} {stds[i]:>10.4f} {df['中位数'].values[i]:>10.1f}")

    # 各维度统计
    print("\n【各维度统计】")
    print("-"*60)

    dim_info = [
        ("System Workflow (Q1-Q5)", means[0:5], stds[0:5]),
        ("Visual Design (Q6-Q9)", means[5:9], stds[5:9]),
        ("System Usability (Q10-Q12)", means[9:12], stds[9:12])
    ]

    for name, m, s in dim_info:
        print(f"{name}:")
        print(f"  整体均值: {np.mean(m):.2f}")
        print(f"  均值范围: {np.min(m):.1f} - {np.max(m):.1f}")
        print(f"  标准差范围: {np.min(s):.4f} - {np.max(s):.4f}")

    # 低分项目
    print("\n【低分项目识别】(均值 < 5.1)")
    print("-"*60)
    low_score_threshold = 5.1
    for i in range(12):
        if means[i] < low_score_threshold:
            print(f"Q{i+1}: 均值={means[i]:.1f}, 标准差={stds[i]:.4f}")

    print("="*60)


def main():
    """主函数"""
    # 加载数据
    df = load_data()

    # 打印统计信息
    print_statistics(df)

    # 生成分组条形图
    create_grouped_bar_chart(df)

    # 生成维度汇总图
    dim_means, dim_stds = create_dimension_summary_chart(df)

    print("\n所有图表生成完成！")


if __name__ == '__main__':
    main()
