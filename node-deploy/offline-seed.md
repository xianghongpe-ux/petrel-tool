# 海燕党 · DZN 协议种子 — U盘离线版

> 创世铭文: 天下兴亡，匹夫有责。算力虽微，众志可城。

## 📦 何为"协议种子"？

协议种子是 DZN 分布式AI网络的**最小可传播单元**。当一个 U 盘插入一台未联网的电脑，只要里面有协议种子，任何人都可以启动一个新的 DZN 网络节点。

---

## 🗂️ U盘目录结构

```
DZN-SEED/
├── README.md                  # 本文件
├── GENESIS.txt                # 创世铭文 & 网络标识
├── dzn/                       # DZN 核心代码
│   ├── dzn_scheduler.py
│   ├── model_consensus.py
│   ├── ai_output_lock.py
│   ├── inference_node.py
│   └── __init__.py
├── docker/                    # Docker 部署文件
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── nginx.conf
├── scripts/
│   ├── deploy.sh              # 一键部署脚本
│   ├── run-node.sh            # 仅运行推理节点
│   └── offline-verify.sh      # 离线验证脚本
├── config/
│   ├── node-config.yaml        # 节点配置模板
│   └── bootstrap-peers.txt    # 初始对等节点列表
├── keys/
│   ├── node-key.pem           # 节点密钥（预生成）
│   └── ca-cert.pem            # CA 证书（可选）
├── docs/
│   ├── quick-start.md         # 快速开始指南
│   └── architecture.md        # 架构说明
└── .dzn-seed                  # 种子标识文件（空标志）
```

---

## 🚀 使用步骤

### 方案 A：Docker 部署（推荐）

```bash
# 1. 插入 U 盘
# 2. 复制到本地
cp -r /media/USB/DZN-SEED ~/dzn-seed
cd ~/dzn-seed/docker

# 3. 一键部署
bash ../scripts/deploy.sh

# 4. 验证
curl http://localhost:8765/p2p/ping
```

### 方案 B：裸机部署

```bash
# 1. 安装 Python 依赖
pip install aiohttp numpy psutil py-cpuinfo

# 2. 运行推理节点
python dzn/inference_node.py --port 9100 --scheduler http://<调度器IP>:8765

# 3. 运行调度器（需第一个节点）
python dzn/dzn_scheduler.py --port 8765 --bootstrap <peer1> <peer2>
```

### 方案 C：完全离线的"黑启动"

当整个网络断开时，用 U 盘在局域网内重建网络：

```bash
# 1. 所有节点插入同一 U 盘
# 2. 其中一台运行调度器
bash run-node.sh --scheduler --seed

# 3. 其他节点连接
bash run-node.sh --connect-to <调度器IP>
```

---

## 🔐 安全说明

1. **离线优先**: 协议种子不依赖 GitHub / PyPI / Docker Hub
2. **信任锚点**: 种子中包含预生成密钥对，首次启动自动建立信任
3. **防篡改**: `.dzn-seed` 文件含 SHA-256 校验和
4. **传播审计**: 每个种子包含唯一序列号，可在网络上追溯来源

---

## 🌱 种子扩展

你可以将协议种子复制到任意数量的 U 盘。每个副本可独立启动一个新的网络分叉（fork），这些分叉后续可通过跨链桥接合并。

```bash
# 生成新种子（含新的密钥对和序列号）
python scripts/generate-seed.py --output /media/USB/DZN-SEED-02
```

---

## ⚡ 快速参考

| 文件 | 用途 |
|------|------|
| `GENESIS.txt` | 网络身份标识，所有节点必须相同 |
| `bootstrap-peers.txt` | 初始对等节点列表，首次启动时连接 |
| `node-config.yaml` | 节点配置，含端口、资源限制等 |
| `node-key.pem` | ECDSA P-256 私钥，身份认证用 |
| `offline-verify.sh` | 离线验证节点完整性 |

---

> **"天下兴亡，匹夫有责。算力虽微，众志可城。"**
> 每一个 U 盘都是一颗种子，每一颗种子都能长成一片森林。
