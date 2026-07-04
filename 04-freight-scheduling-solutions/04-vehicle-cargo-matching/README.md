# 04. 车货匹配算法设计思路

[![Domain](https://img.shields.io/badge/Domain-Vehicle%20Cargo%20Match-orange.svg)](#)
[![Algo](https://img.shields.io/badge/Algorithm-GeoHash%20%2B%20Multi--Factor-blue.svg)](#)
[![Scale](https://img.shields.io/badge/Scale-Ten--Thousand%20Level-brightgreen.svg)](#)

> 给定货物重量 + 起讫点经纬度,在候选货车集合中找出最优匹配车辆

---

## 一、需求定义

**业务场景**: 给物流公司服务。给定一批货物的**重量**以及要运输的路线**起点和终点经纬度**,在候选货车集合中,根据货车的**运输轨迹**和**当前货车状态**找出最优匹配的车辆。

**最远匹配包含如下条件**:

1. 货车历史运输轨迹的"起点"和"终点"与输入路线的起点和终点**完全匹配**(GeoHash)
2. 货车历史运输轨迹的"起点"与输入路线的起点匹配,而"终点"与输入路线的终点**近似匹配**
3. 货车历史运输轨迹的"终点"与输入路线的终点一致,而"起点"与输入路线的起点**近似匹配**
4. 货车历史运输轨迹的"起点"和"终点"与输入路线都是**近似匹配**
5. 货车当前位置坐标是否在输入路线的起点附近(离散因子,距离分等级)
6. 货车当前是否处于**空闲状态**(速度为 0)

返回因子后,对每辆货车评估匹配得分,3 类得分归一化并分配权重:

```
综合匹配得分 = 0.4 × 匹配度 + 0.3 × 距离得分 + 0.3 × 空闲状态得分
```

分数越高代表匹配程度越高。

---

## 二、GeoHash 位置匹配方法

### 2.1 什么是 GeoHash?

GeoHash 是一种空间地址编码方法,把二维的空间经纬度数据编码成一个字符串。每一个字符串代表了一个矩形区域,矩形区域内所有的点都共享相同的 GeoHash 字符串,这样可以把位置落在同一个区域内的两个坐标点看作是可匹配的坐标点。

### 2.2 GeoHash 长度与区域大小

| 长度 | 区域大小 | 适用场景 |
|------|---------|---------|
| 5 位 | 约 5km × 5km | 精确匹配(城市内) |
| 4 位 | 约 25km × 25km | 近似匹配(跨城市/省) |
| 6 位 | 约 1.2km × 0.6km | 高精度匹配 |

**8 邻域扩展**: 即使两个坐标距离在 5km 内,也可能不在同一 GeoHash 区域(可能靠近各自 GeoHash 边界)。
放宽条件:将一个坐标点 GeoHash 的 8 个邻居也考虑进去,只要 1 个坐标的 GeoHash 等于另一个的 8 邻居区域,即可认为可触达。

```
5 位 GeoHash 配 8 邻域 → 最长距离 ~14km
4 位 GeoHash 配 8 邻域 → 最长距离 ~65km
```

### 2.3 工程实现

```python
import geohash2

def get_geohash_with_neighbors(lat, lon, precision=5):
    """获取坐标的 GeoHash + 8 邻域"""
    base = geohash2.encode(lat, lon, precision=precision)
    neighbors = geohash2.expand(base)  # 8 邻域 + 自身共 9 个
    return set([base] + neighbors)


def is_geohash_match(lat1, lon1, lat2, lon2, precision=5):
    """判断两点是否 GeoHash 可达"""
    set1 = get_geohash_with_neighbors(lat1, lon1, precision)
    set2 = get_geohash_with_neighbors(lat2, lon2, precision)
    return bool(set1 & set2)
```

---

## 三、轨迹分段算法

### 3.1 分段规则

```
每一个轨迹片段包含:
- 起始位置 + 时间
- 结束位置 + 时间  
- 北斗位置坐标点数量

约束:
- 轨迹片段内部连续点之间的时间间隔 < 1 小时
- 相邻轨迹片段之间,结束与起始时间间隔 >= 1 小时
```

此处 1 小时为**最小间隔时间**,可根据实际调整。

### 3.2 完整运输路线判断逻辑

**逻辑 1**: 时间间隔都 < 8 小时,且静止片段内部时间间隔 < 8 小时 → 视为**完整运输轨迹**

**逻辑 2**: 如果 `Δt_{ij} > 8h` 且片段 i 终点坐标 == 片段 j 起点坐标 → **不是**(视为返程/中转)

**逻辑 3**: 如果 `Δt_{ij} > 8h` 且两片段地理坐标不连接,**平均速度 < 5 km/h** → **不是**(认为是停车停留)

**逻辑 4**: 如果**静止轨迹片段**(起点 GeoHash == 终点 GeoHash)且 `Δt > 8h` → **不是**

### 3.3 算法伪代码

```python
def split_trace_points(points, min_internal_interval_s=3600):
    """轨迹分段:内部 <1h,片段间 >=1h"""
    segments = []
    current_segment = []
    for i in range(len(points)):
        if not current_segment:
            current_segment.append(points[i])
            continue

        delta = (points[i].timestamp - current_segment[-1].timestamp)
        if delta < min_internal_interval_s:
            current_segment.append(points[i])
        else:
            # 检查片段间隔
            segments.append(current_segment)
            current_segment = [points[i]]

    if current_segment:
        segments.append(current_segment)

    return segments


def is_complete_route(segments):
    """判断片段序列是否是完整运输路线"""
    for i in range(len(segments) - 1):
        curr, next_seg = segments[i], segments[i+1]
        delta_t = next_seg[0].timestamp - curr[-1].timestamp

        if delta_t < 8 * 3600:  # < 8h
            continue

        # 大于 8h 的情况判断
        if geohash_eq(curr[-1].lat, curr[-1].lon, next_seg[0].lat, next_seg[0].lon):
            return False  # 逻辑 2: 中转

        if avg_speed(curr[-1], next_seg[0], delta_t) < 5:
            return False  # 逻辑 3: 停车

    return True


def avg_speed(p1, p2, dt_seconds):
    """平均速度 km/h"""
    distance_km = haversine(p1.lat, p1.lon, p2.lat, p2.lon)
    return distance_km / (dt_seconds / 3600)


def haversine(lat1, lon1, lat2, lon2):
    """Haversine 距离公式"""
    R = 6371  # 地球半径(km)
    lat1_r, lat2_r = radians(lat1), radians(lat2)
    dlat = lat2_r - lat1_r
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(lat1_r) * cos(lat2_r) * sin(dlon/2)**2
    return 2 * R * asin(sqrt(a))
```

---

## 四、车辆召回与匹配

### Step 1: 计算每辆车的所有轨迹片段的 GeoHash

```python
for truck in truck_pool:
    truck.trace_segments = split_trace_points(truck.trace_points)
    for segment in truck.trace_segments:
        segment.start_geohash = geohash2.encode(
            segment.start.lat, segment.start.lon, precision=5
        )
        segment.end_geohash = geohash2.encode(
            segment.end.lat, segment.end.lon, precision=5
        )
```

### Step 2: 严格匹配

```python
order_start_gh = get_geohash_with_neighbors(order.start_lat, order.start_lon, precision=5)
order_end_gh = get_geohash_with_neighbors(order.end_lat, order.end_lon, precision=5)

candidates_strict = []
for truck in truck_pool:
    for segment in truck.trace_segments:
        if (segment.start_geohash in order_start_gh
            and segment.end_geohash in order_end_gh):
            candidates_strict.append((truck, segment))
            break  # 一个 truck 只算一次
```

### Step 3: 多因子评分

```python
def score_truck(truck, order):
    """多因子评分"""
    # 1. 匹配度 (0-1): 历史轨迹起终点匹配
    match_score = calculate_match_score(truck, order)

    # 2. 距离成本 (0-1): 当前车辆位置距离订单起点
    distance_score = 1 - normalize(
        haversine_distance(truck.current_pos, order.start)
    )

    # 3. 空闲/履约 (0-1): 速度为 0 + 历史履约表现
    idle_score = (
        1.0 if truck.speed == 0 else 0.0
    ) * 0.5 + truck.history_completion_rate * 0.5

    # 综合打分
    return (
        0.4 * match_score
        + 0.3 * distance_score
        + 0.3 * idle_score
    )
```

### Step 4: 放宽条件的 4 步回退

如果 Step 3 找不到合适车辆,放宽到 4 位 GeoHash:

| 步骤 | 起点匹配 | 终点匹配 | 时间间隔阈值 |
|------|---------|---------|-------------|
| Step 3 | 5 位精确 | 5 位精确 | 8h |
| Step 4 | 5 位精确 | 4 位(邻域) | 12h |
| Step 5 | 4 位(邻域) | 5 位精确 | 12h |
| Step 6 | 4 位(邻域) | 4 位(邻域) | 24h |

这样搜索范围逐步扩大,从城市内到跨省。

---

## 五、关键性能指标

| 指标 | 数值 |
|------|------|
| 单订单匹配耗时 | < 1s |
| 召回精度(5 位 GeoHash) | 城市内 90%+ |
| 召回精度(4 位 GeoHash) | 跨省 85%+ |
| 平均匹配车辆数 | 5-20 辆/订单 |

---

## 六、可解释性

对最终选中的车辆,系统应能回答:
- 为什么选中这辆车?(决策依据)
- 历史运输轨迹的匹配情况(可视化)
- 距离订单起点的实际距离
- 司机的历史履约率与评价

---

## ⚠️ 已知挑战

1. **边界效应**: GeoHash 边界附近的车辆召回准确率偏低
2. **去重复杂度**: 一辆车起点附近 3-4 小时内多个轨迹片段需去重
3. **数据稀疏**: 新司机/新车缺数据,需要冷启动策略
4. **轨迹质量**: GPS/北斗信号弱时段,轨迹点会跳跃

---

## 📜 License

MIT License - 详见 [`../../LICENSE`](../../LICENSE) 文件。
