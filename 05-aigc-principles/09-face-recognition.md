# 09. 人脸识别:MTCNN + MobileNet + ArcFace

## 9.1 MTCNN 对齐

**MTCNN (Multi-task Cascaded Convolutional Networks)**:
- 三级网络: P-Net → R-Net → O-Net
- 输出: 边界框 + 5 个关键点(左眼、右眼、鼻、左嘴角、右嘴角)
- 关键点对齐后做仿射变换,将人脸标准化到固定位置

**对识别精度的影响**:
- 对齐稳定决定 embedding 质量
- 决定阈值设置是否稳定
- 不对齐会让相似度计算变得不可靠

```python
import facenet_pytorch

# MTCNN 用于人脸检测 + 关键点对齐
mtcnn = MTCNN(
    image_size=160, margin=0, min_face_size=20,
    thresholds=[0.6, 0.7, 0.7], factor=0.709, post_process=True,
    device='cuda' if torch.cuda.is_available() else 'cpu'
)

# 检测 + 对齐
boxes, probs, landmarks = mtcnn.detect(img, landmarks=True)
```

## 9.2 MobileNet 轻量化

**MobileNet** 用**深度可分离卷积**显著降低计算与参数:

```
标准卷积:  FLOPs = H · W · D_F · D_F · D_K · D_K · M
深度可分离: FLOPs = H · W · D_F · D_F · M · (D_K · D_K + M)
压缩比例: ~1/D_K² + 1/M (通常为 1/8 到 1/9)
```

适合在线部署:
- CPU 推理
- 移动端 / 嵌入式
- 实时视频流

## 9.3 ArcFace 损失

```
L = -log( exp(s·cos(θ_y + m)) / (exp(s·cos(θ_y + m)) + Σ_{j≠y} exp(s·cos(θ_j))) )

θ_y: 类别 y 的角度
m:   角度边界(margin, 常用 0.5)
s:   缩放因子(scale, 常用 30-64)
```

**与 Softmax 的差异**:
- Softmax: L = -log(exp(W^T·x_y)/Σ exp(W_j^T·x_j))
- ArcFace: 在角度空间上加 margin,使得同类紧凑、异类分散

**优势**:
- 几何意义清晰(角度空间)
- 训练稳定、收敛快
- 特征判别力强

## 9.4 指标口径

**Top-1**: 模型在测试集上识别准确率。展示整体能力。

**安全场景更看 FAR / FRR**:
```
FAR = 错误接受数 / 实际陌生人次数(误识率)
FRR = 错误拒绝数 / 实际本人次数(拒识率)
```

**必须先说阈值与评测集口径**:
- 阈值: 阈值越低,FAR↑, FRR↓
- 不同阈值下 FAR/FRR 是权衡关系
- 生产环境应在**目标 FAR**(如 1/10000)下选阈值

```python
def compute_far_frr(scores_genuine, scores_impostor, threshold):
    """计算给定阈值下的 FAR 和 FRR"""
    # 本人相似度(应该接受)
    genuine_accepts = scores_genuine >= threshold
    genuine_rejects = ~genuine_accepts
    FRR = genuine_rejects.sum() / len(scores_genuine)

    # 陌生人相似度(应该拒绝)
    impostor_accepts = scores_impostor >= threshold
    impostor_rejects = ~impostor_accepts
    FAR = impostor_accepts.sum() / len(scores_impostor)

    return FAR, FRR
```

**ROC 曲线**: 不同阈值下的 (FAR, TPR=1-FRR),AUC 表示整体能力。

## 9.5 完整训练流程

```
1. 数据准备
   ├── 收集人脸数据集(CASIA-WebFace / VGGFace2 / Glint360K)
   ├── 清洗: 过滤低质量、无关人脸
   ├── MTCNN 检测 + 5 关键点对齐
   ├── 难例挖掘: 找出当前模型识别错误的样本
   └── 多阶段数据增强: 光照、遮挡、姿态

2. 训练
   ├── Backbone: MobileNet / IR-SE / ResNet
   ├── Loss: ArcFace / CosFace / SphereFace
   ├── 优化器: SGD + Warmup + Cosine Decay
   └── 多 GPU + 混合精度

3. 评估
   ├── 验证集(封闭世界): Top-1 准确率
   ├── 验证集(开放): ROC + EER
   ├── LFW / CFP-FP / AgeDB 等 benchmark
   └── 现场业务测试集

4. 部署
   ├── 模型转换: PyTorch → ONNX → TensorRT
   ├── 推理服务: gRPC + 多实例
   └── 监控: 推理延迟、GPU 利用率、识别准确率
```

## 9.6 工程化要点

- **模型量化**: FP16 / INT8 进一步降低推理时间
- **batch 推理**: 多张人脸同时处理提高吞吐
- **特征缓存**: 已注册用户特征入库,识别时只做相似度计算
- **兜底**: 检测不到人脸时不能强行识别
