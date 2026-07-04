#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析解密结果"""

import csv
import json
import re

csv_file = "解密后的Info字段数据.csv"

print("=" * 80)
print("解密结果统计分析")
print("=" * 80)

# 统计数据
total_records = 0
ret_values = {'0': 0, '-1': 0, '空': 0, '其他': 0}
has_monthlist = 0
response_empty = 0
has_乱码 = 0

with open(csv_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    
    for row in reader:
        total_records += 1
        response_info = row['responseInfo_解密']
        
        # 检查是否为空
        if not response_info or response_info == '(空)':
            response_empty += 1
            ret_values['空'] += 1
            continue
        
        # 检查是否有乱码
        if response_info.startswith('W]Q') or '\t' in response_info[:10]:
            has_乱码 += 1
        
        # 尝试解析ret值
        try:
            # 清理可能的乱码前缀
            cleaned = response_info
            if '{' in response_info:
                cleaned = response_info[response_info.index('{'):]
            
            data = json.loads(cleaned)
            
            if 'data' in data:
                ret = data['data'].get('ret', 'N/A')
                
                if ret == 0:
                    ret_values['0'] += 1
                    # 检查是否有monthList
                    if 'monthList' in data['data']:
                        has_monthlist += 1
                        print(f"\n✅ 记录 {row['行号']}: ret=0, 有monthList数据")
                        print(f"   序列号: {row['序列号']}")
                        
                elif ret == -1:
                    ret_values['-1'] += 1
                else:
                    ret_values['其他'] += 1
                    print(f"\n⚠️  记录 {row['行号']}: ret={ret} (未知值)")
        except:
            pass

print("\n" + "=" * 80)
print("统计结果")
print("=" * 80)
print(f"总记录数: {total_records}")
print(f"\nresponseInfo 状态:")
print(f"  - 空值: {response_empty} ({response_empty/total_records*100:.1f}%)")
print(f"  - ret = 0 (有数据): {ret_values['0']} ({ret_values['0']/total_records*100:.1f}%)")
print(f"  - ret = -1 (无数据): {ret_values['-1']} ({ret_values['-1']/total_records*100:.1f}%)")
print(f"  - ret = 其他: {ret_values['其他']}")
print(f"\n包含monthList的记录: {has_monthlist}")
print(f"检测到乱码前缀的记录: {has_乱码}")

print("\n" + "=" * 80)
print("结论:")
print("=" * 80)

if ret_values['0'] < 10:
    print("⚠️  有数据的记录太少！可能的原因：")
    print("   1. 这批车辆确实在2024年6-11月期间很少跑高速")
    print("   2. 解密方法可能需要调整")
    print("   3. 数据源本身就是这样的")
else:
    print("✅ 解密正常，数据分布合理")

if has_乱码 > 0:
    print(f"\n⚠️  发现 {has_乱码} 条记录有乱码前缀，需要清理")
