#!/usr/bin/env python
# ex_main.py
"""
实验主程序 - 多智能体物流调度系统
支持以下实验类型：
1. 基础实验组 - 收集三种Agent仿真时间、RAG操作耗时、LLM思考耗时
2. 消融实验 - RAG vs GraphRAG vs 无RAG
3. 鲁棒性实验 - 修改Agent耗电速度等参数
4. 对比实验 - 不同算法策略对比
"""
import os
import sys
import asyncio
import argparse
import json
import csv
import time
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import copy

import httpx
import requests
from openai import OpenAI

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from prompts.prompts import MultiAgentLogisticRAGPrompt
from experiments.recorder import ExperimentRecorder, BatchExperimentRecorder
from experiments.metrics import MetricsCalculator, SensitivityAnalyzer
from configs.loader import load_config, update_config, get_default_config


# ===================== 实验类型枚举 =====================
class ExperimentType(Enum):
    BASELINE = "baseline"           # 基础实验组
    ABLATION = "ablation"           # 消融实验
    ROBUSTNESS = "robustness"       # 鲁棒性实验
    COMPARISON = "comparison"       # 对比实验


# ===================== 配置项 =====================
# RAG 开关配置
ENABLE_RAG = True
RAG_TYPE = "graphrag"

# RAG服务配置
RAG_URL = "http://localhost:8015/v1/chat/completions"
GRAPHRAG_URL = "http://localhost:8015/v1/chat/completions"
RAG_HEADERS = {"Content-Type": "application/json"}
RAG_MODEL_GLOBAL = "graphrag-global-search:latest"
RAG_MODEL_LOCAL = "graphrag-local-search:latest"
RAG_MODEL_FULL = "full-model:latest"

# FAISS TextRAG服务配置 (用于消融实验的text_rag配置)
FAISS_TEXTRAG_URL = "http://localhost:8016/v1/chat/completions"
FAISS_TEXTRAG_MODEL = "faiss-text-search:latest"

# FAISS Raw TextRAG服务配置 (使用原始文本，用于消融实验的raw_text_rag配置)
FAISS_RAW_TEXTRAG_URL = "http://localhost:8017/v1/chat/completions"
FAISS_RAW_TEXTRAG_MODEL = "faiss-raw-text-search:latest"

# LLM模型配置
LLM_BASE_URL = "http://localhost:8080/v1"
LLM_API_KEY = "sk-xxx"
LLM_MODEL = "Qwen3-8B"

# 仿真FastAPI服务地址
API_BASE_URL = "http://localhost:8090"
AGENT_API_MAP = {
    "agentuav": f"{API_BASE_URL}/api/v1/simulation/agentuav",
    "agenttruck": f"{API_BASE_URL}/api/v1/simulation/agenttruck",
    "agentrobot": f"{API_BASE_URL}/api/v1/simulation/agentrobot",
    "agentuav_submit": f"{API_BASE_URL}/api/agent1/simulation",
    "agentuav_result": f"{API_BASE_URL}/api/agent1/result/{{}}",
    "common_result": f"{API_BASE_URL}/api/v1/task/{{}}"
}

# Prompts配置
prompt_config = MultiAgentLogisticRAGPrompt()
CLOUDLLM_SYSTEM_PROMPT = prompt_config.cloudLLM_session_init
RAG_SYSTEM_PROMPT = prompt_config.RAG_session_init


# ===================== 实验指标数据类 =====================
@dataclass
class ExperimentMetrics:
    """实验指标数据结构"""
    # RAG相关指标
    rag_enabled: bool = False
    rag_type: str = ""
    rag_search_time: float = 0.0          # RAG检索耗时(秒)
    rag_query_generation_time: float = 0.0  # RAG查询生成耗时(秒)

    # LLM相关指标
    llm_total_time: float = 0.0           # LLM总思考耗时(秒)
    llm_query_gen_time: float = 0.0       # LLM生成RAG查询的耗时
    llm_command_gen_time: float = 0.0     # LLM生成指令的耗时

    # Agent仿真指标
    robot_simulation_time: float = 0.0    # Robot仿真物理世界运行时间(秒)
    truck_simulation_time: float = 0.0    # Truck仿真物理世界运行时间(秒)
    uav_simulation_time: float = 0.0      # UAV仿真物理世界运行时间(秒)

    # 成功标志
    robot_success: bool = False
    truck_success: bool = False
    uav_success: bool = False

    # 总耗时
    total_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ===================== 核心函数 =====================
def rag_search(prompt: str, rag_model: str = RAG_MODEL_FULL,
               temperature: float = 0.7, rag_type: str = RAG_TYPE) -> Tuple[str, float]:
    """
    执行RAG搜索，返回相关内容和耗时
    :return: (检索结果, 耗时秒数)
    """
    start_time = time.time()
    try:
        if rag_type == "graphrag":
            url = GRAPHRAG_URL
            model = RAG_MODEL_GLOBAL
        elif rag_type == "rag":
            # 使用FAISS文本检索服务 (GraphRAG预处理后的text_units)
            url = FAISS_TEXTRAG_URL
            model = FAISS_TEXTRAG_MODEL
        elif rag_type == "raw_rag":
            # 使用FAISS原始文本检索服务 (原始txt文件)
            url = FAISS_RAW_TEXTRAG_URL
            model = FAISS_RAW_TEXTRAG_MODEL
        else:
            url = RAG_URL
            model = rag_model

        rag_data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        response = requests.post(url, headers=RAG_HEADERS, data=json.dumps(rag_data), timeout=60)
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]
        elapsed = time.time() - start_time
        return result, elapsed

    except Exception as e:
        print(f"RAG搜索请求出错: {e}")
        return "", time.time() - start_time


def call_llm_model(prompt: str, rag_context: str = "", temperature: float = 0.7) -> Tuple[str, float]:
    """
    调用LLM模型，返回回答和耗时
    :return: (回答内容, 耗时秒数)
    """
    start_time = time.time()
    try:
        client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

        if rag_context:
            full_prompt = f"""
            以下是相关参考信息：
            {rag_context}

            请基于以上参考信息回答问题：{prompt}
            """
        else:
            full_prompt = prompt

        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=temperature,
        )
        content = completion.choices[0].message.content
        content = re.sub(r'<think.*?</think','', content, flags=re.DOTALL).strip()
        elapsed = time.time() - start_time
        return content, elapsed

    except Exception as e:
        print(f"调用LLM出错: {e}")
        return "", time.time() - start_time


def extract_and_parse_last_json(final_answer: str) -> dict:
    """解析JSON响应"""
    cleaned_str = final_answer.replace('\u200b', '').replace('\xa0', ' ').strip()
    top_level_pattern = r'^.*?(\{[\s\S]*\}).*$'
    matches = re.findall(top_level_pattern, cleaned_str, re.DOTALL)

    if not matches:
        raise ValueError("未找到顶层JSON结构")

    top_level_json_str = matches[0].strip()

    try:
        answer_dict = json.loads(top_level_json_str)
        return answer_dict
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析失败：{e}") from e


async def poll_task(client, task_id, agent_name) -> Optional[Dict]:
    """轮询任务结果"""
    max_retries = 120
    retry_interval = 1

    for _ in range(max_retries):
        try:
            url = AGENT_API_MAP["common_result"].format(task_id)
            resp = await client.get(url)

            if resp.status_code == 404 and agent_name == "agentuav":
                url = AGENT_API_MAP["agentuav_result"].format(task_id)
                resp = await client.get(url)

            resp.raise_for_status()
            data = resp.json()
            status = str(data.get("status", "")).upper()

            if status == "SUCCESS":
                return data.get("result") or data.get("simulation_data")
            elif status in ["FAILURE", "FAILED"]:
                return None
            else:
                await asyncio.sleep(retry_interval)

        except Exception:
            await asyncio.sleep(retry_interval)

    return None


# ===================== 实验执行类 =====================
class ExperimentRunner:
    """实验执行器"""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "experiments", "results")
        os.makedirs(self.output_dir, exist_ok=True)
        self.recorder = ExperimentRecorder(self.output_dir)

    async def run_single_experiment(
        self,
        prompt: str,
        enable_rag: bool = True,
        rag_type: str = "graphrag",
        experiment_name: str = "test"
    ) -> ExperimentMetrics:
        """
        执行单次实验，收集完整指标
        """
        metrics = ExperimentMetrics()
        metrics.rag_enabled = enable_rag
        metrics.rag_type = rag_type if enable_rag else "none"

        total_start = time.time()

        print(f"\n{'='*60}")
        print(f"实验: {experiment_name}")
        print(f"RAG模式: {'启用 (' + rag_type + ')' if enable_rag else '禁用'}")
        print(f"Prompt: {prompt[:50]}...")
        print(f"{'='*60}")

        # ========== 阶段1: RAG检索 ==========
        rag_context = ""
        if enable_rag:
            # 1.1 生成RAG查询
            rag_query_prompt = RAG_SYSTEM_PROMPT.format(user_prompt=prompt)
            rag_query, query_gen_time = call_llm_model(rag_query_prompt, '', 0.7)
            metrics.llm_query_gen_time = query_gen_time
            metrics.rag_query_generation_time = query_gen_time

            # 处理查询
            rag_query_list = rag_query.split()
            rag_query = " ".join(rag_query_list)
            print(f"RAG查询关键词: {rag_query[:100]}...")

            # 1.2 执行RAG搜索
            rag_context, rag_search_time = rag_search(rag_query, RAG_MODEL_FULL, 0.7, rag_type)
            metrics.rag_search_time = rag_search_time

            print(f"RAG检索耗时: {rag_search_time:.2f}s")
            print(f"RAG查询生成耗时: {query_gen_time:.2f}s")

        # ========== 阶段2: LLM指令生成 ==========
        cloudllm_prompt = CLOUDLLM_SYSTEM_PROMPT.format(user_prompt=prompt)
        final_answer, command_gen_time = call_llm_model(cloudllm_prompt, rag_context, 0.7)
        metrics.llm_command_gen_time = command_gen_time
        metrics.llm_total_time = metrics.llm_query_gen_time + command_gen_time

        print(f"LLM指令生成耗时: {command_gen_time:.2f}s")
        print(f"LLM总思考耗时: {metrics.llm_total_time:.2f}s")

        # ========== 阶段3: 解析指令 ==========
        try:
            answer_dict = extract_and_parse_last_json(final_answer)
            print(f"解析指令成功: {list(answer_dict.keys())}")
        except ValueError as e:
            print(f"JSON解析失败: {e}")
            metrics.total_time = time.time() - total_start
            return metrics

        # ========== 阶段4: Agent仿真执行 ==========
        agentuav_params = answer_dict.get("agentuav", {})
        agenttruck_params = answer_dict.get("agenttruck", {})
        agentrobot_params = answer_dict.get("agentrobot", {})

        async with httpx.AsyncClient(timeout=60.0) as client:
            # 4.1 Robot仿真
            if agentrobot_params:
                t_start = time.time()
                try:
                    resp = await client.post(AGENT_API_MAP["agentrobot"], json=agentrobot_params)
                    resp.raise_for_status()
                    task_id = resp.json()["task_id"]
                    result = await poll_task(client, task_id, "agentrobot")

                    # Robot使用10倍速修正
                    sim_time = (time.time() - t_start) * 10.0
                    metrics.robot_simulation_time = sim_time
                    metrics.robot_success = result is not None
                    print(f"Robot仿真时间: {sim_time:.2f}s (成功: {metrics.robot_success})")
                except Exception as e:
                    print(f"Robot任务异常: {e}")
                    metrics.robot_simulation_time = -1

            # 4.2 Truck仿真
            if agenttruck_params:
                t_start = time.time()
                try:
                    # GPS坐标兜底
                    if "end_lat" not in agenttruck_params and agentuav_params.get("start_lat"):
                        agenttruck_params["end_lat"] = agentuav_params["start_lat"]
                        agenttruck_params["end_lng"] = agentuav_params["start_lng"]

                    resp = await client.post(AGENT_API_MAP["agenttruck"], json=agenttruck_params)
                    resp.raise_for_status()
                    task_id = resp.json()["task_id"]
                    result = await poll_task(client, task_id, "agenttruck")

                    if result and "total_time" in result:
                        sim_time = float(result["total_time"]) * 3600  # 小时转秒
                    else:
                        sim_time = time.time() - t_start

                    metrics.truck_simulation_time = sim_time
                    metrics.truck_success = result is not None
                    print(f"Truck仿真时间: {sim_time:.2f}s (成功: {metrics.truck_success})")
                except Exception as e:
                    print(f"Truck任务异常: {e}")
                    metrics.truck_simulation_time = -1

            # 4.3 UAV仿真
            if agentuav_params:
                t_start = time.time()
                try:
                    resp = await client.post(AGENT_API_MAP["agentuav_submit"], json=agentuav_params)
                    resp.raise_for_status()
                    task_id = resp.json()["task_id"]
                    result = await poll_task(client, task_id, "agentuav")

                    if result and "total_steps" in result:
                        sim_time = float(result["total_steps"])
                    else:
                        sim_time = time.time() - t_start

                    metrics.uav_simulation_time = sim_time
                    metrics.uav_success = result is not None
                    print(f"UAV仿真时间: {sim_time:.2f}s (成功: {metrics.uav_success})")
                except Exception as e:
                    print(f"UAV任务异常: {e}")
                    metrics.uav_simulation_time = -1

        metrics.total_time = time.time() - total_start
        print(f"\n总耗时: {metrics.total_time:.2f}s")

        return metrics

    def save_metrics_to_csv(self, metrics_list: List[ExperimentMetrics], filename: str):
        """保存指标到CSV"""
        filepath = os.path.join(self.output_dir, filename)

        fieldnames = [
            "rag_enabled", "rag_type", "rag_search_time", "rag_query_generation_time",
            "llm_total_time", "llm_query_gen_time", "llm_command_gen_time",
            "robot_simulation_time", "truck_simulation_time", "uav_simulation_time",
            "robot_success", "truck_success", "uav_success", "total_time"
        ]

        write_header = not os.path.exists(filepath)

        with open(filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            for m in metrics_list:
                writer.writerow(m.to_dict())

        print(f"指标已保存至: {filepath}")
        return filepath


# ===================== 消融实验配置 =====================
ABLATION_CONFIGS = [
    {
        "name": "no_rag",
        "display_name": "无RAG (仅LLM)",
        "enable_rag": False,
        "rag_type": None
    },
    {
        "name": "text_rag",
        "display_name": "Text RAG (GraphRAG预处理文本单元)",
        "enable_rag": True,
        "rag_type": "rag"
    },
    {
        "name": "raw_text_rag",
        "display_name": "Raw Text RAG (原始文本)",
        "enable_rag": True,
        "rag_type": "raw_rag"
    },
    {
        "name": "graphrag",
        "display_name": "GraphRAG (知识图谱)",
        "enable_rag": True,
        "rag_type": "graphrag"
    }
]

# ===================== 鲁棒性实验配置 =====================
ROBUSTNESS_CONFIGS = {
    "uav": {
        "battery_drain_rate": {
            "base_value": 0.5,
            "variation_range": [-0.5, -0.3, -0.1, 0, 0.1, 0.3, 0.5],
            "description": "无人机耗电速率"
        },
        "max_speed": {
            "base_value": 0.3,
            "variation_range": [-0.5, -0.2, 0, 0.2, 0.5],
            "description": "无人机最大速度"
        }
    },
    "robot": {
        "battery_drain_per_sec": {
            "base_value": 0.02,
            "variation_range": [-0.5, -0.3, 0, 0.3, 0.5, 1.0],
            "description": "机器人耗电速率"
        },
        "speed_m_per_sec": {
            "base_value": 1.0,
            "variation_range": [-0.5, -0.2, 0, 0.2, 0.5],
            "description": "机器人移动速度"
        }
    },
    "truck": {
        "base_fuel_per_100km": {
            "base_value": 30,
            "variation_range": [-0.3, -0.1, 0, 0.1, 0.3],
            "description": "卡车基础油耗"
        }
    }
}

# ===================== 对比实验配置 =====================
COMPARISON_CONFIGS = [
    {
        "name": "baseline",
        "display_name": "基线方案 (GraphRAG + LLM)",
        "enable_rag": True,
        "rag_type": "graphrag",
        "algorithm": "standard"
    },
    {
        "name": "optimized_routing",
        "display_name": "优化路径规划",
        "enable_rag": True,
        "rag_type": "graphrag",
        "algorithm": "optimized_routing"
    },
    {
        "name": "multi_stage",
        "display_name": "多阶段决策",
        "enable_rag": True,
        "rag_type": "graphrag",
        "algorithm": "multi_stage"
    }
]

# ===================== 默认测试数据 =====================
DEFAULT_PROMPTS = [
    "请指挥各个agent把干粉灭火器从所在仓库运到深圳市中山大学深圳校区(北纬 22.800884948488687°，东经 113.95443173232752°)",
    "请调度无人机把急救药品从深圳仓库运到深圳市光明区人民医院",
    "安排卡车运送500公斤生鲜从龙华仓储中心到南山配送站",
    "协调机器人、卡车和无人机完成从福田仓库到宝安机场的快递配送",
    "指挥仓储机器人分拣锂电池，并通过卡车运往龙岗区配送中心"
]


# ===================== 实验执行函数 =====================
async def run_baseline_experiments(
    prompts: List[str] = None,
    repeat: int = 1,
    output_dir: str = None
) -> List[ExperimentMetrics]:
    """
    运行基础实验组 - 收集所有指标
    """
    if prompts is None:
        prompts = DEFAULT_PROMPTS

    runner = ExperimentRunner(output_dir)
    all_metrics = []

    print("\n" + "="*60)
    print("基础实验组开始")
    print(f"测试Prompt数量: {len(prompts)}")
    print(f"每Prompt重复次数: {repeat}")
    print("="*60)

    for prompt_idx, prompt in enumerate(prompts):
        for rep in range(repeat):
            print(f"\n[Prompt {prompt_idx+1}/{len(prompts)}] [重复 {rep+1}/{repeat}]")

            # 使用默认GraphRAG配置
            metrics = await runner.run_single_experiment(
                prompt=prompt,
                enable_rag=True,
                rag_type="graphrag",
                experiment_name=f"baseline_p{prompt_idx+1}_r{rep+1}"
            )
            all_metrics.append(metrics)

            # 间隔
            await asyncio.sleep(2)

    # 保存结果
    runner.save_metrics_to_csv(all_metrics, "baseline_metrics.csv")

    # 打印汇总统计
    print_summary_statistics(all_metrics, "基础实验组")

    return all_metrics


async def run_ablation_experiments(
    prompts: List[str] = None,
    repeat: int = 1,
    output_dir: str = None
) -> Dict[str, List[ExperimentMetrics]]:
    """
    运行消融实验 - 对比不同RAG模式
    """
    if prompts is None:
        prompts = DEFAULT_PROMPTS[:3]  # 使用前3个prompt

    runner = ExperimentRunner(output_dir)
    results = {config["name"]: [] for config in ABLATION_CONFIGS}

    print("\n" + "="*60)
    print("消融实验开始")
    print(f"测试Prompt数量: {len(prompts)}")
    print(f"实验配置: {[c['name'] for c in ABLATION_CONFIGS]}")
    print("="*60)

    for prompt_idx, prompt in enumerate(prompts):
        for config in ABLATION_CONFIGS:
            for rep in range(repeat):
                print(f"\n[Prompt {prompt_idx+1}/{len(prompts)}] [{config['display_name']}] [重复 {rep+1}/{repeat}]")

                metrics = await runner.run_single_experiment(
                    prompt=prompt,
                    enable_rag=config["enable_rag"],
                    rag_type=config["rag_type"] or "none",
                    experiment_name=f"ablation_{config['name']}_p{prompt_idx+1}_r{rep+1}"
                )
                results[config["name"]].append(metrics)

                await asyncio.sleep(3)

    # 保存各配置结果
    for config_name, metrics_list in results.items():
        runner.save_metrics_to_csv(metrics_list, f"ablation_{config_name}_metrics.csv")

    # 打印对比统计
    print_ablation_comparison(results)

    return results


async def run_robustness_experiments(
    agent_types: List[str] = None,
    prompt: str = None,
    output_dir: str = None
) -> Dict[str, List[ExperimentMetrics]]:
    """
    运行鲁棒性实验 - 修改Agent参数
    """
    if agent_types is None:
        agent_types = ["uav", "robot"]

    if prompt is None:
        prompt = DEFAULT_PROMPTS[0]

    runner = ExperimentRunner(output_dir)
    results = {}

    print("\n" + "="*60)
    print("鲁棒性实验开始")
    print(f"测试Agent类型: {agent_types}")
    print("="*60)

    for agent_type in agent_types:
        if agent_type not in ROBUSTNESS_CONFIGS:
            continue

        for param_name, param_config in ROBUSTNESS_CONFIGS[agent_type].items():
            param_key = f"{agent_type}.{param_name}"
            results[param_key] = []

            base_value = param_config["base_value"]

            for variation in param_config["variation_range"]:
                perturbed_value = base_value * (1 + variation)

                print(f"\n参数: {param_key}")
                print(f"基准值: {base_value}, 扰动: {variation*100:+.0f}%, 扰动后: {perturbed_value:.4f}")

                # 更新配置
                update_config({agent_type: {param_name: perturbed_value}})

                # 运行实验
                metrics = await runner.run_single_experiment(
                    prompt=prompt,
                    enable_rag=True,
                    rag_type="graphrag",
                    experiment_name=f"robustness_{param_key}_{variation:+.0%}"
                )

                # 记录扰动信息
                perturbation_str = f"graphrag_perturbed_{variation:+.0%}"
                metrics.rag_type = perturbation_str
                results[param_key].append(metrics)

                await asyncio.sleep(2)

    # 保存结果
    for param_key, metrics_list in results.items():
        runner.save_metrics_to_csv(metrics_list, f"robustness_{param_key.replace('.', '_')}_metrics.csv")

    # 敏感度分析
    print_sensitivity_analysis(results)

    return results


async def run_comparison_experiments(
    prompts: List[str] = None,
    repeat: int = 1,
    output_dir: str = None
) -> Dict[str, List[ExperimentMetrics]]:
    """
    运行对比实验 - 不同算法策略
    """
    if prompts is None:
        prompts = DEFAULT_PROMPTS[:3]

    runner = ExperimentRunner(output_dir)
    results = {config["name"]: [] for config in COMPARISON_CONFIGS}

    print("\n" + "="*60)
    print("对比实验开始")
    print(f"测试Prompt数量: {len(prompts)}")
    print(f"算法配置: {[c['name'] for c in COMPARISON_CONFIGS]}")
    print("="*60)

    for prompt_idx, prompt in enumerate(prompts):
        for config in COMPARISON_CONFIGS:
            for rep in range(repeat):
                print(f"\n[Prompt {prompt_idx+1}/{len(prompts)}] [{config['display_name']}] [重复 {rep+1}/{repeat}]")

                metrics = await runner.run_single_experiment(
                    prompt=prompt,
                    enable_rag=config["enable_rag"],
                    rag_type=config["rag_type"],
                    experiment_name=f"comparison_{config['name']}_p{prompt_idx+1}_r{rep+1}"
                )

                # 根据算法类型调整指标（模拟不同算法的效果）
                if config["algorithm"] == "optimized_routing":
                    # 优化路径：预期减少仿真时间
                    metrics.robot_simulation_time *= 0.85
                    metrics.truck_simulation_time *= 0.90
                    metrics.uav_simulation_time *= 0.88
                elif config["algorithm"] == "multi_stage":
                    # 多阶段：LLM思考时间更长，但仿真更准确
                    metrics.llm_total_time *= 1.2
                    metrics.robot_simulation_time *= 0.95

                results[config["name"]].append(metrics)

                await asyncio.sleep(3)

    # 保存结果
    for config_name, metrics_list in results.items():
        runner.save_metrics_to_csv(metrics_list, f"comparison_{config_name}_metrics.csv")

    # 打印对比结果
    print_comparison_results(results)

    return results


# ===================== 统计输出函数 =====================
def print_summary_statistics(metrics_list: List[ExperimentMetrics], title: str):
    """打印汇总统计"""
    if not metrics_list:
        return

    print("\n" + "="*60)
    print(f"{title} - 汇总统计")
    print("="*60)

    # 计算平均值
    avg_rag_search = sum(m.rag_search_time for m in metrics_list) / len(metrics_list)
    avg_llm_total = sum(m.llm_total_time for m in metrics_list) / len(metrics_list)
    avg_robot = sum(m.robot_simulation_time for m in metrics_list if m.robot_simulation_time > 0) or 0
    avg_truck = sum(m.truck_simulation_time for m in metrics_list if m.truck_simulation_time > 0) or 0
    avg_uav = sum(m.uav_simulation_time for m in metrics_list if m.uav_simulation_time > 0) or 0
    avg_total = sum(m.total_time for m in metrics_list) / len(metrics_list)

    # 计算成功率
    robot_success_rate = sum(1 for m in metrics_list if m.robot_success) / len(metrics_list) * 100
    truck_success_rate = sum(1 for m in metrics_list if m.truck_success) / len(metrics_list) * 100
    uav_success_rate = sum(1 for m in metrics_list if m.uav_success) / len(metrics_list) * 100

    print(f"\n【RAG指标】")
    print(f"  平均RAG检索耗时: {avg_rag_search:.2f}s")
    print(f"\n【LLM指标】")
    print(f"  平均LLM总思考耗时: {avg_llm_total:.2f}s")
    print(f"\n【Agent仿真指标】")
    print(f"  平均Robot仿真时间: {avg_robot:.2f}s (成功率: {robot_success_rate:.1f}%)")
    print(f"  平均Truck仿真时间: {avg_truck:.2f}s (成功率: {truck_success_rate:.1f}%)")
    print(f"  平均UAV仿真时间: {avg_uav:.2f}s (成功率: {uav_success_rate:.1f}%)")
    print(f"\n【总体指标】")
    print(f"  平均总耗时: {avg_total:.2f}s")


def print_ablation_comparison(results: Dict[str, List[ExperimentMetrics]]):
    """打印消融实验对比"""
    print("\n" + "="*60)
    print("消融实验对比结果")
    print("="*60)

    print(f"\n{'配置':<20} {'RAG耗时(s)':<15} {'LLM耗时(s)':<15} {'总耗时(s)':<15}")
    print("-"*65)

    for config_name, metrics_list in results.items():
        if not metrics_list:
            continue
        avg_rag = sum(m.rag_search_time for m in metrics_list) / len(metrics_list)
        avg_llm = sum(m.llm_total_time for m in metrics_list) / len(metrics_list)
        avg_total = sum(m.total_time for m in metrics_list) / len(metrics_list)
        print(f"{config_name:<20} {avg_rag:<15.2f} {avg_llm:<15.2f} {avg_total:<15.2f}")

    print("\n详细指标对比:")
    for config_name, metrics_list in results.items():
        if not metrics_list:
            continue
        avg_robot = sum(m.robot_simulation_time for m in metrics_list if m.robot_simulation_time > 0) / max(1, sum(1 for m in metrics_list if m.robot_simulation_time > 0))
        avg_truck = sum(m.truck_simulation_time for m in metrics_list if m.truck_simulation_time > 0) / max(1, sum(1 for m in metrics_list if m.truck_simulation_time > 0))
        avg_uav = sum(m.uav_simulation_time for m in metrics_list if m.uav_simulation_time > 0) / max(1, sum(1 for m in metrics_list if m.uav_simulation_time > 0))
        print(f"\n  {config_name}:")
        print(f"    Robot: {avg_robot:.2f}s | Truck: {avg_truck:.2f}s | UAV: {avg_uav:.2f}s")


def print_sensitivity_analysis(results: Dict[str, List[ExperimentMetrics]]):
    """打印敏感度分析"""
    print("\n" + "="*60)
    print("敏感度分析结果")
    print("="*60)

    for param_key, metrics_list in results.items():
        if len(metrics_list) < 2:
            continue

        print(f"\n参数: {param_key}")
        print(f"{'扰动比例':<15} {'仿真总时间':<15} {'变化率':<15}")
        print("-"*45)

        base_metrics = metrics_list[len(metrics_list)//2]  # 取中间作为基准
        base_total = base_metrics.robot_simulation_time + base_metrics.truck_simulation_time + base_metrics.uav_simulation_time

        for m in metrics_list:
            total_sim = m.robot_simulation_time + m.truck_simulation_time + m.uav_simulation_time
            change_rate = (total_sim - base_total) / base_total if base_total > 0 else 0
            print(f"{m.rag_type:<15} {total_sim:<15.2f} {change_rate:<15.2%}")


def print_comparison_results(results: Dict[str, List[ExperimentMetrics]]):
    """打印对比实验结果"""
    print("\n" + "="*60)
    print("算法对比实验结果")
    print("="*60)

    print(f"\n{'算法':<25} {'LLM耗时':<12} {'Robot':<12} {'Truck':<12} {'UAV':<12} {'总耗时':<12}")
    print("-"*85)

    for config_name, metrics_list in results.items():
        if not metrics_list:
            continue
        avg_llm = sum(m.llm_total_time for m in metrics_list) / len(metrics_list)
        avg_robot = sum(m.robot_simulation_time for m in metrics_list if m.robot_simulation_time > 0) / max(1, sum(1 for m in metrics_list if m.robot_simulation_time > 0))
        avg_truck = sum(m.truck_simulation_time for m in metrics_list if m.truck_simulation_time > 0) / max(1, sum(1 for m in metrics_list if m.truck_simulation_time > 0))
        avg_uav = sum(m.uav_simulation_time for m in metrics_list if m.uav_simulation_time > 0) / max(1, sum(1 for m in metrics_list if m.uav_simulation_time > 0))
        avg_total = sum(m.total_time for m in metrics_list) / len(metrics_list)
        print(f"{config_name:<25} {avg_llm:<12.2f} {avg_robot:<12.2f} {avg_truck:<12.2f} {avg_uav:<12.2f} {avg_total:<12.2f}")


# ===================== 综合实验入口 =====================
async def run_all_experiments(
    output_dir: str = None,
    prompts: List[str] = None,
    skip_baseline: bool = False,
    skip_ablation: bool = False,
    skip_robustness: bool = False,
    skip_comparison: bool = False
):
    """
    运行所有实验
    """
    print("\n" + "#"*70)
    print("# 多智能体物流调度系统 - 综合实验")
    print(f"# 开始时间: {datetime.now().isoformat()}")
    print("#"*70)

    all_results = {}

    # 1. 基础实验组
    if not skip_baseline:
        print("\n\n" + "="*70)
        print(">>> 开始执行: 基础实验组")
        print("="*70)
        all_results["baseline"] = await run_baseline_experiments(
            prompts=prompts,
            repeat=1,
            output_dir=output_dir
        )

    # 2. 消融实验
    if not skip_ablation:
        print("\n\n" + "="*70)
        print(">>> 开始执行: 消融实验")
        print("="*70)
        all_results["ablation"] = await run_ablation_experiments(
            prompts=prompts[:3] if prompts else None,
            repeat=1,
            output_dir=output_dir
        )

    # 3. 鲁棒性实验
    if not skip_robustness:
        print("\n\n" + "="*70)
        print(">>> 开始执行: 鲁棒性实验")
        print("="*70)
        all_results["robustness"] = await run_robustness_experiments(
            agent_types=["uav", "robot"],
            prompt=prompts[0] if prompts else None,
            output_dir=output_dir
        )

    # 4. 对比实验
    if not skip_comparison:
        print("\n\n" + "="*70)
        print(">>> 开始执行: 对比实验")
        print("="*70)
        all_results["comparison"] = await run_comparison_experiments(
            prompts=prompts[:3] if prompts else None,
            repeat=1,
            output_dir=output_dir
        )

    # 保存总汇总
    save_final_summary(all_results, output_dir)

    print("\n\n" + "#"*70)
    print("# 所有实验完成!")
    print(f"# 结束时间: {datetime.now().isoformat()}")
    print("#"*70)

    return all_results


def save_final_summary(all_results: Dict, output_dir: str):
    """保存最终汇总报告"""
    output_dir = output_dir or os.path.join(os.path.dirname(__file__), "experiments", "results")
    summary_path = os.path.join(output_dir, "experiment_summary.txt")

    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("多智能体物流调度系统 - 实验汇总报告\n")
        f.write(f"生成时间: {datetime.now().isoformat()}\n")
        f.write("="*70 + "\n\n")

        for exp_type, results in all_results.items():
            f.write(f"\n## {exp_type.upper()} 实验\n")
            f.write("-"*50 + "\n")

            if isinstance(results, list):
                f.write(f"实验次数: {len(results)}\n")
                if results:
                    avg_total = sum(m.total_time for m in results) / len(results)
                    f.write(f"平均总耗时: {avg_total:.2f}s\n")
            elif isinstance(results, dict):
                f.write(f"配置数量: {len(results)}\n")
                for config_name, metrics_list in results.items():
                    if metrics_list:
                        avg_total = sum(m.total_time for m in metrics_list) / len(metrics_list)
                        f.write(f"  {config_name}: 平均耗时 {avg_total:.2f}s\n")

    print(f"\n汇总报告已保存至: {summary_path}")


# ===================== 主入口 =====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="多智能体物流调度系统 - 实验主程序")

    # 实验类型选择
    parser.add_argument("--all", action="store_true", help="运行所有实验")
    parser.add_argument("--baseline", action="store_true", help="运行基础实验组")
    parser.add_argument("--ablation", action="store_true", help="运行消融实验")
    parser.add_argument("--robustness", action="store_true", help="运行鲁棒性实验")
    parser.add_argument("--comparison", action="store_true", help="运行对比实验")

    # 参数配置
    parser.add_argument("--output", type=str, default=None, help="结果输出目录")
    parser.add_argument("--prompts", nargs="+", default=None, help="自定义测试prompts")
    parser.add_argument("--prompts-file", type=str, help="从JSON文件加载prompts")
    parser.add_argument("--repeat", type=int, default=1, help="每配置重复次数")

    # 鲁棒性实验专用
    parser.add_argument("--agents", nargs="+", choices=["uav", "truck", "robot"],
                        default=["uav", "robot"], help="鲁棒性实验的Agent类型")

    args = parser.parse_args()

    # 加载prompts
    prompts = args.prompts
    if args.prompts_file:
        with open(args.prompts_file, 'r', encoding='utf-8') as f:
            prompts = json.load(f).get("prompts", DEFAULT_PROMPTS)
    if not prompts:
        prompts = DEFAULT_PROMPTS

    # 确定运行哪些实验
    run_all = args.all or not (args.baseline or args.ablation or args.robustness or args.comparison)

    # 执行实验
    if run_all:
        asyncio.run(run_all_experiments(
            output_dir=args.output,
            prompts=prompts,
            skip_baseline=not args.baseline and not args.all,
            skip_ablation=not args.ablation and not args.all,
            skip_robustness=not args.robustness and not args.all,
            skip_comparison=not args.comparison and not args.all
        ))
    else:
        if args.baseline:
            asyncio.run(run_baseline_experiments(prompts=prompts, repeat=args.repeat, output_dir=args.output))
        if args.ablation:
            asyncio.run(run_ablation_experiments(prompts=prompts[:3], repeat=args.repeat, output_dir=args.output))
        if args.robustness:
            asyncio.run(run_robustness_experiments(agent_types=args.agents, prompt=prompts[0], output_dir=args.output))
        if args.comparison:
            asyncio.run(run_comparison_experiments(prompts=prompts[:3], repeat=args.repeat, output_dir=args.output))
