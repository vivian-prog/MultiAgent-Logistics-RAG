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

async def poll_task(client, task_id, agent_name):
    """通用任务轮询函数"""
    print(f"⏳ 正在等待 {agent_name} 任务完成 (Task ID: {task_id})...")
    max_retries = 120  # 增加等待时间
    retry_interval = 1

    for _ in range(max_retries):
        try:
            # 尝试通用接口
            url = AGENT_API_MAP["common_result"].format(task_id)
            resp = await client.get(url)

            # 如果通用接口404（可能是旧的agent1接口），尝试备用接口
            if resp.status_code == 404 and agent_name == "agentuav":
                url = AGENT_API_MAP["agentuav_result"].format(task_id)
                resp = await client.get(url)

            resp.raise_for_status()
            data = resp.json()

            # 兼容不同的状态字段名 (status/state)
            status = str(data.get("status", "")).upper()

            if status == "SUCCESS":
                print(f"✅ {agent_name} 任务执行成功！")
                return data.get("result") or data.get("simulation_data")
            elif status == "FAILURE" or status == "FAILED":
                error_msg = data.get("error") or data.get("result")
                print(f"❌ {agent_name} 任务失败: {error_msg}")
                return None
            else:
                # 仍在运行
                progress = data.get("progress", 0)
                # print(f"   [{agent_name}] 进度: {progress}%")
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
                await poll_task(client, task_id, "agentuav")

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

            # GPS 兜底
            if "start_lat" not in agenttruck_params:
                start_name = agenttruck_params.get("start_location", "深圳北站")
                end_name = agenttruck_params.get("end_location", "中山大学深圳校区")
                s_coords = get_osm_coordinates(start_name)
                e_coords = get_osm_coordinates(end_name)
                if s_coords:
                    agenttruck_params["start_lat"], agenttruck_params["start_lng"] = s_coords
                else: # 默认值
                    agenttruck_params["start_lat"], agenttruck_params["start_lng"] = 22.543, 114.057
                if e_coords:
                    agenttruck_params["end_lat"], agenttruck_params["end_lng"] = e_coords
                else: # 默认值
                    agenttruck_params["end_lat"], agenttruck_params["end_lng"] = 22.793, 113.914

            try:
                resp2 = await client.post(AGENT_API_MAP["agenttruck"], json=agenttruck_params)
                resp2.raise_for_status()
                task_id = resp2.json()["task_id"]
                task_ids["agenttruck"] = task_id
                print(f"Truck 任务已提交: {task_id}")

                # 轮询等待结果
                await poll_task(client, task_id, "agenttruck")

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

                timing_stats["Robot工作时间"] = time.time() - t_start
            except Exception as e:
                print(f"Robot 任务异常: {e}")
                timing_stats["Robot工作时间"] = -1
        else:
            print("无 Robot 任务")

    total_end_time = time.time()
    timing_stats["全流程总耗时"] = total_end_time - total_start_time

    print("\n" + "="*40)
    print("📊 任务执行时间统计")
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
