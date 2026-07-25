# 海燕党 · 可复现构建指南

> 政党名称：**海燕党** ｜ 英文名称：**PETREL AI PARTY** ｜ 创始人：**刘海燕（LIU HAIYAN）**

---

## 目标

核心二进制产物可由第三方独立复现构建，哈希完全一致。

## 原则

1. **锁死所有依赖版本** — 使用精确版本号（`1.2.3` 而非 `^1.2.3`）
2. **固定构建环境** — Docker 容器化构建，使用指定基础镜像
3. **声明式构建** — 所有构建步骤在 `Dockerfile` 或 `Makefile` 中完整声明
4. **输出单一产物** — 每次构建输出确定性的单一产物

## Python 项目

```bash
# 生成依赖锁定文件
pip freeze > requirements-locked.txt

# 使用 requirements-locked.txt 构建
pip install -r requirements-locked.txt
```

## 验证

```bash
# 第三方验证构建
git clone <repo>
cd <repo>
git checkout <release-tag>
make build
sha256sum dist/*
# 与发布页的 SHA256 对比
```
