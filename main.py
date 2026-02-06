import requests
import json
from openai import OpenAI
from prompts.prompts import MultiAgentLogisticRAGPrompt
from typing import Dict, List, Optional, Any
import httpx 
import time
import logging
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
    "agentuav_result": f"{API_BASE_URL}/api/agent1/result/{{}}"
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
            timeout=30  # 设置超时时间
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
        import re
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
    #将user_prompt嵌入rag_system_prompt
    rag_query_prompt = RAG_SYSTEM_PROMPT.format(user_prompt=prompt)
    # 第一步：执行RAG搜索
    rag_query = call_llm_model(rag_query_prompt , '', temperature)
    print("生成的rag搜索的Prompt:",rag_query)
    print("正在执行RAG搜索...")
    rag_context = rag_search(rag_query, rag_model, temperature)
    if rag_context:
        print(f"RAG搜索结果:\n{rag_context}\n")
    else:
        print("RAG搜索未获取到相关内容\n")
    
    # 第二步：调用8B模型生成回答
    #将user_prompt嵌入cloudllm_system_prompt
    cloudllm_prompt = CLOUDLLM_SYSTEM_PROMPT.format(user_prompt=prompt)
    print("正在调用8B模型生成回答...")
    final_answer = call_llm_model(cloudllm_prompt, rag_context, temperature)
    
    return final_answer

import json
import re

def extract_and_parse_json(final_answer: str) -> dict:
    """
    从混杂了调试信息的字符串中提取JSON部分并解析
    
    Args:
        final_answer: 包含调试信息和JSON的原始字符串
    
    Returns:
        解析后的JSON字典
    
    Raises:
        ValueError: 未找到合法JSON或解析失败
    """
    # 步骤1：使用正则表达式匹配JSON对象（{...}）
    # 匹配规则：以{开头，以}结尾，中间包含任意字符（非贪婪匹配）
    json_pattern = r'\{[\s\S]*\}'
    matches = re.findall(json_pattern, final_answer)
    
    if not matches:
        raise ValueError("在final_answer中未找到JSON格式内容")
    
    # 步骤2：取最后一个匹配结果（通常是完整的JSON）
    pure_json_str = matches[-1]
    
    try:
        # 步骤3：解析纯JSON字符串
        answer_dict = json.loads(pure_json_str)
        return answer_dict
    except json.JSONDecodeError as e:
        raise ValueError(f"提取的JSON字符串解析失败：{e}") from e

import json
import re


def extract_and_parse_last_json(final_answer: str) -> dict:
    """
    修复版：精准提取最外层的顶层JSON（解决只提取最后一个子JSON的问题）
    
    Args:
        final_answer: 包含调试信息和JSON的原始字符串
    
    Returns:
        解析后的完整顶层JSON字典（包含agentuav/agenttruck/agentrobot）
    
    Raises:
        ValueError: 未找到合法JSON或解析失败
    """
    # 步骤1：清理特殊字符，只保留关键内容
    cleaned_str = final_answer.replace('\u200b', '').replace('\xa0', ' ').strip()
    
    # 步骤2：匹配最外层的顶层JSON（关键修复：用贪婪匹配找最外层{}）
    # 正则说明：
    # ^.*?  匹配JSON前的所有文本（非贪婪）
    # \{    匹配顶层JSON的起始{
    # [\s\S]*? 匹配中间所有内容（非贪婪，避免匹配到多个JSON）
    # \}    匹配顶层JSON的结束}
    # .*$   匹配JSON后的所有文本
    top_level_pattern = r'^.*?(\{[\s\S]*\}).*$'
    matches = re.findall(top_level_pattern, cleaned_str, re.DOTALL)
    
    if not matches:
        raise ValueError("未找到顶层JSON结构，原始文本片段：\n" + cleaned_str[:500])
    
    # 步骤3：取第一个匹配的顶层JSON（也是唯一的顶层JSON）
    top_level_json_str = matches[0].strip()
    
    # 步骤4：解析顶层JSON
    try:
        answer_dict = json.loads(top_level_json_str)
        # 验证是否包含agentuav/agenttruck/agentrobot（可选，调试用）
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
    :param location_name: 地点名称（如 "中山大学深圳校区"）
    :return: (lat, lng) 元组或 None
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
        # OSM 要求必须带 User-Agent
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

async def extract_agent_commands_and_call_api(user_prompt: str) -> Dict[str, str]:
    """
    1. 调用 RAG+LLM 获取包含三类 Agent 指令的 JSON 结果
    2. 解析指令并调用对应 Agent 的仿真接口
    3. 返回各 Agent 的 task_id
    """
    # 第一步：调用 RAG+LLM 流程，获取 JSON 格式的 final_answer
    final_answer = rag_plus_llm(prompt=user_prompt, rag_model=RAG_MODEL_FULL, temperature=0.7)
    # 关键调试：打印 final_answer 原始内容（必加！）
    print("=== 调试：final_answer 原始内容 ===")
    print(f"内容：{final_answer}")
    print(f"长度：{len(final_answer)}")
    print(f"首个字符：{repr(final_answer[:1]) if final_answer else '空'}")
    print("==================================")
    # 第二步：解析 final_answer 为 JSON 字典（处理可能的解析错误）
    try:
        answer_dict = extract_and_parse_last_json(final_answer)
        print('answer_dict =',answer_dict)
    except ValueError as e:
        raise ValueError(f"final_answer 不是合法的 JSON 格式：{e}") from e
    # 第三步：提取三类 Agent 的指令参数（假设 JSON 结构如下：
    # {
    #   "agent1_command": {"param1": "xxx", "param2": "yyy"},
    #   "agent2_command": {"paramA": "aaa", "paramB": "bbb"},
    #   "agent3_command": {"paramX": "xxx", "paramY": "yyy"}
    # }
    # 可根据实际 JSON 结构调整 key 名称）
    agentuav_params = answer_dict.get("agentuav", {})
    agenttruck_params = answer_dict.get("agenttruck", {})
    agentrobot_params = answer_dict.get("agentrobot", {})

    # 第四步：异步调用各 Agent 的接口（使用 httpx.AsyncClient 提升效率）
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 存储各 Agent 的 task_id
        task_ids = {}

        if agentuav_params:
            logging.info("分类成功 → 识别到UAV")
            try:
                # 1. 提交任务 (注意：直接复用外层client，不要重复 async with)
                resp1 = await client.post(AGENT_API_MAP["agentuav_submit"], json=agentuav_params)
                resp1.raise_for_status()
                submit_data = resp1.json()
                task_id = submit_data["task_id"]
                task_ids["agentuav"] = task_id
                print(f"agentuav 仿真任务已提交，task_id: {task_id}")

                # 2. 轮询查询结果（直到任务完成）
                max_retries = 60  # 最多轮询 60 次（按实际任务时长调整）
                retry_interval = 2  # 每 2 秒查询一次
                for _ in range(max_retries):
                    result_resp = await client.get(AGENT_API_MAP["agentuav_result"].format(task_id))
                    result_resp.raise_for_status()
                    result_data = result_resp.json()

                    if result_data["status"] == "success":
                        # 3. 获取完整的 result
                        agentuav_result = result_data["result"]
                        print(f"Agent1 任务执行完成.")
                        break
                    elif result_data["status"] == "failed":
                        print(f"agentuav 任务执行失败：{result_data['error']}")
                        agentuav_result = None
                        break
                    else:
                        # 任务仍在运行，继续轮询
                        progress = result_data["progress"]
                        print(f"agentuav 任务运行中，进度：{progress}%")
                        await asyncio.sleep(retry_interval)
                else:
                    # 轮询超时
                    print(f"agentuav 任务查询超时（{max_retries*retry_interval} 秒）")
                    agentuav_result = None

            except httpx.HTTPError as e:
                print(f"调用 agentuav 接口失败：{e}")
                task_ids["agentuav"] = None
                agentuav_result = None
        else:
            print("未提取到 agentuav 的指令参数")
            task_ids["agentuav"] = None
            agentuav_result = None



        # 调用 Agent2 接口
        if agenttruck_params:
            logging.info("分类成功 → 识别到TRUCK")

            # ----------------- GPS 参数兜底逻辑 -----------------
            # 如果缺少经纬度参数，尝试从 tasks 描述或字段中解析地点并查询 OSM
            if "start_lat" not in agenttruck_params or "end_lat" not in agenttruck_params:
                print("检测到 agenttruck 缺少 GPS 参数，启动自动地理编码兜底...")

                start_name = agenttruck_params.get("start_location")
                end_name = agenttruck_params.get("end_location")

                # 如果参数中没有明确的 location 字段，尝试从 tasks 列表中简单的正则提取（简单示例）
                # 假设任务描述是 "从北京运输到上海"
                if not start_name or not end_name:
                    tasks = agenttruck_params.get("tasks", [])
                    if tasks:
                        task_str = tasks[0]
                        # 简单的启发式规则，或者直接使用默认值
                        # 这里为了演示，我们假设如果找不到就尝试提取 user_prompt 中的地点
                        # 实际项目中可能需要更复杂的 NLP 提取
                        pass

                # 如果仍未找到，这里可以硬编码一些测试点，或者尝试查询 user_prompt 里的关键词
                # 示例：如果 user_prompt 包含 "中山大学"，则将其设为终点
                if not end_name and "中山大学" in user_prompt:
                    end_name = "中山大学深圳校区"
                if not start_name:
                    start_name = "深圳北站" # 示例默认起点

                # 调用 OSM API
                if start_name and "start_lat" not in agenttruck_params:
                    start_coords = get_osm_coordinates(start_name)
                    if start_coords:
                        agenttruck_params["start_lat"] = start_coords[0]
                        agenttruck_params["start_lng"] = start_coords[1]

                if end_name and "end_lat" not in agenttruck_params:
                    end_coords = get_osm_coordinates(end_name)
                    if end_coords:
                        agenttruck_params["end_lat"] = end_coords[0]
                        agenttruck_params["end_lng"] = end_coords[1]

                # 如果依然缺失，给一个默认值防止报错（仅用于演示/调试）
                if "start_lat" not in agenttruck_params:
                     # 默认：深圳市民中心
                    agenttruck_params["start_lat"] = 22.543099
                    agenttruck_params["start_lng"] = 114.057868
                    print(f"警告：无法获取起点坐标，使用默认值：深圳市民中心")

                if "end_lat" not in agenttruck_params:
                    # 默认：中山大学深圳校区
                    agenttruck_params["end_lat"] = 22.7933
                    agenttruck_params["end_lng"] = 113.9142
                    print(f"警告：无法获取终点坐标，使用默认值：中山大学深圳校区")

            # ----------------- 兜底逻辑结束 -----------------

            try:
                resp2 = await client.post(AGENT_API_MAP["agenttruck"], json=agenttruck_params)
                resp2.raise_for_status()
                task_ids["agenttruck"] = resp2.json()["task_id"]
                print(f"agenttruck 仿真任务已提交，task_id: {task_ids['agenttruck']}")
            except httpx.HTTPError as e:
                print(f"调用 agenttruck 接口失败：{e}")
                task_ids["agenttruck"] = None
        else:
            print("未提取到 agenttruck 的指令参数")
            task_ids["agenttruck"] = None

        # 调用 Agent3 接口
        if agentrobot_params:
            logging.info("分类成功 → 识别到ROBOT")

            try:
                resp3 = await client.post(AGENT_API_MAP["agentrobot"], json=agentrobot_params)
                resp3.raise_for_status()
                task_ids["agentrobot"] = resp3.json()["task_id"]
                print(f"agentrobot 仿真任务已提交，task_id: {task_ids['agentrobot']}")
            except httpx.HTTPError as e:
                print(f"调用 agentrobot 接口失败：{e}")
                task_ids["agentrobot"] = None
        else:
            print("未提取到 agentrobot 的指令参数")
            task_ids["agentrobot"] = None
    
    return task_ids

# 
# ===================== 测试示例 =====================
if __name__ == "__main__":


    import asyncio
    
    # 示例用户问题（会触发 RAG+LLM 生成包含三类 Agent 指令的 JSON）
    test_prompt = "请指挥各个agent把干粉灭火器从所在仓库运到深圳市中山大学深圳校区(北纬 22.770°，东经 113.904°)"
    
    # 异步执行
    task_ids = asyncio.run(extract_agent_commands_and_call_api(test_prompt))
    print("\n所有 Agent 任务提交结果：")
    for agent, task_id in task_ids.items():
        print(f"{agent}: {task_id}")