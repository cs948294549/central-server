# JWT 密钥管理说明

## 📋 概述

JWT (JSON Web Token) 是本系统用于用户身份验证的核心机制。**JWT Secret Key 是后端专用密钥**，用于签名和验证 Token。

---

## ⚠️ 重要警告

### JWT Secret Key 的特性

1. **后端专用**
   - JWT Secret Key 仅在服务端使用
   - **绝对不要**将此密钥分发给客户端、前端或用户
   - 客户端只接收已签名的 Token，不需要知道密钥

2. **修改密钥的影响**
   - ✅ 所有**已签发**的 JWT Token 将**立即失效**
   - ✅ 所有**已登录**用户需要**重新登录**
   - ✅ 无法撤销单个 Token，只能全部失效

3. **密钥泄露的风险**
   - 攻击者可以伪造任意用户的 Token
   - 可以绕过身份验证访问系统
   - 可以冒充管理员执行敏感操作

---

## 🔐 密钥管理最佳实践

### 1. 初始部署

```bash
# 生成安全密钥
python scripts/generate_secret_key.py

# 编辑配置文件
vim config.py

# 替换 jwt_secret_key
jwt_secret_key = "新生成的安全密钥"
```

### 2. 密钥要求

- **长度**: 至少 64 字节（512 位）
- **随机性**: 使用加密安全的随机数生成器
- **格式**: Base64 或十六进制编码
- **禁止**: 字典词汇、简单模式、可预测字符串

### 3. 密钥存储

**开发环境**：
```python
# config.py
jwt_secret_key = "your_dev_secret_key"
```

**生产环境**（推荐）：
```python
# config.py
import os
jwt_secret_key = os.getenv("JWT_SECRET_KEY", "fallback_key")
```

```bash
# 环境变量
export JWT_SECRET_KEY="your_production_secret_key"

# 或使用 .env 文件
echo "JWT_SECRET_KEY=your_production_secret_key" > .env
```

**最佳实践**：
- 使用 AWS Secrets Manager、Azure Key Vault 等密钥管理服务
- 在 CI/CD 流水线中注入密钥
- 不同环境使用不同密钥

---

## 🔄 密钥轮换

### 何时需要轮换密钥

**必须立即轮换**：
- ✅ 密钥被泄露或怀疑泄露
- ✅ 离职员工曾接触过密钥
- ✅ 代码仓库意外提交了密钥
- ✅ 发现安全漏洞

**定期轮换**：
- ✅ 每 3-6 个月轮换一次（推荐）
- ✅ 重大版本发布前
- ✅ 安全审计要求

### 密钥轮换步骤

**准备阶段**：
1. 选择低峰时段（凌晨 2-4 点）
2. 提前通知用户（维护公告）
3. 生成新密钥并备份旧密钥
4. 准备回滚方案

**执行阶段**：
```bash
# 1. 备份当前配置
cp config.py config.py.backup

# 2. 生成新密钥
python scripts/generate_secret_key.py

# 3. 更新配置文件
vim config.py
# 替换 jwt_secret_key

# 4. 重启服务
docker restart central-server

# 5. 验证服务
curl http://localhost:8080/system/health
```

**验证阶段**：
1. 测试新用户登录
2. 确认旧 Token 已失效
3. 监控日志和错误率
4. 准备客户支持

**回滚方案**（如有问题）：
```bash
# 恢复旧配置
cp config.py.backup config.py

# 重启服务
docker restart central-server
```

---

## 🛡️ 安全检查清单

### 部署前检查

- [ ] JWT Secret Key 已更换为强随机密钥
- [ ] 密钥长度至少 64 字节
- [ ] 密钥未提交到版本控制系统
- [ ] `.gitignore` 包含 `config.py`
- [ ] 生产环境使用环境变量或密钥管理服务

### 运行中检查

- [ ] 定期审计密钥访问日志
- [ ] 监控异常登录行为
- [ ] 设置 Token 过期时间（24 小时）
- [ ] 实施速率限制防止暴力破解
- [ ] 启用 HTTPS 保护 Token 传输

### 应急响应

**密钥泄露应急流程**：
1. **立即**更换密钥
2. 强制所有用户重新登录
3. 审计访问日志查找异常
4. 通知安全团队和受影响用户
5. 分析泄露原因并修复漏洞
6. 提交安全事件报告

---

## 📖 常见问题

### Q1: 为什么不能将 JWT Secret Key 发给前端？

**答**: JWT Secret Key 用于**签名** Token。如果前端知道密钥，任何人都可以伪造合法的 Token，绕过身份验证。

**正确流程**：
```
用户登录 → 后端验证密码 → 后端用密钥签名 Token → 返回 Token 给前端
前端使用 Token → 后端用密钥验证 Token → 返回数据
```

### Q2: 修改密钥后所有用户都要重新登录？

**答**: 是的。JWT Token 是用旧密钥签名的，新密钥无法验证旧 Token，因此会被拒绝。

**解决方案**：
- 选择低峰时段更换
- 提前通知用户
- 考虑实施双密钥过渡期（高级特性）

### Q3: 如何在不影响用户的情况下轮换密钥？

**答**: 标准 JWT 无法做到无缝轮换。可选方案：

1. **维护窗口**：选择低峰时段，接受短暂的重新登录
2. **双密钥验证**（需要代码改造）：
   ```python
   # 同时验证新旧密钥
   try:
       verify_token_with_new_key(token)
   except:
       verify_token_with_old_key(token)
   ```
3. **使用 Refresh Token**：短期 Access Token + 长期 Refresh Token

### Q4: JWT Token 有效期设置多久合适？

**答**: 
- **默认**: 24 小时（`jwt_expire_hours = 24`）
- **高安全场景**: 1-4 小时
- **低频访问**: 7 天

**权衡**：
- 更短的有效期更安全，但用户需要更频繁登录
- 更长的有效期更便利，但泄露风险更大

### Q5: 如何检测 JWT Secret Key 是否泄露？

**监控指标**：
- 异常 IP 地址登录
- 短时间内大量不同用户的请求
- Token 验证失败率突然上升
- 凌晨等异常时段的活跃用户

**预防措施**：
- 启用访问日志审计
- 集成安全监控系统（SIEM）
- 定期扫描代码仓库查找泄露密钥

---

## 🔗 相关文档

- [配置文档](CONFIG.md)
- [配置优化报告](CONFIG_IMPROVEMENT.md)
- [快速启动指南](QUICKSTART.md)

---

## 📞 安全问题报告

如发现安全问题或密钥泄露，请立即联系：
- 安全团队邮箱：[待补充]
- 紧急联系人：[待补充]

**不要**在公开渠道（GitHub Issue、论坛）讨论安全问题。

---

**最后更新**: 2026-08-14  
**文档版本**: 1.0
