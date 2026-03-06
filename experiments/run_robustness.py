#!/usr/bin/env python
# experiments/run_robustness.py
"""
鲁棒性实验脚本
修改无人机、卡车、机器人的技术参数，观察指标变化
"""
import os
import sys
import asyncio
import argparse
import json
import yaml
from datetime import datetime
from typing import Dict, Any, List, Optional
import copy
import math

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.recorder import ExperimentRecorder, BatchExperimentRecorder
from configs.loader import load_config, update_config, get_default_config

# ===================== 参数扰动配置 =====================
# 定义各参数的变化范围和步长
PARAM_PERTURBATION_CONFIGS = {
    "uav": {
        "max_speed": {
            "base_value": 0.3,
            "variation_range": [-0.5, -0.2, -0.1, 0, 0.1, 0.2, 0.5],  # 相对变化比例
            "unit": "grid/step",
            "description": "无人机最大速度"
        },
        "volatility": {
            "base_value": 0.02,
            "variation_range": [-0.5, -0.2, 0, 0.2, 0.5, 1.0],
            "unit": "标准差",
            "description": "速度波动程度"
        }
    },
    "truck": {
        "base_fuel_per_100km": {
            "base_value": 30,
            "variation_range": [-0.3, -0.1, 0, 0.1, 0.3],
            "unit": "L/100km",
            "description": "基础油耗"
        },
        "economic_speed": {
            "base_value": 60,
            "variation_range": [-0.3, -0.1, 0, 0.1, 0.3],
            "unit": "km/h",
            "description": "经济时速"
        },
        "load_factor": {
            "base_value": 0.3,
            "variation_range": [-0.3, -0.1, 0, 0.1, 0.3],
            "unit": "系数",
            "description": "载重油耗系数"
        }
    },
    "robot": {
        "speed_m_per_sec": {
            "base_value": 1.0,
            "variation_range": [-0.5, -0.2, 0, 0.2, 0.5],
            "unit": "m/s",
            "description": "移动速度"
        },
        "battery_drain_per_sec": {
            "base_value": 0.02,
            "variation_range": [-0.5, -0.2, 0, 0.2, 0.5, 1.0],
            "unit": "%/s",
            "description": "电量消耗率"
        }
    }
}

# 默认测试prompt
DEFAULT_PROMPT = "请指挥各个agent把干粉灭火器从所在仓库运到深圳市中山大学深圳校区(北纬 22.800884948488687°，东经 113.95443173232752°)"


def generate_perturbed_configs(
    agent_type: str,
    param_name: str,
    variation_range: List[float]
) -> List[Dict[str, Any]]:
    """
    生成参数扰动后的配置列表
    :param agent_type: Agent类型 (uav/truck/robot)
    :param param_name: 参数名称
    :param variation_range: 变化比例列表
    :return: 扰动配置列表
    """
    base_config = load_config()
    perturbed_configs = []

    param_config = PARAM_PERTURBATION_CONFIGS.get(agent_type, {}).get(param_name, {})
    base_value = param_config.get("base_value", base_config.get(agent_type, {}).get(param_name, 1.0))

    for variation in variation_range:
        # 计算扰动后的值
        perturbed_value = base_value * (1 + variation)

        # 创建扰动配置
        config_copy = copy.deepcopy(base_config)
        config_copy[agent_type][param_name] = perturbed_value

        perturbed_configs.append({
            "agent_type": agent_type,
            "param_name": param_name,
            "base_value": base_value,
            "variation_ratio": variation,
            "perturbed_value": perturbed_value,
            "config": config_copy
        })

    return perturbed_configs


async def run_single_robustness_test(
    prompt: str,
    perturbed_config: Dict[str, Any],
    recorder: ExperimentRecorder
) -> Dict[str, Any]:
    """
    执行单次鲁棒性测试
    注意：由于参数是在配置文件层面修改的，需要重新加载模块才能生效
    这里采用模拟方式，实际生产环境可能需要重启服务
    """
    import httpx
    import time

    agent_type = perturbed_config["agent_type"]
    param_name = perturbed_config["param_name"]
    perturbed_value = perturbed_config["perturbed_value"]
    variation_ratio = perturbed_config["variation_ratio"]

    print(f"\n测试参数: {agent_type}.{param_name}")
    print(f"基准值: {perturbed_config['base_value']}, 扰动比例: {variation_ratio*100:.0f}%, 扰动后值: {perturbed_value:.4f}")

    # 更新内存中的配置
    update_config({agent_type: {param_name: perturbed_value}})

    # 记录配置信息
    recorder.current_record["perturbation_info"] = {
        "agent_type": agent_type,
        "param_name": param_name,
        "base_value": perturbed_config["base_value"],
        "variation_ratio": variation_ratio,
        "perturbed_value": perturbed_value
    }

    # 模拟仿真执行（实际生产环境需要调用真实API）
    # 这里返回模拟结果用于演示
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 简化的仿真调用
            # 实际应该调用完整的仿真流程
            await asyncio.sleep(0.5)  # 模拟处理时间

        sim_time = time.time() - start_time

        # 根据参数变化计算预期影响
        # 例如：速度增加会导致时间减少
        if "speed" in param_name.lower():
            time_factor = 1 / (1 + variation_ratio) if variation_ratio > -1 else 1
        elif "fuel" in param_name.lower() or "drain" in param_name.lower():
            time_factor = 1.0  # 能耗参数不影响时间
        else:
            time_factor = 1.0

        result = {
            "success": True,
            "simulation_time": sim_time * time_factor,
            "time_factor": time_factor,
            "perturbed_value": perturbed_value
        }

        recorder.record_agent_result(
            agent_name=f"{agent_type}_perturbed",
            task_id=f"robustness_{int(time.time())}",
            simulation_time=sim_time,
            success=True,
            details=result
        )

    except Exception as e:
        result = {"success": False, "error": str(e)}
        recorder.record_error(str(e), "simulation")

    return result


async def run_robustness_experiment(
    agent_types: List[str] = None,
    prompt: str = None,
    output_dir: str = None,
    custom_variations: Dict[str, Dict[str, List[float]]] = None
):
    """
    执行完整的鲁棒性实验
    :param agent_types: 要测试的Agent类型列表
    :param prompt: 测试prompt
    :param output_dir: 结果输出目录
    :param custom_variations: 自定义参数变化配置
    """
    if agent_types is None:
        agent_types = ["uav", "truck", "robot"]

    if prompt is None:
        prompt = DEFAULT_PROMPT

    # 使用自定义变化配置或默认配置
    variations = custom_variations or PARAM_PERTURBATION_CONFIGS

    batch_recorder = BatchExperimentRecorder(output_dir)
    all_results = []

    print("\n" + "="*60)
    print("鲁棒性实验开始")
    print(f"测试Agent类型: {agent_types}")
    print("="*60)

    for agent_type in agent_types:
        if agent_type not in variations:
            print(f"警告: 未找到 {agent_type} 的参数配置，跳过")
            continue

        print(f"\n\n{'#'*60}")
        print(f"# Agent类型: {agent_type.upper()}")
        print(f"{'#'*60}")

        for param_name, param_config in variations[agent_type].items():
            variation_range = param_config.get("variation_range", [0])

            print(f"\n--- 参数: {param_name} ({param_config.get('description', '')}) ---")

            perturbed_configs = generate_perturbed_configs(
                agent_type,
                param_name,
                variation_range
            )

            for pconfig in perturbed_configs:
                # 开始实验
                recorder = batch_recorder.new_experiment(
                    experiment_type="robustness",
                    config={
                        "agent_type": agent_type,
                        "param_name": param_name,
                        "perturbed_value": pconfig["perturbed_value"],
                        "variation_ratio": pconfig["variation_ratio"]
                    },
                    description=f"{agent_type}.{param_name} 变化 {pconfig['variation_ratio']*100:.0f}%"
                )

                # 执行测试
                result = await run_single_robustness_test(prompt, pconfig, recorder)

                # 结束并保存
                status = "completed" if result.get("success") else "failed"
                recorder.end_experiment(status)
                recorder.save_to_json()
                recorder.append_to_csv()

                all_results.append({
                    "agent_type": agent_type,
                    "param_name": param_name,
                    "variation_ratio": pconfig["variation_ratio"],
                    "perturbed_value": pconfig["perturbed_value"],
                    "result": result
                })

    # 保存汇总结果
    batch_recorder.save_all("robustness_summary.json")

    # 生成敏感度分析报告
    generate_sensitivity_report(all_results, output_dir)

    return all_results


def generate_sensitivity_report(results: List[Dict[str, Any]], output_dir: str):
    """
    生成敏感度分析报告
    """
    report_path = os.path.join(output_dir or os.path.join(os.path.dirname(__file__), "results"), "sensitivity_report.txt")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("鲁棒性实验 - 敏感度分析报告\n")
        f.write(f"生成时间: {datetime.now().isoformat()}\n")
        f.write("="*60 + "\n\n")

        # 按Agent类型和参数分组
        grouped = {}
        for r in results:
            key = (r["agent_type"], r["param_name"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r)

        for (agent_type, param_name), group_results in grouped.items():
            f.write(f"\n{agent_type.upper()}.{param_name}\n")
            f.write("-"*40 + "\n")
            f.write(f"{'变化比例':<15}{'扰动值':<15}{'仿真时间因子':<15}\n")
            f.write("-"*40 + "\n")

            for r in sorted(group_results, key=lambda x: x["variation_ratio"]):
                result = r["result"]
                if result.get("success"):
                    f.write(f"{r['variation_ratio']*100:>+.0f}%{'':<10}{r['perturbed_value']:<15.4f}{result.get('time_factor', 1.0):<15.2f}\n")

            # 计算敏感度系数
            successful_results = [r for r in group_results if r["result"].get("success")]
            if len(successful_results) >= 2:
                # 简单的敏感度计算：输出变化率 / 输入变化率
                base_result = [r for r in successful_results if r["variation_ratio"] == 0]
                if base_result:
                    base_time = base_result[0]["result"].get("simulation_time", 1)

                    f.write("\n敏感度分析:\n")
                    for r in successful_results:
                        if r["variation_ratio"] != 0:
                            time_change = (r["result"].get("simulation_time", base_time) - base_time) / base_time
                            sensitivity = time_change / r["variation_ratio"] if r["variation_ratio"] != 0 else 0
                            f.write(f"  变化{r['variation_ratio']*100:+.0f}%: 敏感度系数 = {sensitivity:.3f}\n")

            f.write("\n")

    print(f"\n敏感度分析报告已保存至: {report_path}")


# ===================== 主入口 =====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="鲁棒性实验脚本")
    parser.add_argument("--agents", nargs="+", choices=["uav", "truck", "robot"],
                        default=["uav", "truck", "robot"], help="要测试的Agent类型")
    parser.add_argument("--prompt", type=str, default=None, help="测试prompt")
    parser.add_argument("--output", type=str, default=None, help="结果输出目录")
    parser.add_argument("--config", type=str, help="自定义参数变化配置文件(YAML)")

    args = parser.parse_args()

    # 加载自定义配置
    custom_variations = None
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            custom_variations = yaml.safe_load(f)

    # 执行实验
    asyncio.run(run_robustness_experiment(
        agent_types=args.agents,
        prompt=args.prompt,
        output_dir=args.output,
        custom_variations=custom_variations
    ))
