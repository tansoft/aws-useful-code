import csv
import random
from datetime import datetime, timedelta

# 数据选项
countries = ['中国', '美国', '日本', '韩国', '英国', '德国', '法国', '印度', '巴西', '澳大利亚']
devices = ['iPhone 15', 'iPhone 14', 'Samsung S24', 'Xiaomi 14', 'Huawei P60', 'OPPO Find X7', 'Vivo X100', 'Google Pixel 8']
actions = ['点击', '浏览', '收藏', '购买', '分享', '评论', '搜索']
preferences = ['科技', '时尚', '运动', '美食', '旅游', '音乐', '游戏', '阅读', '电影', '摄影']

data = []
for i in range(10000):
    user_id = f"U{100000 + i}"
    country = random.choice(countries)
    device = random.choice(devices)
    action = random.choice(actions)
    age = random.randint(18, 65)
    preference = random.choice(preferences)
    
    data.append([user_id, country, device, action, age, preference])

with open('demo_data.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['用户ID', '国家', '机型', '点击行为', '年龄', '偏好'])
    writer.writerows(data)

print("已生成 demo_data.csv，包含10000行数据")
