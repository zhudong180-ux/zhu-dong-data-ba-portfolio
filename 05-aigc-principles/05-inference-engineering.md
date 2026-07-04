# 05. 推理与平台工程:FastAPI 异步队列 + 多进程/多实例 + FP16/batch

## 5.1 异步任务:task_id 状态机

AI 服务常被"长任务"困扰:Stable Diffusion 单图 1-5 秒,数字人视频生成分钟级。HTTP 请求同步等待会阻塞 worker,必须采用**异步任务状态机**。

### 架构图

```
┌──────────────────────────────────────────┐
│  客户端                                    │
│   POST /submit { prompt, params }         │
│        ↓                                   │
│   返回 { task_id: "abc-123" }              │
│                                            │
│   GET /status/abc-123                     │
│        ↓                                   │
│   返回 { status: "running", progress: 0.6 }│
│                                            │
│   GET /result/abc-123                     │
│        ↓                                   │
│   返回 { image_url: "..." }               │
└──────────────────────────────────────────┘
```

### 三层架构

```
┌──────────────────────────────────────────────┐
│  入口层 (API Gateway / FastAPI)               │
│  - 鉴权 / 校验 / 限流                          │
│  - 入队 + 返回 task_id                        │
│  - 不做 GPU 推理                              │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  执行层 (Worker)                              │
│  - 模型预加载(避免重复 load)                  │
│  - 拉任务 → 推理 → 后处理 → 写回状态与结果        │
│  - 多进程 / 多实例并行                         │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  状态层 (MySQL / Redis)                        │
│  - MySQL: 任务元数据 + 结果持久化               │
│  - Redis: 实时状态 + 队列 + 锁                  │
└──────────────────────────────────────────────┘
```

### FastAPI 入口示例

```python
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uuid

app = FastAPI()

class SubmitRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    steps: int = 30
    cfg_scale: float = 7.5


@app.post("/submit")
async def submit(req: SubmitRequest):
    """提交任务"""
    task_id = str(uuid.uuid4())

    # 1. 入口校验
    if req.width > 1024:
        raise HTTPException(400, "Resolution too high")

    # 2. 入队
    enqueue_task(task_id, req.dict())

    # 3. 持久化任务状态
    save_task_status(task_id, "queued")

    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """查询任务状态"""
    status = load_task_status(task_id)
    return {
        "task_id": task_id,
        "status": status,  # queued / running / success / failed
        "progress": load_progress(task_id),
    }


@app.get("/result/{task_id}")
async def get_result(task_id: str):
    """查询任务结果"""
    status = load_task_status(task_id)
    if status != "success":
        raise HTTPException(400, f"Task not ready: {status}")
    return {"task_id": task_id, "result_url": load_result_url(task_id)}
```

## 5.2 性能优化

### FP16 推理

```python
import torch
from diffusers import StableDiffusionPipeline

pipe = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float16,  # 关键:FP16
).to("cuda")

# 推理时自动使用 FP16
image = pipe("a cat", num_inference_steps=30).images[0]
```

**优势**:
- 显存减半(FP16 vs FP32)
- 推理速度提升 1.5x - 2x
- 对大多数模型精度影响可忽略

### batch 推理

```python
# 单次 batch 处理多张
prompts = ["a cat", "a dog", "a bird"]
images = pipe(prompts, num_inference_steps=30).images  # batch=3
```

**取舍**: batch 提升吞吐,但增延迟;实际场景需在 batch_size 与延迟之间权衡。

### 预加载

```python
class Worker:
    def __init__(self):
        # 服务启动时一次加载
        self.pipe = StableDiffusionPipeline.from_pretrained(...).to("cuda")
        self.pipe.enable_xformers_memory_efficient_attention()

    def process_task(self, task):
        # 直接推理,不重新加载模型
        image = self.pipe(task["prompt"]).images[0]
        return image
```

### 多进程 / 多实例

```python
# 多 GPU:每个进程绑定一个 GPU
# CUDA_VISIBLE_DEVICES=0 python worker.py &
# CUDA_VISIBLE_DEVICES=1 python worker.py &

# 单 GPU 多实例:用 MPS 或共享 GPU
# torch.cuda.set_per_process_memory_fraction(0.5)
```

**避免 OOM**: 限制最大 batch_size;超出时排队。

## 5.3 可靠性与可观测

### 关键工程实践

```python
class ReliableInferenceService:
    def submit_task(self, req):
        # 幂等
        if is_duplicate(req.fingerprint):
            return get_existing_task_id(req.fingerprint)

        # 有限重试(只对可恢复错误)
        try:
            task_id = self._execute_with_retry(req, max_retries=3)
        except TransientError:
            # 网络/资源抖动 → 可重试
            return self._retry_later(req)
        except PermanentError:
            # 参数错误 → 不重试,直接拒绝
            raise

        # 限流(令牌桶)
        if not self.rate_limiter.allow(req.user_id):
            raise RateLimitExceeded()

        return task_id
```

### 监控指标

- **业务指标**: 任务成功率 / 平均耗时 / 失败码分布
- **系统指标**: GPU 利用率 / 显存占用 / 队列长度 / 端到端延迟
- **告警**: 错误码激增 / 队列积压 / GPU 异常

### 优雅降级

```python
class InferenceService:
    def infer(self, req):
        try:
            return self.full_quality_inference(req)
        except OutOfMemoryError:
            # OOM → 降级到低分辨率
            return self.degraded_inference(req, scale=0.5)
        except ModelLoadError:
            # 模型加载失败 → 兜底服务
            return self.fallback_service(req)
```

## 5.4 工程指标(本项目实测)

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| **单图耗时** | 4.5s | 1.6-2.0s | -60% |
| **并发数** | 1 | 8 (单 GPU) | 8x |
| **首字延迟** | 5s | < 1s | -80% |
| **失败率** | 5% | < 1% | -80% |

**口径**: 同一硬件、同一分辨率、同一 steps/sampler/CFG;区分端到端 vs 纯推理。

## 5.5 长任务与前端协作

```typescript
// 前端轮询
async function pollTaskStatus(taskId: string) {
  while (true) {
    const { status, progress } = await api.get(`/status/${taskId}`);

    if (status === 'success') {
      return await api.get(`/result/${taskId}`);
    }
    if (status === 'failed') {
      throw new Error('Task failed');
    }

    // 退避策略:逐渐加大间隔
    await sleep(progress < 0.5 ? 1000 : 3000);
  }
}

// 或者用 SSE 替代轮询
const eventSource = new EventSource(`/status-stream/${taskId}`);
eventSource.onmessage = (e) => updateProgress(JSON.parse(e.data));
```

## 5.6 大文件上传

```python
# 分片上传
@app.post("/upload-chunk")
async def upload_chunk(
    chunk: UploadFile,
    task_id: str,
    chunk_index: int,
    total_chunks: int,
):
    """接收分片"""
    chunk_path = f"/tmp/upload/{task_id}/{chunk_index}"
    with open(chunk_path, "wb") as f:
        f.write(await chunk.read())

    # 全部上传完成时合并
    if all_chunks_received(task_id, total_chunks):
        merge_chunks(task_id)

    return {"status": "ok", "chunk_index": chunk_index}
```

**优势**:
- 支持断点续传
- 避免大文件一次上传超时
- 内存友好

## 5.7 部署架构

```
                  ┌─────────┐
                  │  Nginx  │
                  └────┬────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │  API 1  │   │  API 2  │   │  API N  │
   └────┬────┘   └────┬────┘   └────┬────┘
        └──────────────┼──────────────┘
                       ▼
                 ┌─────────┐
                 │  Redis  │ (队列 + 状态)
                 └────┬────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │Worker 1 │   │Worker 2 │   │Worker N │
   │+ GPU 0  │   │+ GPU 1  │   │+ GPU 2  │
   └─────────┘   └─────────┘   └─────────┘
```

**生产部署特点**:
- API 无状态,可水平扩展
- Worker 多 GPU 并行
- Redis 高可用(哨兵/Cluster)
- MySQL 主从 + 读写分离
- 模型文件共享存储(NFS/对象存储)
