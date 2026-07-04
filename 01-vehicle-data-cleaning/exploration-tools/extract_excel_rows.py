"""
逐行提取Excel表格内容的脚本
Extract content from Excel file row by row
"""

import pandas as pd
import os


def extract_excel_rows(input_path, output_path=None):
    """
    逐行提取Excel表格内容
    Extract Excel content row by row
    
    参数:
        input_path: 输入的Excel文件路径
        output_path: 输出文件路径（可选，默认保存为txt文件）
    """
    print(f"{'='*80}")
    print(f"开始读取文件: {input_path}")
    print(f"{'='*80}\n")
    
    # 读取Excel文件（不指定header，保留所有原始行）
    try:
        df = pd.read_excel(input_path, header=None)
        print(f"✓ 成功读取文件")
        print(f"  总行数: {len(df)}")
        print(f"  总列数: {len(df.columns)}")
        print(f"\n{'='*80}")
        
        # 如果没有指定输出路径，创建默认输出文件
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_dir = os.path.dirname(input_path)
            output_path = os.path.join(output_dir, f"{base_name}_extracted.txt")
        
        # 打开输出文件
        with open(output_path, 'w', encoding='utf-8') as f:
            # 逐行处理
            for idx, row in df.iterrows():
                row_number = idx + 1
                
                # 打印到控制台
                print(f"\n第 {row_number} 行:")
                print("-" * 80)
                
                # 写入文件
                f.write(f"\n{'='*80}\n")
                f.write(f"第 {row_number} 行:\n")
                f.write(f"{'-'*80}\n")
                
                # 遍历该行的每一列
                for col_idx, value in enumerate(row):
                    col_letter = chr(65 + col_idx) if col_idx < 26 else f"Col{col_idx+1}"
                    
                    # 处理空值
                    if pd.isna(value):
                        display_value = "[空值]"
                    else:
                        display_value = str(value)
                    
                    # 打印到控制台
                    print(f"  列 {col_letter} ({col_idx+1}): {display_value}")
                    
                    # 写入文件
                    f.write(f"  列 {col_letter} ({col_idx+1}): {display_value}\n")
                
                # 每处理100行显示一次进度
                if row_number % 100 == 0:
                    print(f"\n>>> 已处理 {row_number}/{len(df)} 行...")
        
        print(f"\n{'='*80}")
        print(f"✓ 提取完成！")
        print(f"  总共处理: {len(df)} 行")
        print(f"  结果保存到: {output_path}")
        print(f"{'='*80}")
        
        return df
        
    except Exception as e:
        print(f"✗ 读取文件时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def extract_excel_to_csv(input_path, output_csv=None):
    """
    将Excel内容提取并保存为CSV文件
    Extract Excel content and save as CSV
    
    参数:
        input_path: 输入的Excel文件路径
        output_csv: 输出CSV文件路径（可选）
    """
    print(f"{'='*80}")
    print(f"开始读取并转换为CSV: {input_path}")
    print(f"{'='*80}\n")
    
    try:
        # 读取Excel文件
        df = pd.read_excel(input_path, header=None)
        print(f"✓ 成功读取文件")
        print(f"  总行数: {len(df)}")
        print(f"  总列数: {len(df.columns)}")
        
        # 如果没有指定输出路径，创建默认输出文件
        if output_csv is None:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_dir = os.path.dirname(input_path)
            output_csv = os.path.join(output_dir, f"{base_name}_extracted.csv")
        
        # 保存为CSV
        df.to_csv(output_csv, index=False, header=False, encoding='utf-8-sig')
        
        print(f"\n{'='*80}")
        print(f"✓ 转换完成！")
        print(f"  CSV文件保存到: {output_csv}")
        print(f"{'='*80}")
        
        return df
        
    except Exception as e:
        print(f"✗ 处理文件时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    import argparse
    ap = argparse.ArgumentParser(description="Extract Excel rows to TXT/CSV for exploration")
    ap.add_argument("--input", required=True, help="Path to input .xlsx file")
    args = ap.parse_args()
    # 设置Excel文件路径 - 通过命令行参数注入
    input_path = args.input
    
    # 检查文件是否存在
    if not os.path.exists(input_path):
        print(f"✗ 文件不存在: {input_path}")
        print("请检查文件路径是否正确！")
        return
    
    print("请选择提取方式:")
    print("1. 提取为文本文件 (txt) - 详细格式，每行每列都清晰标注")
    print("2. 提取为CSV文件 - 保持原始表格结构")
    print("3. 两种格式都生成")
    
    choice = input("\n请输入选择 (1/2/3，默认为3): ").strip()
    
    if not choice:
        choice = "3"
    
    print("\n")
    
    if choice == "1":
        # 只提取为文本文件
        extract_excel_rows(input_path)
    elif choice == "2":
        # 只提取为CSV文件
        extract_excel_to_csv(input_path)
    elif choice == "3":
        # 两种都生成
        extract_excel_rows(input_path)
        print("\n")
        extract_excel_to_csv(input_path)
    else:
        print("✗ 无效的选择！")


if __name__ == "__main__":
    main()
