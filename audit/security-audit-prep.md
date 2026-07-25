# M1.6 MVP 安全审计准备文档

> **创世铭文**
> 政党名称：**海燕党** ｜ 英文名称：**PETREL AI PARTY** ｜ 创始人：**刘海燕（LIU HAIYAN）**
> 
> 版本：V1.0 | 最后修订：2026年7月 | 状态：待审计

---

## 1. 审计范围

### Phase 1 MVP 审计范围（M1.6 Gate 1）

| 审计对象 | 路径 | 优先级 |
|---------|------|--------|
| ZKP 电路 | `02-algorithm/zkp/` | Critical |
| DID 身份库 | `02-algorithm/did/` | Critical |
| 匿名投票内核 | `02-algorithm/voting/` | Critical |
| Sybil 三轨验证 | `02-algorithm/sybil/` | High |
| 加密通信接入 | `02-algorithm/communication/` | High |
| 智能合约逻辑 | `02-algorithm/contracts/` | High |

### 审计标准
- OWASP Application Security Verification Standard (ASVS) Level 2
- 密码学审计（ZKP 电路 + 密钥管理）
- 智能合约安全（重入/整数溢出/权限检查）

---

## 2. 已知安全设计

### 2.1 密钥安全
- DID 密钥完全客户端生成，服务端零知识
- 私钥本地加密存储（文件权限 600）
- 支持 GPG/SSH 签名提交
- 社交恢复 3/5 阈值模式

### 2.2 ZKP 安全
- Nullifier 机制防双投
- 证明生成 <3 秒（中端手机目标）
- 链上验证 <100ms
- 电路公开可审计

### 2.3 投票安全
- 端到端匿名：运营方无法将票与人对应
- 计票结果任何人可独立复算
- 提案时间锁防操纵
- 慢治理机制（7 天辩论期 + 3 天冷静期）

### 2.4 金库安全
- 多签控制（5/9 人类密钥）
- 单一来源 5% 上限（合约级拒绝）
- 全自动实时公开流水

### 2.5 熔断机制
- 一级（节点级）：自动隔离异常节点
- 二级（社区级）：1/3 节点异常触发紧急投票
- 三级（协议级）：5/9 人类密钥联合签名全网冻结

---

## 3. 需要外部审计的模块

| 模块 | 建议审计机构类型 | 预计工作量 |
|------|-----------------|-----------|
| ZKP 电路 | 密码学审计公司 | 2-3 周 |
| DID 实现 | 安全审计公司 | 1-2 周 |
| 投票合约 | 智能合约审计 | 1-2 周 |
| 金库合约 | 智能合约审计 | 1 周 |
| 整体渗透测试 | 渗透测试团队 | 2-3 周 |

**发布门禁条件**：所有 Critical/High 漏洞修复并复测后方可进入 Phase 2。

---

## 4. 自检清单

```bash
# ZKP 电路测试
python3 -m pytest 02-algorithm/tests/test_zkp.py -v

# DID 系统测试
python3 -m pytest 02-algorithm/tests/test_did.py -v

# 投票系统测试
python3 -m pytest 02-algorithm/tests/test_voting.py -v

# 创世铭文完整性检查
python3 05-tool/ci-cd/genesis-guard.py --ci

# 依赖漏洞扫描
pip-audit
npm audit
```
