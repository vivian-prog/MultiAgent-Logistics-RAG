import csv
import requests
import time
import os

# ================= 配置区域 =================
# 如果您有 API Key，请在此处填入
# 百度地图 API Key (AK)
BAIDU_API_KEY = ""
# 高德地图 API Key
GAODE_API_KEY = ""
# ===========================================

def get_coordinates_baidu(address, api_key):
    """使用百度地图API查询"""
    url = "http://api.map.baidu.com/geocoding/v3/"
    params = {
        "address": address,
        "output": "json",
        "ak": api_key,
        "city": "深圳市"
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        if data["status"] == 0:
            result = data["result"]["location"]
            return result["lng"], result["lat"]
    except Exception as e:
        print(f"  [Baidu] Error: {e}")
    return None, None

def get_coordinates_gaode(address, api_key):
    """使用高德地图API查询"""
    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "address": address,
        "key": api_key,
        "city": "深圳"
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        if data["status"] == "1" and int(data["count"]) > 0:
            # 高德返回格式为 "lng,lat"
            location = data["geocodes"][0]["location"]
            lng, lat = location.split(",")
            return float(lng), float(lat)
    except Exception as e:
        print(f"  [Gaode] Error: {e}")
    return None, None

def get_coordinates_nominatim(address):
    """使用 OpenStreetMap Nominatim API (免费，无需Key，但在国内可能不稳定)"""
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'LogisticsAgent/1.0'}
    params = {
        'q': address,
        'format': 'json',
        'limit': 1
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data and len(data) > 0:
            return float(data[0]['lon']), float(data[0]['lat'])
    except Exception as e:
        print(f"  [Nominatim] Error: {e}")
    return None, None

def main():
    input_file = 'jd_warehouses_shenzhen.csv'

    print(f"读取文件: {input_file}")
    rows = []
    fieldnames = []

    try:
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            # Ensure columns exist
            if 'Longitude' not in fieldnames:
                fieldnames.extend(['Longitude', 'Latitude'])
            rows = list(reader)
    except FileNotFoundError:
        print(f"错误: 找不到文件 {input_file}")
        return

    print(f"共发现 {len(rows)} 条数据，开始查询经纬度...")

    success_count = 0

    for i, row in enumerate(rows):
        name = row.get('Name', 'Unknown')
        address = row.get('Address', '')

        # 如果已经有经纬度，跳过
        if row.get('Longitude') and row.get('Latitude'):
            print(f"[{i+1}/{len(rows)}] {name} 已有坐标，跳过")
            continue

        if not address:
            print(f"[{i+1}/{len(rows)}] {name} 地址为空，跳过")
            continue

        print(f"[{i+1}/{len(rows)}] 查询: {name}...")
        lng, lat = None, None

        # 优先级: 百度 > 高德 > Nominatim
        if BAIDU_API_KEY:
            lng, lat = get_coordinates_baidu(address, BAIDU_API_KEY)
        elif GAODE_API_KEY:
            lng, lat = get_coordinates_gaode(address, GAODE_API_KEY)

        # 如果没有Key或查询失败，尝试Nominatim
        if not lng and not BAIDU_API_KEY and not GAODE_API_KEY:
            # 稍微简化地址以提高匹配率
            simple_address = address.split('号')[0] + '号' if '号' in address else address
            simple_address = simple_address.replace("广东", "") # 去掉省份可能有助于Nominatim
            lng, lat = get_coordinates_nominatim(simple_address)
            time.sleep(1.1) # 遵守速率限制

        if lng and lat:
            print(f"  -> 成功: {lng}, {lat}")
            row['Longitude'] = lng
            row['Latitude'] = lat
            success_count += 1
        else:
            print("  -> 未找到")

    # 写入结果
    print(f"写入结果到 {input_file}...")
    with open(input_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"完成! 成功更新 {success_count} 条数据的坐标。")

if __name__ == "__main__":
    main()
