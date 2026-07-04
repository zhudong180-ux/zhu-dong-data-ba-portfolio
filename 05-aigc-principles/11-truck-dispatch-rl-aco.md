# 11. 货车智能调度 PoC:RL + ACO + 可视化平台

## 11.1 MDP 建模

**MDP 五元组 (S, A, P, R, γ)**:

```
状态 S: 车辆/订单/路网/约束信息
动作 A: 派单/插单/重路由(可用 action masking)
状态转移 P: P(s'|s, a)
奖励 R: -(里程 + 延误 + 违约 + 风险成本)
折扣因子 γ: 0.99(常用)
```

### 状态设计

```python
state = {
    "vehicles": [
        # 每辆车
        {
            "id": "truck_001",
            "position": (lng, lat),
            "speed_kmh": 60,
            "load_factor": 0.7,        # 装载率
            "remaining_hours": 6.5,    # 司机工时
            "current_task_id": "task_xxx",
            "eta_to_next": 1.2,        # 小时
            "risk_score": 0.1,         # 风险评分
        },
        # ...
    ],
    "orders": [
        # 每个订单
        {
            "id": "order_xxx",
            "origin": (lng, lat),
            "destination": (lng, lat),
            "weight_tons": 15,
            "volume_m3": 30,
            "time_window": (9, 17),    # 9 点-17 点
            "priority": "high",         # high/medium/low
            "posted_at": ...,
            "expires_at": ...,
        },
        # ...
    ],
    "road_network": {
        "congestion_level": np.array,  # 每个路段的拥堵指数
        "weather": "rain",
        "blackspots": [...],
    },
    "constraints": {
        "max_working_hours": 8,
        "max_load_factor": 1.0,
        "max_consecutive_driving_hours": 4,
    },
}
```

### 动作设计

```python
action = {
    "dispatch": {
        "vehicle_id": "truck_001",
        "order_id": "order_xxx",
    },
    "insert": {
        "vehicle_id": "truck_001",
        "order_id": "order_yyy",
        "position": 3,  # 插入到当前路径的第 3 个位置
    },
    "reroute": {
        "vehicle_id": "truck_001",
        "new_route": [...],
    },
}

# 用 action masking 屏蔽非法动作
action_mask = {
    "truck_001": [
        # 每个候选订单 0/1 表示是否能接
        1, 1, 0, 1, 0, 1, ...
    ],
}
```

### 奖励函数

```python
def compute_reward(prev_state, action, next_state):
    """奖励 = -(多目标成本) + 成功奖励"""
    mileage_cost = action.get("added_mileage", 0) * 1.0
    delay_cost = next_state["delay_hours"] * 10.0
    violation_cost = next_state["constraint_violations"] * 100.0
    risk_cost = next_state["incident_probability"] * 50.0

    reward = -(
        λ_mileage * mileage_cost
        + λ_delay * delay_cost
        + λ_violation * violation_cost
        + λ_risk * risk_cost
    )

    # 准时 + 完成奖励
    if action and action["type"] == "dispatch":
        if next_state["order_completed_on_time"]:
            reward += 100.0

    return reward
```

## 11.2 RL 训练关键点

### 三个核心难点

#### ① 离线依赖仿真 / 回放环境

生产环境中 RL 探索成本极高,必须借助仿真器或回放历史数据训练。

```python
class DispatchSimulator:
    """调度仿真器"""
    def reset(self):
        return initial_state

    def step(self, action):
        next_state = self.transition(action)
        reward = self.reward(action, next_state)
        done = self.is_terminal(next_state)
        return next_state, reward, done, {}
```

#### ② 约束处理

- **动作掩码 (Action Masking)**: 直接屏蔽非法动作
- **软罚项**: 一些约束(如违规则)用惩罚项代替硬约束
- **修复算子**: 非法解修复成可行解

```python
def reward_shaping(action, state):
    """奖励塑形"""
    # 主奖励
    base_reward = compute_base_reward(action, state)
    # 软罚项(连续约束)
    penalty = 0
    if state["violations"]["fatigue"] > 0:
        penalty -= 50 * state["violations"]["fatigue"]
    if state["violations"]["overload"] > 0:
        penalty -= 30 * state["violations"]["overload"]
    return base_reward + penalty
```

#### ③ 基线启发式兜底

RL 做增益,启发式做保底:
- 总是先有可行的启发式方案
- RL 在启发式基础上做边际改进

```python
class HybridDispatcher:
    def dispatch(self, order):
        # 1. 启发式获取基线
        baseline_solution = self.heuristic_solver.solve(order)

        # 2. RL 改进
        rl_action = self.rl_policy.predict(self.state)
        rl_solution = self.apply_rl_action(baseline_solution, rl_action)

        # 3. 取优
        if rl_solution["cost"] < baseline_solution["cost"]:
            return rl_solution
        else:
            return baseline_solution
```

## 11.3 ACO 公式与更新

**蚁群算法 (Ant Colony Optimization)** 用于 RL 给出的粗粒度方案做局部精炼。

### 状态转移公式

```
P(i→j) ∝ τ^α · η^β

τ_ij: 信息素(历史经验)
η_ij: 启发因子(贪心,常用 1/distance)
α: 信息素权重
β: 启发因子权重
```

### 信息素更新

```
τ_ij ← (1-ρ)·τ_ij + Σ_k Δτ^k_ij

Δτ^k_ij: 第 k 只蚂蚁在边 (i,j) 上留下的信息素增量
ρ: 蒸发率
```

### RL + ACO 混合框架

```
┌────────────────────────────────────────┐
│  RL 全局策略                            │
│  - 处理订单池分配                       │
│  - 学习长时序依赖                       │
│  - 处理大规模动作空间                    │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│  ACO 局部精炼                           │
│  - 对每个车辆的路线做局部优化             │
│  - 利用历史信息素做快速收敛              │
│  - 解决 RL 在小尺度上的不稳定性          │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│  启发式兜底                             │
│  - 插入启发式 + 局部搜索                │
│  - 保证 RL/ACO 异常时仍能产出可行解       │
└────────────────────────────────────────┘
```

## 11.4 可视化平台:解释与验收

可视化平台不仅是 UI,**更是解释与验收手段**:

- **地图叠加路线 / 时间窗 / 风险点**: 让业务团队能"看见"
- **成本分解**: 里程 / 延误 / 违约 / 风险各项占比
- **回放**: 对比基线 vs 优化,给出"为什么这样决策"
- **置信区间**: 多次蒙特卡洛的分布展示

```python
# React + ECharts + Redux 架构示例
# /pages/dispatching/dashboard.tsx
export function DispatchingDashboard() {
  const { routes, performance } = useDispatchingStore()

  return (
    <GridLayout>
      <MapView>
        <RouteLayer routes={routes} />
        <HeatmapLayer data={riskPoints} />
        <TimeWindowLayer windows={timeWindows} />
      </MapView>

      <CostBreakdownPanel>
        <CostItem name="里程" value={performance.mileage} />
        <CostItem name="延误" value={performance.delay} />
        <CostItem name="违约" value={performance.violation} />
        <CostItem name="风险" value={performance.risk} />
      </CostBreakdownPanel>

      <ReplayPanel>
        <BaselineSlider />
        <OptimizedSlider />
      </ReplayPanel>
    </GridLayout>
  )
}
```
