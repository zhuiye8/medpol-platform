import requests
import json
from collections import defaultdict

# 1. 获取全量数据
print("正在获取全量财务数据...")
response = requests.post("http://ailianhuan.xyz:8333/financeDate/dataList")
data = response.json()

if data["code"] != "0000":
    print(f"错误: {data}")
    exit(1)

records = data["data"]
print(f"\n=== 数据总览 ===")
print(f"总记录数: {len(records)}")

# 2. 分析日期分布
dates = set()
for record in records:
    dates.add(record["keepDate"])
print(f"\n=== 日期分布 ===")
print(f"唯一日期数: {len(dates)}")
print(f"日期范围: {sorted(dates)}")

# 3. 分析财务类型
types = {}
type_mapping = {
    "01": "营业收入",
    "02": "利润总额",
    "03": "实现税金",
    "04": "入库税金",
    "05": "所得税",
    "06": "净利润",
    "07": "实现税金(扬州地区)",
    "08": "入库税金(扬州地区)"
}
for record in records:
    type_no = record["typeNo"]
    types[type_no] = types.get(type_no, 0) + 1

print(f"\n=== 财务类型分布 ===")
for type_no in sorted(types.keys()):
    type_name = type_mapping.get(type_no, "未知")
    print(f"{type_no} ({type_name}): {types[type_no]} 条记录")

# 4. 分析公司分布
companies = {}
levels = {}
for record in records:
    company_name = record["companyName"]
    company_level = record["level"]
    companies[company_name] = companies.get(company_name, 0) + 1
    levels[company_level] = levels.get(company_level, 0) + 1

print(f"\n=== 公司分布 ===")
print(f"唯一公司数: {len(companies)}")
print(f"公司列表:")
for company in sorted(companies.keys()):
    print(f"  - {company}: {companies[company]} 条记录")

print(f"\n=== 公司层级分布 ===")
for level in sorted(levels.keys()):
    level_name = "一级" if level == "0" else "二级"
    print(f"{level_name} (level={level}): {levels[level]} 条记录")

# 5. 按月统计数据量
monthly_stats = defaultdict(lambda: {"total": 0, "companies": set(), "types": set()})
for record in records:
    keep_date = record["keepDate"]
    monthly_stats[keep_date]["total"] += 1
    monthly_stats[keep_date]["companies"].add(record["companyName"])
    monthly_stats[keep_date]["types"].add(record["typeNo"])

print(f"\n=== 按月数据统计 ===")
for date in sorted(monthly_stats.keys()):
    stats = monthly_stats[date]
    print(f"{date}: {stats['total']} 条记录, {len(stats['companies'])} 个公司, {len(stats['types'])} 种类型")

# 6. 测试单月数据
print(f"\n=== 测试按月查询 ===")
test_date = "2024-03-01"
response2 = requests.post(f"http://ailianhuan.xyz:8333/financeDate/dataList?keepDate={test_date}")
data2 = response2.json()
if data2["code"] == "0000":
    print(f"查询 keepDate={test_date}: {len(data2['data'])} 条记录")
else:
    print(f"查询失败: {data2}")

# 7. 示例数据
print(f"\n=== 示例数据（第一条记录）===")
print(json.dumps(records[0], indent=2, ensure_ascii=False))

print("\n=== 数据字段说明 ===")
sample_record = records[0]
for key in sample_record.keys():
    value_type = type(sample_record[key]).__name__
    print(f"{key}: {value_type} - {sample_record.get(key, 'N/A')}")
