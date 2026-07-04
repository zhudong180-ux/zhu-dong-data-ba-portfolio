# AES 双 IV 策略逆向分析笔记

> 本文档记录在数据宝"高速运力"业务中,对加密协议进行逆向分析的完整过程。
> 仅作学习与技术交流用途,严禁用于未授权数据。

## 1. 业务背景

车辆运力数据(高速公路运输车辆的位置、轨迹、风险事件)在数据日志中以加密形式存储。
加密流程:
1. 业务字段(车牌、风险事件类型、时间戳)按 JSON 序列化
2. AES-128-CBC 加密
3. Base64 编码后存入日志

## 2. 现象

尝试用同一 AES 密钥 + IV 解密所有 4 个 info 字段时:
- 2 个字段能正确解析(JSON 完整)
- 2 个字段解析失败(乱码或部分乱码)

## 3. 假设 1: 全零 IV

```python
from Crypto.Cipher import AES

key = b'<your-16-byte-key>'  # ⚠️ 不要硬编码
iv = b'\x00' * 16  # 全零 IV

cipher = AES.new(key, AES.MODE_CBC, iv)
decrypted = cipher.decrypt(encrypted_bytes)
```

**结果**: 2 个字段成功,2 个失败。

## 4. 假设 2: 全密钥 IV

```python
iv = key  # 用密钥作为 IV
```

**结果**: 另外 2 个字段成功,前面那 2 个失败。

## 5. 结论

**两个假设互补** → 说明同一密钥对不同字段使用了**不同的 IV 策略**:

| 字段 | IV 策略 |
|------|---------|
| `callSupplierRequestInfo` | 零 IV |
| `responseInfo` | 零 IV |
| `callSupplierResponseInfo` | 密钥 IV |
| `requestInfo` | 密钥 IV |

## 6. 验证代码

```python
def aes_decrypt_with_strategy(encrypted_data, key, strategy):
    if strategy == "zero_iv":
        iv = b'\x00' * 16
    elif strategy == "key_iv":
        iv = key
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.decrypt(encrypted_data)


# 调用示例
FIELD_STRATEGIES = {
    "callSupplierRequestInfo": "zero_iv",
    "responseInfo": "zero_iv",
    "callSupplierResponseInfo": "key_iv",
    "requestInfo": "key_iv",
}
```

## 7. 为什么这样设计? (推测)

可能的原因(按概率排序):

1. **性能考量**: 部分字段(请求侧)用零 IV 可走预计算路径
2. **历史遗留**: 早期版本全部用零 IV,后期才加入对响应侧字段的额外混淆
3. **加密策略分层**: 不同字段的敏感度不同(请求 vs 响应)
4. **实现错误**: 开发者无意中混用了两种 IV,导致部分字段需要密钥 IV 才能解密

## 8. 启示

- **真正的工程难题不是加密本身,而是协议理解**
- **逆向分析需要系统性假设-验证**
- **多线程 + 错误降级是处理生产数据的必备能力**

---

## 9. 安全提示

⚠️ **本文档仅作学习用途**:
- 不要将发现的协议细节用于未授权数据访问
- 生产环境密钥应通过 KMS / Vault 等专业方案管理
- 任何解密操作应符合当地法律法规与公司合规要求
