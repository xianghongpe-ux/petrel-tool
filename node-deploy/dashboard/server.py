#!/usr/bin/env python3
"""
海燕党 · DZN 社区健康度看板服务器
================================
创世铭文: 天下兴亡，匹夫有责。算力虽微，众志可城。
"""

from __future__ import annotations

import json
import os
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [DASH] %(message)s")
log = logging.getLogger("dashboard")

GENESIS = "天下兴亡，匹夫有责。算力虽微，众志可城。"
PORT = int(os.environ.get("DZN_DASHBOARD_PORT", "9103"))
REFRESH = int(os.environ.get("DZN_DASHBOARD_REFRESH", "30"))


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>海燕党 · DZN 社区健康度</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
       background:#0a0e1a; color:#c8d6e5; }
.container { max-width:1200px; margin:0 auto; padding:20px; }
header { text-align:center; padding:30px 0; border-bottom:1px solid #1a2340; }
h1 { color:#e8d44d; font-size:1.6em; letter-spacing:3px; }
.genesis { color:#3a5a7a; font-size:0.8em; margin-top:6px; font-style:italic; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; margin:24px 0; }
.card { background:#111827; border:1px solid #1e293b; border-radius:12px; padding:20px; }
.card h3 { color:#94a3b8; font-size:0.85em; text-transform:uppercase; letter-spacing:1px; margin-bottom:12px; }
.metric { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #1e293b; }
.metric:last-child { border:none; }
.metric .key { color:#64748b; font-size:0.85em; }
.metric .val { color:#e8d44d; font-weight:bold; }
.status-ok { color:#4ade80; }
.status-warn { color:#facc15; }
.status-err { color:#ef4444; }
.node-list { margin-top:24px; }
.node-item { display:flex; justify-content:space-between; padding:10px 16px;
             background:#0f172a; border-radius:8px; margin-bottom:8px; }
.node-name { color:#94a3b8; }
.node-rep { color:#e8d44d; }
.node-status { font-size:0.8em; padding:2px 8px; border-radius:12px; }
footer { text-align:center; padding:30px 0; color:#3a5a7a; font-size:0.8em; }
.timestamp { text-align:right; color:#3a5a7a; font-size:0.75em; margin-top:8px; }
</style>
</head>
<body>
<div class="container">
<header>
  <h1>🩺 DZN 社区健康度看板</h1>
  <p class="genesis">"{genesis}"</p>
</header>

<div class="grid" id="healthGrid">
  <div class="card">
    <h3>🌐 网络状态</h3>
    <div class="metric"><span class="key">总节点数</span><span class="val" id="totalNodes">--</span></div>
    <div class="metric"><span class="key">在线节点</span><span class="val" id="onlineNodes">--</span></div>
    <div class="metric"><span class="key">熔断状态</span><span class="val" id="fuseState">--</span></div>
    <div class="metric"><span class="key">网络延迟</span><span class="val" id="latency">--</span></div>
  </div>
  <div class="card">
    <h3>⚡ 算力统计</h3>
    <div class="metric"><span class="key">总 TFLOPS·h</span><span class="val" id="totalTflops">--</span></div>
    <div class="metric"><span class="key">活跃任务</span><span class="val" id="activeTasks">--</span></div>
    <div class="metric"><span class="key">排队任务</span><span class="val" id="queuedTasks">--</span></div>
    <div class="metric"><span class="key">任务吞吐</span><span class="val" id="throughput">--</span></div>
  </div>
  <div class="card">
    <h3>🤝 共识统计</h3>
    <div class="metric"><span class="key">共识分数</span><span class="val" id="consensusScore">--</span></div>
    <div class="metric"><span class="key">总提案数</span><span class="val" id="totalProposals">--</span></div>
    <div class="metric"><span class="key">通过率</span><span class="val" id="passRate">--</span></div>
    <div class="metric"><span class="key">分歧数</span><span class="val" id="divergences">--</span></div>
  </div>
  <div class="card">
    <h3>🏆 声誉 TOP5</h3>
    <div id="topReputation"><div class="metric"><span class="key">暂无数据</span></div></div>
  </div>
</div>

<div class="node-list">
  <h3 style="color:#94a3b8;font-size:0.85em;margin-bottom:12px;">📡 节点列表</h3>
  <div id="nodeList"><div class="metric"><span class="key">等待连接...</span></div></div>
</div>

<div class="timestamp" id="lastRefresh">上次刷新: --</div>
<footer>PETREL AI PARTY · DZN Distributed Network v1.0</footer>
</div>

<script>
const REFRESH = {refresh};

function updateData() {{
  fetch('/api/status')
    .then(r => r.json())
    .then(data => {{
      document.getElementById('totalNodes').textContent = data.total_nodes ?? 'N/A';
      document.getElementById('onlineNodes').textContent = data.online_nodes ?? 'N/A';
      const fs = document.getElementById('fuseState');
      fs.textContent = data.fuse_state ?? 'normal';
      fs.className = 'val status-' + (data.fuse_state === 'normal' ? 'ok' : 'warn');
      document.getElementById('latency').textContent = (data.latency_ms || 0) + 'ms';
      document.getElementById('totalTflops').textContent = (data.total_tflops_hours || 0).toFixed(1);
      document.getElementById('activeTasks').textContent = data.active_tasks ?? 0;
      document.getElementById('queuedTasks').textContent = data.queued_tasks ?? 0;
      document.getElementById('throughput').textContent = (data.throughput || '0') + '/h';
      document.getElementById('consensusScore').textContent = ((data.consensus_score || 0)*100).toFixed(0)+'%';
      document.getElementById('totalProposals').textContent = data.total_proposals ?? 0;
      document.getElementById('passRate').textContent = ((data.pass_rate || 0)*100).toFixed(0)+'%';
      document.getElementById('divergences').textContent = data.divergences ?? 0;

      const repDiv = document.getElementById('topReputation');
      if (data.top_reputation && data.top_reputation.length) {{
        repDiv.innerHTML = data.top_reputation.map(n =>
          `<div class="metric"><span class="key">${{n.id?.slice(0,10)||'?'}}</span><span class="val">${{n.rep?.toFixed(1)||'0'}}</span></div>`
        ).join('');
      }}

      const nodeDiv = document.getElementById('nodeList');
      if (data.nodes && data.nodes.length) {{
        nodeDiv.innerHTML = data.nodes.map(n =>
          `<div class="node-item"><span class="node-name">${{n.id?.slice(0,16)||'?'}}</span>
           <span class="node-rep">声誉:${{n.reputation?.toFixed(0)||'0'}}</span>
           <span class="node-status status-ok">${{n.status||'unknown'}}</span></div>`
        ).join('');
      }}

      document.getElementById('lastRefresh').textContent = '上次刷新: ' + new Date().toLocaleTimeString();
    }})
    .catch(() => {{}});
}}

updateData();
setInterval(updateData, REFRESH * 1000);
</script>
</body>
</html>
""".format(genesis=GENESIS, refresh=REFRESH)


class DashboardHandler(BaseHTTPRequestHandler):
    """看板 HTTP 处理器"""

    def do_GET(self):
        if self.path == "/health":
            self._json({"status": "ok", "genesis": GENESIS, "timestamp": time.time()})
        elif self.path == "/api/status":
            self._json(self._generate_status())
        else:
            self._html(DASHBOARD_HTML)

    def _generate_status(self) -> Dict[str, Any]:
        """生成模拟状态数据（实际部署时从 DZN 网络获取）"""
        return {
            "genesis": GENESIS,
            "total_nodes": 12,
            "online_nodes": 9,
            "fuse_state": "normal",
            "latency_ms": 45,
            "total_tflops_hours": 128.5,
            "active_tasks": 3,
            "queued_tasks": 7,
            "throughput": 24,
            "consensus_score": 0.87,
            "total_proposals": 256,
            "pass_rate": 0.92,
            "divergences": 3,
            "top_reputation": [
                {"id": "node_a1b2c3d4", "rep": 245.0},
                {"id": "node_e5f6g7h8", "rep": 198.0},
                {"id": "node_i9j0k1l2", "rep": 176.5},
                {"id": "node_m3n4o5p6", "rep": 152.0},
                {"id": "node_q7r8s9t0", "rep": 134.0},
            ],
            "nodes": [
                {"id": "node_%08x" % h, "status": "online", "reputation": 200 - i * 15}
                for i, h in enumerate([0xa1b2c3d4, 0xe5f6a7b8, 0xdeadbeef, 0x12345678,
                                        0x87654321, 0xabcdef01, 0x11112222, 0x33334444,
                                        0x55556666, 0x77778888, 0x99990000, 0xaaaabbbb])
            ],
        }

    def _json(self, data: Any):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _html(self, html: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, fmt, *args):
        log.info(fmt, *args)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DZN 社区健康度看板")
    parser.add_argument("--port", type=int, default=PORT, help=f"端口 (默认: {PORT})")
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), DashboardHandler)
    print(f"🩺 DZN 健康度看板 → http://localhost:{args.port}")
    print(f"   创世铭文: {GENESIS}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
