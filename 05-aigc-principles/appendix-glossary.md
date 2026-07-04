# 附录:术语与指标速查

## A. 性能与推理指标

### 端到端耗时 vs 纯推理耗时

| 名称 | 包含内容 |
|------|---------|
| **端到端耗时** | 入队 + 推理 + 后处理 + 传输 + 回传 |
| **纯推理耗时** | 仅 GPU 推理时间 |

**口径必须先报告**,否则指标无意义。

### P95 / P99 延迟

```
P95: 95% 的请求延迟 ≤ 此值
P99: 99% 的请求延迟 ≤ 此值
```

反映"尾延迟",体现最坏情况。

### 吞吐 vs 并发

```
吞吐 (Throughput): 单位时间处理的请求数(请求/秒)
并发 (Concurrency): 同时处理的请求数

数学关系: 延迟 L、并发 C、吞吐 T: T = C / L (Little's Law)
```

## B. 计算机视觉指标

### FAR / FRR

```
FAR (False Accept Rate) = 误识率 = 错误接受数 / 实际陌生人次数
FRR (False Reject Rate) = 拒识率 = 错误拒绝数 / 实际本人次数
```

**安全场景更看 FAR**(防止陌生人通过)。

### Top-1 准确率

```
Top-1: 模型预测的 top-1 类别 == 真实类别 的比例
Top-5: 真实类别出现在 top-5 预测中 的比例
```

**必须先说阈值与评测集口径**。

### Lift 提升度

```
Lift @ 十分位 k = 实际正例比例 / 总体正例比例
```

模型排名能力指标,Lift 越大模型区分能力越强。

## C. 调度与优化指标

### 装载率

```
装载率 = 已装载体积 / 货厢容积
```

### 准时率

```
准时率 = 准时完成订单数 / 总订单数
```

### 平均响应时长

```
识别延迟 + 预警延迟 + 干预延迟 = 总响应时长
```

## D. 训练指标

### 收敛监控

- 训练 loss: 应该持续下降
- 验证 loss: 不应过拟合(应同步下降或提前停止)
- IRLS(广义线性模型): 对数似然变化小于阈值

### AUC / EER

```
AUC (Area Under ROC): 越大越好,1 表示完美
EER (Equal Error Rate): FAR = FRR 的点,越小越好
```

## E. 数据 / ETL 指标

### ret=0 / ret=-1

```
ret=0:  业务调用成功,有返回数据
ret=-1: 业务调用成功,但无数据(空记录)
空:     业务调用无响应
```

**健康度报告**: 统计 ret=0 比例是否正常(< 10% 视为警告)。

## F. 生成式 AI 专有

### steps 与时间关系

```
时间 ≈ steps × 单步时间
单步时间 ≈ UNet forward 时间(分辨率²)
```

### CFG Scale 取值经验

| 场景 | 推荐 CFG |
|------|---------|
| 写实风格 | 6-8 |
| 艺术风格 | 7-9 |
| 写实 + LoRA | 5-7 |
| 创意发散 | 9-12 |

### LoRA rank 选择

| 场景 | 推荐 rank |
|------|---------|
| 简单风格 | 4-8 |
| 角色一致性 | 16-32 |
| 复杂任务 | 64+ |

## G. 通用机器学习

### 偏差-方差权衡

```
偏差(欠拟合) + 方差(过拟合) ≈ 总误差
通过正则化 / 数据增强 / 模型简化平衡
```

### 准确率 vs 召回率

```
准确率 = TP / (TP + FP)
召回率 = TP / (TP + FN)

F1 = 2 × (准确率 × 召回率) / (准确率 + 召回率)
```

## H. 缩写速查

| 缩写 | 全称 | 含义 |
|------|------|------|
| SD | Stable Diffusion | 潜在扩散模型 |
| LDM | Latent Diffusion Model | 潜在空间扩散 |
| VAE | Variational Autoencoder | 变分自编码器 |
| CFG | Classifier-Free Guidance | 无分类器引导 |
| LoRA | Low-Rank Adaptation | 低秩自适应 |
| PiP | Picture-in-Picture | 画中画 |
| LLM | Large Language Model | 大语言模型 |
| VLM | Vision Language Model | 视觉语言模型 |
| MCP | Model Context Protocol | 模型上下文协议 |
| PyVRP | Python VRP Solver | 开源 VRP 求解器 |
| BPP | Bin Packing Problem | 装箱问题 |
| GA | Genetic Algorithm | 遗传算法 |
| TS | Tabu Search | 禁忌搜索 |
| LS | Local Search | 局部搜索 |
| ACO | Ant Colony Optimization | 蚁群优化 |
| MDP | Markov Decision Process | 马尔可夫决策过程 |
| IRLS | Iteratively Reweighted Least Squares | 迭代加权最小二乘 |
| GLM | Generalized Linear Model | 广义线性模型 |
| CV | Computer Vision | 计算机视觉 |
| OCR | Optical Character Recognition | 光学字符识别 |
| DMS | Driver Monitoring System | 驾驶员监测 |
| ADAS | Advanced Driver-Assistance System | 高级驾驶辅助 |
| IoT | Internet of Things | 物联网 |

## I. 关键经验

### 模型能力 vs 工程化

模型能力决定上限,**工程化决定下限**。

### 训练 vs 推理

训练时关心**精度 / 收敛**;推理时关心**延迟 / 吞吐 / 成本**。

### 开源 vs 自研

- 开源:起步快、社区好、质量参差
- 自研:可控、长期成本低、风险高

**实际项目**: 优先开源,有差异化需求时再自研。
