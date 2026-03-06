# experiments/recorder.py
"""
实验结果持久化模块
用于保存和管理实验结果，支持JSON和CSV格式
"""
import os
import json
import csv
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid


class ExperimentRecorder:
    """实验记录器"""

    def __init__(self, output_dir: str = None):
        """
        初始化记录器
        :param output_dir: 结果输出目录，默认为 experiments/results
        """
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "results")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 当前实验ID
        self.experiment_id = None
        # 当前实验记录
        self.current_record: Dict[str, Any] = {}

    def start_experiment(
        self,
        experiment_type: str,
        config: Dict[str, Any],
        description: str = ""
    ) -> str:
        """
        开始一个新实验
        :param experiment_type: 实验类型 (ablation/robustness)
        :param config: 实验配置
        :param description: 实验描述
        :return: 实验ID
        """
        self.experiment_id = f"{experiment_type}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        self.current_record = {
            "experiment_id": self.experiment_id,
            "experiment_type": experiment_type,
            "description": description,
            "config": config,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "running",
            "metrics": {},
            "agent_results": {},
            "errors": []
        }
        return self.experiment_id

    def record_rag_metrics(
        self,
        rag_enabled: bool,
        rag_type: str,
        rag_search_time: float,
        llm_inference_time: float,
        rag_context: str = "",
        final_answer: str = ""
    ):
        """
        记录RAG相关指标
        """
        self.current_record["metrics"]["rag"] = {
            "enabled": rag_enabled,
            "type": rag_type,
            "search_time_seconds": round(rag_search_time, 4),
            "llm_inference_time_seconds": round(llm_inference_time, 4),
            "total_time_seconds": round(rag_search_time + llm_inference_time, 4),
            "context_length": len(rag_context) if rag_context else 0,
            "answer_length": len(final_answer) if final_answer else 0
        }

    def record_agent_result(
        self,
        agent_name: str,
        task_id: str,
        simulation_time: float,
        success: bool,
        details: Dict[str, Any] = None
    ):
        """
        记录单个Agent的仿真结果
        """
        self.current_record["agent_results"][agent_name] = {
            "task_id": task_id,
            "simulation_time_seconds": round(simulation_time, 4),
            "success": success,
            "details": details or {}
        }

    def record_generated_commands(self, commands: Dict[str, Any]):
        """
        记录LLM生成的指令JSON
        """
        self.current_record["generated_commands"] = commands

    def record_user_prompt(self, prompt: str):
        """
        记录用户输入的prompt
        """
        self.current_record["user_prompt"] = prompt

    def record_error(self, error_msg: str, stage: str = "unknown"):
        """
        记录错误信息
        """
        self.current_record["errors"].append({
            "stage": stage,
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        })

    def record_benchmark_comparison(
        self,
        real_delivery_time: float = None,
        real_distance_km: float = None,
        notes: str = ""
    ):
        """
        记录与真实配送时间的对比
        """
        self.current_record["benchmark_comparison"] = {
            "real_delivery_time_hours": real_delivery_time,
            "real_distance_km": real_distance_km,
            "notes": notes
        }

    def end_experiment(self, status: str = "completed"):
        """
        结束当前实验
        :param status: 实验状态 (completed/failed/partial)
        """
        self.current_record["end_time"] = datetime.now().isoformat()
        self.current_record["status"] = status

        # 计算总耗时
        start = datetime.fromisoformat(self.current_record["start_time"])
        end = datetime.fromisoformat(self.current_record["end_time"])
        self.current_record["total_duration_seconds"] = (end - start).total_seconds()

    def save_to_json(self, filename: str = None) -> str:
        """
        保存实验结果到JSON文件
        :param filename: 文件名，默认使用实验ID
        :return: 保存的文件路径
        """
        if filename is None:
            filename = f"{self.experiment_id}.json"

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.current_record, f, ensure_ascii=False, indent=2)

        return filepath

    def append_to_csv(self, csv_file: str = "experiments_summary.csv") -> str:
        """
        追加实验结果到CSV汇总文件
        :param csv_file: CSV文件名
        :return: CSV文件路径
        """
        filepath = os.path.join(self.output_dir, csv_file)

        # 定义CSV列
        columns = [
            "experiment_id", "experiment_type", "status", "start_time", "end_time",
            "total_duration_seconds", "rag_enabled", "rag_type",
            "rag_search_time", "llm_inference_time", "rag_total_time",
            "robot_time", "truck_time", "uav_time",
            "robot_success", "truck_success", "uav_success",
            "real_delivery_time", "real_distance_km"
        ]

        # 提取扁平化数据
        row = {
            "experiment_id": self.current_record.get("experiment_id", ""),
            "experiment_type": self.current_record.get("experiment_type", ""),
            "status": self.current_record.get("status", ""),
            "start_time": self.current_record.get("start_time", ""),
            "end_time": self.current_record.get("end_time", ""),
            "total_duration_seconds": self.current_record.get("total_duration_seconds", 0),
            "rag_enabled": self.current_record.get("metrics", {}).get("rag", {}).get("enabled", False),
            "rag_type": self.current_record.get("metrics", {}).get("rag", {}).get("type", ""),
            "rag_search_time": self.current_record.get("metrics", {}).get("rag", {}).get("search_time_seconds", 0),
            "llm_inference_time": self.current_record.get("metrics", {}).get("rag", {}).get("llm_inference_time_seconds", 0),
            "rag_total_time": self.current_record.get("metrics", {}).get("rag", {}).get("total_time_seconds", 0),
            "robot_time": self.current_record.get("agent_results", {}).get("agentrobot", {}).get("simulation_time_seconds", 0),
            "truck_time": self.current_record.get("agent_results", {}).get("agenttruck", {}).get("simulation_time_seconds", 0),
            "uav_time": self.current_record.get("agent_results", {}).get("agentuav", {}).get("simulation_time_seconds", 0),
            "robot_success": self.current_record.get("agent_results", {}).get("agentrobot", {}).get("success", False),
            "truck_success": self.current_record.get("agent_results", {}).get("agenttruck", {}).get("success", False),
            "uav_success": self.current_record.get("agent_results", {}).get("agentuav", {}).get("success", False),
            "real_delivery_time": self.current_record.get("benchmark_comparison", {}).get("real_delivery_time_hours", ""),
            "real_distance_km": self.current_record.get("benchmark_comparison", {}).get("real_distance_km", ""),
        }

        # 判断是否需要写入表头
        write_header = not os.path.exists(filepath)

        with open(filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

        return filepath

    def get_record(self) -> Dict[str, Any]:
        """获取当前实验记录"""
        return self.current_record


class BatchExperimentRecorder:
    """批量实验记录器，用于管理多次实验"""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(self.output_dir, exist_ok=True)
        self.records: List[Dict[str, Any]] = []
        self.recorder = ExperimentRecorder(self.output_dir)

    def new_experiment(self, experiment_type: str, config: Dict[str, Any], description: str = "") -> ExperimentRecorder:
        """开始新实验"""
        self.recorder.start_experiment(experiment_type, config, description)
        return self.recorder

    def save_all(self, summary_name: str = "batch_summary.json"):
        """保存所有实验记录到汇总文件"""
        filepath = os.path.join(self.output_dir, summary_name)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)
        return filepath


# 便捷函数
def create_recorder(output_dir: str = None) -> ExperimentRecorder:
    """创建实验记录器"""
    return ExperimentRecorder(output_dir)
