# 👤 项目 3：人脸识别 + 活体检测生产服务

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org)
[![Redis](https://img.shields.io/badge/Queue-Redis-red.svg)](#技术架构)
[![Models](https://img.shields.io/badge/Models-3--Backends-brightgreen.svg)](#多模型后端)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

> 基于 Redis 消息队列的人脸识别 + 活体检测生产级服务,多模型后端可插拔、多实例水平扩展。

---

## 🎯 项目目标

为生产环境提供**抗照片攻击**的人脸活体检测服务:

```
Redis 消息队列(待处理图) 
  → 接收任务 
  → InsightFace 人脸检测 
  → DeePixBis 活体分类 
  → Redis 回传结果
```

核心能力:
- 抗照片攻击(活体检测,Deepfake 防护)
- 三种人脸检测后端可插拔(InsightFace / cv2.dnn / dlib)
- 多实例水平扩展(`--inst_id`)
- 单/多人脸模式自适应
- 完整的 Redis 异步消息总线

---

## 📦 项目结构

```
03-face-recognition-production/
├── README.md                              # 本文档
├── requirements.txt                       # 依赖清单
├── anti-spoof-service/                    # 活体检测服务
│   ├── anti_spoof_service.py             # 主程序 (Redis 消息循环)
│   ├── face_service.py                    # 人脸识别服务
│   ├── file_service.py                    # 文件管理服务
│   └── license_service.py                 # 车牌识别服务 (OCR)
├── models/                                # 模型层
│   ├── model.py                           # 抽象基类 Model
│   ├── insightface_model.py               # InsightFace 人脸检测
│   ├── cv2dnn_model.py                    # cv2.dnn 检测 + dlib 特征
│   ├── dlib_model.py                      # dlib HOG/SVM 检测
│   ├── deepixbis_model.py                 # DeePixBis 活体分类
│   ├── anti_spoof_model.py                # 活体检测业务封装
│   ├── mask_model.py                      # SSD-like 口罩检测
│   └── MainModel.py                       # 手写 KitModel 神经网络
└── configs/
    └── service_config.example.yaml        # 服务配置示例(不含生产密钥)
```

---

## ⚙️ 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖:
- `insightface` - 工业级人脸识别库
- `opencv-python` - OpenCV DNN 推理
- `dlib` - 经典 HOG/SVM 人脸检测
- `torch` - PyTorch 用于 KitModel + DeePixBis
- `redis` - 消息队列

### 2. 配置 Redis 连接

通过环境变量注入(生产环境推荐):

```bash
# Linux / macOS
export REDIS_HOST="your.redis.host"
export REDIS_PORT="6379"
export REDIS_PASSWORD="your-secure-password"
export REDIS_DB="0"

# 设置消息队列 key 配置
export ANTI_SPOOF_MSG_KEY="anti_spoof:request"
export ANTI_SPOOF_RESP_KEY_PREFIX="anti_spoof:response:"
```

> ⚠️ **不要**在代码中硬编码 Redis 密码!

### 3. 启动服务

```bash
# 单实例启动
python anti-spoof-service/anti_spoof_service.py --inst_id 1

# 多实例水平扩展(每进程一个 inst_id)
python anti-spoof-service/anti_spoof_service.py --inst_id 1 &
python anti-spoof-service/anti_spoof_service.py --inst_id 2 &
python anti-spoof-service/anti_spoof_service.py --inst_id 3 &
```

---

## 🌟 技术亮点

### 1. Redis 异步消息总线

```
                       ┌─────────────────────────────┐
请求侧(caller)         │     Redis Message Bus      │      服务端(daemon)
                       │                             │
   push msg ─────────→ │ ANTI_SPOOF_FACE_MESSAGE_KEY │ ←── pop msg (BLPOP)
   (uid 标记)         │   - data: image_items       │
                       │   - uid: 请求唯一标识        │
                       │   - use_multiple_faces      │
                       │                             │ ┌──────────────┐
                       │                             │ │ InsightFace  │
                       │                             │ │ 特征提取      │
                       │                             │ └──────┬───────┘
                       │                             │        │
                       │                             │ ┌──────▼───────┐
                       │                             │ │ DeePixBis   │
                       │                             │ │ 活体分类      │
                       │                             │ └──────┬───────┘
   ←───── push back ──┤  RESPONSE_KEY_PREFIX + uid   │        │
   (code/data/status) │                             │ ←─────┘
                       └─────────────────────────────┘
```

**请求结构**:
```json
{
  "data": [image_items],
  "uid": "request-uuid-xxx",
  "use_multiple_faces": false
}
```

**响应结构**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "status": "success",
    "image_list": [
      {
        "image_id": "...",
        "image_name": "...",
        "num_faces": 1,
        "face_id": 0,
        "face_box": [x1, y1, x2, y2],
        "real_face_prob": 0.9876
      }
    ]
  },
  "seqNo": "...",
  "instance_id": "1",
  "datetime": "2026-01-15 12:34:56"
}
```

### 2. 三种人脸检测后端可插拔

| 后端 | 实现 | 优势 | 适用场景 |
|------|------|------|---------|
| **InsightFace** | `insightface.app.FaceAnalysis` | 工业级精度,支持 GPU | 生产环境推荐 |
| **cv2.dnn + dlib** | `cv2.dnn` + dlib 关键点 | CPU 推理快 | 边缘设备/无 GPU |
| **dlib HOG/SVM** | `dlib.get_frontal_face_detector` | 纯 CPU,零依赖 | 轻量级场景 |

```python
class Model(ABC):
    """所有模型后端的抽象基类"""
    @abstractmethod
    def extract(self):
        """提取单张图片的人脸特征"""
        pass

    @abstractmethod
    def extract_multiple_faces(self):
        """提取单张图片的多张人脸特征"""
        pass

    @abstractmethod
    def predict(self, image):
        """预测接口"""
        pass
```

### 3. DeePixBis 活体检测 (DenseNet161 Encoder-Decoder)

```python
class DeePixBisModel:
    """基于像素级监督的活体检测"""
    def __init__(self):
        self.encoder = DenseNet161(pretrained=True)
        self.decoder = Decoder(...)
        self.model.load_state_dict(torch.load("deepixbis.pth"))

    def predict(self, face_image) -> float:
        """返回 0~1 的真实人脸概率"""
        mask, prob = self.model.forward(face_image)
        return prob  # >0.5 视为真脸
```

**核心思想**: 真实人脸图像与照片/视频在像素级有细微差异(纹理、反射等),
通过 Encoder-Decoder 学习这些差异来识别伪造。

### 4. SSD-like 口罩检测

```python
class MaskModel(Model):
    """SSD 架构 2 类(口罩/无口罩)口罩检测"""
    def __init__(self):
        self.anchors = generate_anchors()
        self.num_classes = 2  # Mask / NoMask

    def predict(self, image):
        # 多尺度特征 + anchor 生成 + NMS
        boxes, scores = self.detect(image)
        # output: (boxes, classes, scores)
```

### 5. 多实例水平扩展

```bash
# 每进程独立 inst_id,Redis 自然做负载均衡
python anti_spoof_service.py --inst_id 1
python anti_spoof_service.py --inst_id 2
python anti_spoof_service.py --inst_id 3
```

设计要点:
- **无状态服务**: 服务端不维护任何 session 状态
- **多进程隔离**: 每个进程独立加载模型(充分利用多 GPU)
- **响应 trace**: 通过 `instance_id` 字段追踪每个响应的处理实例

### 6. 完整的错误处理

```python
while True:  # 永驻 daemon
    try:
        message = _redis.pop_data(QUEUE_KEY, blocking=True)
        # ... 业务处理 ...
    except FaceDetectionError as e:
        resp_info["code"] = ReturnCode.ANTI_SPOOF_IMAGE_ERROR
        resp_info["data"]["status"] = str(e)
    except Exception as e:
        logger.error(f"unexpected: {e}")
        resp_info["code"] = ReturnCode.SYSTEM_ERROR
    finally:
        # 始终回传响应
        if message_uid:
            _redis.push_data(resp_info, message_uid)
```

每张图片独立 try/except,**单张失败不影响整体**。

---

## 📊 性能指标

| 指标 | 数值 | 备注 |
|------|------|------|
| 单图耗时 | 200-500ms | InsightFace 主后端 |
| 活体检测耗时 | 100-200ms | DeePixBis DenseNet161 |
| 总耗时(pipeline) | 300-700ms | 包括前后处理 |
| 支持并发 | 取决于 Redis | 多实例可水平扩展 |
| 模型加载时间 | ~5-10s | 启动时一次加载 |

---

## 🛡️ 生产部署清单

- [ ] Redis 高可用(哨兵/Cluster)
- [ ] 模型权重文件使用 [Git LFS](https://git-lfs.github.com/) 管理
- [ ] 使用 systemd/supervisord 管理 daemon
- [ ] 监控:消息队列积压、响应延迟、错误率
- [ ] 优雅启动/停机(SIGTERM 处理)
- [ ] 健康检查接口 `/health`
- [ ] 配置中心(etcd/Consul/Nacos)

---

## ⚠️ 安全提示

1. **代码仅供学习**: 本仓库不包含生产模型权重与 Redis 凭证
2. **合规要求**: 人脸数据涉及个人信息保护法(PIPL),生产环境需通过合规审查
3. **数据脱敏**: 不要上传任何真实人脸图像至仓库
4. **访问控制**: Redis 应在内网/VPC 中,禁止公网直连

---

## ⚠️ 已知限制

1. **当前实现依赖 Redis**: 暂不支持 Kafka/RabbitMQ
2. **同步推理**: 未实现 gRPC 流式协议(HTTP+轮询)
3. **未实现模型热更新**: 需要重启 daemon
4. **抗攻击能力**: 高级 Deepfake(3D 面具、GAN 生成)需要更复杂的检测

---

## 📜 License

MIT License - 详见 [`../LICENSE`](../LICENSE) 文件。
