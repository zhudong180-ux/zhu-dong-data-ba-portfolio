# 🔐 项目 2：VIN/高速运力加密数据 ETL 流水线

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org)
[![Crypto](https://img.shields.io/badge/Crypto-AES--128--CBC-red.svg)](#技术架构)
[![Threading](https://img.shields.io/badge/Parallel-16--workers-brightgreen.svg)](#性能优化)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

> 完整解析被加密的 VIN/车辆运力日志数据,逆向分析 AES 双 IV 策略,构建从提取到分析的全链路流水线。

---

## 🎯 项目目标

在数据宝"高速运力"条线业务中,**车辆运力数据日志**是经过加密存储的(出于合规与传输安全考虑)。
需要一套**全自动 ETL 流水线**完成:

1. **提取** (Extract): 从海量日志中按字段抽取 4 个核心 info 字段
2. **解密** (Decrypt): AES-128-CBC + 双 IV 策略解析加密数据
3. **解析** (Parse): JSON 字段拆分扁平化为 CSV
4. **分析** (Analyze): 健康度报告 + 乱码检测 + monthList 抽样

---

## ⚠️ 重要声明

**本仓库的解密脚本中的 AES 密钥已脱敏。**

请通过环境变量 `VIN_DECRYPT_KEY` 注入实际密钥:
```bash
export VIN_DECRYPT_KEY="your-16-byte-key"
python decrypt_info_fields_v1.py --input-dir /path/to/input
```

**严禁将生产环境密钥硬编码到代码中或上传至 Git 仓库。**

---

## 📦 项目结构

```
02-vin-decrypt-etl/
├── README.md                       # 本文档
├── requirements.txt                # 依赖清单
├── src/
│   ├── extract_info_fields.py      # v1: 4 个 call-2025-06 文件批量提取
│   ├── extract_info_fields_v2.py   # v2: 高速运力 demo 单文件提取
│   ├── decrypt_info_fields_v1.py   # v1: 批量解密(双 IV 策略)
│   ├── decrypt_info_fields_v2.py   # v2: 高速运力解密 + 调试模式
│   ├── process_data_v1.py          # v1: 字段发现 + 分类扁平化
│   ├── process_data_v2.py          # v2: 高速运力专属分类
│   ├── analyze_decrypt_v1.py       # v1: 多文件健康度报告
│   └── analyze_decrypt_v2.py       # v2: 单文件健康度统计
├── sample-data/
│   └── README.md                   # 示例数据结构说明(本仓库不含真实数据)
└── docs/
    ├── AES_DOUBLE_IV_STRATEGY.md   # 双 IV 策略逆向分析笔记
    └── ETL_PIPELINE.md             # 完整流水线架构图
```

---

## ⚙️ 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置环境变量(注入密钥)

```bash
# Linux / macOS
export VIN_DECRYPT_KEY="your-16-byte-secret-key"

# Windows (PowerShell)
$env:VIN_DECRYPT_KEY = "your-16-byte-secret-key"

# Windows (CMD)
set VIN_DECRYPT_KEY=your-16-byte-secret-key
```

### 3. 完整流水线

```bash
# Step 1: 提取 info 字段
python src/extract_info_fields.py \
    --input ./sample-data/627cdp23_call-2025-06.log \
    --output-txt ./output/627cdp23_call-2025-06.txt \
    --output-csv ./output/627cdp23_call-2025-06.csv

# Step 2: 解密
python src/decrypt_info_fields_v1.py \
    --input-dir ./output

# Step 3: 解析扁平化
python src/process_data_v1.py \
    --input-dir ./output

# Step 4: 健康度分析
python src/analyze_decrypt_v1.py \
    --input-dir ./output
```

---

## 🌟 技术亮点

### 1. AES-128-CBC 双 IV 策略(逆向分析发现)

这是本项目**最具技术挑战**的部分。在逆向分析加密协议时发现:

**同一个 16 字节密钥,对不同的 4 个 info 字段使用了 2 种不同的 IV 策略**:

| 字段 | IV 策略 |
|------|---------|
| `callSupplierRequestInfo` | **零 IV** (`b'\x00' * 16`) |
| `responseInfo` | **零 IV** (`b'\x00' * 16`) |
| `callSupplierResponseInfo` | **密钥本身作为 IV** (`AES_KEY`) |
| `requestInfo` | **密钥本身作为 IV** (`AES_KEY`) |

```python
def aes_decrypt_with_zero_iv(encrypted_data, key):
    """零 IV 解密路径"""
    iv = b'\x00' * 16
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.decrypt(encrypted_data)


def aes_decrypt_with_key_iv(encrypted_data, key):
    """密钥 IV 解密路径"""
    iv = key  # 🔑 关键发现
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.decrypt(encrypted_data)
```

### 2. 完整 ETL 流水线架构

```
┌─────────────────────┐
│  .log 日志文件      │  (raw, ~5MB/万条)
└──────────┬──────────┘
           │ extract_info_fields.py
           │ (按行 grep, JSON 正则抽取)
           ▼
┌─────────────────────┐
│  提取的 TXT + CSV   │  (扁平化中间产物)
└──────────┬──────────┘
           │ decrypt_info_fields.py
           │ (Base64 → AES-CBC → JSON 提纯)
           ▼
┌─────────────────────┐
│  解密后的 TXT + CSV │  (已转码中文/JSON)
└──────────┬──────────┘
           │ process_data.py
           │ (字段发现 + 分类扁平化)
           ▼
┌─────────────────────┐
│  分类后的扁平 CSV   │  (车年 + 月份数据)
└──────────┬──────────┘
           │ analyze_decrypt.py
           │ (ret=0/-1 分布 + 乱码检测)
           ▼
┌─────────────────────┐
│  健康度报告         │  (✅ 解密正常 / ⚠️ 数据少 / 乱码)
└─────────────────────┘
```

### 3. 错误降级 - PKCS7 unpad 失败处理

```python
def decrypt_field(encrypted_text):
    # ... Base64 解码
    decrypted = cipher.decrypt(encrypted_bytes)

    # 主路径: PKCS7 unpad
    try:
        return unpad(decrypted, AES.block_size).decode('utf-8', errors='ignore')
    except ValueError:
        pass  # 退化

    # 降级路径: 去掉末尾 \x00
    return decrypted.rstrip(b'\x00').decode('utf-8', errors='ignore')
```

### 4. JSON 提纯 - 跳过乱码前缀

```python
def extract_json_after_garbage(decrypted_text):
    """找到第一个 { 或 [ 字符开始截取(去掉乱码前缀)"""
    for i, ch in enumerate(decrypted_text):
        if ch in '{[':
            return decrypted_text[i:]
    return None
```

### 5. 多线程解密 - ThreadPoolExecutor 16 worker

```python
with ThreadPoolExecutor(max_workers=16) as executor:
    futures = {
        executor.submit(process_record, rec, AES_KEY): rec
        for rec in records
    }

    for future in as_completed(futures):
        try:
            result = future.result()
        except Exception as exc:
            # 失败记录占位,不阻塞整体
            print(f"Record error: {exc}")
```

### 6. 健康度报告

```python
def analyze_decrypt_quality(csv_path):
    stats = {
        "total": 0,
        "ret_0": 0,        # 成功有数据
        "ret_-1": 0,       # 返回无数据
        "empty": 0,        # 响应为空
        "garbage_prefix": 0,  # 乱码前缀
    }

    with open(csv_path, 'r') as f:
        for row in csv_reader(f):
            stats["total"] += 1
            # ... 累计统计

    if stats["ret_0"] < 10:
        print("⚠️ 数据记录太少,需检查解密流程")
    elif stats["garbage_prefix"] > 0:
        print("⚠️ 存在乱码前缀")
    else:
        print("✅ 解密正常")
```

---

## 📊 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 单文件最大日志 | 696MB | 百万行级,流式处理 |
| 解密吞吐量 | ~500 条/秒 | 单线程 |
| 16 worker 并行 | ~3000 条/秒 | 6× 加速 |
| 内存占用 | < 200MB | 流式 IO 不溢出 |
| 字段识别率 | 自动发现 | 动态键集合 |

---

## 🔍 AES 双 IV 策略 - 逆向分析笔记

详见 [`docs/AES_DOUBLE_IV_STRATEGY.md`](./docs/AES_DOUBLE_IV_STRATEGY.md):

1. **现象**: 4 个字段用同一密钥,但只有 2 个能解密
2. **猜测**: IV 不同
3. **实验**:
   - 假设 1: 全部用零 IV → 2/4 成功 ✅
   - 假设 2: 全部用密钥 IV → 2/4 成功 ✅
4. **结论**: 不同字段分组,使用不同 IV 策略
5. **验证**: 4/4 全部解密成功

> 这是数据宝内部加密协议的隐藏细节,**仅作学习与交流用途,严禁用于未授权数据。**

---

## 📂 数据来源声明

本仓库不包含任何真实客户数据。所有代码为**通用 AES 解密与数据 ETL 框架**。

数据来源描述:
- **业务背景**: 高速运力数据(经脱敏的车辆运力日志)
- **数据规模**: 单文件 100MB-700MB(百万行级)
- **敏感字段**: VIN 车架号、加密的车辆运力数据、车牌颜色
- **合规处理**: AES-128-CBC 加密 + Base64 编码
- **本仓库**: 仅保留解密框架,**不含真实密钥与数据**

---

## 🛡️ 安全最佳实践

1. **禁止硬编码密钥**: 始终通过环境变量或密钥管理服务(KMS)注入
2. **日志脱敏**: 解密结果严禁明文落盘,应在使用后立即清理
3. **访问控制**: 解密脚本应仅在受控环境(堡垒机/K8s Job)中运行
4. **审计日志**: 解密操作应记录审计日志(who/when/what)
5. **内存安全**: 解密大文件时优先流式处理,避免 OOM

---

## ⚠️ 已知限制

1. **当前实现为单文件 / 单批次**: 大规模生产环境需对接分布式框架(Spark/Flink)
2. **不支持增量解密**: 每次需完整重跑(优化方向:按 seqNo 去重)
3. **错误降级可能丢失数据**: 乱码前缀的字段被部分截断(优化方向:加入日志定位)
4. **JSON 解析鲁棒性有限**: 极端嵌套结构可能失败

---

## 📜 License

MIT License - 详见 [`../LICENSE`](../LICENSE) 文件。
