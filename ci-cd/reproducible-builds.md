# =============================================================================
#  海燕党 PETREL AI PARTY
#  创始人：刘海燕（LIU HAIYAN）
#  可复现构建说明
#  版本: 1.0.0 | 协议: MIT
# =============================================================================

# 可复现构建说明

## 🎯 目标

确保海燕党（PETREL AI PARTY）的所有构建产物可以在任意环境中
**精确重现**，从而实现：

- **可信审计**：任何人都可独立验证发布包与源代码的对应关系
- **供应链安全**：防止构建服务器被攻破时植入后门
- **去中心化验证**：不依赖单一可信构建方

> **"不可复现的构建，就是不可信任的构建。"**

---

## 🔍 当前状态

| 模块 | 状态 | 备注 |
|------|------|------|
| Python 包 | ✅ 可复现 | 使用 `build` + 固定依赖 |
| Solidity 合约 | 🚧 进行中 | 需要确定编译器版本锁定方案 |
| JavaScript/TypeScript | 🚧 进行中 | 需要 lockfile 和缓存策略 |
| Docker 镜像 | 📋 计划中 | 需要多阶段构建 + digest 固定 |
| Go 模块 | 📋 计划中 | 需要 Go module hash 验证 |

---

## 📦 Python 包可复现构建

### 前置条件

```bash
# 安装构建工具
pip install build wheel setuptools
```

### 构建命令

```bash
# 标准构建
python -m build

# 验证产物
ls -la dist/
```

### 验证可复现性

```bash
# 方法一：两次构建比较
python -m build
sha256sum dist/*.tar.gz > /tmp/build1.sha256

# 删除构建产物后再次构建
rm -rf dist/
python -m build
sha256sum dist/*.tar.gz > /tmp/build2.sha256

# 比较两次构建的哈希
diff /tmp/build1.sha256 /tmp/build2.sha256
# 无输出 = 可复现
```

### 要求

1. **固定所有依赖版本**（`requirements.txt` 中指定精确版本号）
2. **设置 SOURCE_DATE_EPOCH**（用于时间戳固定）

```bash
# 构建时固定时间戳
SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) python -m build
```

3. **排除不可复现元数据**（`setup.cfg` 或 `pyproject.toml` 中配置）

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68.0", "wheel>=0.41"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
include-package-data = true
```

---

## 🐳 Docker 可复现构建

### 多阶段构建

```dockerfile
# =============================================================================
#  海燕党 PETREL AI PARTY
#  创始人：刘海燕（LIU HAIYAN）
#  可复现构建 Dockerfile 模板
# =============================================================================

# Stage 1: Build
FROM python:3.12-slim AS builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . /app
WORKDIR /app
CMD ["python", "-m", "petrel"]
```

### 构建命令

```bash
# 使用固定的 base image digest
docker build \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  -t ghcr.io/petrel-ai-party/petrel-core:latest \
  .

# 验证构建哈希
docker images --no-trunc --digests ghcr.io/petrel-ai-party/petrel-core
```

### 要求

1. **始终使用 digest 而非 tag 引用基础镜像**
   ```dockerfile
   FROM python:3.12-slim@sha256:abc123def456...
   ```
2. **使用 `--no-cache` 避免缓存污染**
3. **在 CI 中固定 `DOCKER_BUILDKIT=1`**

---

## 🔧 CI 验证脚本

CI 中的可复现构建验证由 `scripts/ci/verify-reproducible-build.py` 自动执行：

```bash
python3 scripts/ci/verify-reproducible-build.py --ci
```

### 验证流程

1. 首次构建 → 记录产物哈希到 `dist/.build-hashes`
2. 清空构建目录
3. 再次构建 → 重新计算产物哈希
4. 比较两次哈希 → 不一致则 CI 失败

---

## 📋 清单

### 提交前检查

- [ ] `requirements.txt` 或 `pyproject.toml` 中所有依赖版本固定
- [ ] 未引入新的不可复现依赖
- [ ] Dockerfile 使用 digest 引用基础镜像
- [ ] 构建脚本使用 `SOURCE_DATE_EPOCH`

### CI 中检查

- [ ] `verify-reproducible-build.py` 通过
- [ ] 两次顺序构建的哈希一致
- [ ] 产物上传至 GitHub Actions Artifacts 存档

### 发布前检查

- [ ] 发布标签已 GPG 签名
- [ ] 构建产物哈希已记录到发布说明
- [ ] 构建日志中无可复现性警告

---

## 🔗 参考资源

- [Reproducible Builds](https://reproducible-builds.org/)
- [Python Packaging: Reproducible Builds](https://packaging.python.org/en/latest/guides/reproducible-builds/)
- [Docker: Reproducible Builds](https://docs.docker.com/build/ci/reproducible-builds/)
- [SLSA Framework](https://slsa.dev/)
- [GitHub: Attestations](https://docs.github.com/en/actions/security-guides/using-artifact-attestations)

---

*海燕党（PETREL AI PARTY）承诺：所有公开发布的构建产物均可独立复现验证。*
