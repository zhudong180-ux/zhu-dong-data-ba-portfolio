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
    
    def combine_brand_series(brand, series, extra_prefixes=None):
        brand = brand.strip()
        series = series.strip()

        if not brand and not series:
            return ""
        if not brand:
            return series
        if not series:
            return brand

        brand_clean = re.sub(r'\s+', '', brand)
        series_clean = re.sub(r'\s+', '', series)

        # 先移除额外提供的前缀（如合资品牌名）
        if extra_prefixes:
            for prefix in extra_prefixes:
                prefix = prefix.strip()
                if not prefix:
                    continue
                if series.startswith(prefix):
                    series = series[len(prefix):].strip()
                elif series_clean.startswith(re.sub(r'\s+', '', prefix)):
                    # 当存在空格差异时使用去空格对比
                    collapsed_prefix = re.sub(r'\s+', '', prefix)
                    collapsed_series = re.sub(r'\s+', '', series)
                    if collapsed_series.startswith(collapsed_prefix):
                        series = collapsed_series[len(collapsed_prefix):]
                        series = series.strip()
                        series_clean = re.sub(r'\s+', '', series)
                        continue

        # 重新计算清理后的文本
        series_clean = re.sub(r'\s+', '', series)

        # 如果车系中已经包含品牌，则直接返回车系（避免“福特长安福特锐界”）
        if brand_clean and brand_clean in series_clean:
            return series

        # 去掉车系开头重复的品牌
        if series.startswith(brand):
            series = series[len(brand):].strip()

        # 去掉品牌尾部与车系开头的重叠部分
        max_overlap = min(len(brand), len(series))
        for overlap in range(max_overlap, 0, -1):
            if brand.endswith(series[:overlap]):
                series = series[overlap:].strip()
                break

        if series:
            return f"{brand}{series}"
        return brand

    # 如果有>分隔符，优先从结构化数据中提取
    if '>' in text:
        parts = [p.strip() for p in text.split('>') if p.strip()]
        canonical_brand = ""
        if parts:
            canonical_brand = parts[0]
            if '_' in canonical_brand:
                canonical_brand = canonical_brand.split('_', 1)[0].strip()
        if len(parts) >= 2:
            # 取倒数第二部分，通常是：品牌_车系
            series_part = parts[-2].strip()
            if '_' in series_part:
                # 分割，如：长安凯程_凯程70 -> 提取车系名
                brand, car_series = series_part.split('_', 1)
                extra_prefixes = [brand.strip()]
                final_brand = canonical_brand.strip() if canonical_brand else brand.strip()
                if canonical_brand and canonical_brand.strip() != brand.strip():
                    extra_prefixes.append(canonical_brand.strip())
                return combine_brand_series(final_brand, car_series, extra_prefixes=extra_prefixes)
            else:
                brand_candidate = canonical_brand.strip()
                if len(parts) >= 3:
                    # 追加额外候选，避免品牌为空
                    candidates = [c for c in parts[:-1] if c != series_part]
                    if candidates and not brand_candidate:
                        brand_candidate = candidates[0]

                if brand_candidate and '_' in brand_candidate:
                    brand_candidate = brand_candidate.split('_', 1)[0].strip()

                if brand_candidate:
                    return combine_brand_series(brand_candidate, series_part, extra_prefixes=[series_part])
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
    
    # 移除所有车系/品牌名（更全面的列表）
    brand_series_names = [
        'CS15', 'CS35', 'CS55', 'CS75', 'CS85', 'CS35PLUS', 'CS55PLUS', 'CS75PLUS',
        'KX5', 'K5', 'K3', 'K2', 'KX3', 'KX7',
        '锐界', '蒙迪欧', '福克斯', '翼虎', '翼搏', '金牛座',
        '凯程', '长安', '福特', '起亚', '奇瑞', '吉利', '比亚迪', '长城',
        '自由光', '牧马人', '指南者', '大切诺基', '汽车'
    ]
    for brand_name in brand_series_names:
        temp_text = temp_text.replace(brand_name, ' ')
    
    # 提取所有2个字以上的中文词组
    matches = re.findall(r'[\u4e00-\u9fa5]{2,}', temp_text)
    
    # 过滤配置词
    config_keywords = ['版', '型']
    exclude_keywords = ['选装', '彩贴', '装饰', '悦联', '互联', '导航', '天窗', '真皮', '座椅', '音响', '系统', '配置']
    valid_matches = []
    
    for m in matches:
        # 跳过排除词
        if any(ex in m for ex in exclude_keywords):
            continue
        # 只取包含配置关键字的词组
        if any(kw in m for kw in config_keywords):
            # 移除末尾单个"国"字（国V/国VI标记残留）
            m = re.sub(r'国$', '', m)
            if len(m) >= 2:  # 确保处理后仍是有效配置名
                valid_matches.append(m)
    
    if valid_matches:
        # 取最后一个作为配置（通常配置在末尾）
        return valid_matches[-1]
    
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
    input_path = r"/root/autodl-tmp/车表/VIN合并数据/AI-ok更新/AI_总表.xlsx"
    output_dir = r"/root/autodl-tmp/车表/VIN合并数据/AI-ok更新/清洗结果"
    output_path = os.path.join(output_dir, "cleaned_AI_总表.xlsx")
    
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
