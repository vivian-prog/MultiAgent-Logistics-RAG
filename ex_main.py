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
import logging
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
from experiments.optimization_algorithms import (
    AntColonyDispatchOptimizer,
    GeneticDispatchOptimizer,
    Location,
    DispatchScenario,
    ResourceCandidate,
)

AGENT_SIM_PATH = os.path.join(os.path.dirname(__file__), "agentSimulation")
if AGENT_SIM_PATH not in sys.path:
    sys.path.insert(0, AGENT_SIM_PATH)




# ===================== 日志配置 =====================
class ExperimentLogger:
    """实验日志记录器，将所有print内容同时输出到控制台和文件"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 创建日志文件（带时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(output_dir, f"experiment_log_{timestamp}.txt")
        self._init_log_file()

    def _init_log_file(self):
        """初始化日志文件"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write(f"实验日志 - {datetime.now().isoformat()}\n")
            f.write("=" * 70 + "\n\n")

    def log(self, message: str):
        """记录日志（同时输出到控制台和文件）"""
        # 输出到控制台
        print(message)
        # 输出到文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(message + "\n")


# 全局日志记录器
_global_logger: Optional[ExperimentLogger] = None


def get_logger() -> ExperimentLogger:
    """获取全局日志记录器"""
    global _global_logger
    if _global_logger is None:
        # 默认输出目录
        output_dir = os.path.join(os.path.dirname(__file__), "experiments", "results")
        _global_logger = ExperimentLogger(output_dir)
    return _global_logger


def log_print(message: str):
    """统一的日志输出函数"""
    get_logger().log(message)


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
    """实验指标数据结构（时间单位统一为秒）"""
    # RAG相关指标
    rag_enabled: bool = False
    rag_type: str = ""
    rag_search_time: float = 0.0          # RAG检索耗时(秒)
    rag_query_generation_time: float = 0.0  # RAG查询生成耗时(秒)

    # LLM相关指标
    llm_total_time: float = 0.0           # LLM总思考耗时(秒)
    llm_query_gen_time: float = 0.0       # LLM生成RAG查询的耗时(秒)
    llm_command_gen_time: float = 0.0     # LLM生成指令的耗时(秒)

    # Agent仿真指标（单位统一为秒）
    robot_simulation_time: float = 0.0    # Robot仿真物理世界运行时间(秒)
    truck_simulation_time: float = 0.0    # Truck仿真物理世界运行时间(秒)
    uav_simulation_time: float = 0.0      # UAV仿真物理世界运行时间(秒，由仿真步数转换)

    # 成功标志
    robot_success: bool = False
    truck_success: bool = False
    uav_success: bool = False

    # 总耗时
    total_time: float = 0.0               # 总耗时(秒)

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
        log_print(f"RAG搜索请求出错: {e}")
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
        log_print(f"调用LLM出错: {e}")
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


def preview_text_for_log(text: str, limit: int = 240) -> str:
    """压缩 LLM 原始输出，便于日志里快速定位格式问题。"""
    normalized = (text or "").replace("\r", "\n").replace("\n", "\\n").strip()
    if not normalized:
        return "(empty)"
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def extract_destination_from_prompt(prompt: str) -> Optional[Tuple[float, float]]:
    """从 prompt 中提取最后一组经纬度，返回 (lat, lng)。"""
    matches = re.findall(r'([0-9]+\.[0-9]+)\s*,\s*([0-9]+\.[0-9]+)', prompt)
    if not matches:
        return None
    lng_str, lat_str = matches[-1]
    return float(lat_str), float(lng_str)


def build_dispatch_scenario_from_db(
    prompt: str,
    answer_dict: Dict[str, Any],
    top_k: int = 3,
) -> DispatchScenario:
    """
    基于当前项目数据库提取 GA 高层调度候选集。
    """
    robot_plan = answer_dict.get("agentrobot", {}) or {}
    uav_plan = answer_dict.get("agentuav", {}) or {}
    goods_name = robot_plan.get("goods_name", "通用货物")

    destination_coords = extract_destination_from_prompt(prompt)
    if destination_coords is None and uav_plan.get("end_lat") and uav_plan.get("end_lng"):
        destination_coords = (float(uav_plan["end_lat"]), float(uav_plan["end_lng"]))
    if destination_coords is None:
        raise ValueError("无法从 prompt 或基线计划中提取目标坐标，无法构造 GA 场景")

    destination = Location(
        id="DESTINATION",
        name="最终目的地",
        lat=destination_coords[0],
        lng=destination_coords[1],
    )

    from common.db import get_sync_db
    from common.models import WarehouseBase, WarehouseGoods, AgentBase, UavLandingPoint
    db = next(get_sync_db())
    try:
        warehouse_rows = (
            db.query(WarehouseGoods, WarehouseBase)
            .join(WarehouseBase, WarehouseGoods.warehouse_id == WarehouseBase.warehouse_id)
            .filter(WarehouseGoods.stock_quantity > 0)
            .filter(WarehouseBase.status == 1)
            .all()
        )

        filtered_warehouse_rows = [
            row for row in warehouse_rows
            if goods_name in row[0].goods_name or row[0].goods_name in goods_name
        ] or warehouse_rows

        warehouse_candidates: List[ResourceCandidate] = []
        for goods, warehouse in filtered_warehouse_rows:
            warehouse_candidates.append(
                ResourceCandidate(
                    id=str(warehouse.warehouse_id),
                    name=warehouse.warehouse_name,
                    lat=float(warehouse.location_y),
                    lng=float(warehouse.location_x),
                    resource_type="warehouse",
                    metadata={
                        "goods_name": goods.goods_name,
                        "stock_quantity": goods.stock_quantity,
                    },
                )
            )

        warehouse_candidates.sort(key=lambda item: item.as_location().distance_to(destination))
        warehouse_candidates = warehouse_candidates[:top_k]

        landing_candidates = [
            ResourceCandidate(
                id=str(point.id),
                name=point.name,
                lat=float(point.location_y),
                lng=float(point.location_x),
                resource_type="landing",
                metadata={"description": point.description},
            )
            for point in db.query(UavLandingPoint).all()
        ]
        landing_candidates.sort(key=lambda item: item.as_location().distance_to(destination))
        landing_candidates = landing_candidates[:top_k]

        warehouse_lookup: Dict[str, ResourceCandidate] = {candidate.id: candidate for candidate in warehouse_candidates}
        for _, warehouse in filtered_warehouse_rows:
            wid = str(warehouse.warehouse_id)
            if wid not in warehouse_lookup:
                warehouse_lookup[wid] = ResourceCandidate(
                    id=wid,
                    name=warehouse.warehouse_name,
                    lat=float(warehouse.location_y),
                    lng=float(warehouse.location_x),
                    resource_type="warehouse",
                )

        agent_rows = db.query(AgentBase).filter(AgentBase.status == 1).all()

        def build_agent_candidates(agent_type: int, label: str, speed_kmh: float) -> List[ResourceCandidate]:
            items: List[ResourceCandidate] = []
            for agent in agent_rows:
                if agent.agent_type != agent_type:
                    continue
                home = warehouse_lookup.get(str(agent.warehouse_id)) if agent.warehouse_id is not None else None
                lat = home.lat if home else destination.lat
                lng = home.lng if home else destination.lng
                items.append(
                    ResourceCandidate(
                        id=str(agent.agent_id),
                        name=str(agent.agent_id),
                        lat=lat,
                        lng=lng,
                        resource_type=label,
                        metadata={
                            "warehouse_id": agent.warehouse_id,
                            "max_load": float(agent.max_load),
                            "battery_capacity": agent.battery_capacity,
                            "speed_kmh": speed_kmh,
                        },
                    )
                )
            return items[:top_k]

        truck_candidates = build_agent_candidates(2, "truck", 45.0)
        uav_candidates = build_agent_candidates(1, "uav", 36.0)
        robot_candidates = build_agent_candidates(3, "robot", 3.6)

        if not warehouse_candidates or not landing_candidates or not truck_candidates or not uav_candidates or not robot_candidates:
            raise ValueError("数据库候选集不足，无法构造完整的 GA 调度场景")

        return DispatchScenario(
            goods_name=goods_name,
            destination=destination,
            warehouse_candidates=warehouse_candidates,
            landing_candidates=landing_candidates,
            truck_candidates=truck_candidates,
            uav_candidates=uav_candidates,
            robot_candidates=robot_candidates,
            source_prompt=prompt,
        )
    finally:
        db.close()


def _format_dispatch_candidate_line(candidate: ResourceCandidate) -> str:
    """格式化候选资源，供严格版 baseline 的二次 LLM 选择使用。"""
    extras: List[str] = []
    if candidate.resource_type == "warehouse":
        if candidate.metadata.get("goods_name"):
            extras.append(f"goods={candidate.metadata['goods_name']}")
        if candidate.metadata.get("stock_quantity") is not None:
            extras.append(f"stock={candidate.metadata['stock_quantity']}")
    elif candidate.resource_type in {"truck", "uav", "robot"}:
        if candidate.metadata.get("warehouse_id") is not None:
            extras.append(f"home_warehouse_id={candidate.metadata['warehouse_id']}")
        if candidate.metadata.get("max_load") is not None:
            extras.append(f"max_load={candidate.metadata['max_load']}")
        if candidate.metadata.get("battery_capacity") is not None:
            extras.append(f"battery_capacity={candidate.metadata['battery_capacity']}")

    extra_text = f", {', '.join(extras)}" if extras else ""
    return (
        f"- id={candidate.id}, name={candidate.name}, "
        f"lat={candidate.lat:.6f}, lng={candidate.lng:.6f}{extra_text}"
    )


def format_dispatch_candidates_for_llm(scenario: DispatchScenario) -> str:
    """将调度候选集序列化为紧凑文本，供 LLM 在固定候选中做选择。"""
    sections = [
        ("仓库候选", scenario.warehouse_candidates),
        ("起降点候选", scenario.landing_candidates),
        ("卡车候选", scenario.truck_candidates),
        ("无人机候选", scenario.uav_candidates),
        ("机器人候选", scenario.robot_candidates),
    ]

    lines = [
        f"货物名称: {scenario.goods_name}",
        f"最终目的地: {scenario.destination.name} ({scenario.destination.lng:.6f},{scenario.destination.lat:.6f})",
    ]
    for title, candidates in sections:
        lines.append(f"{title}:")
        lines.extend(_format_dispatch_candidate_line(candidate) for candidate in candidates)
    return "\n".join(lines)


def build_strict_baseline_selection_prompt(
    user_prompt: str,
    draft_plan: Dict[str, Any],
    scenario: DispatchScenario,
) -> str:
    """构造严格版 baseline 二阶段 LLM 选站 prompt。"""
    draft_truck = draft_plan.get("agenttruck", {}) or {}
    draft_uav = draft_plan.get("agentuav", {}) or {}
    draft_robot = draft_plan.get("agentrobot", {}) or {}
    draft_hint = {
        "goods_name": draft_robot.get("goods_name", scenario.goods_name),
        "truck_start": [draft_truck.get("start_lng"), draft_truck.get("start_lat")],
        "truck_end": [draft_truck.get("end_lng"), draft_truck.get("end_lat")],
        "uav_start": [draft_uav.get("start_lng"), draft_uav.get("start_lat")],
        "uav_end": [draft_uav.get("end_lng"), draft_uav.get("end_lat")],
        "draft_robot_id": draft_robot.get("agent_id"),
        "draft_truck_id": draft_truck.get("agent_id"),
        "draft_uav_id": draft_uav.get("agent_id"),
    }
    draft_hint_json = json.dumps(draft_hint, ensure_ascii=False, indent=2)
    candidate_summary = format_dispatch_candidates_for_llm(scenario)
    return f"""
你是多智能体物流调度系统中的资源选择器。
你只负责在固定候选集中选择资源，不要重写执行计划。

要求：
1. 只能从候选集中各选择 1 个 warehouse、1 个 landing、1 个 truck、1 个 uav、1 个 robot。
2. 所有 ID 必须与候选列表完全一致，不能发明新 ID、新名称、新坐标。
3. warehouse 必须能提供当前货物。
4. landing 必须同时满足 truck 的终点和 uav 的起点语义。
5. 只输出一个 JSON 对象，不要解释，不要 markdown，不要代码块。

用户需求：
{user_prompt}

第一阶段草案提示：
{draft_hint_json}

固定候选集：
{candidate_summary}

输出 JSON 的格式必须严格等于：
{{
  "selected_resources": {{
    "warehouse_id": "...",
    "landing_id": "...",
    "truck_id": "...",
    "uav_id": "...",
    "robot_id": "..."
  }},
  "selection_reason": "..."
}}

现在直接输出 JSON，并且第一个字符必须是 {{，最后一个字符必须是 }}。
""".strip()


def _find_candidate_by_id(
    candidates: List[ResourceCandidate],
    resource_id: Any,
    resource_label: str,
) -> ResourceCandidate:
    """按候选 ID 严格匹配，匹配失败直接报错。"""
    normalized_id = str(resource_id).strip().lower()
    for candidate in candidates:
        if candidate.id.strip().lower() == normalized_id:
            return candidate
    raise ValueError(f"LLM选择的{resource_label}不在候选集中: {resource_id}")


def build_strict_baseline_plan_from_selection(
    selection_dict: Dict[str, Any],
    scenario: DispatchScenario,
    draft_plan: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """将 LLM 的严格选站结果物化为可执行 plan，并返回统一的选择结果元数据。"""
    selected_resources = selection_dict.get("selected_resources") or selection_dict

    warehouse = _find_candidate_by_id(
        scenario.warehouse_candidates,
        selected_resources.get("warehouse_id"),
        "仓库",
    )
    landing = _find_candidate_by_id(
        scenario.landing_candidates,
        selected_resources.get("landing_id"),
        "起降点",
    )
    truck = _find_candidate_by_id(
        scenario.truck_candidates,
        selected_resources.get("truck_id"),
        "卡车",
    )
    uav = _find_candidate_by_id(
        scenario.uav_candidates,
        selected_resources.get("uav_id"),
        "无人机",
    )
    robot = _find_candidate_by_id(
        scenario.robot_candidates,
        selected_resources.get("robot_id"),
        "机器人",
    )

    draft_truck = copy.deepcopy(draft_plan.get("agenttruck", {}) or {})
    draft_uav = copy.deepcopy(draft_plan.get("agentuav", {}) or {})
    draft_robot = copy.deepcopy(draft_plan.get("agentrobot", {}) or {})

    strict_plan = {
        "agenttruck": {
            "type": "TRUCK",
            "tasks": [f"从{warehouse.name}运输到{landing.name}"],
            "start_location": warehouse.name,
            "end_location": landing.name,
            "start_lat": warehouse.lat,
            "start_lng": warehouse.lng,
            "end_lat": landing.lat,
            "end_lng": landing.lng,
            "agent_id": truck.id,
            "truck_params": draft_truck.get("truck_params", {"load_weight": 5.0, "base_fuel": 30}),
        },
        "agentuav": {
            "type": "UAV",
            "tasks": [f"从{landing.name}接驳配送到最终目的地"],
            "Map_name": draft_uav.get("Map_name", "Map1"),
            "max_steps": draft_uav.get("max_steps", 1000),
            "start_lat": landing.lat,
            "start_lng": landing.lng,
            "end_lat": scenario.destination.lat,
            "end_lng": scenario.destination.lng,
            "agent_id": uav.id,
        },
        "agentrobot": {
            "type": "ROBOTS",
            "tasks": [f"在{warehouse.name}内分拣并交接{scenario.goods_name}"],
            "agent_id": robot.id,
            "goods_name": draft_robot.get("goods_name", scenario.goods_name),
        },
        "instruction_summary": (
            selection_dict.get("selection_reason")
            or f"LLM严格选择 {warehouse.name} -> {landing.name}，分配 {robot.id} / {truck.id} / {uav.id}"
        ),
    }

    selection_metadata = {
        "warehouse": {"id": warehouse.id, "name": warehouse.name, "lat": warehouse.lat, "lng": warehouse.lng},
        "landing": {"id": landing.id, "name": landing.name, "lat": landing.lat, "lng": landing.lng},
        "truck": {"id": truck.id, "name": truck.name, "lat": truck.lat, "lng": truck.lng},
        "uav": {"id": uav.id, "name": uav.name, "lat": uav.lat, "lng": uav.lng},
        "robot": {"id": robot.id, "name": robot.name, "lat": robot.lat, "lng": robot.lng},
    }
    return strict_plan, selection_metadata


def select_strict_baseline_plan_with_llm(
    user_prompt: str,
    draft_plan: Dict[str, Any],
    scenario: DispatchScenario,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], float]:
    """让 LLM 在固定候选集内做严格资源选择，并返回可执行 plan。"""
    selection_prompt = build_strict_baseline_selection_prompt(
        user_prompt=user_prompt,
        draft_plan=draft_plan,
        scenario=scenario,
    )
    selection_answer, selection_time = call_llm_model(selection_prompt, "", 0.0)
    try:
        selection_dict = extract_and_parse_last_json(selection_answer)
    except ValueError:
        first_preview = preview_text_for_log(selection_answer)
        log_print(f"严格资源选择首轮输出不可解析，准备重试。预览: {first_preview}")
        retry_prompt = (
            selection_prompt
            + "\n\n上一次回答如下：\n"
            + (selection_answer or "(empty)")
            + "\n\n请删除上一次回答中的所有解释性文字，只保留一个合法 JSON 对象重新输出。"
            + "\n再次强调：不要 markdown，不要代码块，不要额外句子。"
        )
        retry_answer, retry_time = call_llm_model(retry_prompt, "", 0.0)
        selection_time += retry_time
        try:
            selection_dict = extract_and_parse_last_json(retry_answer)
        except ValueError as retry_error:
            retry_preview = preview_text_for_log(retry_answer)
            raise ValueError(
                "严格资源选择未返回可解析JSON，"
                f"首轮输出预览: {first_preview}，"
                f"重试输出预览: {retry_preview}"
            ) from retry_error
    strict_plan, selection_metadata = build_strict_baseline_plan_from_selection(
        selection_dict=selection_dict,
        scenario=scenario,
        draft_plan=draft_plan,
    )
    return strict_plan, selection_metadata, selection_time


def build_ga_agent_plan(
    opt_result,
    scenario: DispatchScenario,
    baseline_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """把 GA 结果转换成与当前项目兼容的 agent 参数 JSON。"""
    meta = opt_result.metadata
    warehouse = meta["warehouse"]
    landing = meta["landing"]
    truck = meta["truck"]
    uav = meta["uav"]
    robot = meta["robot"]

    base_truck = copy.deepcopy(baseline_plan.get("agenttruck", {}) or {})
    base_uav = copy.deepcopy(baseline_plan.get("agentuav", {}) or {})

    return {
        "agenttruck": {
            "type": "TRUCK",
            "tasks": [f"从{warehouse['name']}运输到{landing['name']}"],
            "start_location": warehouse["name"],
            "end_location": landing["name"],
            "start_lat": warehouse["lat"],
            "start_lng": warehouse["lng"],
            "end_lat": landing["lat"],
            "end_lng": landing["lng"],
            "agent_id": truck["id"],
            "truck_params": base_truck.get("truck_params", {"load_weight": 5.0, "base_fuel": 30}),
        },
        "agentuav": {
            "type": "UAV",
            "tasks": [f"从{landing['name']}接驳配送到最终目的地"],
            "Map_name": base_uav.get("Map_name", "Map1"),
            "max_steps": base_uav.get("max_steps", 1000),
            "start_lat": landing["lat"],
            "start_lng": landing["lng"],
            "end_lat": scenario.destination.lat,
            "end_lng": scenario.destination.lng,
            "agent_id": uav["id"],
        },
        "agentrobot": {
            "type": "ROBOTS",
            "tasks": [f"在{warehouse['name']}内分拣并交接{scenario.goods_name}"],
            "agent_id": robot["id"],
            "goods_name": scenario.goods_name,
        },
        "instruction_summary": f"GA选择 {warehouse['name']} -> {landing['name']} 并分配 {robot['id']} / {truck['id']} / {uav['id']}",
    }


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

    def __init__(self, output_dir: str = None, overwrite: bool = False):
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "experiments", "results")
        self.overwrite = overwrite
        os.makedirs(self.output_dir, exist_ok=True)
        self.recorder = ExperimentRecorder(self.output_dir)

    def generate_instruction_plan(
        self,
        prompt: str,
        enable_rag: bool = True,
        rag_type: str = "graphrag",
    ) -> Tuple[ExperimentMetrics, Dict[str, Any]]:
        """
        仅生成 RAG / LLM 指令，不执行仿真。
        供 comparison 实验复用，用于把 GA 接入当前主链路。
        """
        metrics = ExperimentMetrics()
        metrics.rag_enabled = enable_rag
        metrics.rag_type = rag_type if enable_rag else "none"

        rag_context = ""
        if enable_rag:
            rag_query_prompt = RAG_SYSTEM_PROMPT.format(user_prompt=prompt)
            rag_query, query_gen_time = call_llm_model(rag_query_prompt, '', 0.7)
            metrics.llm_query_gen_time = query_gen_time
            metrics.rag_query_generation_time = query_gen_time

            rag_query_list = rag_query.split()
            rag_query = " ".join(rag_query_list)
            log_print(f"RAG查询关键词: {rag_query[:100]}...")

            rag_context, rag_search_time = rag_search(rag_query, RAG_MODEL_FULL, 0.7, rag_type)
            metrics.rag_search_time = rag_search_time

            log_print(f"RAG检索耗时: {rag_search_time:.2f}s")
            log_print(f"RAG查询生成耗时: {query_gen_time:.2f}s")

        cloudllm_prompt = CLOUDLLM_SYSTEM_PROMPT.format(user_prompt=prompt)
        final_answer, command_gen_time = call_llm_model(cloudllm_prompt, rag_context, 0.7)
        metrics.llm_command_gen_time = command_gen_time
        metrics.llm_total_time = metrics.llm_query_gen_time + command_gen_time

        log_print(f"LLM指令生成耗时: {command_gen_time:.2f}s")
        log_print(f"LLM总思考耗时: {metrics.llm_total_time:.2f}s")

        answer_dict = extract_and_parse_last_json(final_answer)
        log_print(f"解析指令成功: {list(answer_dict.keys())}")
        return metrics, answer_dict

    async def execute_agent_plan(
        self,
        answer_dict: Dict[str, Any],
        metrics: ExperimentMetrics,
    ) -> None:
        """执行已经生成好的 agent 任务计划，并把结果写回 metrics。"""
        agentuav_params = copy.deepcopy(answer_dict.get("agentuav", {}) or {})
        agenttruck_params = copy.deepcopy(answer_dict.get("agenttruck", {}) or {})
        agentrobot_params = copy.deepcopy(answer_dict.get("agentrobot", {}) or {})

        async with httpx.AsyncClient(timeout=60.0) as client:
            if agentrobot_params:
                t_start = time.time()
                try:
                    resp = await client.post(AGENT_API_MAP["agentrobot"], json=agentrobot_params)
                    resp.raise_for_status()
                    task_id = resp.json()["task_id"]
                    result = await poll_task(client, task_id, "agentrobot")
                    sim_time = (time.time() - t_start) * 10.0
                    metrics.robot_simulation_time = sim_time
                    metrics.robot_success = result is not None
                    log_print(f"Robot仿真时间: {sim_time:.2f}s (成功: {metrics.robot_success})")
                except Exception as e:
                    log_print(f"Robot任务异常: {e}")
                    metrics.robot_simulation_time = -1

            if agenttruck_params:
                t_start = time.time()
                try:
                    if "end_lat" not in agenttruck_params and agentuav_params.get("start_lat"):
                        agenttruck_params["end_lat"] = agentuav_params["start_lat"]
                        agenttruck_params["end_lng"] = agentuav_params["start_lng"]

                    resp = await client.post(AGENT_API_MAP["agenttruck"], json=agenttruck_params)
                    resp.raise_for_status()
                    task_id = resp.json()["task_id"]
                    result = await poll_task(client, task_id, "agenttruck")

                    sim_data = result.get("simulation_data", result) if result else {}
                    if sim_data and "total_time" in sim_data:
                        sim_time = float(sim_data["total_time"]) * 3600
                    else:
                        sim_time = time.time() - t_start

                    metrics.truck_simulation_time = sim_time
                    metrics.truck_success = result is not None
                    log_print(f"Truck仿真时间: {sim_time:.2f}s (成功: {metrics.truck_success})")
                except Exception as e:
                    log_print(f"Truck任务异常: {e}")
                    metrics.truck_simulation_time = -1

            if agentuav_params:
                t_start = time.time()
                try:
                    resp = await client.post(AGENT_API_MAP["agentuav_submit"], json=agentuav_params)
                    resp.raise_for_status()
                    task_id = resp.json()["task_id"]
                    result = await poll_task(client, task_id, "agentuav")

                    if result:
                        sim_data = result.get("simulation_data", result)
                        sim_time = float(sim_data.get("total_time_seconds", sim_data.get("total_steps", 0.0)))
                    else:
                        sim_time = time.time() - t_start

                    metrics.uav_simulation_time = sim_time
                    metrics.uav_success = result is not None
                    log_print(f"UAV仿真时间: {sim_time:.2f}s (成功: {metrics.uav_success})")
                except Exception as e:
                    log_print(f"UAV任务异常: {e}")
                    metrics.uav_simulation_time = -1

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

        log_print(f"\n{'='*60}")
        log_print(f"实验: {experiment_name}")
        log_print(f"RAG模式: {'启用 (' + rag_type + ')' if enable_rag else '禁用'}")
        log_print(f"Prompt: {prompt[:50]}...")
        log_print(f"{'='*60}")

        try:
            plan_metrics, answer_dict = self.generate_instruction_plan(
                prompt=prompt,
                enable_rag=enable_rag,
                rag_type=rag_type,
            )
            metrics = plan_metrics
        except ValueError as e:
            log_print(f"JSON解析失败: {e}")
            metrics.total_time = time.time() - total_start
            return metrics

        await self.execute_agent_plan(answer_dict, metrics)

        metrics.total_time = time.time() - total_start
        log_print(f"\n总耗时: {metrics.total_time:.2f}s")

        return metrics

    def save_metrics_to_csv(self, metrics_list: List[ExperimentMetrics], filename: str, overwrite: bool = None):
        """保存指标到CSV（字段名包含单位）"""
        filepath = os.path.join(self.output_dir, filename)

        # 使用实例级别的overwrite设置（如果参数未指定）
        use_overwrite = overwrite if overwrite is not None else self.overwrite

        # 字段名包含单位说明
        fieldnames = [
            "rag_enabled",
            "rag_type",
            "rag_search_time_s",           # RAG检索耗时(秒)
            "rag_query_generation_time_s", # RAG查询生成耗时(秒)
            "llm_total_time_s",            # LLM总思考耗时(秒)
            "llm_query_gen_time_s",        # LLM生成RAG查询耗时(秒)
            "llm_command_gen_time_s",      # LLM生成指令耗时(秒)
            "robot_simulation_time_s",     # Robot仿真时间(秒)
            "truck_simulation_time_s",     # Truck仿真时间(秒)
            "uav_simulation_time_s",       # UAV仿真时间(秒)
            "robot_success",
            "truck_success",
            "uav_success",
            "total_time_s"                 # 总耗时(秒)
        ]

        # 根据overwrite设置决定写入模式
        write_header = use_overwrite or not os.path.exists(filepath)
        mode = 'w' if use_overwrite else 'a'

        with open(filepath, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            for m in metrics_list:
                # 转换字段名以匹配新格式
                row = {
                    "rag_enabled": m.rag_enabled,
                    "rag_type": m.rag_type,
                    "rag_search_time_s": m.rag_search_time,
                    "rag_query_generation_time_s": m.rag_query_generation_time,
                    "llm_total_time_s": m.llm_total_time,
                    "llm_query_gen_time_s": m.llm_query_gen_time,
                    "llm_command_gen_time_s": m.llm_command_gen_time,
                    "robot_simulation_time_s": m.robot_simulation_time,
                    "truck_simulation_time_s": m.truck_simulation_time,
                    "uav_simulation_time_s": m.uav_simulation_time,
                    "robot_success": m.robot_success,
                    "truck_success": m.truck_success,
                    "uav_success": m.uav_success,
                    "total_time_s": m.total_time
                }
                writer.writerow(row)

        log_print(f"指标已保存至: {filepath}")
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
        "algorithm": "standard",
        "algorithm_params": {
            "candidate_top_k": 3
        }
    },
    {
        "name": "ACO",
        "display_name": "蚁群算法 (Ant Colony Optimization)",
        "enable_rag": True,
        "rag_type": "graphrag",
        "algorithm": "ACO",
        "algorithm_params": {
            "candidate_top_k": 3,
            "num_ants": 20,
            "alpha": 1.0,
            "beta": 2.0,
            "rho": 0.5,
            "max_iterations": 50
        }
    },
    {
        "name": "GA",
        "display_name": "遗传算法 (Genetic Algorithm)",
        "enable_rag": True,
        "rag_type": "graphrag",
        "algorithm": "GA",
        "algorithm_params": {
            "candidate_top_k": 3,
            "population_size": 50,
            "crossover_rate": 0.8,
            "mutation_rate": 0.1,
            "elite_size": 5,
            "max_iterations": 50
        }
    }
]

# ===================== 默认测试数据 =====================
# 基于GraphRag/input目录下的真实数据构造的运送任务
DEFAULT_PROMPTS = [

    # 任务4: 多Agent协同任务 - 仓储机器人分拣+卡车运输
    # "请协调仓储机器人和卡车，将数据传输线从仓库分拣后运往深圳福田区购物公园（114.054706,22.534678）",

    # 任务5: 三Agent协同任务 - Robot抓取+Truck运输+UAV配送
    # 场景：干粉灭火器(1.2kg)从深圳文锦仓库出发，卡车运至光明城站起降点，无人机完成最后配送
    # 数据依据：WARE-003(18kg载重,待命)、GROUND-002(60kg载重,待命)、UAV-001(5kg载重,待命)
    # 流程：Robot从货架抓取干粉灭火器 → Truck运至光明城站起降点 → UAV配送到光明区人民医院
    "请协调仓储机器人、卡车和无人机完成干粉灭火器的多阶段配送任务：从深圳福田区购物公园（114.054706,22.534678）配送到深圳光明区深理工大学医院(113.928589,22.769395)"
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

    log_print("\n" + "="*60)
    log_print("基础实验组开始")
    log_print(f"测试Prompt数量: {len(prompts)}")
    log_print(f"每Prompt重复次数: {repeat}")
    log_print("="*60)

    for prompt_idx, prompt in enumerate(prompts):
        for rep in range(repeat):
            log_print(f"[Prompt {prompt_idx+1}/{len(prompts)}] [重复 {rep+1}/{repeat}]")

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

    log_print("\n" + "="*60)
    log_print("消融实验开始")
    log_print(f"测试Prompt数量: {len(prompts)}")
    log_print(f"实验配置: {[c['name'] for c in ABLATION_CONFIGS]}")
    log_print("="*60)

    for prompt_idx, prompt in enumerate(prompts):
        for config in ABLATION_CONFIGS:
            for rep in range(repeat):
                log_print(f"\n[Prompt {prompt_idx+1}/{len(prompts)}] [{config['display_name']}] [重复 {rep+1}/{repeat}]")

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

    log_print("\n" + "="*60)
    log_print("鲁棒性实验开始")
    log_print(f"测试Agent类型: {agent_types}")
    log_print("="*60)

    for agent_type in agent_types:
        if agent_type not in ROBUSTNESS_CONFIGS:
            continue

        for param_name, param_config in ROBUSTNESS_CONFIGS[agent_type].items():
            param_key = f"{agent_type}.{param_name}"
            results[param_key] = []

            base_value = param_config["base_value"]

            for variation in param_config["variation_range"]:
                perturbed_value = base_value * (1 + variation)

                log_print(f"\n参数: {param_key}")
                log_print(f"基准值: {base_value}, 扰动: {variation*100:+.0f}%, 扰动后: {perturbed_value:.4f}")

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
    包含基线方案、蚁群算法(ACO)、遗传算法(GA)
    """
    if prompts is None:
        prompts = DEFAULT_PROMPTS[:3]

    runner = ExperimentRunner(output_dir)
    results = {config["name"]: [] for config in COMPARISON_CONFIGS}

    log_print("\n" + "="*60)
    log_print("对比实验开始")
    log_print(f"测试Prompt数量: {len(prompts)}")
    log_print(f"算法配置: {[c['name'] for c in COMPARISON_CONFIGS]}")
    log_print("="*60)

    for prompt_idx, prompt in enumerate(prompts):
        for config in COMPARISON_CONFIGS:
            for rep in range(repeat):
                log_print(f"\n[Prompt {prompt_idx+1}/{len(prompts)}] [{config['display_name']}] [重复 {rep+1}/{repeat}]")

                algorithm = config.get("algorithm", "baseline")
                experiment_name = f"comparison_{config['name']}_p{prompt_idx+1}_r{rep+1}"

                if algorithm == "standard":
                    total_start = time.time()
                    algo_params = config.get("algorithm_params", {})
                    candidate_top_k = int(algo_params.get("candidate_top_k", 3))
                    metrics = ExperimentMetrics(
                        rag_enabled=config["enable_rag"],
                        rag_type=config["rag_type"] if config["enable_rag"] else "none",
                    )
                    log_print(f"\n{'='*60}")
                    log_print(f"实验: {experiment_name}")
                    log_print(f"RAG模式: {'启用 (' + config['rag_type'] + ')' if config['enable_rag'] else '禁用'}")
                    log_print(f"Prompt: {prompt[:50]}...")
                    log_print(f"{'='*60}")

                    try:
                        metrics, draft_plan = runner.generate_instruction_plan(
                            prompt=prompt,
                            enable_rag=config["enable_rag"],
                            rag_type=config["rag_type"],
                        )

                        scenario = build_dispatch_scenario_from_db(
                            prompt=prompt,
                            answer_dict=draft_plan,
                            top_k=candidate_top_k,
                        )
                        strict_plan, strict_selection, selection_time = select_strict_baseline_plan_with_llm(
                            user_prompt=prompt,
                            draft_plan=draft_plan,
                            scenario=scenario,
                        )

                        metrics.llm_command_gen_time += selection_time
                        metrics.llm_total_time += selection_time
                        log_print(f"LLM严格资源选择耗时: {selection_time:.2f}s")
                        log_print(f"LLM更新后总思考耗时: {metrics.llm_total_time:.2f}s")
                        log_print(
                            "    baseline选择结果: "
                            f"warehouse={strict_selection['warehouse']['name']}, "
                            f"landing={strict_selection['landing']['name']}, "
                            f"truck={strict_selection['truck']['name']}, "
                            f"uav={strict_selection['uav']['name']}, "
                            f"robot={strict_selection['robot']['name']}"
                        )

                        await runner.execute_agent_plan(strict_plan, metrics)
                        metrics.total_time = time.time() - total_start
                    except Exception as e:
                        log_print(f"基线实验执行失败: {e}")
                        metrics.rag_enabled = config["enable_rag"]
                        metrics.rag_type = f"{config['rag_type']}_baseline_failed"
                        metrics.total_time = time.time() - total_start

                # ================= 2. 传统启发式算法 (ACO / GA) =================
                elif algorithm in ["ACO", "GA"]:
                    total_start = time.time()
                    algo_params = config.get("algorithm_params", {})
                    candidate_top_k = int(algo_params.get("candidate_top_k", 3))

                    log_print(f"\n>>> 运行 {algorithm} 高层调度优化...")

                    try:
                        metrics, baseline_plan = runner.generate_instruction_plan(
                            prompt=prompt,
                            enable_rag=config["enable_rag"],
                            rag_type=config["rag_type"],
                        )

                        scenario = build_dispatch_scenario_from_db(
                            prompt=prompt,
                            answer_dict=baseline_plan,
                            top_k=candidate_top_k,
                        )

                        if algorithm == "GA":
                            optimizer = GeneticDispatchOptimizer(
                                population_size=int(algo_params.get("population_size", 50)),
                                generations=int(algo_params.get("max_iterations", 50)),
                                crossover_rate=float(algo_params.get("crossover_rate", 0.8)),
                                mutation_rate=float(algo_params.get("mutation_rate", 0.1)),
                                elite_size=int(algo_params.get("elite_size", 5)),
                                tournament_size=int(algo_params.get("tournament_size", 3)),
                                random_seed=42,
                            )
                            opt_result = optimizer.optimize_dispatch(scenario)
                            dispatch_tag = "ga_dispatch"
                        else:
                            optimizer = AntColonyDispatchOptimizer(
                                num_ants=int(algo_params.get("num_ants", 20)),
                                iterations=int(algo_params.get("max_iterations", 50)),
                                alpha=float(algo_params.get("alpha", 1.0)),
                                beta=float(algo_params.get("beta", 2.0)),
                                rho=float(algo_params.get("rho", 0.5)),
                                q=float(algo_params.get("q", 100.0)),
                                random_seed=42,
                            )
                            opt_result = optimizer.optimize_dispatch(scenario)
                            dispatch_tag = "aco_dispatch"

                        opt_plan = build_ga_agent_plan(opt_result, scenario, baseline_plan)

                        log_print(
                            f"    {algorithm}选择结果: "
                            f"warehouse={opt_result.metadata['warehouse']['name']}, "
                            f"landing={opt_result.metadata['landing']['name']}, "
                            f"truck={opt_result.metadata['truck']['name']}, "
                            f"uav={opt_result.metadata['uav']['name']}, "
                            f"robot={opt_result.metadata['robot']['name']}"
                        )
                        log_print(f"    {algorithm}估计总代价: {opt_result.best_time:.2f}s")
                        log_print(f"    {algorithm}改进比例: {opt_result.improvement_ratio:.2%}")

                        metrics.llm_command_gen_time = 0.0
                        metrics.llm_total_time = metrics.llm_query_gen_time
                        metrics.rag_type = f"{config['rag_type']}_{dispatch_tag}"

                        await runner.execute_agent_plan(opt_plan, metrics)
                        metrics.total_time = time.time() - total_start
                    except Exception as e:
                        log_print(f"{algorithm}对比实验执行失败: {e}")
                        metrics = ExperimentMetrics(
                            rag_enabled=config["enable_rag"],
                            rag_type=f"{config['rag_type']}_{algorithm.lower()}_dispatch_failed",
                            total_time=time.time() - total_start,
                        )

                results[config["name"]].append(metrics)

                await asyncio.sleep(2)

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

    log_print("\n" + "="*70)
    log_print(f"{title} - 汇总统计")
    log_print("="*70)

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

    log_print(f"\n【RAG指标】")
    log_print(f"  平均RAG检索耗时: {avg_rag_search:.2f}s")
    log_print(f"\n【LLM指标】")
    log_print(f"  平均LLM总思考耗时: {avg_llm_total:.2f}s")
    log_print(f"\n【Agent仿真指标】")
    log_print(f"  平均Robot仿真时间: {avg_robot:.2f}s (成功率: {robot_success_rate:.1f}%)")
    log_print(f"  平均Truck仿真时间: {avg_truck:.2f}s (成功率: {truck_success_rate:.1f}%)")
    log_print(f"  平均UAV仿真时间: {avg_uav:.2f}s (成功率: {uav_success_rate:.1f}%)")
    log_print(f"\n【总体指标】")
    log_print(f"  平均总耗时: {avg_total:.2f}s")


def print_ablation_comparison(results: Dict[str, List[ExperimentMetrics]]):
    """打印消融实验对比"""
    log_print("\n" + "="*80)
    log_print("消融实验对比结果")
    log_print("="*80)

    log_print(f"\n{'配置':<20} {'RAG耗时(s)':<15} {'LLM耗时(s)':<15} {'总耗时(s)':<15}")
    log_print("-"*70)

    for config_name, metrics_list in results.items():
        if not metrics_list:
            continue
        avg_rag = sum(m.rag_search_time for m in metrics_list) / len(metrics_list)
        avg_llm = sum(m.llm_total_time for m in metrics_list) / len(metrics_list)
        avg_total = sum(m.total_time for m in metrics_list) / len(metrics_list)
        log_print(f"{config_name:<20} {avg_rag:<15.2f} {avg_llm:<15.2f} {avg_total:<15.2f}")

    log_print("\n详细仿真指标对比:")
    log_print(f"  {'配置':<20} {'Robot(s)':<12} {'Truck(s)':<12} {'UAV(s)':<12}")
    log_print("  " + "-"*58)
    for config_name, metrics_list in results.items():
        if not metrics_list:
            continue
        robot_count = sum(1 for m in metrics_list if m.robot_simulation_time > 0)
        truck_count = sum(1 for m in metrics_list if m.truck_simulation_time > 0)
        uav_count = sum(1 for m in metrics_list if m.uav_simulation_time > 0)
        avg_robot = sum(m.robot_simulation_time for m in metrics_list if m.robot_simulation_time > 0) / max(1, robot_count)
        avg_truck = sum(m.truck_simulation_time for m in metrics_list if m.truck_simulation_time > 0) / max(1, truck_count)
        avg_uav = sum(m.uav_simulation_time for m in metrics_list if m.uav_simulation_time > 0) / max(1, uav_count)
        log_print(f"  {config_name:<20} {avg_robot:<12.2f} {avg_truck:<12.2f} {avg_uav:<12.2f}")


def print_sensitivity_analysis(results: Dict[str, List[ExperimentMetrics]]):
    """打印敏感度分析"""
    log_print("\n" + "="*70)
    log_print("敏感度分析结果")
    log_print("="*70)

    for param_key, metrics_list in results.items():
        if len(metrics_list) < 2:
            continue

        log_print(f"\n参数: {param_key}")
        log_print(f"{'扰动比例':<15} {'仿真总时间(s)':<18} {'变化率':<15}")
        log_print("-"*50)

        base_metrics = metrics_list[len(metrics_list)//2]  # 取中间作为基准
        base_total = base_metrics.robot_simulation_time + base_metrics.truck_simulation_time + base_metrics.uav_simulation_time

        for m in metrics_list:
            total_sim = m.robot_simulation_time + m.truck_simulation_time + m.uav_simulation_time
            change_rate = (total_sim - base_total) / base_total if base_total > 0 else 0
            log_print(f"{m.rag_type:<15} {total_sim:<18.2f} {change_rate:<15.2%}")


def print_comparison_results(results: Dict[str, List[ExperimentMetrics]]):
    """打印对比实验结果"""
    log_print("\n" + "="*90)
    log_print("算法对比实验结果")
    log_print("="*90)

    log_print(f"\n{'算法':<25} {'LLM耗时(s)':<12} {'Robot(s)':<12} {'Truck(s)':<12} {'UAV(s)':<12} {'总耗时(s)':<12}")
    log_print("-"*90)

    success_summaries = []
    for config_name, metrics_list in results.items():
        if not metrics_list:
            continue
        avg_llm = sum(m.llm_total_time for m in metrics_list) / len(metrics_list)
        robot_count = sum(1 for m in metrics_list if m.robot_simulation_time > 0)
        truck_count = sum(1 for m in metrics_list if m.truck_simulation_time > 0)
        uav_count = sum(1 for m in metrics_list if m.uav_simulation_time > 0)
        avg_robot = sum(m.robot_simulation_time for m in metrics_list if m.robot_simulation_time > 0) / max(1, robot_count)
        avg_truck = sum(m.truck_simulation_time for m in metrics_list if m.truck_simulation_time > 0) / max(1, truck_count)
        avg_uav = sum(m.uav_simulation_time for m in metrics_list if m.uav_simulation_time > 0) / max(1, uav_count)
        avg_total = sum(m.total_time for m in metrics_list) / len(metrics_list)
        robot_success_rate = sum(1 for m in metrics_list if m.robot_success) / len(metrics_list) * 100
        truck_success_rate = sum(1 for m in metrics_list if m.truck_success) / len(metrics_list) * 100
        uav_success_rate = sum(1 for m in metrics_list if m.uav_success) / len(metrics_list) * 100
        success_summaries.append(
            f"  {config_name}: Robot {robot_success_rate:.0f}%, Truck {truck_success_rate:.0f}%, UAV {uav_success_rate:.0f}%"
        )
        log_print(f"{config_name:<25} {avg_llm:<12.2f} {avg_robot:<12.2f} {avg_truck:<12.2f} {avg_uav:<12.2f} {avg_total:<12.2f}")

    log_print("\n指标说明:")
    log_print("  1. LLM耗时: baseline 显示 LLM 总思考时间；ACO/GA 当前仅保留任务解析与查询生成时间，不包含被传统算法替代的高层调度生成时间。")
    log_print("  2. Robot/Truck/UAV: 这三列是各智能体仿真执行时间，口径偏向业务/仿真时间，不是纯程序墙钟时间。")
    log_print("  3. 总耗时: 端到端真实耗时，包含 RAG、LLM、ACO/GA 优化、接口请求、轮询等待和仿真执行，因此不等于前面几列直接相加。")
    log_print("  4. 若某个 Agent 成功标记为 False，该行时间通常包含失败前的等待或超时，不能直接当成有效完成时间解读。")

    log_print("\n成功率摘要:")
    for line in success_summaries:
        log_print(line)


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
    log_print("\n" + "#"*70)
    log_print("# 多智能体物流调度系统 - 综合实验")
    log_print(f"# 开始时间: {datetime.now().isoformat()}")
    log_print("#"*70)

    all_results = {}

    # 1. 基础实验组
    if not skip_baseline:
        log_print("\n\n" + "="*70)
        log_print(">>> 开始执行: 基础实验组")
        log_print("="*70)
        all_results["baseline"] = await run_baseline_experiments(
            prompts=prompts,
            repeat=1,
            output_dir=output_dir
        )

    # 2. 消融实验
    if not skip_ablation:
        log_print("\n\n" + "="*70)
        log_print(">>> 开始执行: 消融实验")
        log_print("="*70)
        all_results["ablation"] = await run_ablation_experiments(
            prompts=prompts[:3] if prompts else None,
            repeat=1,
            output_dir=output_dir
        )

    # 3. 鲁棒性实验
    if not skip_robustness:
        log_print("\n\n" + "="*70)
        log_print(">>> 开始执行: 鲁棒性实验")
        log_print("="*70)
        all_results["robustness"] = await run_robustness_experiments(
            agent_types=["uav", "robot"],
            prompt=prompts[0] if prompts else None,
            output_dir=output_dir
        )

    # 4. 对比实验
    if not skip_comparison:
        log_print("\n\n" + "="*70)
        log_print(">>> 开始执行: 对比实验")
        log_print("="*70)
        all_results["comparison"] = await run_comparison_experiments(
            prompts=prompts[:3] if prompts else None,
            repeat=1,
            output_dir=output_dir
        )

    # 保存总汇总
    save_final_summary(all_results, output_dir)

    log_print("\n\n" + "#"*70)
    log_print("# 所有实验完成!")
    log_print(f"# 结束时间: {datetime.now().isoformat()}")
    log_print("#"*70)

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

    log_print(f"\n汇总报告已保存至: {summary_path}")


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
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有结果文件")

    # 鲁棒性实验专用
    parser.add_argument("--agents", nargs="+", choices=["uav", "truck", "robot"],
                        default=["uav", "robot"], help="鲁棒性实验的Agent类型")

    args = parser.parse_args()

    # 初始化全局日志记录器（使用用户指定的输出目录）
    output_dir = args.output or os.path.join(os.path.dirname(__file__), "experiments", "results")
    _global_logger = ExperimentLogger(output_dir)

    # 加载prompts
    prompts = args.prompts
    if args.prompts_file:
        with open(args.prompts_file, 'r', encoding='utf-8') as f:
            prompts = json.load(f).get("prompts", DEFAULT_PROMPTS)
    if not prompts:
        prompts = DEFAULT_PROMPTS

    # 确定运行哪些实验
    run_all = args.all or not (args.baseline or args.ablation or args.robustness or args.comparison)

    # 记录程序开始时间
    program_start_time = time.time()
    log_print("\n" + "="*70)
    log_print("多智能体物流调度系统 - 实验程序启动")
    log_print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_print("="*70)

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

    # 计算并打印程序总耗时
    program_total_time = time.time() - program_start_time
    log_print("\n" + "="*70)
    log_print("程序执行完毕")
    log_print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_print(f"程序总耗时: {program_total_time:.2f} 秒 ({program_total_time/60:.2f} 分钟)")
    log_print("="*70)
