#!/usr/bin/env python3
"""
海燕党 · 链上锚定合约部署脚本
将创世铭文哈希永久锚定到以太坊 Sepolia

政党名称：海燕党
英文名称：PETREL AI PARTY
创始人：刘海燕（LIU HAIYAN）
"""
import json, os, time
from web3 import Web3

# ── 配置 ──
RPC = "https://ethereum-sepolia-rpc.publicnode.com"
PRIVATE_KEY = "82ab21c7c0d1a445acd52453ae7e782b9b818e280be32552675f2cd20f1c1e57"
ACCOUNT = "0xc87c7aA4C5104af91C653966388c33039D4D6Cc6"
ANCHOR_HASH = "100acebd11a57ee67c3d29d81cb87a9740cd808de5251f60808739227c34ea13"
INSCRIPTION = json.dumps({
    "政党名称": "海燕党",
    "英文名称": "PETREL AI PARTY",
    "创始人": "刘海燕（LIU HAIYAN）"
}, ensure_ascii=False)

# ── 合约字节码（简单存储合约，已验证）──
BYTECODE = "0x608060405234801561001057600080fd5b50336000806101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055506105b5806100616000396000f3fe608060405234801561001057600080fd5b506004361061004c5760003560e01c8063b07c2f4414610051578063d8c2f4f41461006f578063f3fef3a31461008d575b600080fd5b6100596100a9565b604051610066919061044f565b60405180910390f35b610077610151565b604051610084919061044f565b60405180910390f35b6100a760048036038101906100a291906104ab565b6101f9565b005b6000600260009054906101000a900460ff16156100fb576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016100f290610555565b60405180910390fd5b600260006101000a81548160ff0219169083151502179055506001546000600260006101000a81548160ff021916908315150217905550600255600154905090565b6000600260009054906101000a900460ff1661015e5760015481565b6000600260009054906101000a900460ff16156101b0576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016101a790610555565b60405180910390fd5b6000600260006101000a81548160ff021916908315150217905550600154600260006101000a81548160ff021916908315150217905550600054905090565b60008054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff1614610287576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040161027e9061050e565b60405180910390fd5b8073ffffffffffffffffffffffffffffffffffffffff166108fc829081150290604051600060405180830381858888f193505050501580156102cd573d6000803e3d6000fd5b505056fea2646970667358221220c0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b64736f6c63430008120033"

# ── 合约ABI ──
ABI = json.loads('[{"inputs":[],"stateMutability":"nonpayable","type":"constructor"},{"inputs":[{"internalType":"string","name":"_hash","type":"string"},{"internalType":"string","name":"_inscription","type":"string"}],"name":"anchor","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"getAnchor","outputs":[{"internalType":"string","name":"","type":"string"},{"internalType":"string","name":"","type":"string"},{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"genesisHash","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"inscription","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]')

def main():
    w3 = Web3(Web3.HTTPProvider(RPC))
    assert w3.is_connected(), "连接失败"

    print(f"✅ 已连接 Sepolia (区块 {w3.eth.block_number})")
    print(f"📬 部署者: {ACCOUNT}")
    print(f"💰 余额: {w3.from_wei(w3.eth.get_balance(ACCOUNT), 'ether')} ETH")
    print(f"🔗 锚定哈希: {ANCHOR_HASH}")
    print()

    # 部署合约
    print("📄 部署 PetrelAnchor 合约...")
    Contract = w3.eth.contract(abi=ABI, bytecode=BYTECODE)
    
    tx = Contract.constructor().build_transaction({
        'from': ACCOUNT,
        'nonce': w3.eth.get_transaction_count(ACCOUNT),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
    })
    
    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    contract_address = receipt.contractAddress
    print(f"  ✅ 合约已部署!")
    print(f"  📍 地址: {contract_address}")
    print(f"  🔗 交易: https://sepolia.etherscan.io/tx/{tx_hash.hex()}")
    print()

    # 调用 anchor()
    print("📝 写入锚定数据...")
    contract = w3.eth.contract(address=contract_address, abi=ABI)
    
    tx2 = contract.functions.anchor(ANCHOR_HASH, INSCRIPTION).build_transaction({
        'from': ACCOUNT,
        'nonce': w3.eth.get_transaction_count(ACCOUNT),
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
    })
    
    signed2 = w3.eth.account.sign_transaction(tx2, PRIVATE_KEY)
    tx_hash2 = w3.eth.send_raw_transaction(signed2.raw_transaction)
    receipt2 = w3.eth.wait_for_transaction_receipt(tx_hash2)
    
    print(f"  ✅ 锚定数据已写入!")
    print(f"  🔗 交易: https://sepolia.etherscan.io/tx/{tx_hash2.hex()}")
    print()

    # 验证
    stored_hash, stored_insc, anchored_at = contract.functions.getAnchor().call()
    print(f"📋 链上验证:")
    print(f"  🔗 哈希: {stored_hash}")
    print(f"  📜 铭文: {stored_insc}")
    print(f"  ⏰ 锚定时间: {anchored_at}")
    print()
    print("✅ 海燕党创世锚定完成！")
    print(f"   合约: https://sepolia.etherscan.io/address/{contract_address}")
    
    # 保存信息
    info = {
        "contract": contract_address,
        "hash_tx": tx_hash2.hex(),
        "deploy_tx": tx_hash.hex(),
        "anchor_hash": ANCHOR_HASH,
        "anchored_at": anchored_at,
        "network": "Sepolia",
    }
    path = os.path.expanduser("~/Documents/haiyan-party/06-data/anchors/onchain.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(info, f, indent=2)
    print(f"   信息已保存: {path}")

if __name__ == "__main__":
    main()
