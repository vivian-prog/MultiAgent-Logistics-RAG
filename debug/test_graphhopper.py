import requests
url = 'http://127.0.0.1:8989/route?point=22.9934,113.3278&point=22.8200,113.1175&profile=car&layer=OpenStreetMap'
response = requests.get(url)  
# 新增调试代码1：打印HTTP响应状态码（判断请求是否成功）
print("HTTP响应状态码：", response.status_code)
# 新增调试代码2：打印完整的JSON响应（查看服务端返回的真实数据）
print("完整JSON响应：", response.json())
info = response.json()['paths'][0]
print("=================================================================================")
print("path的info响应：",info)  # 获取json
# print(info['distance'])  # 获取路径距离,单位为米
# print(info['time'])  # 获取路径时间，单位为毫秒
print("=================================================================================")
print(round(info['distance']/1000,2))  # 单位转为千米
print(round(info['time']/(60*1000),0))  # 单位转为分钟