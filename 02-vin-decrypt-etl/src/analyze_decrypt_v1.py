#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析多个解密结果"""

import csv
import json
import os


def analyze_file(csv_path):
    """输出单个解密结果的统计信息"""

    print("=" * 80)
    print(f"解密结果统计分析 - {os.path.basename(csv_path)}")
    print("=" * 80)

    total_records = 0
    ret_values = {'0': 0, '-1': 0, '空': 0, '其他': 0}
    has_monthlist = 0
    response_empty = 0
    has_乱码 = 0

    if not os.path.exists(csv_path):
        print(f"错误：找不到文件 {csv_path}")
        return

    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        sanitized_lines = (line.replace('\x00', '') for line in f)
        reader = csv.DictReader(sanitized_lines)

        for row in reader:
            total_records += 1
            response_info = None
            for key in ['responseInfo_解密', 'callSupplierResponseInfo_解密']:
                if key in row and row[key]:
                    response_info = row[key]
                    break

            # 如果解析表中没有解密后的JSON，尝试直接读取ret列
            if response_info is None:
                ret_raw = row.get('ret')
                if ret_raw is not None:
                    try:
                        ret_val = int(ret_raw)
                    except (TypeError, ValueError):
                        ret_val = ret_raw

                    if ret_val == 0:
                        ret_values['0'] += 1
                    elif ret_val == -1:
                        ret_values['-1'] += 1
                    else:
                        ret_values['其他'] += 1
                    continue
                else:
                    response_empty += 1
                    ret_values['空'] += 1
                    continue

            if not response_info or response_info == '(空)':
                response_empty += 1
                ret_values['空'] += 1
                continue

            if response_info.startswith('W]Q') or '\t' in response_info[:10]:
                has_乱码 += 1

            try:
                cleaned = response_info
                if '{' in response_info:
                    cleaned = response_info[response_info.index('{'):]

                data = json.loads(cleaned)

                if 'data' in data:
                    ret = data['data'].get('ret', 'N/A')

                    if ret == 0:
                        ret_values['0'] += 1
                        if 'monthList' in data['data']:
                            has_monthlist += 1
                            print(f"\n✅ 记录 {row.get('行号', 'N/A')}: ret=0, 有monthList数据")
                            print(f"   序列号: {row.get('序列号', 'N/A')}")

                    elif ret == -1:
                        ret_values['-1'] += 1
                    else:
                        ret_values['其他'] += 1
                        print(f"\n⚠️  记录 {row.get('行号', 'N/A')}: ret={ret} (未知值)")
            except Exception:
                pass

    if total_records == 0:
        print("没有数据记录，跳过统计\n")
        return

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

    print("\n")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Analyze decrypt result quality")
    ap.add_argument("--input-dir", required=True, help="Directory containing *_call-2025-06_分类.csv files")
    args = ap.parse_args()

    base_dir = args.input_dir
    file_stems = [
        "117cdp5_call-2025-06",
        "593cdp4_call-2025-06",
        "616cdp1_call-2025-06",
        "627cdp23_call-2025-06",
    ]

    for name in file_stems:
        csv_path = os.path.join(base_dir, f"{name}_分类.csv")
        if not os.path.exists(csv_path):
            # 回退到解密后的明细
            csv_path = os.path.join(base_dir, f"{name}_解密.csv")
            if not os.path.exists(csv_path):
                print(f"跳过 {name}: 找不到分类或解密后的CSV\n")
                continue

        analyze_file(csv_path)


if __name__ == "__main__":
    main()
