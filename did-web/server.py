#!/usr/bin/env python3
"""
海燕党 · DID:web 解析服务器
为 did:web:xianghongpe-ux.github.io 提供 DID Document 解析

政党名称：海燕党
英文名称：PETREL AI PARTY
创始人：刘海燕（LIU HAIYAN）
创世铭文 · 历史纪念碑，不是权力凭证 · 六层冗余永久嵌入
"""
import os
import json
import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

# ── DID Document ──
# did:web:xianghongpe-ux.github.io → https://xianghongpe-ux.github.io/.well-known/did.json
# Also supports did:petrel:xxx resolution via the petrel did:web bridge
DID_DOCUMENT = {
    "@context": [
        "https://www.w3.org/ns/did/v1",
        "https://w3id.org/security/multikey/v1"
    ],
    "id": "did:web:xianghongpe-ux.github.io",
    "alsoKnownAs": [
        "did:petrel:genesis",
        "did:petrel:0x7e7r3l_p4r7y_genesis_001"
    ],
    "verificationMethod": [
        {
            "id": "did:web:xianghongpe-ux.github.io#genesis-key",
            "type": "Multikey",
            "controller": "did:web:xianghongpe-ux.github.io",
            "publicKeyMultibase": "z6MkmM42vBZ4Tb3qLgkQp3GKZrPJkXnNmVJ9eNqGzKxvQy7F"
        }
    ],
    "authentication": [
        "did:web:xianghongpe-ux.github.io#genesis-key"
    ],
    "assertionMethod": [
        "did:web:xianghongpe-ux.github.io#genesis-key"
    ],
    "service": [
        {
            "id": "did:web:xianghongpe-ux.github.io#petrel-course",
            "type": "LinkedDomains",
            "serviceEndpoint": "https://xianghongpe-ux.github.io/petrel-course"
        },
        {
            "id": "did:web:xianghongpe-ux.github.io#petrel-github",
            "type": "LinkedDomains",
            "serviceEndpoint": "https://github.com/xianghongpe-ux"
        },
        {
            "id": "did:web:xianghongpe-ux.github.io#petrel-did-web",
            "type": "DIDResolution",
            "serviceEndpoint": "https://xianghongpe-ux.github.io/.well-known/did.json"
        }
    ],
    "inscription": {
        "partyName": "海燕党",
        "partyNameEn": "PETREL AI PARTY",
        "founder": "刘海燕（LIU HAIYAN）",
        "genesis": "海燕党/PETREL AI PARTY/刘海燕 — 六层冗余永久嵌入"
    }
}

# ── DID:petrel 到 DID:web 的桥接映射 ──
PETREL_DID_MAP = {
    "genesis": "did:web:xianghongpe-ux.github.io",
    "0x7e7r3l_p4r7y_genesis_001": "did:web:xianghongpe-ux.github.io",
}

app = FastAPI(
    title="海燕党 DID:web 解析服务",
    description="PETREL AI PARTY DID:web Resolution Server",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/.well-known/did.json")
async def resolve_did_web():
    """返回 did:web:xianghongpe-ux.github.io 的 DID Document"""
    return Response(
        content=json.dumps(DID_DOCUMENT, indent=2, ensure_ascii=False),
        media_type="application/did+json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "max-age=3600",
        }
    )


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "海燕党 DID:web 解析服务", "version": "1.0.0"}


@app.get("/resolve/{did:path}")
async def resolve_did(did: str):
    """
    解析 did:petrel:xxx 到对应的 DID Document
    通过桥接映射转发到 did:web
    """
    if not did.startswith("did:petrel:"):
        return Response(
            content=json.dumps({"error": "仅支持 did:petrel: 格式的 DID"}, ensure_ascii=False),
            media_type="application/json",
            status_code=400,
        )

    petrel_id = did.removeprefix("did:petrel:")
    web_did = PETREL_DID_MAP.get(petrel_id)

    if not web_did:
        return Response(
            content=json.dumps(
                {"error": f"无法解析: {did}", "note": "未知的海燕党DID标识符"},
                ensure_ascii=False,
            ),
            media_type="application/json",
            status_code=404,
        )

    return Response(
        content=json.dumps(DID_DOCUMENT, indent=2, ensure_ascii=False),
        media_type="application/did+json",
        headers={
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.get("/")
async def root():
    """服务概览"""
    return {
        "service": "海燕党 DID:web 解析服务",
        "service_en": "PETREL AI PARTY DID:web Resolution Server",
        "endpoints": {
            "/.well-known/did.json": "DID Document (did:web:xianghongpe-ux.github.io)",
            "/resolve/did:petrel:xxx": "did:petrel 桥接解析",
            "/health": "健康检查",
        },
        "inscription": "海燕党/PETREL AI PARTY/刘海燕",
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9300))
    print(f"""
    ╔══════════════════════════════════════════╗
    ║  海燕党 DID:web 解析服务                ║
    ║  PETREL AI PARTY DID Resolution Server   ║
    ╠══════════════════════════════════════════╣
    ║  端口: {port}                                 ║
    ║  DID:  did:web:xianghongpe-ux.github.io  ║
    ║  铭文: 海燕党/PETREL AI PARTY/刘海燕     ║
    ╚══════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=port)
