# 04. U²-Net / SAM:抠图与边缘处理

## 4.1 U²-Net:RSU 多尺度上下文

**U²-Net** 用于显著性/前景分割,RSU (ReSidual U-block) 把多尺度上下文嵌入 block,兼顾语义与边缘。

```
┌────────────────────────────────────────┐
│        U²-Net 结构                       │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  En_1 (RSU-7)                      │  │
│  └────────────┬───────────────────────┘  │
│               ▼                           │
│  ┌────────────────────────────────────┐  │
│  │  En_2 (RSU-6) ── De_1              │  │
│  └────────────┬───────────────────────┘  │
│               ▼                           │
│  ┌────────────────────────────────────┐  │
│  │  En_3 (RSU-5) ── De_2              │  │
│  └────────────┬───────────────────────┘  │
│               ▼                           │
│  ... (嵌套 U 形)                          │
│                                          │
└────────────────────────────────────────┘
```

**核心优势**:
- **深监督**: 多级损失在不同深度
- **嵌套 U 形**: 多尺度特征融合
- **细节保留**: RSU 的残差连接保留边缘细节

```python
import torch
from u2net import U2NET

model = U2NET(3, 1)  # 输入 RGB(3 通道),输出 1 通道显著性图
model.load_state_dict(torch.load("u2net.pth"))
model.eval()

# 推理
with torch.no_grad():
    saliency_map = model(input_image)  # 0-1 范围的显著性图
mask = (saliency_map > 0.5).float()  # 二值化前景 mask
```

## 4.2 SAM:Promptable Segmentation

**SAM (Segment Anything Model)** 由 Meta AI 提出:
- **ViT 图像编码器**: 一次性编码整张图像
- **Prompt 编码器**: 点 / 框 / mask 作为提示
- **Mask 解码器**: 输出多个候选分割 + 置信度

```
┌──────────────────────────────────────────┐
│              SAM 工作流                    │
│                                           │
│    输入图像 → ViT Encoder → Image Embedding │
│                                           │
│    Prompt (点/框) → Prompt Encoder         │
│                                           │
│         Image + Prompt Embeddings          │
│                  ↓                          │
│           Mask Decoder                      │
│                  ↓                          │
│       多个候选 mask + IoU 预测              │
└──────────────────────────────────────────┘
```

**特点**:
- **泛化强**: 零样本/少样本分割多种对象
- **推理重**: ViT-L / ViT-H 计算量大
- **提示驱动**: 用点/框指定目标

```python
from segment_anything import sam_model_registry, SamPredictor
import numpy as np

sam = sam_model_registry["vit_b"](checkpoint="sam_vit_b.pth")
predictor = SamPredictor(sam)

predictor.set_image(image)
masks, scores, logits = predictor.predict(
    point_coords=np.array([[500, 375]]),  # 一个前景点
    point_labels=np.array([1]),
    multimask_output=True,
)
```

## 4.3 后处理要点

分割不是终点,**后处理才是从"可用"到"高质量"的关键**:

### 羽化 (Feathering)

```python
import cv2

# 生成柔软的边缘
def feather_mask(mask, kernel_size=15):
    """mask 边缘羽化,避免硬切"""
    blurred = cv2.GaussianBlur(mask.astype(np.float32), (kernel_size, kernel_size), 0)
    return blurred
```

### 形态学操作

```python
# 膨胀 + 腐蚀 = 开运算 (去小噪点)
opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

# 闭运算 (填洞)
closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

# 连通域分析 (取最大连通块)
num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
cleaned = (labels == largest_label).astype(np.uint8)
```

### 对齐

分割 mask 与原图的**坐标映射一致性**:
- 模型输出和原图分辨率必须匹配
- 必要时上采样
- 校验 bbox 是否合理

## 4.4 在项目中的应用:证件照生成

证件照场景的特殊挑战:
- **头发边缘**: 发丝级别的精细分割
- **背景**: 干净纯色(白/蓝/红)
- **人脸比例**: 标准 3:2 或 2:2

```python
def generate_id_photo(raw_image, bg_color=(255, 255, 255)):
    """证件照生成流水线"""
    # 1. 显著性检测
    saliency_map = u2net_model(raw_image)
    alpha_mask = extract_alpha(saliency_map)

    # 2. 后处理:羽化 + 形态学
    alpha_feathered = feather_mask(alpha_mask, kernel_size=7)
    alpha_clean = morphological_cleanup(alpha_feathered)

    # 3. 合成新背景
    new_bg = np.ones_like(raw_image) * np.array(bg_color)
    composite = (raw_image * alpha_clean[..., None]
                 + new_bg * (1 - alpha_clean[..., None]))

    # 4. 标准裁剪 + 缩放
    cropped = crop_to_face(composite, face_bbox, target_size=(295, 413))

    return cropped
```

## 4.5 U²-Net vs SAM 对比

| 维度 | U²-Net | SAM |
|------|--------|-----|
| 训练数据量 | 中等(显著性数据集) | 超大(SA-1B 11M 图) |
| 推理速度 | 快 | 慢(ViT 大模型) |
| 显存需求 | 低 | 高 |
| 适用场景 | 单前景分割 | 通用分割,多目标 |
| 提示方式 | 无需提示 | 点/框/mask |
| 部署 | 边缘设备友好 | 服务器 GPU |

**项目选择**: 证件照这种"高质量单前景"场景,**U²-Net 更合适**(快、稳、可量化部署);
SAM 更适合"灵活多目标"场景。

## 4.6 面试高频问题

### Q: U²-Net 的 RSU 解决了什么问题?

**A**: 多尺度上下文 + 残差连接,在不损失边缘细节的前提下捕捉大范围语义信息。

### Q: SAM 在证件照场景为什么不够好?

**A**: SAM 是通用分割,需要 prompt;对于"未知前景"的纯背景替换,反而需要更多后处理。

### Q: 怎么评估扣图质量?

**A**:
- 边缘准确率(人工抽检)
- 边缘过渡自然度
- 头发丝级别细节保留
- 二值化后连通域正确性
