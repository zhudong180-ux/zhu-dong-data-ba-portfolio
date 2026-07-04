# 🤖 项目 5：AIGC 平台与算法原理详解

[![Domain](https://img.shields.io/badge/Domain-AIGC-blue.svg)](#)
[![Topics](https://img.shields.io/badge/Topics-15-orange.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](../../LICENSE)

> 完整覆盖生成式 AI、计算机视觉、运筹优化、金融建模的算法原理 - 个人作品集核心知识库

---

## 🎯 项目目标

本目录收录**简历上所有项目的算法原理与公式详解**,适合:

- 🤝 **面试前**: 复习高频追问点
- 📚 **学习参考**: 15 大主题 + 完整数学表达
- 🏗️ **工程参考**: 从理论到生产部署的关键参数

---

## 📦 项目结构

```
05-aigc-principles/
├── README.md                                       # 本文档
├── 00-总框架.md                                     # 智能体/生成式 AI 工程化总览
├── 01-stable-diffusion.md                          # SD 与扩散模型
├── 02-controlnet.md                                # 结构条件注入
├── 03-lora.md                                      # LoRA 低秩微调
├── 04-u2net-sam.md                                 # 抠图与边缘处理
├── 05-inference-engineering.md                     # FastAPI 异步队列
├── 06-digital-human-video.md                       # TTS + Wav2Lip/SadTalker
├── 07-frontend-toolkit.md                          # React/Next.js/tRPC 工程化
├── 08-car-insurance-pricing.md                     # Tweedie GLM + IRLS
├── 09-face-recognition.md                          # MTCNN + MobileNet + ArcFace
├── 10-logistics-optimization.md                    # DVRP + 3D-BPP + 元启发式
├── 11-truck-dispatch-rl-aco.md                     # RL + ACO + 可视化平台
├── 12-risk-emergency.md                            # 风控闭环 + 应急调度
├── 13-freight-hub-data.md                          # Lakehouse + IaaS
├── 14-vehicle-cargo-matching.md                    # GeoHash + 多因子
├── 15-research-projects.md                         # 近红外光谱 + 视觉 SLAM
└── appendix-glossary.md                            # 术语速查
```

---

## 🚀 快速开始

### 阅读顺序建议

**第一阶段 - AIGC 基础**:
1. [00-总框架](./00-总框架.md)
2. [01-stable-diffusion](./01-stable-diffusion.md)
3. [02-controlnet](./02-controlnet.md)
4. [03-lora](./03-lora.md)

**第二阶段 - 工程化**:
5. [05-inference-engineering](./05-inference-engineering.md)
6. [07-frontend-toolkit](./07-frontend-toolkit.md)

**第三阶段 - 其他方向**:
7. [08-car-insurance-pricing](./08-car-insurance-pricing.md)
8. [09-face-recognition](./09-face-recognition.md)
9. [10-logistics-optimization](./10-logistics-optimization.md)

### 面试前复习清单

- ☐ 念出 SD 的 5 个核心组件与原理
- ☐ 解释 LoRA 为什么 ΔW = BA,且 r<<d
- ☐ ArcFace Loss 公式与 s、m 参数含义
- ☐ Tweedie GLM 的 Var(Y) = φ·μ^p 中 p 的范围
- ☐ 写出 ACO 的 P(i→j) ∝ τ^α · η^β
- ☐ GeoHash 5 位和 4 位的最长距离
- ☐ 风控闭环的 4 个阶段与对应模型

---

## 🌟 核心知识点速查

### 1. Stable Diffusion 原理

```
正向加噪:
  q(x_t|x_{t-1}) = N(√α_t · x_{t-1}, (1-α_t)I)
  x_t = √α̅_t · x_0 + √(1-α̅_t) · ε,  ε~N(0, I)

反向去噪(Latent Diffusion):
  - 在 VAE latent z 上做扩散,VAE 编解码像素与潜空间
  - Text Encoder 把 prompt 转 token embedding
  - UNet 多尺度去噪,Cross-Attention 注入文本条件

CFG(Classifier-Free Guidance):
  ε = (1+w)·ε_cond - w·ε_uncond
  w 越大,模型越"听 prompt"
```

### 2. LoRA 低秩微调

```
冻结 W,只学 ΔW = BA(B ∈ R^{d×r}, A ∈ R^{r×d}, r<<d)
W' = W + BA

工程优势:
- 成本低:只需训练几个 MB 的 BA 矩阵
- 切换快:不同 LoRA 叠加或切换无需重新加载主模型
- 上线风险低:异常时可快速回滚
```

### 3. ArcFace Loss

```
L = -log( exp(s·cos(θ_y + m)) / (exp(s·cos(θ_y + m)) + Σ_{j≠y} exp(s·cos(θ_j))) )

- θ_y: 类别 y 的角度
- m: 角度边界(常用 0.5)
- s: 缩放因子(常用 30-64)
- 比 Softmax 更适合人脸识别
```

### 4. Tweedie GLM

```
Var(Y) = φ · μ^p,    1 < p < 2   (复合泊松-伽马分布)

特点:
- 允许 Y=0(零赔付率高)
- 对长尾赔付分布友好

log 链接:    η = Xβ,  μ = exp(η)
exp(β_k) = 乘性费率因子

训练:IRLS(迭代加权最小二乘)
评估:离差残差 + 卡方近似 + 十分位 Lift
```

### 5. PyVRP / DVRP

```python
# 动态车辆路径问题
# 步骤:
#   1. 插入启发式 → 可行解
#   2. 局部搜索 (2-opt / relocate) → 改进
#   3. 元启发式 (GA / Tabu / ACO) → 收敛
# 动态场景下实时性优先
```

### 6. 蚁群算法(ACO)

```
状态转移:  P(i→j) ∝ τ^α · η^β
信息素更新:  τ_ij ← (1-ρ) · τ_ij + Σ_k Δτ^k_ij

α: 信息素权重(历史经验)
β: 启发因子权重(贪心)
ρ: 蒸发率(避免信息素饱和)
```

### 7. GeoHash 召回

```
长度    区域大小          含 8 邻域最长距离
5 位    5km × 5km         14km
4 位    25km × 25km       65km
3 位    125km × 125km     350km

多因子评分:
综合分 = 0.4 × 匹配度 + 0.3 × 距离成本 + 0.3 × (空闲 + 履约)
```

### 8. 风控闭环

```
识别 (Identify) → 预警 (Alert) → 干预 (Act) → 复盘 (Review)

模型选择:
- 规则引擎(可解释强,上线快)
- GBDT(预测概率,精度高)
- 异常检测(发现未知模式)
- 概率校准(阈值统一)
```

### 9. 视觉 SLAM 回环

```
NetVLAD / GeM 描述符
+ KNN 召回候选回环
+ RANSAC 几何验证(过滤假回环)
+ 位姿估计

GeM 池化:
f_k = ( (1/|X|) · Σ x_k^p )^(1/p)
```

---

## 📊 面试防御三原则

```
1. 先报口径(耗时/指标怎么算)
   ↓
2. 再报证据链(日志/评测/对比实验)
   ↓
3. 最后实现细节(为什么这样设计)
```

---

## 📚 详细文档索引

| 编号 | 主题 | 文档入口 |
|------|------|---------|
| 00 | 智能体/生成式 AI 工程化总框架 | [00-总框架.md](./00-总框架.md) |
| 01 | Stable Diffusion / LDM / CFG | [01-stable-diffusion.md](./01-stable-diffusion.md) |
| 02 | ControlNet / 结构控制 | [02-controlnet.md](./02-controlnet.md) |
| 03 | LoRA 低秩微调 | [03-lora.md](./03-lora.md) |
| 04 | U²-Net / SAM 抠图 | [04-u2net-sam.md](./04-u2net-sam.md) |
| 05 | FastAPI 异步队列 | [05-inference-engineering.md](./05-inference-engineering.md) |
| 06 | 数字人短视频 | [06-digital-human-video.md](./06-digital-human-video.md) |
| 07 | React/Next.js/tRPC | [07-frontend-toolkit.md](./07-frontend-toolkit.md) |
| 08 | Tweedie GLM | [08-car-insurance-pricing.md](./08-car-insurance-pricing.md) |
| 09 | MTCNN/MobileNet/ArcFace | [09-face-recognition.md](./09-face-recognition.md) |
| 10 | DVRP/3D-BPP | [10-logistics-optimization.md](./10-logistics-optimization.md) |
| 11 | MDP/RL + ACO | [11-truck-dispatch-rl-aco.md](./11-truck-dispatch-rl-aco.md) |
| 12 | 风控闭环 | [12-risk-emergency.md](./12-risk-emergency.md) |
| 13 | Lakehouse + IaaS | [13-freight-hub-data.md](./13-freight-hub-data.md) |
| 14 | GeoHash + 多因子 | [14-vehicle-cargo-matching.md](./14-vehicle-cargo-matching.md) |
| 15 | 近红外光谱 + 视觉 SLAM | [15-research-projects.md](./15-research-projects.md) |
| 附录 | 术语速查 | [appendix-glossary.md](./appendix-glossary.md) |

---

## ⚠️ 配套资源

原始 PDF 已脱敏整理为 Markdown:

- `01简历算法与技术原理详解_朱东.pdf` (9 页) → 拆分为本目录 15 个文档
- `03技术资产_2025年_数据研发部_交通物流-*` 5 份 → 见项目 4 子目录
- `面试项目经验QA_朱东.docx` → 见 [`../docs/interview-qa.md`](../docs/interview-qa.md)

---

## 📜 License

MIT License - 详见 [`../../LICENSE`](../../LICENSE) 文件。
