import requests
import pandas as pd
import time
 
# 高德API参数
key = "f104b4f956280fdfa5c446d03ffa9a2c"
url = "https://restapi.amap.com/v3/geocode/geo"
 
# 读取Excel数据
df = pd.read_csv("/home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/getSite/jd_warehouses_shenzhen.csv")
 
# 请求参数
max_retries = 3
retry_delay = 1  # 秒
request_interval = 0.5  # 秒
 
failed_addresses = []
 
for index, row in df.iterrows():
    address = row["Address"] #如果报错，可检查这里表格储存地址的列名是否对应
    params = {
        "address": address,
        "key": key,
    }
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params)
            result = response.json()
            if result["status"] == "1" and result["geocodes"]:
                location = result["geocodes"][0]["location"]
                lng, lat = location.split(",")
                df.at[index, "Longitude"] = lng
                df.at[index, "Latitude"] = lat
                break
            else:
                #如果报错，可复制粘贴“返回结果”的内容，询问AI进行调试
                print(f"地址 {address} 第{attempt+1}次尝试失败：{result.get('info')},返回结果：{result}") 
                time.sleep(retry_delay)
        except Exception as e:
            print(f"请求异常：{e}")
            time.sleep(retry_delay)
    else:
        df.at[index, "Longitude"] = "失败"
        df.at[index, "Latitude"] = "失败"
        failed_addresses.append(address)
    
    time.sleep(request_interval)  # 控制请求频率
 
# 保存结果
df.to_csv("/home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/getSite/jd_warehouses_shenzhen_latlng.csv", index=False)
 
# 保存失败地址
if failed_addresses:
    with open("failed_addresses.txt", "w") as f:
        f.write("\n".join(failed_addresses))
    print(f"有{len(failed_addresses)}个地址解析失败，已保存到文件。")