"""
Vehicle model cleanup script.
Builds names following: 年份款型 + 品牌车系 + 动力单元 + 变速箱/驱动形式 + 配置等级
Example: 2019款 起亚KX5 1.6T 自动两驱豪华版
"""

import os
import re
from datetime import datetime

import pandas as pd


def extract_year(text):
    """Return a year trim such as 2019款."""
    if pd.isna(text):
        return ""
    text = str(text)
    match = re.search(r'(\d{4})款', text)
    if match:
        return match.group(1) + "款"
    match = re.search(r'年款[：:]\s*(\d{4})', text)
    if match:
        return match.group(1) + "款"
    return ""


def extract_brand_series(text):
    """Return the brand+series string, e.g. 福特锐界."""
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

        if extra_prefixes:
            for prefix in extra_prefixes:
                prefix = prefix.strip()
                if prefix and series.startswith(prefix):
                    series = series[len(prefix):].strip()

        brand_clean = re.sub(r'\s+', '', brand)
        series_clean = re.sub(r'\s+', '', series)

        pos = series.find(brand)
        if pos > 0:
            series = series[pos + len(brand):].strip()
            series_clean = re.sub(r'\s+', '', series)
        elif pos == 0:
            series = series[len(brand):].strip()
            series_clean = re.sub(r'\s+', '', series)
        elif brand_clean:
            pos_clean = series_clean.find(brand_clean)
            if pos_clean != -1:
                series = series_clean[pos_clean + len(brand_clean):].strip()
                series_clean = re.sub(r'\s+', '', series)

        if series.startswith(brand):
            series = series[len(brand):].strip()

        max_overlap = min(len(brand), len(series))
        for overlap in range(max_overlap, 0, -1):
            if brand.endswith(series[:overlap]):
                series = series[overlap:].strip()
                break

        if series:
            return f"{brand}{series}"
        return brand

    def sanitize_brand(token: str) -> str:
        token = token.strip()
        if not token:
            return ""
        token = re.sub(r'\d{4}款?', '', token)
        token = re.sub(r'年款[：:]?\s*\d{4}', '', token)
        token = re.sub(r'\d+(?:\.\d+)?[A-Za-z]*', '', token)
        token = re.sub(r'[><_:/\\|]', '', token)
        token = token.replace('款', '')
        token = re.sub(r'\s+', '', token)
        return token.strip()

    def sanitize_series(token: str) -> str:
        token = token.strip()
        if not token:
            return ""
        token = re.sub(r'\d{4}款?', '', token)
        token = re.sub(r'年款[：:]?\s*\d{4}', '', token)
        token = re.sub(r'\d+(?:\.\d+)?[A-Za-z]*', '', token)
        token = re.sub(r'[><_:/\\|]', ' ', token)
        token = re.sub(r'\s+', ' ', token)
        return token.strip()

    if '>' in text:
        parts = [p.strip() for p in text.split('>') if p.strip()]
        # 收集所有可能的品牌前缀（含下划线前的部分）
        brand_candidates = []
        for p in parts[:-1]:
            if '_' in p:
                raw_brand = p.split('_', 1)[0].strip()
            else:
                raw_brand = p
            sanitized_brand = sanitize_brand(raw_brand)
            if sanitized_brand:
                brand_candidates.append(sanitized_brand)
        # 选最长的品牌前缀
        if brand_candidates:
            brand_candidates.sort(key=lambda x: len(x.replace(' ','')), reverse=True)
            full_brand = brand_candidates[0]
        else:
            full_brand = ''

        # 车系部分优先取倒数第二段（如有下划线则取后半）
        if len(parts) >= 2:
            series_part = parts[-2].strip()
            if '_' in series_part:
                _, car_series = series_part.split('_', 1)
            else:
                car_series = series_part
        else:
            car_series = ''

        car_series = sanitize_series(car_series)

        # 品牌+车系合成
        if full_brand:
            return combine_brand_series(full_brand, car_series, extra_prefixes=[full_brand])
        elif car_series:
            return car_series
        else:
            return ''
    return ""


def extract_power(text):
    """Return power-unit string such as 1.6T or 插电式混合动力."""
    if pd.isna(text):
        return ""
    text = str(text)

    decimal_matches = re.findall(r'(\d\.\d+[A-Za-z]+)', text)
    if decimal_matches:
        return decimal_matches[-1].upper()

    int_matches = re.findall(r'(?<!\d)([1-9][TL])(?!\d)', text)
    if int_matches:
        return int_matches[-1].upper()

    match = re.search(r'(纯电动|插电式混合动力|混合动力)', text)
    if match:
        return match.group(1)

    return ""


def extract_transmission(text):
    """Return transmission text; ignore EV single speed."""
    if pd.isna(text):
        return ""
    text = str(text)

    if '电动车单速变速箱' in text or '单速变速箱' in text:
        return ""

    if '纯电动' in text:
        return ""

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
            if '手自一体' in result:
                return '自动'
            return result.strip()

    return ""


def extract_drive(text):
    """Return drive mode string such as 两驱/四驱."""
    if pd.isna(text):
        return ""
    text = str(text)

    match = re.search(r'([\u4e00-\u9fa5]*驱)', text)
    if match:
        return match.group(1)

    return ""


def extract_config(text):
    """Return configuration trim name, filtering banned keywords."""
    if pd.isna(text):
        return ""
    text = str(text)

    if '>' in text:
        text = text.split('>')[-1]

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
    temp_text = re.sub(r'[A-Z]+\d+[A-Z]*', '', temp_text)
    temp_text = re.sub(r'[IVX]+$', '', temp_text)

    matches = re.findall(r'[\u4e00-\u9fa5]{2,}', temp_text)

    brand_prefixes = [
        '自由光', '牧马人', '指南者', '大切诺基', '汽车', '长安', '福特', '雪佛兰', '别克', '凯迪拉克', '大众', '上汽',
        '一汽', '广汽', '北汽', '北京', '奇瑞', '吉利', '比亚迪', '长城', '哈弗', '欧拉', '坦克', '魏牌', '红旗',
        '荣威', '名爵', '五菱', '宝骏', '宝沃', '传祺', '领克', '蔚来', '理想', '小鹏', '零跑', '哪吒', '腾势',
        '岚图', '极狐', '深蓝', '阿维塔', '高合', '智己', '合创', '思皓', '捷途', '星途', '启辰', '风神', '风行',
        '风光', '风度', '瑞驰', '福田', '东风', '海马', '海格', '江淮', '江铃', '华晨', '华泰', '上汽大通', '广汽埃安',
        '东南', '莲花', '观致', '讴歌', '英菲尼迪', '斯巴鲁', '标致', '雪铁龙', 'DS', 'MINI', '保时捷', '玛莎拉蒂',
        '兰博基尼', '法拉利', '宾利', '劳斯莱斯', '捷达', '思铭', '斯柯达', '现代', '起亚', '丰田', '本田', '日产',
        '马自达', '斯玛特', 'smart', 'Jeep', '林肯', '沃尔沃', '宝马', '奔驰', '奥迪', '雷克萨斯', '路虎', '捷豹'
    ]

    banned_keywords = ['选装', '彩贴', '悦联']
    config_suffixes = ('版', '型', '款')
    config_whitelist = {
        '豪华', '舒适', '标准', '尊贵', '旗舰', '精英', '领先', '运动', '时尚', '智享', '越享', '尊享', '尊雅', '尊御',
        '尊尚', '尊领', '尊耀', '尊馭', '智尊', '智领', '智驾', '智驾型', '智驾版', '尊逸', '臻享', '畅享', '悦享',
        '蓝鲸', '荣耀', '荣耀版', '荣耀型', '尊雅版', '尊耀版', '菁英', '菁英型', '菁英版'
    }

    def strip_brand_prefix(word: str) -> str:
        for prefix in brand_prefixes:
            if word.startswith(prefix) and len(word) > len(prefix):
                return word[len(prefix):].strip()
        return word

    def is_config_candidate(word: str) -> bool:
        if any(bad in word for bad in banned_keywords):
            return False
        if any(word.endswith(suffix) for suffix in config_suffixes):
            return True
        if any(suffix in word for suffix in config_suffixes):
            return True
        return word in config_whitelist

    candidates = []
    for word in matches:
        word = word.strip()
        if not word or word in brand_prefixes:
            continue
        word = strip_brand_prefix(word)
        if len(word) < 2:
            continue
        if not is_config_candidate(word):
            continue
        cleaned = re.sub(r'国$', '', word)
        if cleaned:
            candidates.append(cleaned)

    if candidates:
        return candidates[-1]

    for word in reversed(matches):
        word = word.strip()
        if not word or word in brand_prefixes:
            continue
        word = strip_brand_prefix(word)
        if len(word) < 2:
            continue
        if is_config_candidate(word):
            return re.sub(r'国$', '', word)

    return ""


def clean_vehicle_name_complete(vin, raw_info, year_col=""):
    """Build cleaned name and return a dict with all interim fields."""
    full_text = str(raw_info) + " " + str(year_col)

    year = extract_year(full_text)
    brand_series = extract_brand_series(full_text)
    power = extract_power(full_text)
    transmission = extract_transmission(full_text)
    drive = extract_drive(full_text)
    config = extract_config(full_text)

    trans_drive = ""
    if transmission and drive:
        if drive.startswith(transmission):
            trans_drive = drive
        else:
            trans_drive = transmission + drive
    elif transmission:
        trans_drive = transmission
    elif drive:
        trans_drive = drive

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


def _concat_columns(row, indices):
    parts = []
    for idx in indices:
        if idx >= len(row):
            continue
        value = row[idx]
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text:
            parts.append(text)
    return ' '.join(parts)


def _process_template(input_path, output_path, columns_to_join=None, join_all_after_first=False):
    df_original = pd.read_excel(input_path, header=None)
    print(f"[INFO] Source rows: {len(df_original)}, columns: {len(df_original.columns)}")

    cleaned_names = []
    total = len(df_original)

    for idx, row in df_original.iterrows():
        vin = row[0] if len(row) > 0 else ""
        if join_all_after_first:
            raw_info = _concat_columns(row, range(1, len(row)))
            year_col = ""
        elif columns_to_join is None:
            raw_info = row[1] if len(row) > 1 else ""
            year_col = row[2] if len(row) > 2 else ""
        else:
            raw_info = _concat_columns(row, columns_to_join)
            year_col = ""
        result = clean_vehicle_name_complete(vin, raw_info, year_col)
        cleaned_names.append(result['清洗后车型名称'])

        if (idx + 1) % 100 == 0 or idx == 0:
            print(f"[INFO] Progress: {idx + 1}/{total}")

    df_original['清洗后车型名称'] = cleaned_names
    df_original.to_excel(output_path, index=False, header=False)
    print(f"[INFO] Saved: {output_path}")

    preview_rows = min(3, len(df_original))
    if preview_rows:
        print("[INFO] Preview of first rows:")
        for idx in range(preview_rows):
            print(f"  Row {idx + 1} VIN: {df_original.iloc[idx, 0]}")
            print(f"  Raw: {str(df_original.iloc[idx, 1])[:60]}...")
            print(f"  Cleaned: {df_original.iloc[idx, -1]}")


def process_file_1(input_path, output_path):
    _process_template(input_path, output_path)


def process_file_2(input_path, output_path):
    _process_template(input_path, output_path)


def process_file_3(input_path, output_path):
    _process_template(input_path, output_path, columns_to_join=range(1, 11))


def process_file_4(input_path, output_path):
    _process_template(input_path, output_path, columns_to_join=range(1, 10))


def process_file_wide(input_path, output_path):
    _process_template(input_path, output_path, join_all_after_first=True)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Wide-table vehicle name cleaner")
    ap.add_argument("--input", required=True, help="Path to input .xlsx file")
    ap.add_argument("--output-dir", default="./output", help="Output directory")
    ap.add_argument("--filename", default="cleaned_output.xlsx",
                    help="Output filename")
    args = ap.parse_args()

    input_path = args.input
    output_dir = args.output_dir
    output_path = os.path.join(output_dir, args.filename)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"[INFO] Created output directory: {output_dir}")

    start_time = datetime.now()
    print(f"[INFO] Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        if os.path.exists(input_path):
            df_check = pd.read_excel(input_path, header=None, nrows=1)
            num_cols = len(df_check.columns)
            print(f"[INFO] Detected {num_cols} columns")

            if num_cols == 3:
                process_file_1(input_path, output_path)
            elif num_cols == 7:
                process_file_2(input_path, output_path)
            elif num_cols == 11:
                process_file_3(input_path, output_path)
            elif num_cols == 10:
                process_file_4(input_path, output_path)
            elif num_cols >= 8:
                process_file_wide(input_path, output_path)
            else:
                print(f"[WARN] Unexpected column count {num_cols}, fallback to process_file_2")
                process_file_2(input_path, output_path)
        else:
            print(f"[ERROR] Missing input file: {input_path}")
    except Exception as exc:
        print(f"[ERROR] Processing failed: {exc}")
        import traceback
        traceback.print_exc()

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"[INFO] Finish time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Duration: {duration}")
    print(f"[INFO] Output file: {output_path}")


if __name__ == "__main__":
    main()
