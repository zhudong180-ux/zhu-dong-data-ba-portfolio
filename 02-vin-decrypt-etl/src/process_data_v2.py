"""
高速运力数据处理脚本
功能：读取解密后的CSV文件，动态提取所有字段并分类
"""

import csv
import json
from collections import OrderedDict

def main():
    """主函数"""
    import argparse
    ap = argparse.ArgumentParser(description="Process decrypted data into flat CSV (v2)")
    ap.add_argument("--input-csv", required=True, help="Input decrypted CSV path")
    ap.add_argument("--output-csv", required=True, help="Output flat CSV path")
    args = ap.parse_args()
    input_csv = args.input_csv
    output_csv = args.output_csv
    
    print(f"正在读取文件: {input_csv}")
    print("正在分析数据结构...")
    
    # 第一步：扫描所有数据，收集所有可能的字段名
    all_fields = OrderedDict()
    basic_fields = ['行号', '序列号', '请求时间', '车牌号', '车牌颜色', '起保时间前推1年观察期', '起保时间']
    
    # 初始化基本字段
    for field in basic_fields:
        all_fields[field] = True
    
    with open(input_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, 1):
            # 从callSupplierResponseInfo中提取字段
            response_info = row.get('callSupplierResponseInfo_解密', '')
            
            if response_info:
                try:
                    resp_data = json.loads(response_info)
                    
                    # 检查result字段
                    if 'result' in resp_data and isinstance(resp_data['result'], dict):
                        result_data = resp_data['result']
                        
                        # 如果有info数组，遍历info中的所有字段
                        if 'info' in result_data and isinstance(result_data['info'], list):
                            for info_item in result_data['info']:
                                if isinstance(info_item, dict):
                                    for key in info_item.keys():
                                        if key not in ['routeStationToplist', 'routeCityToplist', 'encryptPlateNUmber']:
                                            all_fields[key] = True
                except:
                    pass
            
            # 每处理100行显示进度
            if row_num % 100 == 0:
                print(f"  已扫描 {row_num} 行...")
    
    # 转换为列表
    field_names = list(all_fields.keys())
    
    print(f"\n✓ 共发现 {len(field_names)} 个字段")
    print(f"字段列表: {', '.join(field_names[:20])}...")
    print("\n开始提取数据...")
    
    # 第二步：提取数据
    output_data = []
    processed_count = 0
    error_count = 0
    
    with open(input_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, 1):
            new_row = OrderedDict()
            
            # 初始化所有字段为空字符串
            for field in field_names:
                new_row[field] = ''
            
            # 提取基本信息
            new_row['行号'] = row.get('行号', '')
            new_row['序列号'] = row.get('序列号', '')
            new_row['请求时间'] = row.get('请求时间', '')
            
            # 从requestInfo中提取基本信息
            request_info = row.get('requestInfo_解密', '')
            if request_info:
                try:
                    req_data = json.loads(request_info)
                    new_row['车牌号'] = req_data.get('plateNumber', '')
                    new_row['车牌颜色'] = req_data.get('color', '')
                    new_row['起保时间前推1年观察期'] = req_data.get('startTime', '')
                    new_row['起保时间'] = req_data.get('endTime', '')
                except:
                    pass
            
            # 从callSupplierResponseInfo中提取运力数据
            response_info = row.get('callSupplierResponseInfo_解密', '')
            
            if response_info:
                try:
                    resp_data = json.loads(response_info)
                    
                    # 检查result字段
                    if 'result' in resp_data and isinstance(resp_data['result'], dict):
                        result_data = resp_data['result']
                        
                        # 如果ret=-1，说明没有数据
                        if result_data.get('ret') == -1:
                            pass
                        # 如果有info数组，提取第一个月份的数据（或者汇总所有月份）
                        elif 'info' in result_data and isinstance(result_data['info'], list) and len(result_data['info']) > 0:
                            # 这里提取第一个有数据的月份
                            for info_item in result_data['info']:
                                if isinstance(info_item, dict) and len(info_item) > 1:  # 排除只有encryptPlateNUmber的空记录
                                    for key, value in info_item.items():
                                        if key in field_names and key not in ['routeStationToplist', 'routeCityToplist', 'encryptPlateNUmber']:
                                            new_row[key] = value
                                    processed_count += 1
                                    break  # 只取第一个月份的数据
                    
                except Exception as e:
                    error_count += 1
            
            output_data.append(new_row)
            
            # 每处理100行显示进度
            if row_num % 100 == 0:
                print(f"  已处理 {row_num} 行...")
    
    # 写入输出CSV
    print(f"\n正在写入文件: {output_csv}")
    with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(output_data)
    
    print(f"\n✓ 处理完成！")
    print(f"  - 总记录数: {len(output_data)}")
    print(f"  - 成功提取运力数据: {processed_count}")
    print(f"  - 空数据记录: {len(output_data) - processed_count}")
    print(f"  - 解析错误: {error_count}")
    print(f"  - 输出字段数: {len(field_names)}")
    print(f"✓ 输出文件: {output_csv}")

if __name__ == "__main__":
    main()
