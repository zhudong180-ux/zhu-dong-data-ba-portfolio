# 02. ControlNet:结构条件注入(边缘/姿态/深度/分割)

## 2.1 解决什么

**核心目标**: 把"结构先验"写进扩散过程:**锁住构图/姿态/轮廓**,避免生成漂移。

**典型条件**:
- **Canny / Lineart**: 边缘图,锁定物体轮廓
- **OpenPose**: 人体姿态,锁定关节位置
- **Depth**: 深度图,锁定空间结构
- **Seg**: 语义分割图,锁定物体类别与分布

**与 LoRA 组合**:
- ControlNet 控结构
- LoRA 控风格/一致性
- 需要调权重避免过约束

## 2.2 原理直觉

在 UNet 旁边**加条件分支**,把条件图编码成特征并注入 UNet 多尺度;**主模型不变**,等于外挂"结构控制器"。

```
┌──────────────────────────────────────────┐
│         ControlNet 结构                     │
│                                           │
│   ┌───────────────┐                       │
│   │  条件编码器     │ ← Canny/Depth/...    │
│   └───────┬───────┘                       │
│           ▼                               │
│   ┌───────────────┐                       │
│   │ Zero Conv     │(零卷积,训练起点)      │
│   └───────┬───────┘                       │
│           ▼                               │
│   ┌───────────────┐                       │
│   │  注入到 UNet   │ ← 多尺度注入          │
│   └───────────────┘                       │
└──────────────────────────────────────────┘
```

**关键创新**:
- **零卷积 (Zero Convolution)**: 1×1 卷积,初始化为 0
- 训练初期:**条件分支输出 = 0,不影响主模型**(保护主模型能力)
- 训练后期:**条件分支逐渐学习**,渐进式影响扩散过程

## 2.3 典型条件

### Canny 边缘图

```python
import cv2

def get_canny(image, low_threshold=100, high_threshold=200):
    """生成 Canny 边缘图"""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, low_threshold, high_threshold)
    # 转 3 通道
    edges_rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
    return edges_rgb
```

### OpenPose 姿态图

```python
from controlnet_aux import OpenposeDetector

pose_detector = OpenposeDetector.from_pretrained("lllyasviel/Annotators")
pose_image = pose_detector(image)
```

### 深度图

```python
from controlnet_aux import MidasDetector

depth_estimator = MidasDetector.from_pretrained("lllyasviel/Annotators")
depth_map = depth_estimator(image)
```

### 语义分割

```python
from controlnet_aux import SegformerDetector

segmenter = SegformerDetector.from_pretrained("lllyasviel/Annotators")
seg_map = segmenter(image)
```

## 2.4 工程实践

### 典型应用:人像背景替换 + 结构锁定

```python
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel

# 加载 ControlNet
controlnet = ControlNetModel.from_pretrained(
    "lllyasviel/control_v11p_sd15_openpose"
)
pipeline = StableDiffusionControlNetPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    controlnet=controlnet,
)

# 加载 LoRA
pipeline.load_lora_weights("path/to/lora")

# 推理
result = pipeline(
    prompt="professional ID photo, white background, formal attire",
    negative_prompt="blurry, deformed",
    image=pose_image,                # 控制图
    num_inference_steps=30,
    guidance_scale=7.5,
    controlnet_conditioning_scale=0.8,  # ControlNet 强度
    cross_attention_kwargs={"scale": 0.85},  # LoRA 强度
).images[0]
```

### 关键参数

| 参数 | 含义 | 典型值 |
|------|------|--------|
| `controlnet_conditioning_scale` | ControlNet 强度 | 0.5 - 1.0 |
| LoRA `scale` | LoRA 强度 | 0.6 - 0.9 |
| 过高后果 | 过约束(姿态僵硬,风格不自然) | - |
| 过低后果 | 约束不足(姿态漂移) | - |

## 2.5 优缺点

### 优点

- **结构可控**: 大幅减少"姿态跳变"
- **不破坏主模型**: 主模型加 ControlNet 前后的能力保留
- **多种条件**: Canny/OpenPose/Depth/Seg 灵活组合

### 缺点

- **推理慢**: ControlNet 加一次 UNet forward
- **显存高**: 多条件时显存压力大
- **条件图质量依赖**: Canny 边缘若不稳定,生成也不稳定

## 2.6 面试高频问题

### Q: ControlNet 的"零卷积"为什么重要?

**A**:
- 训练初期条件分支输出 = 0,主模型行为不变
- 保护主模型的先验能力(避免灾难性遗忘)
- 训练后期条件分支逐渐学习,渐进式融入
- 这是 ControlNet 能"外挂"成功的关键工程创新

### Q: ControlNet 和 LoRA 怎么配合?

**A**:
- ControlNet 控**结构**(姿态、轮廓)
- LoRA 控**风格/一致性**(画面风格、人物特征)
- 二者通过 `controlnet_conditioning_scale` 和 LoRA `scale` 两个权重独立调节

### Q: 工程上 ControlNet 失效怎么排查?

**A**:
1. 控制图本身是否正确生成?
2. Conditioning scale 是否设得过低?
3. ControlNet 是否针对主模型微调过(SD1.5 vs SDXL)?

## 2.7 在项目中的应用场景

| 场景 | 控制图 | 业务价值 |
|------|--------|---------|
| **证件照** | OpenPose | 锁住姿态(不能歪头/闭眼) |
| **头像生成** | Canny | 锁住脸部轮廓(避免变形) |
| **背景替换** | 语义分割 + 抠图 | 锁住主体,换背景不跑偏 |
| **艺术肖像** | Depth | 锁住空间感 |
