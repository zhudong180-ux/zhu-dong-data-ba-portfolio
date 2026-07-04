# 10. 物流优化:动态 VRP/PyVRP + 3D-BPP 装箱 + 元启发式

## 10.1 动态 VRP:先可行后改进

**VRP (Vehicle Routing Problem)** 是运筹学经典问题:
- 给定车辆、客户、需求、约束
- 找总成本(里程/时间)最小的车辆分配 + 路径
- NP-Hard 组合优化问题

**DVRP (Dynamic VRP)** 在 VRP 基础上加入**动态事件**:
- 实时新增订单
- 交通拥堵 / 道路封闭
- 客户取消
- 车辆故障

### 解题策略:分层

```
第一步:插入启发式 → 可行解 (1-5 ms)
   ↓
第二步:局部搜索 (2-opt / relocate) → 改进 (10-50 ms)
   ↓
第三步:元启发式 (GA / Tabu / ACO) → 收敛 (秒级)
```

**动态场景的实时性优先**: 通常先满足实时性(几百毫秒内可决策),再考虑全局最优。

### PyVRP 用法示例

```python
from pyvrp import Model, Client, VehicleType

model = Model()

# 添加客户(订单)
depot = model.depot(latitude=..., longitude=..., demand=0)
client_1 = model.client(latitude=..., longitude=..., demand=10)
# ...

# 添加车辆
vehicle_type = model.vehicle_type(num_available=10, capacity=100)
model.add_vehicles(vehicle_type, count=10)

# 时窗约束
for client in clients:
    client.time_window = (earliest, latest)

# 求解
solution = model.solve()
```

## 10.2 3D-BPP:工业约束

**3D Bin Packing Problem**:
- 给定一批货物(长宽高 + 重量)
- 找最少的车辆(货箱)
- 或最大化装载率

### 工业约束

| 约束 | 业务场景 |
|------|---------|
| **重不压轻** | 重物在下方,避免压坏轻货 |
| **旋转限制** | 有些货物不允许旋转 90 度 |
| **支撑面** | 接触面积 ≥ 80% 才视为有效支撑 |
| **易碎品** | 易碎物品不允许任何压栈 |
| **LIFO** | 后进先出,便于多点配送卸货 |
| **温度隔离** | 冷链/热链货物不能混装 |

### 算法实现

```python
def hybrid_3d_bpp(items, vehicles, max_iterations=1000):
    """混合元启发式 3D-BPP"""
    # 排序启发式: 重 - 大 - 易碎
    sorted_items = sorted(
        items,
        key=lambda x: (
            -x.weight,             # 重优先
            -x.volume,             # 大优先
            x.is_fragile,         # 易碎优先
        )
    )

    best_solution = None
    best_fill_rate = 0

    population = init_population(sorted_items, vehicles, size=50)

    for gen in range(max_iterations):
        fitness = evaluate(population, vehicles)
        offspring = crossover_and_mutate(population)
        for ind in offspring:
            ind = tabu_search(ind, vehicles, iterations=20)
            ind = local_search(ind, vehicles)  # 2-opt / relocate
        population = elitism_replace(population, offspring)

        best = max(population, key=lambda x: x.fill_rate)
        if best.fill_rate > best_fill_rate:
            best_fill_rate = best.fill_rate
            best_solution = best

    return best_solution
```

### 关键考量

- **旋转**: 立方体有 6 种朝向;长方体有更多
- **位置选择**: 候选位策略(角优先 / 极点 / 支撑最大)
- **回退机制**: 当物品放置失败时记录,后续启发式跳过

## 10.3 元启发式

### 遗传算法(GA)

```
编码: 物品序列 + 朝向序列
适应度: 装载率 - 重量溢出 - 约束违反罚分
选择: 锦标赛 / 轮盘赌
交叉: 顺序交叉(OX) / 部分映射交叉(PMX)
变异: 交换 / 翻转 / 随机插入
精英保留: 前 N 个直接进入下一代
```

### 禁忌搜索(Tabu Search)

```
邻域结构: 任意两位置的交换 / 翻转
禁忌表: 记录最近 K 个操作,避免循环
藐视准则: 优于历史最优时可破禁忌
终止: 最大迭代 / 无改进计数
```

### 局部搜索

```
2-opt: 翻转一段路径
relocate: 把一个客户从一条路径移到另一条
swap: 交换两个客户
or-opt: 移动一小段路径
```

### 工业中常见的混合组合

"局部搜索 / 禁忌 / GA 混合是工业常见组合":
- 短期: 局部搜索快速改进
- 中期: 禁忌搜索跳出局部最优
- 长期: GA 全局探索
