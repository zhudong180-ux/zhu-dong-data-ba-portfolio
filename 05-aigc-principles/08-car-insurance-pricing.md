# 08. 车险纯保费:Tweedie-GLM(log 链接)+ IRLS

## 8.1 Tweedie 适配"零多+长尾"

**业务场景**: 车险保单与理赔数据,具有**高零赔付率**和**长尾赔付分布**特点。
传统的正态分布假设或泊松回归都无法很好处理。

**Tweedie 分布** 在 1<p<2 时可视为复合泊松-伽马:
- 允许 Y=0
- 对长尾赔付分布友好

```
Var(Y) = φ · μ^p
```

p 的范围决定了分布族:
- p<1: 不适用(不能有大量零)
- 1<p<2: 复合泊松-伽马(车险常用)
- p=2: Gamma 分布
- p=3: Inverse Gaussian
- p>2: 不适用(过于厚尾)

## 8.2 log 链接与费率因子解释

**log 链接** 是广义线性模型的一种链接函数:

```
η = X·β
μ = exp(η)
```

**关键意义**: exp(β_k) 是**乘性费率因子**(multiplicative rate factor)，
业务方可以直接解读为"特征 k 增加 1 个单位,赔付率变为原来的 N 倍"。

业务侧更关心的"为什么是这个费率"变得可解释。

## 8.3 IRLS 训练与评估

**IRLS (Iteratively Reweighted Least Squares)**:
- 每一步解一个加权最小二乘问题
- 权重根据当前 μ 和 Var(μ) 重新计算
- 监控收敛(对数似然变化小于阈值)

```python
import statsmodels.api as sm

def fit_tweedie_glm(X, y, p=1.5, weights=None):
    """训练 Tweedie GLM"""
    # 构建 Tweedie GLM
    model = sm.GLM(
        y,
        X,
        family=sm.families.Tweedie(link=sm.families.links.Log(), var_power=p),
        freq_weights=weights,
    )
    result = model.fit()  # IRLS 内部迭代
    return result


# 特征工程
def feature_engineering(df):
    """特征分箱 + 互信息选择"""
    from sklearn.preprocessing import KBinsDiscretizer
    # 驾驶行为分箱
    df['driving_style_bin'] = KBinsDiscretizer(n_bins=10).fit_transform(
        df[['hard_brake_freq']]
    )
    # 互信息降低共线性
    from sklearn.feature_selection import mutual_info_regression
    mi = mutual_info_regression(X, y)
    selected_features = X.columns[mi > threshold]
    return X[selected_features]
```

## 8.4 评估指标

| 指标 | 公式 | 含义 |
|------|------|------|
| **离差残差** | d = 2·[y·log(y/μ) - (y-μ)] | 越小拟合越好 |
| **卡方近似** | χ² ≈ Σ (y-μ)²/Var(μ) | Pearson χ² |
| **Lift 十分位** | 实际/预期赔付率 | 模型排名能力 |
| **AUC** | 0-1 | 区分好坏客户 |

## 8.5 完整实施步骤

```
1. 数据准备
   ├── 按"车年"构建风险单位
   ├── 处理高零赔付率 + 长尾赔付
   └── 训练 / 验证 / 测试切分

2. 特征工程
   ├── 驾驶行为特征分箱
   ├── 里程数、时段、地区
   ├── 单变量分析 + 互信息降共线性
   └── 编码(One-Hot / Target / Embedding)

3. 训练
   ├── 选定 p 值(通常用 deviance 检验)
   ├── log 链接 + IRLS
   └── 收敛监控

4. 评估
   ├── 离差残差
   ├── 十分位 Lift 曲线
   ├── 残差图
   └── 业务解读(exp(β_k))

5. 部署
   ├── 系数表存储
   ├── 实时打分(μ = exp(Σ β_k · x_k))
   └── A/B 测试
```

## 8.6 Q&A 高频问题

### Q: Tweedie 的 p 值怎么选?

**口径**: 用 deviance 检验或 grid search 选最匹配的 p,
常见范围 1.1-1.9。

### Q: 与传统线性回归的差异?

A: 传统 OLS 假设 Y~N(μ, σ²),无法处理零过多 + 长尾;
Tweedie GLM 显式建模 Var(Y) = φ·μ^p,且支持非正态分布。

### Q: IRLS 为什么不用随机梯度下降?

A: IRLS 在 GLM 框架下有理论保证收敛到最优解,且计算快;
数据规模小时(如几千到几万保单)首选 IRLS。
数据规模大时(如百万级)才考虑分布式优化。

### Q: 怎么报告费率?

A: 用 exp(β_k) 解释为"乘性费率因子"。
例如 exp(β_年龄段)=1.3,意味着该年龄段的人平均赔付率是基线的 1.3 倍。
