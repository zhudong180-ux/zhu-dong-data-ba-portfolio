"""
车型名称数据清洗脚本 - 完整版
第一步：读取原始数据并解析所有字段
第二步：按照规则重组：年份款型 + 品牌车系 + 动力单元 + 变速箱/驱动形式 + 配置等级
示例：2019款 起亚KX5 1.6T 自动两驱豪华版
"""

import pandas as pd
import re
import os
from datetime import datetime


def extract_year(text):
    """提取年款，如：2019款、2021款"""
    if pd.isna(text):
        return ""
    text = str(text)
    # 查找4位数字+款
    match = re.search(r'(\d{4})款', text)
    if match:
        return match.group(1) + "款"
    # 查找年款：2019这种格式
    match = re.search(r'年款[：:]\s*(\d{4})', text)
    if match:
        return match.group(1) + "款"
    return ""


def extract_brand_series(text):
    """
    提取品牌车系，如：起亚KX5、长城炮EV、福特锐界
    从 品牌>品牌_车系>详细信息 这种格式中提取
    """
    if pd.isna(text):
        return ""
    text = str(text)
    
    # 如果有>分隔符，优先从结构化数据中提取
    if '>' in text:
        parts = text.split('>')
        if len(parts) >= 2:
            # 取倒数第二部分，通常是：品牌_车系
            series_part = parts[-2].strip()
            if '_' in series_part:
                # 分割，如：长安凯程_凯程70 -> 提取车系名
                brand, car_series = series_part.split('_', 1)
                brand = brand.strip()
                car_series = car_series.strip()

                # 如果车系以品牌名开头，去掉重复部分
                if car_series.startswith(brand):
                    car_series = car_series[len(brand):].strip()

                # 去掉与品牌尾部重叠的前缀，避免“长安凯程凯程F70”这类重复
                max_overlap = min(len(brand), len(car_series))
                for overlap in range(max_overlap, 0, -1):
                    if brand.endswith(car_series[:overlap]):
                        car_series = car_series[overlap:].strip()
                        break

                if car_series:
                    return f"{brand}{car_series}"
                return brand
            else:
                return series_part
    
    # 如果没有>分隔符，从文本中提取
    return ""


def extract_power(text):
    """
    自动提取动力单元：排量、电动等任何格式
    """
    if pd.isna(text):
        return ""
    text = str(text)
    
    # 优先匹配：带小数点的排量（如 1.5T、2.0L、1.6GTDI）
    decimal_matches = re.findall(r'(\d\.\d+[A-Za-z]+)', text)
    if decimal_matches:
        return decimal_matches[-1].upper()

    # 匹配整数排量（如 2T、3L）。为避免把品牌数字当成排量，只取单个数字的排量。
    int_matches = re.findall(r'(?<!\d)([1-9][TL])(?!\d)', text)
    if int_matches:
        return int_matches[-1].upper()
    
    # 匹配中文动力描述
    match = re.search(r'(纯电动|插电式混合动力|混合动力)', text)
    if match:
        return match.group(1)
    
    return ""


def extract_transmission(text):
    """
    自动提取变速箱类型
    """
    if pd.isna(text):
        return ""
    text = str(text)
    
    # 电动车单速变速箱不显示
    if '电动车单速变速箱' in text or '单速变速箱' in text:
        return ""
    
    # 纯电动车不显示变速箱
    if '纯电动' in text:
        return ""
    
    # 匹配任何变速箱相关的词
    trans_patterns = [
        r'(手自一体)',
        r'(双离合)',
        r'(CVT)',
        r'(自动)',
        r'(手动)',
    ]
    
    for pattern in trans_patterns:
        match = re.search(pattern, text)
        if match:
            result = match.group(1)
            # 简化常见名称
            if '手自一体' in result:
                return '自动'
            return result.strip()
    
    return ""


def extract_drive(text):
    """
    自动提取驱动形式
    """
    if pd.isna(text):
        return ""
    text = str(text)
    
    # 匹配任何包含"驱"的词
    match = re.search(r'([\u4e00-\u9fa5]*驱)', text)
    if match:
        return match.group(1)
    
    return ""


def extract_config(text):
    """
    自动提取配置等级，提取文本末尾的配置信息
    """
    if pd.isna(text):
        return ""
    text = str(text)
    
    # 从最后的>分隔部分提取
    if '>' in text:
        text = text.split('>')[-1]
    
    # 移除年款、排量、变速箱、驱动等已识别部分
    temp_text = text
    temp_text = re.sub(r'\d{4}款', '', temp_text)
    temp_text = re.sub(r'年款[：:]\s*\d{4}', '', temp_text)
    temp_text = re.sub(r'\d+\.\d+[A-Z]+', '', temp_text, flags=re.IGNORECASE)
    temp_text = re.sub(r'\d+[TL]', '', temp_text)
    temp_text = re.sub(r'电动车单速变速箱', '', temp_text)
    temp_text = re.sub(r'单速变速箱', '', temp_text)
    temp_text = re.sub(r'[\u4e00-\u9fa5]*变速[\u4e00-\u9fa5]*', '', temp_text)
    temp_text = re.sub(r'手自一体|双离合|自动|手动|CVT', '', temp_text)
    temp_text = re.sub(r'两驱|前驱|后驱|四驱', '', temp_text)
    temp_text = re.sub(r'纯电动|插电式混合动力|混合动力|电动', '', temp_text)
    temp_text = re.sub(r'\d+座', '', temp_text)
    temp_text = re.sub(r'[><_]', ' ', temp_text)
    temp_text = re.sub(r'磷酸铁锂|三元锂', '', temp_text)
    temp_text = re.sub(r'[A-Z]+\d+[A-Z]*', '', temp_text)  # 移除车系代码
    temp_text = re.sub(r'[IVX]+$', '', temp_text)  # 移除末尾的罗马数字（如VI, V等）
    
    # 提取所有2个字以上的中文词组
    matches = re.findall(r'[\u4e00-\u9fa5]{2,}', temp_text)
    
    # 过滤掉常见的非配置词和品牌名
    config_keywords = ['版', '型', '款']
    brand_names = ['自由光', '牧马人', '指南者', '大切诺基', '汽车']  # 添加常见品牌/车系名，避免重复
    valid_matches = []
    
    for m in matches:
        # 跳过品牌名
        if m in brand_names:
            continue
        # 如果包含配置关键字，或者是常见配置词
        if any(kw in m for kw in config_keywords) or m in ['豪华', '舒适', '标准', '尊贵', '旗舰', '精英', '领先', '运动', '时尚', '智享', '越享']:
            # 移除末尾单个"国"字（国V/国VI标记残留）
            m = re.sub(r'国$', '', m)
            if len(m) >= 2:  # 确保处理后仍是有效配置名
                valid_matches.append(m)
    
    if valid_matches:
        # 取最后一个作为配置（通常配置在末尾）
        return valid_matches[-1]
    elif matches and len(matches) > 0:
        # 如果没有明显的配置词，取最后一个中文词组（但要排除品牌名）
        for m in reversed(matches):
            if m not in brand_names:
                # 移除末尾单个"国"字
                m = re.sub(r'国$', '', m)
                if len(m) >= 2:
                    return m
    
    return ""


def clean_vehicle_name_complete(vin, raw_info, year_col=""):
    """
    完整解析车型信息
    返回：字典包含所有提取的字段
    """
    # 合并所有文本信息
    full_text = str(raw_info) + " " + str(year_col)
    
    # 提取各个部分
    year = extract_year(full_text)
    brand_series = extract_brand_series(full_text)
    power = extract_power(full_text)
    transmission = extract_transmission(full_text)
    drive = extract_drive(full_text)
    config = extract_config(full_text)
    
    # 组合变速箱和驱动
    trans_drive = ""
    if transmission and drive:
        trans_drive = transmission + drive
    elif transmission:
        trans_drive = transmission
    elif drive:
        trans_drive = drive
    
    # 按规则组合：年份款型 + 品牌车系 + 动力单元 + 变速箱/驱动形式 + 配置等级
    parts = []
    if year:
        parts.append(year)
    if brand_series:
        parts.append(brand_series)
    if power:
        parts.append(power)
    if trans_drive:
        parts.append(trans_drive)
    if config:
        parts.append(config)
    
    cleaned_name = ' '.join(parts) if parts else full_text
    
    return {
        'VIN': vin,
        '原始信息': raw_info,
        '年款': year,
        '品牌车系': brand_series,
        '动力单元': power,
        '变速箱': transmission,
        '驱动形式': drive,
        '变速箱驱动': trans_drive,
        '配置等级': config,
        '清洗后车型名称': cleaned_name
    }


def process_file_1(input_path, output_path):
    """处理表格1（3列格式）"""
    print(f"\n{'='*60}")
    print(f"正在处理: {input_path}")
    print(f"{'='*60}")
    
    # 第一步：完整读取所有原始数据
    df_original = pd.read_excel(input_path, header=None)
    print(f"✓ 读取原始数据: {len(df_original)} 行 × {len(df_original.columns)} 列")
    
    # 第二步：逐行清洗，生成新列
    cleaned_names = []
    total = len(df_original)
    print(f"✓ 开始逐行处理...")
    
    for idx, row in df_original.iterrows():
        vin = row[0] if len(row) > 0 else ""
        raw_info = row[1] if len(row) > 1 else ""
        year_col = row[2] if len(row) > 2 else ""
        
        # 清洗车型名称
        result = clean_vehicle_name_complete(vin, raw_info, year_col)
        cleaned_names.append(result['清洗后车型名称'])
        
        # 显示进度
        if (idx + 1) % 100 == 0 or idx == 0:
            print(f"  处理进度: {idx + 1}/{total} 行")
    
    # 第三步：在原始数据后面添加新列"清洗后车型名称"
    df_original['清洗后车型名称'] = cleaned_names
    print(f"✓ 数据清洗完成，共 {len(df_original)} 行")
    
    # 第四步：写入新表格
    df_original.to_excel(output_path, index=False, header=False)
    print(f"✓ 保存到新表格: {output_path}")
    
    # 验证数据对齐
    print(f"\n{'='*60}")
    print(f"数据对齐验证（前3条）:")
    print(f"{'='*60}")
    for idx in range(min(3, len(df_original))):
        print(f"\n第 {idx+1} 条:")
        print(f"  VIN码: {df_original.iloc[idx, 0]}")
        print(f"  原始信息: {str(df_original.iloc[idx, 1])[:60]}...")
        print(f"  清洗后: {df_original.iloc[idx, -1]}")
        print("-"*60)


def process_file_2(input_path, output_path):
    """处理表格2（7列格式）"""
    print(f"\n{'='*60}")
    print(f"正在处理: {input_path}")
    print(f"{'='*60}")
    
    # 第一步：完整读取所有原始数据
    df_original = pd.read_excel(input_path, header=None)
    print(f"✓ 读取原始数据: {len(df_original)} 行 × {len(df_original.columns)} 列")
    
    # 第二步：逐行清洗，生成新列
    cleaned_names = []
    total = len(df_original)
    print(f"✓ 开始逐行处理...")
    
    for idx, row in df_original.iterrows():
        vin = row[0] if len(row) > 0 else ""
        raw_info = row[1] if len(row) > 1 else ""
        
        result = clean_vehicle_name_complete(vin, raw_info)
        cleaned_names.append(result['清洗后车型名称'])
        
        if (idx + 1) % 100 == 0 or idx == 0:
            print(f"  处理进度: {idx + 1}/{total} 行")
    
    # 第三步：在原始数据后面添加新列
    df_original['清洗后车型名称'] = cleaned_names
    print(f"✓ 数据清洗完成，共 {len(df_original)} 行")
    
    df_original.to_excel(output_path, index=False, header=False)
    print(f"✓ 保存到新表格: {output_path}")
    
    print(f"\n{'='*60}")
    print(f"数据对齐验证（前3条）:")
    print(f"{'='*60}")
    for idx in range(min(3, len(df_original))):
        print(f"\n第 {idx+1} 条:")
        print(f"  VIN码: {df_original.iloc[idx, 0]}")
        print(f"  原始信息: {str(df_original.iloc[idx, 1])[:60]}...")
        print(f"  清洗后: {df_original.iloc[idx, -1]}")
        print("-"*60)


def process_file_3(input_path, output_path):
    """处理表格3（11列格式）"""
    print(f"\n{'='*60}")
    print(f"正在处理: {input_path}")
    print(f"{'='*60}")
    
    # 第一步：完整读取所有原始数据
    df_original = pd.read_excel(input_path, header=None)
    print(f"✓ 读取原始数据: {len(df_original)} 行 × {len(df_original.columns)} 列")
    
    # 第二步：逐行清洗，生成新列
    cleaned_names = []
    total = len(df_original)
    print(f"✓ 开始逐行处理...")
    
    for idx, row in df_original.iterrows():
        vin = row[0] if len(row) > 0 else ""
        # 合并多列信息
        raw_info = " ".join([str(row[i]) for i in range(1, min(len(row), 11))])
        
        result = clean_vehicle_name_complete(vin, raw_info)
        cleaned_names.append(result['清洗后车型名称'])
        
        if (idx + 1) % 100 == 0 or idx == 0:
            print(f"  处理进度: {idx + 1}/{total} 行")
    
    # 第三步：在原始数据后面添加新列
    df_original['清洗后车型名称'] = cleaned_names
    print(f"✓ 数据清洗完成，共 {len(df_original)} 行")
    
    df_original.to_excel(output_path, index=False, header=False)
    print(f"✓ 保存到新表格: {output_path}")
    
    print(f"\n{'='*60}")
    print(f"数据对齐验证（前3条）:")
    print(f"{'='*60}")
    for idx in range(min(3, len(df_original))):
        print(f"\n第 {idx+1} 条:")
        print(f"  VIN码: {df_original.iloc[idx, 0]}")
        print(f"  清洗后: {df_original.iloc[idx, -1]}")
        print("-"*60)


def process_file_4(input_path, output_path):
    """处理表格4（10列格式）"""
    print(f"\n{'='*60}")
    print(f"正在处理: {input_path}")
    print(f"{'='*60}")
    
    # 第一步：完整读取所有原始数据
    df_original = pd.read_excel(input_path, header=None)
    print(f"✓ 读取原始数据: {len(df_original)} 行 × {len(df_original.columns)} 列")
    
    # 第二步：逐行清洗，生成新列
    cleaned_names = []
    total = len(df_original)
    print(f"✓ 开始逐行处理...")
    
    for idx, row in df_original.iterrows():
        vin = row[0] if len(row) > 0 else ""
        # 合并多列信息
        raw_info = " ".join([str(row[i]) for i in range(1, min(len(row), 10))])
        
        result = clean_vehicle_name_complete(vin, raw_info)
        cleaned_names.append(result['清洗后车型名称'])
        
        if (idx + 1) % 100 == 0 or idx == 0:
            print(f"  处理进度: {idx + 1}/{total} 行")
    
    # 第三步：在原始数据后面添加新列
    df_original['清洗后车型名称'] = cleaned_names
    print(f"✓ 数据清洗完成，共 {len(df_original)} 行")
    
    df_original.to_excel(output_path, index=False, header=False)
    print(f"✓ 保存到新表格: {output_path}")
    
    print(f"\n{'='*60}")
    print(f"数据对齐验证（前3条）:")
    print(f"{'='*60}")
    for idx in range(min(3, len(df_original))):
        print(f"\n第 {idx+1} 条:")
        print(f"  VIN码: {df_original.iloc[idx, 0]}")
        print(f"  清洗后: {df_original.iloc[idx, -1]}")
        print("-"*60)


def main():
    """主函数"""
    # 设置文件路径
    input_path = r"/root/autodl-tmp/车表/VIN合并数据/AI-ok更新/AI -OK _总表.xlsx"
    output_dir = r"/root/autodl-tmp/车表/VIN合并数据/AI-ok更新/清洗结果"
    output_path = os.path.join(output_dir, "cleaned_AI_OK_总表.xlsx")
    
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"✓ 创建输出目录: {output_dir}")
    
    start_time = datetime.now()
    print(f"\n{'='*60}")
    print(f"开始处理时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    try:
        if os.path.exists(input_path):
            # 先读取文件判断列数
            df_check = pd.read_excel(input_path, header=None, nrows=1)
            num_cols = len(df_check.columns)
            print(f"✓ 检测到 {num_cols} 列数据")
            
            # 根据列数选择处理函数
            if num_cols == 3:
                process_file_1(input_path, output_path)
            elif num_cols == 7:
                process_file_2(input_path, output_path)
            elif num_cols == 11:
                process_file_3(input_path, output_path)
            elif num_cols == 10:
                process_file_4(input_path, output_path)
            else:
                # 默认使用process_file_2的逻辑（通用处理）
                print(f"⚠ 列数为 {num_cols}，使用通用处理逻辑")
                process_file_2(input_path, output_path)
        else:
            print(f"× 文件不存在: {input_path}")
    except Exception as e:
        print(f"× 处理文件时出错: {str(e)}")
        import traceback
        traceback.print_exc()
    
    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\n{'='*60}")
    print(f"✓ 全部处理完成！")
    print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {duration}")
    print(f"结果保存在: {output_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
