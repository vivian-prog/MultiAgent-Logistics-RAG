import requests
import csv
import time
import re

# 目标URL
URL = "https://www.ckuaidi.cn/jingdong/shenzhenshi.php"

# 模拟浏览器Header
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

def get_coordinates(address):
    """
    根据地址获取经纬度。
    注意：原网站HTML中不包含具体的网点经纬度（只有默认的中心点）。
    要获取准确的经纬度，需要调用地图API（如百度地图、高德地图）。

    此处为示例代码，如果拥有百度地图API Key (AK)，可以取消注释并填入AK。
    """
    # 百度地图API示例 (需要申请AK)
    # ak = "YOUR_BAIDU_MAP_API_KEY"
    # url = "http://api.map.baidu.com/geocoding/v3/"
    # params = {
    #     "address": address,
    #     "output": "json",
    #     "ak": ak,
    #     "city": "深圳市"
    # }
    # try:
    #     response = requests.get(url, params=params)
    #     data = response.json()
    #     if data["status"] == 0:
    #         lng = data["result"]["location"]["lng"]
    #         lat = data["result"]["location"]["lat"]
    #         return lng, lat
    # except Exception as e:
    #     print(f"Geocoding error: {e}")

    return "", ""  # 如果没有API Key，返回空值

def scrape_jd_warehouses():
    print(f"正在爬取页面: {URL}")
    try:
        response = requests.get(URL, headers=HEADERS)
        response.raise_for_status()
        response.encoding = 'utf-8'
        html_content = response.text
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return

    # 使用正则表达式提取信息
    # 匹配模式：
    # <a class="title" ...>(名称)</a>
    # 地址：(地址)<

    # 查找所有 content-item 块
    item_pattern = re.compile(r'<div class="content-item">.*?</div></div></div></div>', re.DOTALL)
    items = item_pattern.findall(html_content)

    print(f"找到 {len(items)} 个网点信息 (当前页面)")

    results = []

    for item_html in items:
        # 提取名称
        name_match = re.search(r'<a class="title"[^>]*>(.*?)</a>', item_html)
        name = name_match.group(1).strip() if name_match else "未知名称"

        # 提取地址
        # 地址：广东深圳市罗湖区...<a
        address_match = re.search(r'地址：(.*?)(?:<a|<img|<\/ul)', item_html)
        address = address_match.group(1).strip() if address_match else "未知地址"

        # 提取电话
        phone_match = re.search(r'查询电话：(.*?)(?:<|\s)', item_html)
        phone = phone_match.group(1).strip() if phone_match else "未知电话"

        print(f"正在处理: {name}")

        # 尝试获取经纬度 (需要配置API)
        lng, lat = get_coordinates(address)

        results.append({
            "Name": name,
            "Address": address,
            "Phone": phone,
            "Longitude": lng,
            "Latitude": lat
        })

    # 保存到CSV
    filename = "jd_warehouses_shenzhen.csv"
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = ["Name", "Address", "Phone", "Longitude", "Latitude"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(results)

    print(f"爬取完成，结果已保存至 {filename}")

if __name__ == "__main__":
    scrape_jd_warehouses()
