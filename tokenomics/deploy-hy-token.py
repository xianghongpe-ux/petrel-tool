#!/usr/bin/env python3
"""
海燕党 · HY Token 部署脚本
部署 HY Token 到 Sepolia 测试网

政党名称：海燕党
英文名称：PETREL AI PARTY
创始人：刘海燕（LIU HAIYAN）
"""
import os, json, sys
from web3 import Web3

RPC = os.environ.get("SEPOLIA_RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
PK = os.environ.get("ETH_PRIVATE_KEY", "")
ACCT = os.environ.get("ETH_ACCOUNT", "")

def main():
    if not PK:
        print("❌ 请设置 ETH_PRIVATE_KEY 环境变量")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={'timeout': 120}))
    assert w3.is_connected(), "连接失败"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "build/HYToken.bin")) as f: bytecode = "0x" + f.read().strip()
    with open(os.path.join(base, "build/HYToken.abi")) as f: abi = json.load(f)

    balance = w3.from_wei(w3.eth.get_balance(ACCT), 'ether')
    print(f"✅ 连接 Sepolia (区块 {w3.eth.block_number})")
    print(f"📬 部署者: {ACCT}")
    print(f"💰 余额: {balance} ETH")
    print(f"🪙 合约: HY Token (1亿枚, ERC20+Permit+Ownable)")
    print()

    # 部署
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = Contract.constructor().build_transaction({
        'from': ACCT,
        'nonce': w3.eth.get_transaction_count(ACCT),
        'gas': 3000000,
        'gasPrice': w3.eth.gas_price,
    })
    signed = w3.eth.account.sign_transaction(tx, PK)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"⏳ 等待确认...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    addr = receipt.contractAddress

    print()
    print("=" * 60)
    print("  🪙  HY Token 已部署到 Sepolia！")
    print("=" * 60)
    print(f"  📍 合约地址: {addr}")
    print(f"  🔗 Etherscan: https://sepolia.etherscan.io/address/{addr}")
    print(f"  🔗 交易: https://sepolia.etherscan.io/tx/{tx_hash.hex()}")
    print()

    # 保存
    info = {
        "contract": addr,
        "tx": tx_hash.hex(),
        "network": "Sepolia",
        "symbol": "HY",
        "total_supply": "100,000,000",
        "account": ACCT,
        "vaults_initialized": False,
    }
    path = os.path.expanduser("~/Documents/haiyan-party/06-data/anchors/hy-token.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(info, f, indent=2)
    print(f"  ✅ 信息已保存: {path}")
    print()
    print("  📋 下一步:")
    print("  1. 创建4个金库地址 (community/team/treasury/ecosystem)")
    print(f"  2. 调用 initializeVaults() 铸造代币到各金库")
    print(f"  3. 在 MetaMask 添加 HY Token 查看余额")
    print("=" * 60)


if __name__ == "__main__":
    main()
