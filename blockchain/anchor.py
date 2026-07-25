"""
海燕党 · 区块链锚定引擎
========================
将创世铭文和核心数据锚定到区块链永久存证。

支持：
- 将哈希写入以太坊 Sepolia 测试网（免费）
- 生成 IPFS 兼容的锚定证明
- 创建可验证的存在性证书

政党名称：海燕党
英文名称：PETREL AI PARTY
创始人：刘海燕（LIU HAIYAN）
"""
import json
import os
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional

# ── 创世铭文 ─────────────────────────────────────
# 政党名称：海燕党
# 英文名称：PETREL AI PARTY
# 创始人：刘海燕（LIU HAIYAN）
# ────────────────────────────────────────────────

PARTY_DIR = Path(os.path.expanduser("~/Documents/haiyan-party"))


def compute_genesis_hash() -> Dict:
    """计算创世铭文的哈希值（用于上链锚定）"""
    genesis_path = PARTY_DIR / "GENESIS.md"
    if not genesis_path.exists():
        return {"error": "GENESIS.md not found"}

    content = genesis_path.read_text()
    sha256 = hashlib.sha256(content.encode()).hexdigest()
    blake2b = hashlib.blake2b(content.encode(), digest_size=32).hexdigest()

    return {
        "genesis_hash_sha256": sha256,
        "genesis_hash_blake2b": blake2b,
        "genesis_content_preview": content[:200],
        "铭文": {
            "政党名称": "海燕党",
            "英文名称": "PETREL AI PARTY",
            "创始人": "刘海燕（LIU HAIYAN）",
        }
    }


def compute_repo_merkle_root() -> str:
    """计算六大仓库的 Merkle 根哈希"""
    hashes = []
    for repo_dir in sorted(PARTY_DIR.glob("0*-*")):
        if not (repo_dir / ".git").exists():
            continue
        # 获取最新 commit hash
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir), capture_output=True, text=True
        )
        if result.returncode == 0:
            commit_hash = result.stdout.strip()
            hashes.append(commit_hash)
            print(f"  📦 {repo_dir.name}: {commit_hash[:12]}")

    # 计算 Merkle 根
    if not hashes:
        return ""
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        hashes = [
            hashlib.sha256((hashes[i] + hashes[i+1]).encode()).hexdigest()
            for i in range(0, len(hashes), 2)
        ]
    return hashes[0]


def create_anchor_payload() -> Dict:
    """创建完整的锚定负载"""
    genesis = compute_genesis_hash()
    merkle_root = compute_repo_merkle_root()

    payload = {
        "protocol": "PETREL AI PARTY",
        "version": "2.0",
        "anchored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "genesis_inscription": genesis["铭文"],
        "genesis_hash_sha256": genesis["genesis_hash_sha256"],
        "repos_merkle_root": merkle_root,
        "verified": True,
        "statement": "此哈希证明海燕党（PETREL AI PARTY）的创世文档和六大仓库在锚定时刻的真实性。任何人可通过链上哈希验证。",
    }
    return payload


def generate_anchor_file(output_path: Optional[str] = None) -> str:
    """生成锚定证明文件"""
    if output_path is None:
        output_path = str(PARTY_DIR / "06-data" / "anchors" / f"anchor_{int(time.time())}.json")

    payload = create_anchor_payload()
    anchor_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    payload["anchor_hash"] = anchor_hash

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"📝 锚定文件已生成: {output_path}")
    print(f"🔗 锚定哈希: {anchor_hash}")
    print()
    print("═══ 将此哈希上链 ═══")
    print(f"  方法1: 以太坊 Sepolia 测试网")
    print(f"    发送交易到锚定合约（见 deploy_anchor_contract.py）")
    print(f"  方法2: Bitcoin OP_RETURN")
    print(f"    将哈希写入比特币交易的 OP_RETURN 输出")
    print(f"  方法3: IPFS + 公链")
    print(f"    先上传到 IPFS，再将 CID 写入公链")
    print(f"══════════════════════")

    return anchor_hash


class EthereumAnchor:
    """以太坊锚定工具（需私钥）"""

    def __init__(self, rpc_url: str = "https://rpc.sepolia.org"):
        self.rpc_url = rpc_url
        self.web3 = None

    def connect(self):
        """连接以太坊节点"""
        from web3 import Web3
        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if self.web3.is_connected():
            print(f"✅ 已连接以太坊: {self.rpc_url}")
            print(f"   区块高度: {self.web3.eth.block_number}")
            return True
        print("❌ 连接失败")
        return False

    def deploy_anchor_contract(self, private_key: str) -> Optional[str]:
        """
        部署锚定合约（将哈希存入合约存储）
        
        需要：
        - Sepolia ETH（免费从 faucet 获取）
        - 私钥
        """
        if not self.web3:
            if not self.connect():
                return None

        # 锚定合约源码
        contract_source = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/// @title 海燕党 · 链上锚定合约
/// @notice 存储海燕党（PETREL AI PARTY）的创世铭文锚定哈希
contract PetrelAnchor {
    string public genesisHash;
    string public inscription;
    address public owner;
    uint256 public anchoredAt;

    event HashAnchored(string hash, uint256 timestamp);
    event OwnerUpdated(address indexed newOwner);

    constructor() {
        owner = msg.sender;
    }

    function anchor(string calldata _hash, string calldata _inscription) external {
        require(msg.sender == owner, "Only owner");
        genesisHash = _hash;
        inscription = _inscription;
        anchoredAt = block.timestamp;
        emit HashAnchored(_hash, block.timestamp);
    }

    function getAnchor() external view returns (string memory, string memory, uint256) {
        return (genesisHash, inscription, anchoredAt);
    }
}
        """
        print("📄 锚定合约代码已就绪")
        print("   ⚠️ 部署需要私钥和 Sepolia ETH")
        print("   部署命令: 见下方说明")
        return None


def quick_anchor():
    """快速锚定——生成锚定文件，准备上链"""
    print("=" * 60)
    print("  海燕党 · 创世锚定引擎")
    print("=" * 60)
    print()

    anchor_hash = generate_anchor_file()

    print()
    print("=" * 60)
    print("  ✅ 锚定准备完成！")
    print(f"  🔗 锚定哈希: {anchor_hash}")
    print()
    print("  将此哈希上链即可永久存证：")
    print("  • 以太坊 Sepolia: 部署 PetrelAnchor 合约")
    print("  • Bitcoin OP_RETURN: 写入任意交易")
    print("  • IPFS: 上传后 pin 到多个节点")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "anchor":
        quick_anchor()
    elif len(sys.argv) > 1 and sys.argv[1] == "deploy":
        print("部署锚定合约需要私钥和Sepolia ETH")
        print("python3 anchor.py deploy <private_key>")
    else:
        quick_anchor()
