# 03. LoRA:低秩微调(风格/一致性)

## 3.1 原理与公式

LoRA (Low-Rank Adaptation) 通过低秩分解近似权重的增量更新:

```
冻结 W,只学习 ΔW = B·A

W' = W + B·A
B ∈ R^(d×r), A ∈ R^(r×d), r << d
```

**核心思想**: 完整微调时 ΔW 可能是满秩的,但实际所需的"任务特定变化"通常是低秩的。

```
原参数量: d×d
LoRA 参数量: d×r + r×d = 2dr

压缩比: 2dr / d² = 2r/d

当 r=4, d=1024 时,压缩比 = 8/1024 ≈ 0.78%
```

## 3.2 训练与部署

### 训练要点

- **数据一致性第一位**: 数据质量 > 数据量
- **控制 rank / 步数**: rank 越大能力越强但容易过拟合;步数太多同样过拟合
- **典型参数**: rank = 4-32, learning rate = 1e-4

### 部署要点

- **按需加载**: 不同风格用不同 LoRA,运行时切换
- **多 LoRA 叠加**: 注意权重和顺序
- **快速回滚**: 主模型不变,只需替换 LoRA 即可恢复

## 3.3 工程优势 vs 全量微调

| 维度 | 全量微调 | LoRA |
|------|---------|------|
| 训练参数量 | 全部 | 仅 0.78%-1% |
| 显存需求 | 高 | 低(可训练大模型) |
| 训练时间 | 长 | 短 |
| 模型文件大小 | GB 级 | MB 级 |
| 切换成本 | 重启服务 | 热切换 |
| 部署风险 | 高 | 低 |
| 实验迭代速度 | 慢 | 快 |

## 3.4 在项目中的具体应用

### 证件照风格锁定

```python
# 在文生图管线中加入 LoRA
pipeline = StableDiffusionXLPipeline.from_pretrained("base_model")
lora_path = "lora/id_photo_style.safetensors"
pipeline.load_lora_weights(lora_path)

# 推理时 LoRA 权重生效
image = pipeline(
    prompt="portrait photo, formal, white background",
    negative_prompt="blurry, low quality",
    num_inference_steps=30,
    cross_attention_kwargs={"scale": 0.85},  # LoRA 权重
).images[0]
```

### 多场景 LoRA 切换

| LoRA 名称 | 用途 | 触发条件 |
|---------|------|---------|
| `id_photo_v1.safetensors` | 证件照风格 | 业务类型=证件照 |
| `artistic_painting.safetensors` | 艺术绘画 | 业务类型=艺术照 |
| `realistic_portrait.safetensors` | 写实人像 | 业务类型=写实 |

## 3.5 与其他微调方法对比

### LoRA vs DreamBooth

- **DreamBooth**: 微调整个 UNet + Text Encoder,学习新主体(人/物)的 few-shot
- **LoRA**: 在不改变主模型的前提下加一个低秩增量

### LoRA vs Adapter

- **Adapter**: 在 Transformer block 中插入小型全连接网络
- **LoRA**: 直接修改 attention 权重

LoRA 通常更轻量,且推理时可通过合并权重做到零开销。

### LoRA vs Textual Inversion

- **Textual Inversion**: 学习新的"伪 token"嵌入,不动主模型
- **LoRA**: 学习权重增量,影响范围更大(全层)

LoRA 在"风格迁移"上更强;Textual Inversion 在"新概念注入"上更轻。

## 3.6 面试要点

### Q: LoRA 为什么 ΔW = BA 且 r<<d 就能逼近全量微调?

**A**:
1. 实际"任务特定变化"通常在低秩子空间
2. 经验上 r=4 已经能覆盖 95% 的表达能力
3. r 越大能力越强,但容易过拟合

### Q: LoRA 的 rank 怎么选?

**A**:
- 风格迁移: r=4-8
- 角色一致性: r=16-32
- 复杂任务: r=64+
- 经验公式: 大约 100 张图对应 r=8

### Q: 多 LoRA 怎么叠加?

**A**:
- **权重混合**: `W' = W + Σ w_i · BA_i`,每个 LoRA 一个权重
- **顺序敏感**: 前面的 LoRA 影响更大
- **工程上常用**: 把多个 LoRA 权重动态加权,避免显式叠加
