#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本功能：解密提取的四个info字段
解密流程：Base64解码 -> AES解密
作者：GitHub Copilot
创建时间：2025年10月31日
"""

import base64
import json
import csv
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


# AES密钥 - 严禁在生产环境硬编码,务必通过环境变量注入!
# 详见 README.md "安全说明" 章节
AES_KEY = os.environ.get("VIN_DECRYPT_KEY", "REPLACE_WITH_PRODUCTION_KEY").encode("utf-8")  # 16字节密钥(请通过环境变量注入)


def aes_decrypt_with_zero_iv(encrypted_data, key):
    """
    AES-CBC解密 - 零IV
    用于: callSupplierRequestInfo, responseInfo
    """
    try:
        iv = b'\x00' * 16
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted_data)
        
        # 尝试PKCS7 unpad
        try:
            decrypted = unpad(decrypted, AES.block_size)
        except:
            # 如果PKCS7失败，尝试去除零填充
            decrypted = decrypted.rstrip(b'\x00')
        
        # 先尝试用UTF-8解码
        result = decrypted.decode('utf-8', errors='ignore')
        
        # 强制清理：找到第一个 { 字符
        if '{' in result:
            result = result[result.index('{'):]
        elif '[' in result:
            result = result[result.index('['):]
        else:
            # 如果没有JSON字符，可能整个都是乱码，返回原始尝试
            return result.strip()
        
        return result
    except Exception as e:
        return None


def aes_decrypt_with_key_iv(encrypted_data, key):
    """
    AES-CBC解密 - 密钥作为IV
    用于: callSupplierResponseInfo, requestInfo
    """
    try:
        cipher = AES.new(key, AES.MODE_CBC, key)  # 密钥本身作为IV
        decrypted = cipher.decrypt(encrypted_data)
        
        # 尝试PKCS7 unpad
        try:
            decrypted = unpad(decrypted, AES.block_size)
        except:
            # 如果PKCS7失败，尝试去除零填充
            decrypted = decrypted.rstrip(b'\x00')
        
        # 先尝试用UTF-8解码
        result = decrypted.decode('utf-8', errors='ignore')
        
        # 强制清理：找到第一个 { 字符
        if '{' in result:
            result = result[result.index('{'):]
        elif '[' in result:
            result = result[result.index('['):]
        else:
            # 如果没有JSON字符，可能整个都是乱码，返回原始尝试
            return result.strip()
        
        return result
    except Exception as e:
        return None


def decrypt_field(field_name, encrypted_text, debug=False):
    """
    解密单个字段 - 根据字段名选择正确的IV
    
    Args:
        field_name: 字段名称
        encrypted_text: 加密的文本（Base64编码）
        debug: 是否输出调试信息
    
    Returns:
        解密后的文本，如果失败返回原文或错误信息
    """
    if not encrypted_text or encrypted_text == '(空)':
        return encrypted_text
    
    try:
        # 移除可能的换行符和空格
        encrypted_text = encrypted_text.replace('\n', '').replace('\r', '').strip()
        
        if debug:
            print(f"\n调试 - {field_name}:")
            print(f"  Base64长度: {len(encrypted_text)}")
        
        # Step 1: Base64解码
        encrypted_bytes = base64.b64decode(encrypted_text)
        
        if debug:
            print(f"  解码后字节长度: {len(encrypted_bytes)}")
            print(f"  前16字节(hex): {encrypted_bytes[:16].hex()}")
        
        # Step 2: 根据字段名选择解密方法
        if field_name in ['callSupplierRequestInfo', 'responseInfo']:
            # 使用零IV
            decrypted_text = aes_decrypt_with_zero_iv(encrypted_bytes, AES_KEY)
            iv_type = "零IV"
        else:  # callSupplierResponseInfo, requestInfo
            # 使用密钥作为IV
            decrypted_text = aes_decrypt_with_key_iv(encrypted_bytes, AES_KEY)
            iv_type = "密钥IV"
        
        if decrypted_text:
            if debug:
                print(f"  ✓ 解密成功! (使用{iv_type})")
                print(f"  长度: {len(decrypted_text)}")
                print(f"  内容预览: {decrypted_text[:200]}")
            return decrypted_text
        else:
            error_msg = f"[解密失败: {field_name}]"
            if debug:
                print(f"  ✗ 解密失败")
            return error_msg
            
    except base64.binascii.Error as e:
        error_msg = f"[Base64解码失败: {e}]"
        if debug:
            print(f"  ✗ {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"[解密错误: {e}]"
        if debug:
            print(f"  ✗ {error_msg}")
        return error_msg


def process_record(record_data):
    """
    处理单条记录（用于多线程）
    
    Args:
        record_data: 记录数据字典
    
    Returns:
        解密后的记录
    """
    result = {
        'line_number': record_data['line_number'],
        'seqNo': record_data['seqNo'],
        'requestTime': record_data['requestTime'],
    }
    
    # 解密四个info字段
    fields_to_decrypt = [
        'callSupplierRequestInfo',
        'callSupplierResponseInfo',
        'requestInfo',
        'responseInfo'
    ]
    
    for field in fields_to_decrypt:
        encrypted_value = record_data.get(field, '')
        decrypted_value = decrypt_field(field, encrypted_value)
        result[field + '_decrypted'] = decrypted_value
        result[field + '_original'] = encrypted_value
    
    return result


def parse_txt_file(txt_file_path):
    """
    解析TXT文件提取数据
    
    Args:
        txt_file_path: TXT文件路径
    
    Returns:
        记录列表
    """
    records = []
    current_record = {}
    current_field = None
    field_content = []
    
    with open(txt_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            
            # 检测记录开始
            if line.startswith('记录 '):
                if current_record:
                    records.append(current_record)
                current_record = {}
                current_field = None
                field_content = []
            
            # 检测序列号
            elif line.startswith('序列号 (seqNo): '):
                current_record['seqNo'] = line.split(': ', 1)[1]
            
            # 检测请求时间
            elif line.startswith('请求时间 (requestTime): '):
                current_record['requestTime'] = line.split(': ', 1)[1]
            
            # 检测字段开始
            elif line.endswith('RequestInfo:') or line.endswith('ResponseInfo:') or line.endswith('requestInfo:') or line.endswith('responseInfo:'):
                # 保存之前的字段
                if current_field:
                    current_record[current_field] = ''.join(field_content)
                
                current_field = line.rstrip(':')
                field_content = []
            
            # 字段内容
            elif current_field and line and not line.startswith('=') and not line.startswith('-'):
                field_content.append(line)
        
        # 保存最后一条记录
        if current_field:
            current_record[current_field] = ''.join(field_content)
        if current_record:
            records.append(current_record)
    
    # 规范化字段名
    for record in records:
        record['line_number'] = len(records)  # 临时使用
        for old_key in list(record.keys()):
            if 'RequestInfo' in old_key or 'ResponseInfo' in old_key or 'requestInfo' in old_key or 'responseInfo' in old_key:
                new_key = old_key.replace('RequestInfo', 'RequestInfo').replace('ResponseInfo', 'ResponseInfo')
                if old_key != new_key:
                    record[new_key] = record.pop(old_key)
    
    return records


def read_csv_file(csv_file_path):
    """
    读取CSV文件
    
    Args:
        csv_file_path: CSV文件路径
    
    Returns:
        记录列表
    """
    records = []
    
    with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                'line_number': row['行号'],
                'seqNo': row['序列号'],
                'requestTime': row['请求时间'],
                'callSupplierRequestInfo': row['callSupplierRequestInfo'],
                'callSupplierResponseInfo': row['callSupplierResponseInfo'],
                'requestInfo': row['requestInfo'],
                'responseInfo': row['responseInfo']
            })
    
    return records


def decrypt_all_records(input_file, output_txt, output_csv, use_threading=True, max_workers=8):
    """
    解密所有记录
    
    Args:
        input_file: 输入文件路径（CSV或TXT）
        output_txt: 输出TXT文件路径
        output_csv: 输出CSV文件路径
        use_threading: 是否使用多线程
        max_workers: 最大线程数
    """
    
    print("=" * 60)
    print("高速运力数据 - Info字段解密工具")
    print("=" * 60)
    print(f"AES密钥: {AES_KEY.decode('utf-8')}")
    print(f"算法: AES-128-CBC")
    print(f"IV配置:")
    print(f"  - callSupplierRequestInfo: 零IV")
    print(f"  - callSupplierResponseInfo: 密钥作为IV")
    print(f"  - requestInfo: 密钥作为IV")
    print(f"  - responseInfo: 零IV")
    print(f"输入文件: {input_file}")
    print(f"多线程: {'是' if use_threading else '否'} (线程数: {max_workers})" if use_threading else "")
    print()
    
    # 读取数据
    print("读取输入文件...")
    if input_file.endswith('.csv'):
        records = read_csv_file(input_file)
    else:
        records = parse_txt_file(input_file)
    
    print(f"共读取 {len(records)} 条记录")
    print()
    
    # 解密数据
    print("开始解密...")
    decrypted_records = []
    
    if use_threading:
        # 使用多线程处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_record, record): i for i, record in enumerate(records)}
            
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    result['line_number'] = idx + 1
                    decrypted_records.append(result)
                    
                    if len(decrypted_records) % 100 == 0:
                        print(f"已处理 {len(decrypted_records)}/{len(records)} 条记录...")
                except Exception as e:
                    print(f"记录 {idx+1} 处理失败: {e}")
    else:
        # 单线程处理
        for i, record in enumerate(records, 1):
            try:
                result = process_record(record)
                result['line_number'] = i
                decrypted_records.append(result)
                
                if i % 100 == 0:
                    print(f"已处理 {i}/{len(records)} 条记录...")
            except Exception as e:
                print(f"记录 {i} 处理失败: {e}")
    
    # 按行号排序
    decrypted_records.sort(key=lambda x: x['line_number'])
    
    print(f"解密完成！成功处理 {len(decrypted_records)} 条记录")
    print()
    
    # 保存为TXT格式
    print("保存TXT格式...")
    save_as_txt(decrypted_records, output_txt)
    
    # 保存为CSV格式
    print("保存CSV格式...")
    save_as_csv(decrypted_records, output_csv)
    
    print()
    print("=" * 60)
    print("所有任务完成！")
    print(f"TXT输出: {output_txt}")
    print(f"CSV输出: {output_csv}")
    print("=" * 60)


def save_as_txt(records, output_file):
    """保存为TXT格式"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("高速运力数据 - 解密后的Info字段\n")
        f.write(f"解密时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"AES密钥: {AES_KEY.decode('utf-8')}\n")
        f.write(f"总记录数: {len(records)}\n")
        f.write("=" * 80 + "\n\n")
        
        for i, record in enumerate(records, 1):
            f.write(f"记录 {i:04d}\n")
            f.write("-" * 60 + "\n")
            f.write(f"序列号: {record['seqNo']}\n")
            f.write(f"请求时间: {record['requestTime']}\n")
            f.write("\n")
            
            fields = [
                ('callSupplierRequestInfo', 'callSupplierRequestInfo_decrypted'),
                ('callSupplierResponseInfo', 'callSupplierResponseInfo_decrypted'),
                ('requestInfo', 'requestInfo_decrypted'),
                ('responseInfo', 'responseInfo_decrypted')
            ]
            
            for original_field, decrypted_field in fields:
                f.write(f"{original_field} [解密后]:\n")
                decrypted_value = record.get(decrypted_field, '')
                if decrypted_value:
                    # 美化JSON输出
                    try:
                        json_obj = json.loads(decrypted_value)
                        pretty_json = json.dumps(json_obj, ensure_ascii=False, indent=2)
                        f.write(pretty_json + "\n")
                    except:
                        f.write(decrypted_value + "\n")
                else:
                    f.write("(空)\n")
                f.write("\n")
            
            f.write("=" * 60 + "\n\n")


def save_as_csv(records, output_file):
    """保存为CSV格式"""
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = [
            '行号', '序列号', '请求时间',
            'callSupplierRequestInfo_解密',
            'callSupplierResponseInfo_解密',
            'requestInfo_解密',
            'responseInfo_解密'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for record in records:
            writer.writerow({
                '行号': record['line_number'],
                '序列号': record['seqNo'],
                '请求时间': record['requestTime'],
                'callSupplierRequestInfo_解密': record.get('callSupplierRequestInfo_decrypted', ''),
                'callSupplierResponseInfo_解密': record.get('callSupplierResponseInfo_decrypted', ''),
                'requestInfo_解密': record.get('requestInfo_decrypted', ''),
                'responseInfo_解密': record.get('responseInfo_decrypted', '')
            })


def main():
    """主函数"""

    import argparse
    ap = argparse.ArgumentParser(description="Decrypt VIN info fields (v1 batch)")
    ap.add_argument("--input-dir", required=True, help="Directory containing input *_call-2025-06.{csv,txt} files")
    args = ap.parse_args()

    base_dir = args.input_dir
    file_stems = [
        "117cdp5_call-2025-06",
        "593cdp4_call-2025-06",
        "616cdp1_call-2025-06",
        "627cdp23_call-2025-06",
    ]

    for name in file_stems:
        csv_path = os.path.join(base_dir, f"{name}.csv")
        txt_path = os.path.join(base_dir, f"{name}.txt")

        if os.path.exists(csv_path):
            input_file = csv_path
        elif os.path.exists(txt_path):
            input_file = txt_path
        else:
            print(f"跳过 {name}: 找不到对应的CSV或TXT文件")
            continue

        output_txt = os.path.join(base_dir, f"{name}_解密.txt")
        output_csv = os.path.join(base_dir, f"{name}_解密.csv")

        print("\n" + "=" * 80)
        print(f"开始处理: {name}")
        print("=" * 80)

        try:
            decrypt_all_records(
                input_file=input_file,
                output_txt=output_txt,
                output_csv=output_csv,
                use_threading=True,
                max_workers=16,
            )
        except Exception as e:
            print(f"处理 {name} 时发生错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
