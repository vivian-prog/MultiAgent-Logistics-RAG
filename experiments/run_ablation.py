#!/usr/bin/env python
# experiments/run_ablation.py
"""
消融实验脚本
比较三种模式：无RAG、文本RAG、GraphRAG
"""
import os
import sys
import asyncio
import argparse
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from experiments.recorder import ExperimentRecorder, BatchExperimentRecorder
import httpx
import time
import re

# ===================== 配置 =====================
# 从main.py复用的配置
LLM_BASE_URL = "http://localhost:8080/v1"
LLM_API_KEY = "sk-xxx"
LLM_MODEL = "Qwen3-8B"

# GraphRAG服务配置
GRAPHRAG_URL = "http://localhost:8015/v1/chat/completions"
RAG_HEADERS = {"Content-Type": "application/json"}
RAG_MODEL_GLOBAL = "graphrag-global-search:latest"
RAG_MODEL_LOCAL = "graphrag-local-search:latest"

# FAISS TextRAG服务配置 (新增)
FAISS_TEXTRAG_URL = "http://localhost:8016/v1/chat/completions"
FAISS_TEXTRAG_MODEL = "faiss-text-search:latest"

API_BASE_URL = "http://localhost:8090"
AGENT_API_MAP = {
    "agentuav": f"{API_BASE_URL}/api/v1/simulation/agentuav",
    "agenttruck": f"{API_BASE_URL}/api/v1/simulation/agenttruck",
    "agentrobot": f"{API_BASE_URL}/api/v1/simulation/agentrobot",
    "agentuav_submit": f"{API_BASE_URL}/api/agent1/simulation",
    "agentuav_result": f"{API_BASE_URL}/api/agent1/result/{{}}",
    "common_result": f"{API_BASE_URL}/api/v1/task/{{}}"
}

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
        "display_name": "文本RAG",
        "enable_rag": True,
        "rag_type": "rag"
    },
    {
        "name": "graphrag",
        "display_name": "GraphRAG (知识图谱)",
        "enable_rag": True,
        "rag_type": "graphrag"
    }
]

# 默认测试prompts
DEFAULT_PROMPTS = [
    "请指挥各个agent把干粉灭火器从所在仓库运到深圳市中山大学深圳校区(北纬 22.800884948488687°，东经 113.95443173232752°)",
    "请调度无人机把急救药品从深圳仓库运到深圳市光明区人民医院",
    "安排卡车运送500公斤生鲜从龙华仓储中心到南山配送站"
]


# ===================== 核心函数 =====================
def rag_search(prompt: str, temperature: float = 0.7, rag_type: str = "graphrag") -> str:
    """执行RAG搜索"""
    import requests
    try:
        if rag_type == "graphrag":
            url = GRAPHRAG_URL
            model = RAG_MODEL_GLOBAL
        elif rag_type == "rag":
            # 使用FAISS文本检索服务
            url = FAISS_TEXTRAG_URL
            model = FAISS_TEXTRAG_MODEL
        else:
            url = GRAPHRAG_URL
            model = RAG_MODEL_GLOBAL

        rag_data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        response = requests.post(url, headers=RAG_HEADERS, data=json.dumps(rag_data), timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"RAG搜索请求出错: {e}")
        return ""


def call_llm_model(prompt: str, rag_context: str = "", temperature: float = 0.7) -> str:
    """调用LLM模型"""
    from openai import OpenAI
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
        content = re.sub(r'<think.*?</think','',content, flags=re.DOTALL).strip()
        return content

    except Exception as e:
        print(f"调用LLM出错: {e}")
        return ""


def extract_and_parse_last_json(final_answer: str) -> dict:
    """解析JSON响应"""
    json_pattern = r'\{[\s\S]*\}'
    matches = re.findall(json_pattern, final_answer)

    if not matches:
        raise ValueError("未找到JSON格式内容")

    top_level_json_str = matches[-1].strip()

    try:
        return json.loads(top_level_json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析失败：{e}")


async def poll_task(client, task_id, agent_name):
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


async def run_single_experiment(
    prompt: str,
    config: Dict[str, Any],
    recorder: ExperimentRecorder
) -> Dict[str, Any]:
    """
    执行单次实验
    """
    enable_rag = config["enable_rag"]
    rag_type = config["rag_type"]

    print(f"\n{'='*60}")
    print(f"实验配置: {config['display_name']}")
    print(f"Prompt: {prompt[:50]}...")
    print(f"{'='*60}")

    # 记录开始时间
    total_start = time.time()
    rag_search_time = 0
    llm_inference_time = 0

    # Step 1: RAG + LLM
    t0 = time.time()
    rag_context = ""

    if enable_rag:
        # RAG检索
        print(f"执行 {rag_type.upper()} 检索...")
        rag_context = rag_search(prompt, RAG_MODEL_FULL, 0.7, rag_type)
        rag_search_time = time.time() - t0
        print(f"RAG检索耗时: {rag_search_time:.2f}s")

        t1 = time.time()
    else:
        t1 = t0
        print("跳过RAG检索，直接调用LLM...")

    # LLM推理
    print("调用LLM生成指令...")
    final_answer = call_llm_model(prompt, rag_context, 0.7)
    llm_inference_time = time.time() - t1
    print(f"LLM推理耗时: {llm_inference_time:.2f}s")

    # 记录RAG指标
    recorder.record_rag_metrics(
        rag_enabled=enable_rag,
        rag_type=rag_type or "none",
        rag_search_time=rag_search_time,
        llm_inference_time=llm_inference_time,
        rag_context=rag_context,
        final_answer=final_answer
    )
    recorder.record_user_prompt(prompt)

    # Step 2: 解析指令
    try:
        answer_dict = extract_and_parse_last_json(final_answer)
        recorder.record_generated_commands(answer_dict)
        print(f"解析指令成功: {list(answer_dict.keys())}")
    except ValueError as e:
        recorder.record_error(str(e), "json_parse")
        print(f"JSON解析失败: {e}")
        return {"success": False, "error": str(e)}

    # Step 3: 执行仿真
    agent_results = {}

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Robot任务
        robot_params = answer_dict.get("agentrobot", {})
        if robot_params:
            t_start = time.time()
            try:
                resp = await client.post(AGENT_API_MAP["agentrobot"], json=robot_params)
                resp.raise_for_status()
                task_id = resp.json()["task_id"]
                result = await poll_task(client, task_id, "agentrobot")
                sim_time = (time.time() - t_start) * 10.0  # 时间修正

                recorder.record_agent_result("agentrobot", task_id, sim_time, result is not None)
                agent_results["agentrobot"] = {"success": result is not None, "time": sim_time}
                print(f"Robot完成: {sim_time:.2f}s")
            except Exception as e:
                recorder.record_error(str(e), "agentrobot")
                recorder.record_agent_result("agentrobot", "", 0, False)

        # Truck任务
        truck_params = answer_dict.get("agenttruck", {})
        if truck_params:
            t_start = time.time()
            try:
                resp = await client.post(AGENT_API_MAP["agenttruck"], json=truck_params)
                resp.raise_for_status()
                task_id = resp.json()["task_id"]
                result = await poll_task(client, task_id, "agenttruck")

                sim_data = result.get("simulation_data", result) if result else {}
                if sim_data and "total_time" in sim_data:
                    sim_time = float(sim_data["total_time"]) * 3600
                else:
                    sim_time = time.time() - t_start

                recorder.record_agent_result("agenttruck", task_id, sim_time, result is not None)
                agent_results["agenttruck"] = {"success": result is not None, "time": sim_time}
                print(f"Truck完成: {sim_time:.2f}s")
            except Exception as e:
                recorder.record_error(str(e), "agenttruck")
                recorder.record_agent_result("agenttruck", "", 0, False)

        # UAV任务
        uav_params = answer_dict.get("agentuav", {})
        if uav_params:
            t_start = time.time()
            try:
                resp = await client.post(AGENT_API_MAP["agentuav_submit"], json=uav_params)
                resp.raise_for_status()
                task_id = resp.json()["task_id"]
                result = await poll_task(client, task_id, "agentuav")

                if result:
                    sim_data = result.get("simulation_data", result)
                    sim_time = float(sim_data.get("total_time_seconds", sim_data.get("total_steps", 0.0)))
                else:
                    sim_time = time.time() - t_start

                recorder.record_agent_result("agentuav", task_id, sim_time, result is not None)
                agent_results["agentuav"] = {"success": result is not None, "time": sim_time}
                print(f"UAV完成: {sim_time:.2f}s")
            except Exception as e:
                recorder.record_error(str(e), "agentuav")
                recorder.record_agent_result("agentuav", "", 0, False)

    total_time = time.time() - total_start
    print(f"\n总耗时: {total_time:.2f}s")

    return {
        "success": True,
        "total_time": total_time,
        "agent_results": agent_results
    }


async def run_ablation_experiment(
    prompts: List[str] = None,
    output_dir: str = None,
    repeat: int = 1
):
    """
    执行完整的消融实验
    :param prompts: 测试prompt列表
    :param output_dir: 结果输出目录
    :param repeat: 每个配置重复次数
    """
    if prompts is None:
        prompts = DEFAULT_PROMPTS

    batch_recorder = BatchExperimentRecorder(output_dir)
    all_results = []

    print("\n" + "="*60)
    print("消融实验开始")
    print(f"测试Prompt数量: {len(prompts)}")
    print(f"实验配置数量: {len(ABLATION_CONFIGS)}")
    print(f"每配置重复次数: {repeat}")
    print("="*60)

    for prompt_idx, prompt in enumerate(prompts):
        print(f"\n\n{'#'*60}")
        print(f"# Prompt {prompt_idx + 1}/{len(prompts)}")
        print(f"{'#'*60}")

        for config in ABLATION_CONFIGS:
            for repeat_idx in range(repeat):
                print(f"\n--- 第 {repeat_idx + 1}/{repeat} 次重复 ---")

                # 开始实验
                recorder = batch_recorder.new_experiment(
                    experiment_type="ablation",
                    config=config,
                    description=f"Prompt {prompt_idx + 1}, Config: {config['name']}, Repeat: {repeat_idx + 1}"
                )

                # 执行实验
                result = await run_single_experiment(prompt, config, recorder)

                # 结束并保存
                status = "completed" if result.get("success") else "failed"
                recorder.end_experiment(status)
                recorder.save_to_json()
                recorder.append_to_csv()

                all_results.append({
                    "prompt_idx": prompt_idx,
                    "config_name": config["name"],
                    "repeat_idx": repeat_idx,
                    "result": result
                })

                # 打印实验间隔
                print(f"\n等待5秒后继续下一个实验...")
                await asyncio.sleep(5)

    # 保存汇总结果
    batch_recorder.save_all("ablation_summary.json")

    # 打印汇总统计
    print("\n\n" + "="*60)
    print("消融实验完成 - 汇总统计")
    print("="*60)

    for config in ABLATION_CONFIGS:
        config_results = [r for r in all_results if r["config_name"] == config["name"]]
        if config_results:
            avg_rag_time = sum(r["result"].get("rag_search_time", 0) for r in config_results if r["result"].get("success")) / len(config_results)
            avg_llm_time = sum(r["result"].get("llm_inference_time", 0) for r in config_results if r["result"].get("success")) / len(config_results)
            avg_total = sum(r["result"].get("total_time", 0) for r in config_results if r["result"].get("success")) / len(config_results)

            print(f"\n{config['display_name']}:")
            print(f"  - 平均RAG检索时间: {avg_rag_time:.2f}s")
            print(f"  - 平均LLM推理时间: {avg_llm_time:.2f}s")
            print(f"  - 平均总耗时: {avg_total:.2f}s")

    return all_results


# ===================== 主入口 =====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="消融实验脚本")
    parser.add_argument("--prompts", nargs="+", help="自定义测试prompts")
    parser.add_argument("--output", type=str, default=None, help="结果输出目录")
    parser.add_argument("--repeat", type=int, default=1, help="每配置重复次数")
    parser.add_argument("--config", type=str, help="从JSON文件加载prompts")

    args = parser.parse_args()

    # 加载prompts
    prompts = args.prompts
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            prompts = json.load(f).get("prompts", DEFAULT_PROMPTS)

    if not prompts:
        prompts = DEFAULT_PROMPTS

    # 执行实验
    asyncio.run(run_ablation_experiment(
        prompts=prompts,
        output_dir=args.output,
        repeat=args.repeat
    ))
