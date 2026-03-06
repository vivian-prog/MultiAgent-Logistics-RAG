# experiments/metrics.py
"""
实验指标计算模块
提供统一的指标计算和评估功能
"""
import math
from typing import Dict, Any, List, Optional
from datetime import datetime


class MetricsCalculator:
    """指标计算器"""

    @staticmethod
    def calculate_time_error(
        simulated_time: float,
        real_time: float,
        unit: str = "hours"
    ) -> Dict[str, float]:
        """
        计算时间误差
        :param simulated_time: 仿真时间
        :param real_time: 真实时间
        :param unit: 时间单位 (hours/seconds)
        :return: 误差指标字典
        """
        if real_time == 0:
            return {"error": "real_time is zero"}

        absolute_error = abs(simulated_time - real_time)
        relative_error = absolute_error / real_time
        accuracy = 1 - min(relative_error, 1)

        return {
            "absolute_error": round(absolute_error, 4),
            "relative_error": round(relative_error, 4),
            "accuracy": round(accuracy, 4),
            "simulated_time": simulated_time,
            "real_time": real_time
        }

    @staticmethod
    def calculate_rag_performance(
        rag_search_time: float,
        llm_inference_time: float,
        retrieval_quality_score: float = None
    ) -> Dict[str, float]:
        """
        计算RAG性能指标
        :param rag_search_time: RAG检索时间
        :param llm_inference_time: LLM推理时间
        :param retrieval_quality_score: 检索质量分数（可选）
        """
        total_time = rag_search_time + llm_inference_time
        rag_ratio = rag_search_time / total_time if total_time > 0 else 0

        return {
            "rag_search_time": rag_search_time,
            "llm_inference_time": llm_inference_time,
            "total_time": total_time,
            "rag_time_ratio": round(rag_ratio, 4),
            "retrieval_quality": retrieval_quality_score
        }

    @staticmethod
    def calculate_agent_efficiency(
        simulation_time: float,
        task_complexity: float = 1.0,
        success: bool = True
    ) -> Dict[str, float]:
        """
        计算Agent效率指标
        :param simulation_time: 仿真时间
        :param task_complexity: 任务复杂度因子
        :param success: 是否成功
        """
        efficiency = (1 / simulation_time) * task_complexity if simulation_time > 0 else 0
        if not success:
            efficiency = 0

        return {
            "simulation_time": simulation_time,
            "task_complexity": task_complexity,
            "efficiency": round(efficiency, 6),
            "success": success
        }

    @staticmethod
    def calculate_fuel_efficiency(
        actual_fuel: float,
        expected_fuel: float,
        distance_km: float
    ) -> Dict[str, float]:
        """
        计算燃油效率指标
        :param actual_fuel: 实际油耗
        :param expected_fuel: 预期油耗
        :param distance_km: 行驶距离
        """
        fuel_per_km = actual_fuel / distance_km if distance_km > 0 else 0
        fuel_per_100km = fuel_per_km * 100
        efficiency_ratio = expected_fuel / actual_fuel if actual_fuel > 0 else 0

        return {
            "actual_fuel": actual_fuel,
            "expected_fuel": expected_fuel,
            "fuel_per_km": round(fuel_per_km, 4),
            "fuel_per_100km": round(fuel_per_100km, 2),
            "efficiency_ratio": round(efficiency_ratio, 4)
        }


class ExperimentComparator:
    """实验结果对比器"""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def add_result(self, result: Dict[str, Any]):
        """添加实验结果"""
        self.results.append(result)

    def compare_time_metrics(self) -> Dict[str, Any]:
        """对比时间指标"""
        comparison = {}

        for result in self.results:
            config_name = result.get("config", {}).get("name", "unknown")

            total_time = result.get("result", {}).get("total_time", 0)
            rag_time = result.get("result", {}).get("rag_search_time", 0)
            llm_time = result.get("result", {}).get("llm_inference_time", 0)

            comparison[config_name] = {
                "total_time": total_time,
                "rag_time": rag_time,
                "llm_time": llm_time
            }

        return comparison

    def get_best_config(self, metric: str = "total_time") -> str:
        """获取最优配置"""
        if not self.results:
            return None

        best_config = None
        best_value = float('inf')

        for result in self.results:
            config_name = result.get("config", {}).get("name", "unknown")
            value = result.get("result", {}).get(metric, float('inf'))

            if value < best_value:
                best_value = value
                best_config = config_name

        return best_config

    def generate_comparison_report(self) -> str:
        """生成对比报告"""
        lines = []
        lines.append("="*60)
        lines.append("实验对比报告")
        lines.append(f"生成时间: {datetime.now().isoformat()}")
        lines.append("="*60)

        # 时间对比
        lines.append("\n## 时间指标对比\n")
        lines.append(f"{'配置':<20}{'总时间(s)':<15}{'RAG时间(s)':<15}{'LLM时间(s)':<15}")
        lines.append("-"*60)

        for result in self.results:
            config_name = result.get("config", {}).get("name", "unknown")
            total = result.get("result", {}).get("total_time", 0)
            rag = result.get("result", {}).get("rag_search_time", 0)
            llm = result.get("result", {}).get("llm_inference_time", 0)

            lines.append(f"{config_name:<20}{total:<15.2f}{rag:<15.2f}{llm:<15.2f}")

        # Agent结果对比
        lines.append("\n## Agent仿真结果对比\n")
        for result in self.results:
            config_name = result.get("config", {}).get("name", "unknown")
            agent_results = result.get("result", {}).get("agent_results", {})

            lines.append(f"\n### {config_name}")
            for agent, data in agent_results.items():
                lines.append(f"  {agent}: {data.get('time', 0):.2f}s (成功: {data.get('success', False)})")

        return "\n".join(lines)


class SensitivityAnalyzer:
    """敏感度分析器"""

    @staticmethod
    def calculate_sensitivity(
        base_value: float,
        perturbed_values: List[float],
        base_output: float,
        perturbed_outputs: List[float]
    ) -> Dict[str, float]:
        """
        计算敏感度系数
        :param base_value: 基准参数值
        :param perturbed_values: 扰动后的参数值列表
        :param base_output: 基准输出
        :param perturbed_outputs: 扰动后的输出列表
        :return: 敏感度分析结果
        """
        sensitivities = []

        for p_value, p_output in zip(perturbed_values, perturbed_outputs):
            if base_value != 0 and base_output != 0:
                input_change = (p_value - base_value) / base_value
                output_change = (p_output - base_output) / base_output

                if input_change != 0:
                    sensitivity = output_change / input_change
                    sensitivities.append(sensitivity)

        if sensitivities:
            return {
                "avg_sensitivity": sum(sensitivities) / len(sensitivities),
                "max_sensitivity": max(sensitivities),
                "min_sensitivity": min(sensitivities),
                "sensitivity_values": sensitivities
            }

        return {"avg_sensitivity": 0, "max_sensitivity": 0, "min_sensitivity": 0}

    @staticmethod
    def classify_sensitivity(sensitivity: float) -> str:
        """分类敏感度级别"""
        abs_sensitivity = abs(sensitivity)
        if abs_sensitivity < 0.1:
            return "低敏感"
        elif abs_sensitivity < 0.5:
            return "中敏感"
        elif abs_sensitivity < 1.0:
            return "高敏感"
        else:
            return "极高敏感"


# 便捷函数
def calculate_all_metrics(experiment_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    计算实验结果的所有指标
    :param experiment_result: 实验结果字典
    :return: 计算后的指标字典
    """
    metrics = {}

    # RAG指标
    rag_metrics = experiment_result.get("metrics", {}).get("rag", {})
    if rag_metrics:
        metrics["rag_performance"] = MetricsCalculator.calculate_rag_performance(
            rag_metrics.get("search_time_seconds", 0),
            rag_metrics.get("llm_inference_time_seconds", 0)
        )

    # Agent效率
    agent_results = experiment_result.get("agent_results", {})
    for agent_name, agent_data in agent_results.items():
        metrics[f"{agent_name}_efficiency"] = MetricsCalculator.calculate_agent_efficiency(
            agent_data.get("simulation_time_seconds", 0),
            success=agent_data.get("success", False)
        )

    # 与基准对比
    benchmark = experiment_result.get("benchmark_comparison", {})
    if benchmark.get("real_delivery_time_hours"):
        total_sim_time = sum(
            a.get("simulation_time_seconds", 0) for a in agent_results.values()
        ) / 3600  # 转换为小时

        metrics["time_error"] = MetricsCalculator.calculate_time_error(
            total_sim_time,
            benchmark["real_delivery_time_hours"]
        )

    return metrics
