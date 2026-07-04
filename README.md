# 👋 朱东 (Zhu Dong) - 算法工程师作品集

> **数据宝 ChinaDataPay 上海分公司** ｜ 算法工程师 (2024.10 - 2026.01) ｜ 智能体 / 生成式 AI 应用工程化

本仓库(`zhu-dong-data-ba-portfolio`)是我在 **贵州数据宝网络科技有限公司上海分公司**(数据要素市场化领军企业、国资参股的"大数据国家队")担任算法工程师期间的**完整工作成果**。

涵盖 5 大方向、13+ 项目：数据清洗工具集、AES 加密数据 ETL、人脸识别生产服务、货运调度方案、AIGC 平台原理详解。

---

## 🧭 快速导航

| 项目 | 主题 | 关键技术 | 路径 |
|------|------|---------|------|
| 1️⃣ | **[车型数据清洗工具集](#1-车型数据清洗工具集)** | 百万行 Excel + 7 版本演进 + 正则规则链 | [`01-vehicle-data-cleaning/`](./01-vehicle-data-cleaning/) |
| 2️⃣ | **[VIN 加密数据 ETL 流水线](#2-vin-高速运力加密数据-etl-流水线)** | AES-128-CBC + 双 IV 策略 + 多线程解密 | [`02-vin-decrypt-etl/`](./02-vin-decrypt-etl/) |
| 3️⃣ | **[人脸识别 + 活体检测生产服务](#3-人脸识别--活体检测生产服务)** | Redis 队列 + InsightFace + DeePixBis | [`03-face-recognition-production/`](./03-face-recognition-production/) |
| 4️⃣ | **[货运调度与风控方案文档](#4-货运调度与风控方案文档)** | 6 份完整技术资产(RL+ACO、3D-BPP、GeoHash、风控) | [`04-freight-scheduling-solutions/`](./04-freight-scheduling-solutions/) |
| 5️⃣ | **[AIGC 平台与算法原理详解](#5-aigc-平台与算法原理详解)** | SD/ControlNet/LoRA + Tweedie GLM + VRP | [`05-aigc-principles/`](./05-aigc-principles/) |

---

## 🎯 核心方向：把模型能力做成"能上线交付"的产品能力

把算法能力工程化、产品化交付，贯通**业务建模、流程拆解、接口契约、异步任务、性能优化、失败兜底、可观测、可交付**完整闭环。

### 通用方法论：六段式项目讲述

```
① 业务需求 → ② 数据形态 → ③ 方案/算法 → ④ 关键实现 → ⑤ 指标/效果 → ⑥ 复盘
```

---

## 🔥 5 大核心成果

### 1. 车型数据清洗工具集

百万行级 Excel 清洗，**7 个版本迭代**。每次升级都解决真实边界 case。

- **算法创新**："双前缀剥离"、"路径最长候选"、"无空格全称降级"
- **工程化**：流式 IO(`openpyxl read_only + xlsxwriter constant_memory`) + tqdm 进度 + 错误降级
- **规则链**：年份款型 → 品牌车系 → 动力单元 → 变速箱/驱动形式 → 配置等级
- **典型结果**：`2019款 起亚KX5 1.6T 自动两驱豪华版`

➡️ [进入项目 1](./01-vehicle-data-cleaning/)

### 2. VIN/高速运力加密数据 ETL 流水线

独立**逆向分析 AES-128-CBC 双 IV 策略**(同一密钥对不同字段分别用零 IV / 密钥 IV)。

- **密码学发现**：4 个字段分用 2 种 IV
- **ETL 流水线**：提取→解密→解析→分类→扁平化→统计分析
- **多线程加速**：`ThreadPoolExecutor` 16 worker
- **错误降级**：PKCS7 unpad 失败回退 `rstrip(b'\x00')`
- **健康度报告**：ret=0 / -1 / 空值分布 + 乱码检测 + monthList 抽样

➡️ [进入项目 2](./02-vin-decrypt-etl/)

### 3. 人脸识别 + 活体检测生产服务

基于 **Redis 消息队列**的活体检测 + 识别生产服务。

- **Redis 入队 → 模型推理 → 回传** 全异步
- **三模型后端可插拔**：InsightFace / cv2.dnn / dlib
- **活体检测**：DeePixBis(DenseNet161 Encoder-Decoder)
- **口罩检测**：SSD-like 架构(2 类 + anchor generation + NMS)
- **多实例水平扩展**：`--inst_id` 参数

➡️ [进入项目 3](./03-face-recognition-production/)

### 4. 货运调度与风控方案文档

数据宝"数据研发部 - 交通物流"条线的 5 份完整技术资产：

| 方案 | 页数 | 核心技术 |
|------|------|---------|
| [一体化智能调度与物流优化](./04-freight-scheduling-solutions/01-vehicle-load-optimization/) | 21 | 3D-BPP 装箱 + PyVRP 动态路径 + 多租户数据沙箱 |
| [货车智能调度(R L+ACO)](./04-freight-scheduling-solutions/02-truck-smart-dispatch/) | 61 | MDP+RL 全局策略 + ACO 局部精炼 + React/ECharts 可视化 |
| [综合货运枢纽智能化解决方案](./04-freight-scheduling-solutions/03-freight-hub-intelligence/) | 31 | Lakehouse + 联邦学习 + API 网关 |
| [车货匹配算法设计思路](./04-freight-scheduling-solutions/04-vehicle-cargo-matching/) | 7 | GeoHash 5位召回 + 多因子评分 + 轨迹分段清洗 |
| ["两客一危一重"风控与应急调度](./04-freight-scheduling-solutions/05-risk-emergency-dispatch/) | 20 | 风控闭环(识别→预警→干预→复盘)+ 应急动态重路由 |

➡️ [进入项目 4](./04-freight-scheduling-solutions/)

### 5. AIGC 平台与算法原理详解

涵盖 **15 大主题、9 页算法原理详解**：

```
1.  Stable Diffusion 与扩散模型(VAE + UNet + CFG)
2.  ControlNet(结构条件注入：Canny/Lineart/OpenPose/Depth/Seg)
3.  LoRA 低秩微调(ΔW = BA, r<<d)
4.  U²-Net / SAM(显著性/前景分割)
5.  FastAPI 异步队列 + 多进程多实例 + FP16/batch 推理优化
6.  数字人短视频(TTS + Wav2Lip/SadTalker + OpenCV/FFmpeg)
7.  React/Next.js/tRPC 前端工程化
8.  车险纯保费 Tweedie-GLM(log 链接 + IRLS)
9.  人脸识别 MTCNN + MobileNet + ArcFace Loss
10. 物流优化 动态 VRP/PyVRP + 3D-BPP + 元启发式
11.货车智能调度 RL + ACO 框架与可视化平台
12.两客一危一重 风控闭环(规则引擎 + GBDT + 异常检测)
13.综合货运枢纽 Lakehouse + Intelligence-as-a-Service
14.车货匹配 GeoHash 召回 + 多因子评分
15.近红外光谱分类；视觉 SLAM 回环(NetVLAD/GeM + KNN+RANSAC)
```

➡️ [进入项目 5](./05-aigc-principles/)

---

## 🛠️ 技术栈全景

### 生成式 AI / 计算机视觉
| 类别 | 技术 |
|------|------|
| 图像生成 | Stable Diffusion(LDM)、ControlNet、LoRA、U²-Net、SAM |
| 视频/数字人 | Wav2Lip、SadTalker、Edge-TTS、OpenCV、FFmpeg |
| 人脸识别 | MTCNN、MobileNet、ArcFace Loss、InsightFace、cv2.dnn、dlib |
| 活体检测 | DeePixBis(DenseNet161) |
| 口罩检测 | SSD-like + 自研 KitModel 神经网络 |
| 视觉 SLAM | NetVLAD / GeM + KNN + RANSAC |

### 运筹 / 优化
| 类别 | 技术 |
|------|------|
| 路径优化 | VRP / VRPTW / DSVRP / DVRP、PyVRP、ACO |
| 装箱 | 3D-BPP(重不压轻、旋转约束、支撑面、易碎品、LIFO) |
| 元启发式 | 遗传算法(GA)/禁忌搜索/局部搜索(2-opt/relocate) |
| 决策学习 | MDP / RL(actor-critic、动作掩码、reward shaping) |

### 数据科学 / 金融建模
| 类别 | 技术 |
|------|------|
| 广义线性模型 | Tweedie GLM(1<p<2 复合泊松-伽马)+ log 链接 + IRLS |
| 评估 | 离差残差 / 卡方近似 / 十分位 Lift / 互信息 / 共线性 |
| 召回 | GeoHash(5 位 ≈5km、4 位 ≈25km，含 8 邻域) |
| 多因子打分 | 加权归一 + A/B 回放 |

### 数据架构 / 平台
| 类别 | 技术 |
|------|------|
| 湖仓一体 | Lakehouse(流批统一 + Schema 标准化)|
| 协同生态 | 联邦学习 / 数据沙箱 / API 网关 |
| 治理 | DAMA-DMBOK 框架 |

### 工程化与服务
| 类别 | 技术 |
|------|------|
| API 框架 | FastAPI 异步队列(任务状态机 task_id) |
| 部署 | Docker + Nginx + MySQL + Redis |
| 性能 | FP16 + batch + 多进程多实例 |
| 大文件 | 分片上传 + 断点续传；SSE/WebSocket 长任务 |
| 加解密 | AES-128-CBC + Base64 + PKCS7 + 多线程 |
| 加密数据恢复 | 双 IV 策略(零 IV / 密钥 IV)|
| 流式 IO | openpyxl(read_only) + xlsxwriter(constant_memory)|
| 多线程 | ThreadPoolExecutor 16 worker |
| 前端 | React + Next.js + tRPC + TypeScript + Ant Design + ECharts + Redux Toolkit |

---

## 🏢 公司简介：数据宝 ChinaDataPay

> **国资参股、政府监管扶持、市场化运作、大数据资产交易合法经营资质**的大数据"国家队"

- 2016 年成立于中国首个大数据综合试验区贵州省贵安新区
- 2021 年工信部评为**国家级大数据产业发展试点示范项目**
- 2023 年中国社科研究院调研并出版《数据要素市场化"数据宝模式"研究》
- 2024 年**国家发改委**列为**国家数据流通利用基础设施试点工程**
- 已链接(代运营)50+ 部委厅局国央企数据、9 家省级平台公司数据
- 已开发 1800+ 产品，在互联网、金融、保险、交通等行业落地 300+ 应用场景
- 服务字节跳动、华为、太平洋保险、网商银行、中国邮政、顺丰等

---

## 📞 联系方式

- 📧 Email: 2667286040@qq.com
- 📱 Phone: 18621826216
- 🎯 求职意向:算法研究员 / 智能体 应用工程师
- 📍 期望城市:上海

---

## ⚠️ 重要声明

- 本仓库所有代码均为**在数据宝工作期间编写的内部业务代码的脱敏版本**(已移除生产机密,如真实密钥、内部路径、个人账号等)。
- 业务数据为**虚构示例**或**脱敏数据**,不包含任何客户真实信息。
- 本仓库仅作**个人作品集展示**与技术交流用途。

---

## 📜 许可证

MIT License - 详见 [`LICENSE`](./LICENSE) 文件。
