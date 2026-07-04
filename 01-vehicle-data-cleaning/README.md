# 📊 项目 1：车型数据清洗工具集 (Vehicle Data Cleaning Toolkit)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)
[![Streaming](https://img.shields.io/badge/IO-Streaming-brightgreen.svg)](#技术亮点)

> 把百万行级 Excel 车型数据按规则清洗为标准化字段。

---

## 🎯 项目目标

汽车数据厂商的原始车型数据往往是**多列散乱**或**多行+`>`品牌路径**格式,需要按业务规则组装成：

```
年份款型 + 品牌车系 + 动力单元 + 变速箱/驱动形式 + 配置等级
示例:2019款 起亚KX5 1.6T 自动两驱豪华版
```

数据规模达**百万行级**(单文件约 696MB 文本),核心挑战是:
- 处理速度(必须流式 IO,不能一次加载全表)
- 规则覆盖度(中英文混合、嵌套子品牌、电车特殊类型)
- 可演进性(7 个版本迭代)

---

## 📦 项目结构

```
01-vehicle-data-cleaning/
├── README.md                       # 本文档
├── requirements.txt                # 依赖清单
├── cli-version/                    # 命令行版 (流式 openpyxl+xlsxwriter)
│   ├── v1_basic.py                 # 第一版基础规则
│   ├── v2_basic.py                 # 引入 tqdm + 错误降级
│   ├── v3_with_header.py           # 支持 --has-header 参数
│   └── v4_multi_column.py          # 支持品牌路径兜底 + 多列合并
├── pandas-version/                 # pandas 版 (多列格式专用)
│   ├── v1_basic.py                 # 4 类入口文件处理函数
│   ├── v2_joint_brand.py           # 合资品牌前缀处理
│   ├── v3_extra_prefix.py          # extra_prefixes 多前缀剥离
│   ├── v4_unified_template.py      # _process_template 模板函数
│   ├── v5_brand_candidates.py      # 多级品牌嵌套处理
│   ├── v6_wide_table.py            # 宽表(≥8 列)自动检测
│   └── v7_multi_sheet.py           # 多 Sheet 指定 (TARGET_ACCURACY_SHEET)
└── exploration-tools/
    └── extract_excel_rows.py       # 逐行提取 Excel → TXT/CSV 用于探索
```

---

## ⚙️ 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 使用命令行版

```bash
# 处理完整 Excel
python cli-version/v4_multi_column.py --input your_data.xlsx --output cleaned.xlsx

# 支持自定义列名与多 sheet
python cli-version/v4_multi_column.py \
    --input your_data.xlsx \
    --output cleaned.xlsx \
    --new-col-name "标准化车型" \
    --sheets "Sheet1" "Sheet2"

# 只跑前 10000 行做验证
python cli-version/v4_multi_column.py \
    --input your_data.xlsx \
    --output demo.xlsx \
    --limit 10000
```

### 使用 pandas 版

```bash
# 处理宽表(≥8 列)
python pandas-version/v6_wide_table.py \
    --input 你的数据.xlsx \
    --output-dir ./output \
    --filename result.xlsx

# 处理多 sheet 的精确度子集
TARGET_ACCURACY_SHEET="70%_1准确度" \
python pandas-version/v7_multi_sheet.py \
    --input ./data/input.xlsx \
    --target-sheet "70%_1准确度" \
    --output-dir ./output
```

---

## 🌟 技术亮点

### 1. 流式 IO 处理百万行级数据

```python
# 读：openpyxl read_only=True (不一次性加载全表)
wb = openpyxl.load_workbook(input_path, read_only=True, data_only=True)

# 写：xlsxwriter constant_memory=True (边读边写,内存友好)
out = xlsxwriter.Workbook(output_path, {
    "constant_memory": True,
    "strings_to_urls": False,
    "nan_inf_to_errors": True,
})
```

**核心优势**：百万行 Excel 仅需几十 MB 内存,可以处理 696MB+ 文本文件。

### 2. 7 版本演进式解决问题

| 版本 | 关键改进 | 解决问题 |
|------|---------|---------|
| v1 | 基础规则链 | 5 段式清洗框架 |
| v2 | tqdm 进度条 + 错误降级 | 用户体验 |
| v3 | `--has-header` 参数 | 适配有/无表头数据 |
| v4 | 品牌路径兜底 | 多行+`>`品牌路径 |
| v5 | `sanitize_brand/series` | 多级品牌嵌套("北京奔驰_E260L")|
| v6 | `_concat_columns` 宽表合并 | ≥8 列的精简版宽表 |
| v7 | `TARGET_ACCURACY_SHEET` 多 Sheet | 准确度子集重清洗 |

### 3. 创新算法：**"双前缀剥离"**

处理"长安福特锐界"类合资品牌重复问题:

```python
def combine_brand_series(brand_path, extra_prefixes=None):
    """从品牌路径抽取规范品牌名,避免 `福特长安福特锐界` 重复"""
    parts = [p.strip() for p in brand_path.split(">") if p.strip()]

    # 1. 优先取 parts[0] 作为规范品牌
    canonical_brand = parts[0] if parts else ""

    # 2. 在 series 中剥离 extra_prefixes
    series = parts[-1].split("_")[-1] if "_" in parts[-1] else parts[-1]
    for prefix in (extra_prefixes or []) + [canonical_brand]:
        # re.sub(r'\s+', '', prefix) 处理空格差异
        if re.sub(r'\s+', '', prefix) in re.sub(r'\s+', '', series):
            series = series.replace(prefix, "").strip()

    return canonical_brand + series
```

### 4. 创新算法：**"路径最长候选"**

处理"北京奔驰 > 北京 > 北京奔驰_E260L"多级嵌套:

```python
def sanitize_brand(token):
    """剔除 token 中的年款/排量/特殊符号,规范化品牌名"""
    token = re.sub(r'\d{4}款', '', token)  # 剔除年款
    token = re.sub(r'\d+(?:\.\d+)?[TL]', '', token, flags=re.I)  # 剔除排量
    return token.strip()

# 遍历所有 parts[:-1] 收集品牌候选,按"去空格后长度"排序取最长
candidates = []
for p in parts[:-1]:
    s = sanitize_brand(p)
    if s:
        candidates.append(s)

candidates.sort(key=lambda x: len(re.sub(r'\s+', '', x)), reverse=True)
canonical_brand = candidates[0] if candidates else ""
```

### 5. 规则链：5 段式拼装

```
年份款型 → 品牌车系 → 动力单元 → 变速箱/驱动形式 → 配置等级
2019款   → 起亚KX5  → 1.6T     → 自动两驱         → 豪华版
```

每段都有独立的 `extract_*` 函数 + `normalize_*` 函数,失败回退到下一级。

---

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| 单文件最大行数 | 100 万+ |
| 单文件最大大小 | 696MB+ 文本 |
| 内存占用 | < 200MB |
| 处理速度 | ~5000-8000 行/秒(单核 CPU) |
| 错误降级覆盖 | 单行失败不影响全局 |

---

## 🧪 测试与验证

由于原数据是**真实的汽车厂商数据**,本仓库仅保留**脱敏后的算法与工具链**,所有脚本为可独立运行的工具。

### 生成测试数据

```python
import pandas as pd
import random

data = {
    "VIN": [f"LSVAF61C0{random.randint(1000000, 9999999)}" for _ in range(1000)],
    "年款": [f"{random.randint(2015, 2024)}款" for _ in range(1000)],
    "排量": [random.choice(["1.6T", "2.0L", "3.0T"]) for _ in range(1000)],
    "变速器": [random.choice(["自动", "手动", "CVT"]) for _ in range(1000)],
    "原始车型全称": [
        f"{random.randint(2015, 2024)}款 帕萨特{random.choice(['1.8T', '2.0T'])} 自动豪华版"
        for _ in range(1000)
    ]
}
pd.DataFrame(data).to_excel("test_data.xlsx", index=False)
```

然后运行:
```bash
python cli-version/v4_multi_column.py --input test_data.xlsx --output cleaned.xlsx --limit 100
```

---

## 📂 数据来源声明

本工具集用于处理**汽车行业的车型清洗业务数据**:
- 数据格式示例：**VIN 码 + 年款 + 排量 + 变速器 + 原始车型全称**
- 数据规模：百万行级
- 业务用途：车辆识别、车型匹配、二手车估值、车险定价等
- 本仓库不包含任何真实客户数据,代码为通用清洗框架

---

## ⚠️ 已知限制

1. **纯规则方案局限**：少数品牌(如"凯迪拉克 ATS-L""奔驰 E 260 L")有空格与字母连写差异,部分场景需要 LLM 辅助
2. **方言未覆盖**：极少见车辆型号未在规则中
3. **多语言支持**：当前主要支持中文,英文品牌名规则待增强

### 下一步计划

- [ ] 集成 LLM(微调 Qwen2.5)处理 5% 长尾 case
- [ ] 支持并行处理(openpyxl + multiprocessing)
- [ ] 增加 unit test 与 fixture
- [ ] 发布到 PyPI

---

## 📜 License

MIT License - 详见 [`../LICENSE`](../LICENSE) 文件。

本项目基于数据宝 ChinaDataPay 内部业务代码的脱敏版本,**仅供学习与交流用途**。
