import requests
import json
from openai import OpenAI
from prompts.prompts import MultiAgentLogisticRAGPrompt
from typing import Dict, List, Optional, Any
import httpx
import time
import logging
import re

# ===================== 配置项 =====================
# RAG服务配置
RAG_URL = "http://localhost:8015/v1/chat/completions"
RAG_HEADERS = {"Content-Type": "application/json"}
# 可选的RAG模型类型
RAG_MODEL_GLOBAL = "graphrag-global-search:latest"
RAG_MODEL_LOCAL = "graphrag-local-search:latest"
RAG_MODEL_FULL = "full-model:latest"

# 8B模型配置
LLM_BASE_URL = "http://localhost:8080/v1"
LLM_API_KEY = "sk-xxx"  # 随便填写，只是为了通过接口参数校验
LLM_MODEL = "Qwen3-8B"

# 仿真FastAPI 服务地址（根据你的部署地址修改）
API_BASE_URL = "http://localhost:8090"
# 三类 Agent 的接口路径映射
AGENT_API_MAP = {
    "agentuav": f"{API_BASE_URL}/api/v1/simulation/agentuav",
    "agenttruck": f"{API_BASE_URL}/api/v1/simulation/agenttruck",
    "agentrobot": f"{API_BASE_URL}/api/v1/simulation/agentrobot",
    "agentuav_submit": f"{API_BASE_URL}/api/agent1/simulation",
    "agentuav_result": f"{API_BASE_URL}/api/agent1/result/{{}}",
    "common_result": f"{API_BASE_URL}/api/v1/task/{{}}"  # 通用结果查询接口
}
#实例化prompts
# 实例化数据类（使用默认的Prompt字符串）
prompt_config = MultiAgentLogisticRAGPrompt()
CLOUDLLM_SYSTEM_PROMPT = prompt_config.cloudLLM_session_init
RAG_SYSTEM_PROMPT= prompt_config.RAG_session_init

# ===================== 核心函数 =====================
def rag_search(prompt: str, rag_model: str = RAG_MODEL_FULL, temperature: float = 0.7) -> str:
    """
    执行RAG搜索，返回相关内容
    :param prompt: 用户原始问题
    :param rag_model: 使用的RAG模型类型
    :param temperature: 温度参数
    :return: RAG搜索返回的相关内容
    """
    try:
        rag_data = {
            "model": rag_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        # 发送RAG请求
        response = requests.post(
            RAG_URL,
            headers=RAG_HEADERS,
            data=json.dumps(rag_data),
            timeout=60  # 设置超时时间
        )
        response.raise_for_status()  # 检查HTTP错误

        # 解析RAG响应
        rag_result = response.json()["choices"][0]["message"]["content"]
        return rag_result

    except requests.exceptions.RequestException as e:
        print(f"RAG搜索请求出错: {e}")
        return ""
    except KeyError as e:
        print(f"RAG响应解析出错，缺少字段: {e}")
        return ""

def call_llm_model(prompt: str, rag_context: str, temperature: float = 0.7) -> str:
    """
    调用8B模型，将RAG结果作为上下文拼接进prompt
    :param prompt: 用户原始问题
    :param rag_context: RAG搜索得到的相关内容
    :param temperature: 温度参数
    :return: 8B模型生成的回答
    """
    try:
        # 初始化OpenAI客户端
        client = OpenAI(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
        )

        # 拼接prompt和RAG上下文
        if rag_context:
            full_prompt = f"""
            以下是相关参考信息：
            {rag_context}

            请基于以上参考信息回答问题：{prompt}
            """
        else:
            full_prompt = prompt  # 如果RAG无结果，直接使用原始问题

        # 调用8B模型
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=temperature,
        )
        content=completion.choices[0].message.content

        content=re.sub(r'<think>.*?</think>','',content,flags=re.DOTALL).strip()
        # 返回模型回答
        return content

    except Exception as e:
        print(f"调用8B模型出错: {e}")
        return ""

def rag_plus_llm(prompt: str, rag_model: str = RAG_MODEL_FULL, temperature: float = 0.7) -> str:
    """
    完整的RAG+LLM流程：先RAG搜索，再调用8B模型
    :param prompt: 用户输入的问题
    :param rag_model: 使用的RAG模型类型
    :param temperature: 温度参数
    :return: 最终的回答结果
    """
    print(f"用户问题: {prompt}\n")

    t0 = time.time()
    #将user_prompt嵌入rag_system_prompt
    rag_query_prompt = RAG_SYSTEM_PROMPT.format(user_prompt=prompt)
    # 第一步：执行RAG搜索
    rag_query = call_llm_model(rag_query_prompt , '', temperature)

    # 处理：按空格切分字段形成列表
    rag_query_list = rag_query.split()
    print(f"RAG检索关键词列表: {rag_query_list}")
    # 重新组合为标准字符串传给检索接口（去除多余空白）
    rag_query = " ".join(rag_query_list)

    print("正在执行RAG搜索...")
    rag_context = rag_search(rag_query, rag_model, temperature)
    t1 = time.time()
    rag_time = t1 - t0

    if rag_context:
        print(f"RAG搜索结果:\n{rag_context}\n")
    else:
        print("RAG搜索未获取到相关内容\n")

    # 第二步：调用8B模型生成回答
    #将user_prompt嵌入cloudllm_system_prompt
    cloudllm_prompt = CLOUDLLM_SYSTEM_PROMPT.format(user_prompt=prompt)
    print("正在调用8B模型生成回答...")
    final_answer = call_llm_model(cloudllm_prompt, rag_context, temperature)
    t2 = time.time()
    llm_time = t2 - t1

    print(f"\n[性能统计] RAG搜索耗时: {rag_time:.2f}s | LLM推理耗时: {llm_time:.2f}s")

    return final_answer

def extract_and_parse_json(final_answer: str) -> dict:
    """
    从混杂了调试信息的字符串中提取JSON部分并解析
    """
    json_pattern = r'\{[\s\S]*\}'
    matches = re.findall(json_pattern, final_answer)

    if not matches:
        raise ValueError("在final_answer中未找到JSON格式内容")

    pure_json_str = matches[-1]

    try:
        answer_dict = json.loads(pure_json_str)
        return answer_dict
    except json.JSONDecodeError as e:
        raise ValueError(f"提取的JSON字符串解析失败：{e}") from e

def extract_and_parse_last_json(final_answer: str) -> dict:
    """
    修复版：精准提取最外层的顶层JSON（解决只提取最后一个子JSON的问题）
    """
    cleaned_str = final_answer.replace('\u200b', '').replace('\xa0', ' ').strip()
    top_level_pattern = r'^.*?(\{[\s\S]*\}).*$'
    matches = re.findall(top_level_pattern, cleaned_str, re.DOTALL)

    if not matches:
        raise ValueError("未找到顶层JSON结构，原始文本片段：\n" + cleaned_str[:500])

    top_level_json_str = matches[0].strip()

    try:
        answer_dict = json.loads(top_level_json_str)
        required_keys = ["agentuav", "agenttruck", "agentrobot"]
        missing_keys = [k for k in required_keys if k not in answer_dict]
        if missing_keys:
            print(f"警告：顶层JSON缺少关键字段 {missing_keys}，当前字段：{list(answer_dict.keys())}")
        return answer_dict
    except json.JSONDecodeError as e:
        raise ValueError(f"顶层JSON解析失败：{e}\n原始JSON字符串：\n{top_level_json_str[:1000]}")


def get_osm_coordinates(location_name: str) -> Optional[tuple]:
    """
    使用 OpenStreetMap Nominatim API 将地点名称转换为经纬度
    """
    if not location_name:
        return None

    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location_name,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "AgentSimulation/1.0 (contact@example.com)"
        }

        print(f"正在通过 OSM 查询地点坐标: {location_name} ...")
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                print(f"OSM 查询成功: {location_name} -> ({lat}, {lon})")
                return lat, lon
            else:
                print(f"OSM 未找到地点: {location_name}")
        else:
            print(f"OSM API 请求失败: {response.status_code}")

    except Exception as e:
        print(f"OSM 地理编码出错: {e}")

    return None

async def poll_task(client, task_id, agent_name):
    """通用任务轮询函数"""
    print(f"⏳ 正在等待 {agent_name} 任务完成 (Task ID: {task_id})...")
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
                print(f"✅ {agent_name} 任务执行成功！")
                return data.get("result") or data.get("simulation_data")
            elif status == "FAILURE" or status == "FAILED":
                error_msg = data.get("error") or data.get("result")
                print(f"❌ {agent_name} 任务失败: {error_msg}")
                return None
            else:
                await asyncio.sleep(retry_interval)

        except Exception as e:
            print(f"⚠️ {agent_name} 轮询异常: {e}")
            await asyncio.sleep(retry_interval)

    print(f"❌ {agent_name} 任务等待超时")
    return None

async def extract_agent_commands_and_call_api(user_prompt: str) -> Dict[str, str]:
    """
    1. 调用 RAG+LLM 获取包含三类 Agent 指令的 JSON 结果
    2. 解析指令并调用对应 Agent 的仿真接口
    3. 返回各 Agent 的 task_id 及耗时统计
    """
    total_start_time = time.time()
    timing_stats = {}

    # 第一步：调用 RAG+LLM 流程
    print(">>> 阶段1: RAG检索与指令生成")
    final_answer = rag_plus_llm(prompt=user_prompt, rag_model=RAG_MODEL_FULL, temperature=0.7)

    # 解析 JSON
    try:
        answer_dict = extract_and_parse_last_json(final_answer)
        print('解析后的指令参数:', answer_dict)
    except ValueError as e:
        raise ValueError(f"final_answer 不是合法的 JSON 格式：{e}") from e

    agentuav_params = answer_dict.get("agentuav", {})
    agenttruck_params = answer_dict.get("agenttruck", {})
    agentrobot_params = answer_dict.get("agentrobot", {})

    # 第四步：异步调用各 Agent 的接口
    print("\n>>> 阶段2: 多智能体仿真任务执行")
    async with httpx.AsyncClient(timeout=60.0) as client:
        task_ids = {}

        # 1. UAV 任务
        if agentuav_params:
            logging.info("启动 UAV 任务...")
            t_start = time.time()
            try:
                resp1 = await client.post(AGENT_API_MAP["agentuav_submit"], json=agentuav_params)
                resp1.raise_for_status()
                task_id = resp1.json()["task_id"]
                task_ids["agentuav"] = task_id
                print(f"UAV 任务已提交: {task_id}")

                # 轮询等待结果
                uav_result = await poll_task(client, task_id, "agentuav")

                # 修正：从 simulation_data 提取
                sim_data = uav_result.get("simulation_data", uav_result) if uav_result else {}
                if sim_data and "total_steps" in sim_data:
                    timing_stats["UAV工作时间"] = float(sim_data["total_steps"])
                else:
                    timing_stats["UAV工作时间"] = time.time() - t_start
            except Exception as e:
                print(f"UAV 任务异常: {e}")
                timing_stats["UAV工作时间"] = -1
        else:
            print("无 UAV 任务")

        # 2. Truck 任务
        if agenttruck_params:
            logging.info("启动 Truck 任务...")
            t_start = time.time()

            # ----------------- GPS 补全逻辑 -----------------
            # 1. 尝试从 UAV 参数中复用坐标 (因为 Truck终点 = UAV起点)
            if "end_lat" not in agenttruck_params and agentuav_params.get("start_lat"):
                print("💡 从 UAV 任务中复用终点坐标")
                agenttruck_params["end_lat"] = agentuav_params["start_lat"]
                agenttruck_params["end_lng"] = agentuav_params["start_lng"]

            # 2. 尝试从数据库中查找起降点/仓库坐标 (TODO: 对接数据库查询)
            # 这里暂时只能依赖 OSM 或默认值

            # 3. OSM 兜底 (网络不可达时会失败)
            if "start_lat" not in agenttruck_params:
                start_name = agenttruck_params.get("start_location", "深圳北站")
                end_name = agenttruck_params.get("end_location", "中山大学深圳校区")

                # 只有当确实缺坐标时才调 OSM
                s_coords = get_osm_coordinates(start_name)
                if s_coords:
                    agenttruck_params["start_lat"], agenttruck_params["start_lng"] = s_coords
                else:
                    # 默认值 (深圳市民中心)
                    if "start_lat" not in agenttruck_params:
                        agenttruck_params["start_lat"], agenttruck_params["start_lng"] = 22.543, 114.057
                        print(f"⚠️ 无法获取起点坐标，使用默认值: {start_name} -> (22.543, 114.057)")

                if "end_lat" not in agenttruck_params:
                    e_coords = get_osm_coordinates(end_name)
                    if e_coords:
                        agenttruck_params["end_lat"], agenttruck_params["end_lng"] = e_coords
                    else:
                        # 默认值
                        agenttruck_params["end_lat"], agenttruck_params["end_lng"] = 22.793, 113.914
                        print(f"⚠️ 无法获取终点坐标，使用默认值: {end_name} -> (22.793, 113.914)")
            # -----------------------------------------------

            try:
                resp2 = await client.post(AGENT_API_MAP["agenttruck"], json=agenttruck_params)
                resp2.raise_for_status()
                task_id = resp2.json()["task_id"]
                task_ids["agenttruck"] = task_id
                print(f"Truck 任务已提交: {task_id}")

                # 轮询等待结果
                truck_result = await poll_task(client, task_id, "agenttruck")

                # 修正：从 simulation_data 提取
                sim_data = truck_result.get("simulation_data", truck_result) if truck_result else {}
                if sim_data and "total_time" in sim_data:
                    timing_stats["Truck工作时间"] = float(sim_data["total_time"]) * 3600
                else:
                    timing_stats["Truck工作时间"] = time.time() - t_start
            except Exception as e:
                print(f"Truck 任务异常: {e}")
                timing_stats["Truck工作时间"] = -1
        else:
            print("无 Truck 任务")

        # 3. Robot 任务
        if agentrobot_params:
            logging.info("启动 Robot 任务...")
            t_start = time.time()
            try:
                resp3 = await client.post(AGENT_API_MAP["agentrobot"], json=agentrobot_params)
                resp3.raise_for_status()
                task_id = resp3.json()["task_id"]
                task_ids["agentrobot"] = task_id
                print(f"Robot 任务已提交: {task_id}")

                # 轮询等待结果
                await poll_task(client, task_id, "agentrobot")

                # Robot 目前使用客户端计时，但由于 core.py 中开启了 10倍速 (TIME_SCALE=10)
                # 为了还原真实的业务仿真耗时，我们需要乘以 10
                robot_physical_time = time.time() - t_start
                timing_stats["Robot工作时间"] = robot_physical_time * 10.0
            except Exception as e:
                print(f"Robot 任务异常: {e}")
                timing_stats["Robot工作时间"] = -1
        else:
            print("无 Robot 任务")

    total_end_time = time.time()
    timing_stats["全流程总耗时"] = total_end_time - total_start_time

    print("\n" + "="*40)
    print("📊 任务执行时间统计 (单位: 秒)")
    print("注: Agent时间为仿真业务耗时(如行驶时间)，非计算耗时")
    print("="*40)
    for k, v in timing_stats.items():
        if v == -1:
            print(f"{k:<15}: ❌ 失败/未执行")
        else:
            print(f"{k:<15}: {v:.2f} s")
    print("="*40 + "\n")

    return task_ids

#
# ===================== 测试示例 =====================
if __name__ == "__main__":


    import asyncio

    # 示例用户问题
    test_prompt = "请指挥各个agent把干粉灭火器从所在仓库运到深圳市中山大学深圳校区(北纬 22.800884948488687°，东经 113.95443173232752°)"

    # 异步执行
    task_ids = asyncio.run(extract_agent_commands_and_call_api(test_prompt))
    print("\n所有 Agent 任务提交结果：")
    for agent, task_id in task_ids.items():
        print(f"{agent}: {task_id}")
