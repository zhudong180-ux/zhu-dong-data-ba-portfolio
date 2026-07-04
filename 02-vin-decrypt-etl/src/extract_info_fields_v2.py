#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本功能：从日志文件中提取四个info字段的信息
作者：GitHub Copilot
创建时间：2025年10月31日
"""

import json
import re
import os
from datetime import datetime


def extract_info_fields(log_file_path, output_file_path):
    """
    从日志文件中提取四个info字段并保存到新文件
    
    Args:
        log_file_path: 输入的日志文件路径
        output_file_path: 输出文件路径
    """
    
    # 要提取的四个字段
    target_fields = [
        'callSupplierRequestInfo',
        'callSupplierResponseInfo', 
        'requestInfo',
        'responseInfo'
    ]
    
    extracted_data = []
    line_count = 0
    success_count = 0
    
    print(f"开始处理日志文件: {log_file_path}")
    
    try:
        with open(log_file_path, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                line_count += 1
                line = line.strip()
                
                if not line:
                    continue
                
                try:
                    # 尝试找到JSON部分（从第一个{开始到最后一个}）
                    json_match = re.search(r'\{.*\}', line)
                    if json_match:
                        json_str = json_match.group()
                        
                        # 解析JSON
                        data = json.loads(json_str)
                        
                        # 提取目标字段
                        record = {
                            'line_number': line_num,
                            'timestamp': data.get('requestTime', ''),
                            'seqNo': data.get('seqNo', ''),
                        }
                        
                        # 添加四个info字段
                        for field in target_fields:
                            record[field] = data.get(field, '')
                        
                        extracted_data.append(record)
                        success_count += 1
                        
                        if success_count % 100 == 0:
                            print(f"已处理 {success_count} 条记录...")
                            
                except json.JSONDecodeError as e:
                    print(f"第 {line_num} 行JSON解析失败: {e}")
                    continue
                except Exception as e:
                    print(f"第 {line_num} 行处理失败: {e}")
                    continue
    
    except FileNotFoundError:
        print(f"错误：找不到文件 {log_file_path}")
        return False
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return False
    
    # 保存提取的数据
    try:
        with open(output_file_path, 'w', encoding='utf-8') as output_file:
            # 写入文件头
            output_file.write("=" * 80 + "\n")
            output_file.write("高速运力数据 - 四个Info字段提取结果\n")
            output_file.write(f"提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            output_file.write(f"源文件: {os.path.basename(log_file_path)}\n")
            output_file.write(f"总处理行数: {line_count}\n")
            output_file.write(f"成功提取记录数: {success_count}\n")
            output_file.write("=" * 80 + "\n\n")
            
            # 写入每条记录
            for i, record in enumerate(extracted_data, 1):
                output_file.write(f"记录 {i:04d} (原文件第 {record['line_number']} 行)\n")
                output_file.write("-" * 60 + "\n")
                output_file.write(f"序列号 (seqNo): {record['seqNo']}\n")
                output_file.write(f"请求时间 (requestTime): {record['timestamp']}\n")
                output_file.write(f"\n")
                
                # 输出四个info字段
                for field in target_fields:
                    value = record[field]
                    if value:
                        output_file.write(f"{field}:\n")
                        # 如果内容很长，进行适当换行处理
                        if len(value) > 100:
                            # 每100个字符换行
                            wrapped_value = '\n'.join([value[i:i+100] for i in range(0, len(value), 100)])
                            output_file.write(f"{wrapped_value}\n")
                        else:
                            output_file.write(f"{value}\n")
                    else:
                        output_file.write(f"{field}: (空)\n")
                    output_file.write("\n")
                
                output_file.write("=" * 60 + "\n\n")
        
        print(f"提取完成！")
        print(f"总共处理了 {line_count} 行")
        print(f"成功提取了 {success_count} 条记录")
        print(f"结果已保存到: {output_file_path}")
        return True
        
    except Exception as e:
        print(f"保存文件时发生错误: {e}")
        return False


def create_csv_output(log_file_path, csv_output_path):
    """
    创建CSV格式的输出文件
    
    Args:
        log_file_path: 输入的日志文件路径
        csv_output_path: CSV输出文件路径
    """
    
    target_fields = [
        'callSupplierRequestInfo',
        'callSupplierResponseInfo', 
        'requestInfo',
        'responseInfo'
    ]
    
    extracted_data = []
    
    print(f"创建CSV格式输出...")
    
    try:
        with open(log_file_path, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                line = line.strip()
                
                if not line:
                    continue
                
                try:
                    json_match = re.search(r'\{.*\}', line)
                    if json_match:
                        json_str = json_match.group()
                        data = json.loads(json_str)
                        
                        record = [
                            line_num,
                            data.get('seqNo', ''),
                            data.get('requestTime', ''),
                            data.get('callSupplierRequestInfo', ''),
                            data.get('callSupplierResponseInfo', ''),
                            data.get('requestInfo', ''),
                            data.get('responseInfo', '')
                        ]
                        
                        extracted_data.append(record)
                            
                except:
                    continue
    
        # 保存CSV文件
        with open(csv_output_path, 'w', encoding='utf-8-sig') as csv_file:  # 使用utf-8-sig支持Excel
            # 写入CSV头部
            csv_file.write("行号,序列号,请求时间,callSupplierRequestInfo,callSupplierResponseInfo,requestInfo,responseInfo\n")
            
            # 写入数据行
            for record in extracted_data:
                # 对包含逗号的字段进行引号包装
                csv_record = []
                for field in record:
                    field_str = str(field)
                    if ',' in field_str or '"' in field_str:
                        # 转义引号并用引号包装
                        field_str = '"' + field_str.replace('"', '""') + '"'
                    csv_record.append(field_str)
                
                csv_file.write(','.join(csv_record) + '\n')
        
        print(f"CSV文件已保存到: {csv_output_path}")
        return True
        
    except Exception as e:
        print(f"创建CSV文件时发生错误: {e}")
        return False


def main():
    """主函数"""
    
    # 输入和输出文件路径 - 通过命令行参数注入
    import argparse
    ap = argparse.ArgumentParser(description="Extract info fields from highway capacity log")
    ap.add_argument("--input", required=True, help="Input log file path")
    ap.add_argument("--output-txt", required=True, help="Output txt path")
    ap.add_argument("--output-csv", required=True, help="Output csv path")
    args = ap.parse_args()

    input_file = args.input
    output_file = args.output_txt
    csv_output_file = args.output_csv
    
    print("高速运力数据Info字段提取工具")
    print("=" * 50)
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"错误：找不到输入文件 {input_file}")
        print("请确认文件路径是否正确")
        return
    
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"CSV文件: {csv_output_file}")
    print()
    
    # 提取数据并保存为文本格式
    success1 = extract_info_fields(input_file, output_file)
    
    # 创建CSV格式
    success2 = create_csv_output(input_file, csv_output_file)
    
    if success1 and success2:
        print("\n" + "=" * 50)
        print("所有任务完成！")
        print("已生成以下文件：")
        print(f"1. 详细文本格式: {output_file}")
        print(f"2. CSV格式: {csv_output_file}")
    else:
        print("\n处理过程中出现错误，请检查日志信息")


if __name__ == "__main__":
    main()