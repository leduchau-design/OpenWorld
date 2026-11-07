"""OpenWorld Visual Web UI & Agent Sandbox.

A modern, zero-dependency browser-based interface for OpenWorld:
- Visual interactive agent graph and world map
- God Mode controls: Spawn agents, connect edges, toggle weather, queue actions
- AI Brain Dialogue: Chat with agents, inspect inner thoughts, and trigger autonomous actions
- HyperMemory inspector and cryptographic SHA-256 replay verifier

Usage:
    python examples/web_ui.py [--port 8080] [--host 127.0.0.1]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# Ensure src and examples are in path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))

from interactive_playground import AIBrain, PlaygroundWorld


# Global world instance for the web server
WORLD: PlaygroundWorld = None


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenWorld — AI Agent Sandbox</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #151d30;
      --card-border: #233152;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --purple: #a855f7;
      --green: #10b981;
      --amber: #f59e0b;
      --rose: #f43f5e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: var(--card-bg);
      border-bottom: 1px solid var(--card-border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .logo {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .logo-badge {
      background: linear-gradient(135deg, #3b82f6, #8b5cf6);
      color: white;
      font-weight: 800;
      font-size: 14px;
      padding: 6px 12px;
      border-radius: 8px;
      letter-spacing: 1px;
    }
    .title {
      font-size: 18px;
      font-weight: 700;
    }
    .subtitle {
      font-size: 12px;
      color: var(--text-muted);
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      padding: 6px 10px;
      border-radius: 6px;
      background: rgba(255,255,255,0.06);
      border: 1px solid var(--card-border);
    }
    .badge.green { background: rgba(16, 185, 129, 0.15); color: #34d399; border-color: rgba(16, 185, 129, 0.3); }
    .badge.purple { background: rgba(168, 85, 247, 0.15); color: #c084fc; border-color: rgba(168, 85, 247, 0.3); }
    .btn {
      background: var(--accent);
      color: white;
      border: none;
      padding: 8px 16px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .btn:hover { background: var(--accent-hover); transform: translateY(-1px); }
    .btn.secondary {
      background: rgba(255,255,255,0.08);
      color: var(--text);
      border: 1px solid var(--card-border);
    }
    .btn.secondary:hover { background: rgba(255,255,255,0.15); }
    .btn.danger { background: rgba(244, 63, 94, 0.2); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.4); }
    .btn.danger:hover { background: rgba(244, 63, 94, 0.35); }

    /* Main Container Grid */
    main {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 440px;
      gap: 20px;
      padding: 20px;
      max-width: 1600px;
      margin: 0 auto;
      width: 100%;
    }
    @media (max-width: 1024px) {
      main { grid-template-columns: 1fr; }
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .card-title {
      font-size: 15px;
      font-weight: 700;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--card-border);
    }

    /* World Regions & Agents */
    .regions-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin-top: 8px;
    }
    @media (max-width: 768px) {
      .regions-grid { grid-template-columns: 1fr; }
    }
    .region-box {
      background: rgba(11, 15, 25, 0.6);
      border: 1px dashed var(--card-border);
      border-radius: 10px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 240px;
    }
    .region-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 600;
      font-size: 13px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .weather-pill {
      font-size: 12px;
      padding: 3px 8px;
      border-radius: 12px;
      cursor: pointer;
      user-select: none;
    }
    .weather-pill.clear { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .weather-pill.rain { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); }

    /* Agent Card */
    .agent-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      cursor: pointer;
      transition: all 0.15s ease;
      position: relative;
    }
    .agent-card:hover {
      border-color: var(--accent);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .agent-card.selected {
      border-color: #8b5cf6;
      box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.4);
      background: rgba(139, 92, 246, 0.08);
    }
    .agent-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .agent-name {
      font-weight: 700;
      font-size: 14px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .agent-avatar {
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: linear-gradient(135deg, #3b82f6, #ec4899);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: bold;
    }
    .agent-balance {
      font-weight: 700;
      color: #34d399;
      font-size: 14px;
      background: rgba(16, 185, 129, 0.12);
      padding: 2px 8px;
      border-radius: 6px;
    }
    .agent-neighbors {
      font-size: 11px;
      color: var(--text-muted);
    }
    .agent-prob {
      font-size: 11px;
      color: #c084fc;
      display: flex;
      justify-content: space-between;
    }

    /* Right Panel Tabs */
    .tabs-header {
      display: flex;
      gap: 6px;
      background: rgba(11, 15, 25, 0.6);
      padding: 4px;
      border-radius: 8px;
    }
    .tab-btn {
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-weight: 600;
      font-size: 12px;
      padding: 8px 10px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .tab-btn.active {
      background: var(--card-bg);
      color: var(--text);
      box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    }
    .tab-content { display: none; }
    .tab-content.active { display: flex; flex-direction: column; gap: 14px; }

    /* Chat bubble container */
    .chat-box {
      background: rgba(11, 15, 25, 0.6);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 14px;
      height: 380px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .bubble {
      padding: 10px 14px;
      border-radius: 10px;
      font-size: 13px;
      line-height: 1.5;
      max-width: 90%;
      word-break: break-word;
    }
    .bubble.user {
      align-self: flex-end;
      background: var(--accent);
      color: white;
    }
    .bubble.thought {
      align-self: flex-start;
      background: rgba(168, 85, 247, 0.15);
      border: 1px solid rgba(168, 85, 247, 0.35);
      color: #e9d5ff;
      font-style: italic;
    }
    .bubble.thought::before {
      content: "🧠 Suy nghĩ nội tâm: ";
      font-weight: bold;
      font-style: normal;
      color: #c084fc;
      display: block;
      margin-bottom: 4px;
    }
    .bubble.message {
      align-self: flex-start;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.35);
      color: #a7f3d0;
    }
    .bubble.message::before {
      content: "💬 Lời nói của Agent: ";
      font-weight: bold;
      color: #34d399;
      display: block;
      margin-bottom: 4px;
    }
    .bubble.action-tag {
      align-self: center;
      background: rgba(245, 158, 11, 0.12);
      border: 1px dashed rgba(245, 158, 11, 0.4);
      color: #fde68a;
      font-size: 11px;
      padding: 4px 10px;
      border-radius: 20px;
    }

    /* Form Controls */
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .form-group label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
    }
    input, select, textarea {
      background: rgba(11, 15, 25, 0.8);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 13px;
      outline: none;
      transition: border-color 0.15s ease;
    }
    input:focus, select:focus, textarea:focus {
      border-color: var(--accent);
    }
    .form-row {
      display: flex;
      gap: 10px;
    }
    .form-row > * { flex: 1; }

    /* Quick Suggestions */
    .quick-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip {
      background: rgba(255,255,255,0.06);
      border: 1px solid var(--card-border);
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 11px;
      cursor: pointer;
      color: var(--text-muted);
      transition: all 0.15s ease;
    }
    .chip:hover {
      background: rgba(59, 130, 246, 0.15);
      border-color: var(--accent);
      color: var(--text);
    }

    /* Event Table */
    .events-list {
      max-height: 220px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-size: 12px;
    }
    .event-row {
      background: rgba(11, 15, 25, 0.4);
      padding: 8px 10px;
      border-radius: 6px;
      display: flex;
      justify-content: space-between;
      border-left: 3px solid var(--accent);
    }
  </style>
</head>
<body>
  <header>
    <div class="logo">
      <div class="logo-badge">OPENWORLD</div>
      <div>
        <div class="title">Visual Agent Sandbox & AI Brain</div>
        <div class="subtitle">Thế giới tác tử tự do & Replay kiểm chứng mật mã</div>
      </div>
    </div>
    <div class="header-actions">
      <div class="badge green" id="badge-tick">Tick: 0</div>
      <div class="badge purple" id="badge-ai">AI: Heuristic (Offline)</div>
      <div class="badge" id="badge-replay">Replay: PASS</div>
      <button class="btn" onclick="tickWorld()">▶ Next Tick</button>
      <button class="btn secondary" id="btn-auto" onclick="toggleAuto()">⚡ Auto: Off</button>
      <button class="btn danger" onclick="resetWorld()">↺ Reset</button>
    </div>
  </header>

  <main>
    <!-- LEFT: World Visualization -->
    <div class="card">
      <div class="card-title">
        <span>🗺️ Bản đồ thế giới & Quần thể Agent</span>
        <span style="font-size: 12px; font-weight: normal; color: var(--text-muted);" id="digest-label">Digest: loading...</span>
      </div>

      <div class="regions-grid" id="regions-container">
        <!-- Rendered dynamically -->
      </div>

      <!-- Live Event Feed -->
      <div style="margin-top: 14px;">
        <div class="card-title" style="margin-bottom: 8px; font-size: 13px;">
          <span>📜 Nhật ký sự kiện thế giới (Event Ledger)</span>
          <span style="font-size: 11px; color: var(--text-muted);">Mọi hành động đều được băm SHA-256</span>
        </div>
        <div class="events-list" id="events-container">
          <div style="color: var(--text-muted); padding: 8px;">Chưa có sự kiện nào được ghi nhận.</div>
        </div>
      </div>
    </div>

    <!-- RIGHT: Control & AI Chat Panel -->
    <div class="card">
      <div class="tabs-header">
        <button class="tab-btn active" onclick="switchTab('tab-ai')">💬 Não AI & Trò chuyện</button>
        <button class="tab-btn" onclick="switchTab('tab-god')">⚡ Tạo & Điều khiển</button>
        <button class="tab-btn" onclick="switchTab('tab-memory')">🧠 Trí nhớ Agent</button>
        <button class="tab-btn" onclick="switchTab('tab-config')">⚙️ Cấu hình AI</button>
      </div>

      <!-- TAB 1: AI Chat & Reasoning -->
      <div class="tab-content active" id="tab-ai">
        <div style="font-size: 13px; font-weight: 600; color: #93c5fd;" id="selected-agent-header">
          Đang tương tác với: <b>alice</b>
        </div>

        <div class="chat-box" id="chat-messages">
          <div class="bubble message">Chào bạn! Tôi là Agent trong OpenWorld. Bạn hãy giao nhiệm vụ hoặc hỏi bất kỳ điều gì, tôi sẽ suy nghĩ và thực hiện.</div>
        </div>

        <div class="quick-chips">
          <div class="chip" onclick="fillPrompt('Chào hỏi hàng xóm và thăm dò tình hình')">👋 Chào hỏi hàng xóm</div>
          <div class="chip" onclick="fillPrompt('Tôi cần thêm tài nguyên, hãy thương lượng với hàng xóm')">🤝 Thương lượng tài nguyên</div>
          <div class="chip" onclick="fillPrompt('Chuyển 1 tài nguyên cho hàng xóm để kết giao')">🎁 Tặng tài nguyên</div>
          <div class="chip" onclick="fillPrompt('Thời tiết đang mưa bão, hãy giữ tài nguyên và phòng thủ')">🛡️ Phòng thủ mùa bão</div>
        </div>

        <div class="form-group">
          <textarea id="prompt-input" rows="2" placeholder="Gõ yêu cầu tự nhiên (Ví dụ: 'Alice ơi, hãy chia sẻ tài nguyên cho Bob nhé')..."></textarea>
        </div>

        <div class="form-row">
          <button class="btn secondary" onclick="askAI(false)">🧠 Chỉ suy nghĩ (Ask)</button>
          <button class="btn" onclick="askAI(true)">⚡ Suy nghĩ & Thi hành (Act)</button>
        </div>
      </div>

      <!-- TAB 2: God Mode (Tạo & Thao tác thủ công) -->
      <div class="tab-content" id="tab-god">
        <div style="font-weight: 700; font-size: 13px;">Tạo Agent mới vào thế giới</div>
        <div class="form-row">
          <div class="form-group">
            <label>Tên Agent</label>
            <input type="text" id="new-agent-id" placeholder="vd: charlie">
          </div>
          <div class="form-group">
            <label>Tài nguyên ban đầu</label>
            <input type="number" id="new-agent-bal" value="5">
          </div>
          <div class="form-group">
            <label>Vùng</label>
            <select id="new-agent-region">
              <option value="north">North</option>
              <option value="mid" selected>Mid</option>
              <option value="south">South</option>
            </select>
          </div>
        </div>
        <button class="btn" onclick="createAgent()">+ Tạo nhân vật</button>

        <hr style="border-color: var(--card-border); margin: 6px 0;">

        <div style="font-weight: 700; font-size: 13px;">Nối quan hệ hàng xóm</div>
        <div class="form-row">
          <select id="connect-a1"></select>
          <select id="connect-a2"></select>
          <button class="btn secondary" onclick="connectAgents()">🔗 Nối</button>
        </div>

        <hr style="border-color: var(--card-border); margin: 6px 0;">

        <div style="font-weight: 700; font-size: 13px;">Chuyển tài nguyên thủ công</div>
        <div class="form-row">
          <select id="transfer-from"></select>
          <select id="transfer-to"></select>
          <input type="number" id="transfer-amt" value="1" min="1" style="width: 70px;">
          <button class="btn" onclick="queueTransfer()">Chuyển</button>
        </div>
      </div>

      <!-- TAB 3: HyperMemory & Inspector -->
      <div class="tab-content" id="tab-memory">
        <div style="font-weight: 700; font-size: 13px;">Hệ thống Trí nhớ HyperMemory</div>
        <div style="font-size: 12px; color: var(--text-muted);">
          HyperMemory theo dõi sự kiện chính xác (exact-evidence lane) và cập nhật phân phối xác suất Bayesian Beta-Bernoulli sau mỗi tương tác.
        </div>
        <div id="memory-stats-box" style="background: rgba(11,15,25,0.6); padding: 12px; border-radius: 8px; font-size: 13px; line-height: 1.8;">
          Chọn một Agent để xem trí nhớ...
        </div>
      </div>

      <!-- TAB 4: Cấu hình AI Backend -->
      <div class="tab-content" id="tab-config">
        <div style="font-weight: 700; font-size: 13px;">Chọn nguồn Não AI</div>
        <div class="form-group">
          <label>Nguồn AI</label>
          <select id="ai-provider" onchange="onAIProviderChange()">
            <option value="heuristic">Heuristic (Chạy Offline máy tính, 0đ)</option>
            <option value="gemini">Google Gemini API</option>
            <option value="openai">OpenAI ChatGPT API</option>
            <option value="ollama">Ollama (Mô hình AI Local trên máy)</option>
          </select>
        </div>
        <div class="form-group" id="group-api-key" style="display: none;">
          <label id="label-api-key">API Key</label>
          <input type="password" id="ai-api-key" placeholder="Nhập API Key...">
        </div>
        <div class="form-group" id="group-model" style="display: none;">
          <label>Tên Model (vd: gemini-1.5-flash / llama3 / gpt-4o-mini)</label>
          <input type="text" id="ai-model" placeholder="Model name...">
        </div>
        <button class="btn" onclick="saveAIConfig()">💾 Lưu cấu hình AI</button>
      </div>
    </div>
  </main>

  <script>
    let currentState = null;
    let selectedAgent = "alice";
    let autoInterval = null;

    async function fetchState() {
      try {
        const res = await fetch("/api/state");
        currentState = await res.json();
        renderWorld();
      } catch (err) {
        console.error("Error fetching state:", err);
      }
    }

    function renderWorld() {
      if (!currentState) return;

      document.getElementById("badge-tick").innerText = "Tick: " + currentState.tick;
      document.getElementById("badge-replay").innerText = "Replay: " + (currentState.replay_ok ? "PASS" : "FAIL");
      document.getElementById("digest-label").innerText = "Digest: " + currentState.fingerprint.substring(0, 16) + "...";

      const regions = { north: [], mid: [], south: [] };
      currentState.agents.forEach(a => {
        if (regions[a.region]) regions[a.region].push(a);
        else regions.mid.push(a);
      });

      const container = document.getElementById("regions-container");
      container.innerHTML = "";

      ["north", "mid", "south"].forEach(reg => {
        const weatherCond = currentState.weather[reg] || "clear";
        const box = document.createElement("div");
        box.className = "region-box";

        const weatherEmoji = weatherCond === "rain" ? "🌧️ Mưa" : "☀️ Nắng";
        box.innerHTML = `
          <div class="region-header">
            <span>${reg.toUpperCase()}</span>
            <span class="weather-pill ${weatherCond}" onclick="toggleWeather('${reg}', '${weatherCond}')">${weatherEmoji}</span>
          </div>
          <div id="agents-in-${reg}" style="display: flex; flex-direction: column; gap: 8px;"></div>
        `;
        container.appendChild(box);

        const agentContainer = box.querySelector(`#agents-in-${reg}`);
        regions[reg].forEach(agent => {
          const isSel = agent.id === selectedAgent;
          const card = document.createElement("div");
          card.className = "agent-card" + (isSel ? " selected" : "");
          card.onclick = () => selectAgent(agent.id);

          const initial = agent.id.substring(0, 2).toUpperCase();
          const neighborsStr = agent.neighbors.join(", ") || "(chưa có)";

          card.innerHTML = `
            <div class="agent-top">
              <div class="agent-name">
                <div class="agent-avatar">${initial}</div>
                <span>${agent.id}</span>
              </div>
              <div class="agent-balance">⚡ ${agent.balance}</div>
            </div>
            <div class="agent-neighbors">🔗 Hàng xóm: ${neighborsStr}</div>
            <div class="agent-prob">
              <span>Tin cậy Bayes:</span>
              <b>${(agent.p_success * 100).toFixed(1)}%</b>
            </div>
          `;
          agentContainer.appendChild(card);
        });
      });

      // Update dropdowns
      updateDropdowns();

      // Render events
      const eventsContainer = document.getElementById("events-container");
      if (currentState.events && currentState.events.length > 0) {
        eventsContainer.innerHTML = currentState.events.slice().reverse().slice(0, 8).map(e => `
          <div class="event-row">
            <span><b>T:${e.tick}</b> | <b>${e.actor}</b> ➔ ${e.kind} ➔ <b>${e.target}</b> (${e.amount > 0 ? e.amount + ' tài nguyên' : 'tín hiệu'})</span>
            <span style="color: var(--text-muted); font-size: 11px;">${e.provenance}</span>
          </div>
        `).join("");
      }

      // Update memory inspector if open
      updateMemoryStats();
    }

    function selectAgent(id) {
      selectedAgent = id;
      document.getElementById("selected-agent-header").innerHTML = "Đang tương tác với: <b>" + id + "</b>";
      renderWorld();
    }

    function updateDropdowns() {
      if (!currentState) return;
      const agentIds = currentState.agents.map(a => a.id);
      const fills = ["connect-a1", "connect-a2", "transfer-from", "transfer-to"];
      fills.forEach(id => {
        const el = document.getElementById(id);
        const curVal = el.value;
        el.innerHTML = agentIds.map(aid => `<option value="${aid}">${aid}</option>`).join("");
        if (curVal && agentIds.includes(curVal)) el.value = curVal;
      });
      if (agentIds.length >= 2) {
        if (!document.getElementById("connect-a2").value || document.getElementById("connect-a2").value === document.getElementById("connect-a1").value) {
          document.getElementById("connect-a2").value = agentIds[1];
        }
        if (!document.getElementById("transfer-to").value || document.getElementById("transfer-to").value === document.getElementById("transfer-from").value) {
          document.getElementById("transfer-to").value = agentIds[1];
        }
      }
    }

    function updateMemoryStats() {
      if (!currentState) return;
      const agent = currentState.agents.find(a => a.id === selectedAgent);
      if (!agent) return;
      const box = document.getElementById("memory-stats-box");
      box.innerHTML = `
        <div><b>Agent ID:</b> <span style="color: #60a5fa">${agent.id}</span></div>
        <div><b>Chủ sở hữu (Owner):</b> ${agent.owner}</div>
        <div><b>Số quan sát đã ghi nhận:</b> ${agent.memory_stats.n}</div>
        <div><b>Số tương tác thành công:</b> ${agent.memory_stats.successes}</div>
        <div><b>Mã chuỗi (Sequence #):</b> ${agent.memory_stats.seq}</div>
        <div><b>Ước lượng niềm tin (P-Success):</b> <span style="color: #34d399; font-weight: bold">${(agent.p_success * 100).toFixed(2)}%</span></div>
        <div><b>Mô hình dự đoán tích cực:</b> ${agent.estimator}</div>
      `;
    }

    async function tickWorld() {
      await fetch("/api/tick", { method: "POST" });
      await fetchState();
    }

    function toggleAuto() {
      const btn = document.getElementById("btn-auto");
      if (autoInterval) {
        clearInterval(autoInterval);
        autoInterval = null;
        btn.innerText = "⚡ Auto: Off";
        btn.classList.remove("danger");
        btn.classList.add("secondary");
      } else {
        autoInterval = setInterval(async () => {
          await fetch("/api/tick", { method: "POST" });
          await fetchState();
        }, 1500);
        btn.innerText = "⏸ Đang chạy Auto...";
        btn.classList.remove("secondary");
        btn.classList.add("danger");
      }
    }

    async function resetWorld() {
      if (confirm("Bạn có chắc muốn đặt lại thế giới về ban đầu?")) {
        await fetch("/api/reset", { method: "POST" });
        await fetchState();
      }
    }

    async function createAgent() {
      const name = document.getElementById("new-agent-id").value.trim();
      const bal = parseInt(document.getElementById("new-agent-bal").value) || 5;
      const reg = document.getElementById("new-agent-region").value;
      if (!name) return alert("Vui lòng nhập tên Agent");
      const res = await fetch("/api/create_agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: name, balance: bal, region: reg, owner: "owner1" })
      });
      const data = await res.json();
      if (data.error) alert(data.error);
      else {
        document.getElementById("new-agent-id").value = "";
        await fetchState();
      }
    }

    async function connectAgents() {
      const a1 = document.getElementById("connect-a1").value;
      const a2 = document.getElementById("connect-a2").value;
      if (a1 === a2) return alert("Chọn 2 agent khác nhau để nối");
      await fetch("/api/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent1: a1, agent2: a2 })
      });
      await fetchState();
    }

    async function toggleWeather(reg, curCond) {
      const nextCond = curCond === "clear" ? "rain" : "clear";
      await fetch("/api/weather", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ region: reg, condition: nextCond })
      });
      await tickWorld();
    }

    async function queueTransfer() {
      const from = document.getElementById("transfer-from").value;
      const to = document.getElementById("transfer-to").value;
      const amt = parseInt(document.getElementById("transfer-amt").value) || 1;
      if (from === to) return alert("Người nhận phải khác người chuyển");
      await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: from, target: to, kind: "transfer", amount: amt })
      });
      await tickWorld();
    }

    function fillPrompt(text) {
      document.getElementById("prompt-input").value = text;
    }

    async function askAI(shouldAct) {
      const promptInput = document.getElementById("prompt-input");
      const prompt = promptInput.value.trim();
      if (!prompt) return alert("Vui lòng nhập câu hỏi hoặc yêu cầu cho Agent.");

      const chatBox = document.getElementById("chat-messages");
      chatBox.innerHTML += `<div class="bubble user">${prompt}</div>`;
      chatBox.scrollTop = chatBox.scrollHeight;
      promptInput.value = "";

      const endpoint = shouldAct ? "/api/act" : "/api/ask";
      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agent_id: selectedAgent, prompt: prompt })
        });
        const data = await res.json();
        const decision = data.decision || data;

        chatBox.innerHTML += `<div class="bubble thought">${decision.thought || "(Đang suy nghĩ...)"}</div>`;
        chatBox.innerHTML += `<div class="bubble message">${decision.message || "(Không có phản hồi)"}</div>`;
        if (shouldAct && decision.action && decision.action !== "hold") {
          chatBox.innerHTML += `<div class="bubble action-tag">⚡ Đã thi hành: ${decision.action.toUpperCase()} ➔ ${decision.target || ''} (SL: ${decision.amount || 0})</div>`;
        }
        chatBox.scrollTop = chatBox.scrollHeight;
        await fetchState();
      } catch (err) {
        alert("Lỗi khi gọi AI: " + err);
      }
    }

    function switchTab(tabId) {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      event.target.classList.add("active");
      document.getElementById(tabId).classList.add("active");
    }

    function onAIProviderChange() {
      const prov = document.getElementById("ai-provider").value;
      const keyGroup = document.getElementById("group-api-key");
      const modelGroup = document.getElementById("group-model");

      if (prov === "heuristic") {
        keyGroup.style.display = "none";
        modelGroup.style.display = "none";
      } else if (prov === "ollama") {
        keyGroup.style.display = "none";
        modelGroup.style.display = "flex";
        document.getElementById("ai-model").value = "llama3";
      } else {
        keyGroup.style.display = "flex";
        modelGroup.style.display = "flex";
        document.getElementById("label-api-key").innerText = prov.toUpperCase() + " API Key";
        document.getElementById("ai-model").value = prov === "gemini" ? "gemini-1.5-flash" : "gpt-4o-mini";
      }
    }

    async function saveAIConfig() {
      const prov = document.getElementById("ai-provider").value;
      const key = document.getElementById("ai-api-key").value.trim();
      const model = document.getElementById("ai-model").value.trim();

      const res = await fetch("/api/set_ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: prov, api_key: key, model: model })
      });
      const data = await res.json();
      document.getElementById("badge-ai").innerText = "AI: " + prov.toUpperCase();
      alert("Đã lưu cấu hình AI thành công!");
    }

    // Auto fetch state at launch
    fetchState();
  </script>
</body>
</html>
"""


class OpenWorldWebHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP Handler serving SPA frontend and REST APIs."""

    def log_message(self, format: str, *args: Any) -> None:
        # Keep console output clean
        return

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            content = HTML_TEMPLATE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        elif path == "/api/state":
            global WORLD
            agents_list = []
            for aid, agent in WORLD.agents_dict.items():
                obs = WORLD.observe(aid)
                pred, est = WORLD.get_prediction(aid)
                owner = agent.owner_id
                mem_state = WORLD.memory.get_state(owner_id=owner, agent_id=aid, requester_owner_id=owner)
                agents_list.append({
                    "id": aid,
                    "owner": owner,
                    "region": agent.region,
                    "balance": agent.resources,
                    "neighbors": list(obs.neighbors),
                    "p_success": round(pred, 4),
                    "estimator": est,
                    "memory_stats": {
                        "n": mem_state["n"],
                        "successes": mem_state["successes"],
                        "seq": mem_state["seq"],
                    },
                })

            weather_dict = {reg: cond for reg, cond in WORLD.current_world.weather}
            events_list = [
                {
                    "tick": e.tick,
                    "sequence": e.sequence,
                    "actor": e.actor,
                    "target": e.target,
                    "kind": e.kind,
                    "amount": e.amount,
                    "provenance": e.provenance,
                }
                for e in WORLD.current_world.events
            ]

            payload = {
                "tick": WORLD.current_world.tick,
                "fingerprint": WORLD.current_world.fingerprint(),
                "replay_ok": WORLD.verify_chain(),
                "weather": weather_dict,
                "agents": agents_list,
                "events": events_list,
            }
            self._send_json(payload)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        global WORLD
        path = urlparse(self.path).path
        body = self._read_json()

        try:
            if path == "/api/create_agent":
                aid = body.get("agent_id")
                bal = int(body.get("balance", 5))
                reg = body.get("region", "mid")
                owner = body.get("owner", "owner1")
                WORLD.add_agent(aid, bal, reg, owner)
                self._send_json({"ok": True})

            elif path == "/api/connect":
                a1 = body.get("agent1")
                a2 = body.get("agent2")
                WORLD.connect(a1, a2)
                self._send_json({"ok": True})

            elif path == "/api/weather":
                reg = body.get("region")
                cond = body.get("condition")
                WORLD.set_weather(reg, cond)
                self._send_json({"ok": True})

            elif path == "/api/action":
                actor = body.get("actor")
                target = body.get("target")
                kind = body.get("kind", "transfer")
                amt = int(body.get("amount", 1))
                req_id = WORLD.queue_action(actor, target, kind, amt)
                self._send_json({"ok": True, "request_id": req_id})

            elif path == "/api/tick":
                step = WORLD.tick()
                self._send_json({
                    "tick": step.world.tick,
                    "accepted": list(step.accepted),
                    "rejected": list(step.rejected),
                })

            elif path == "/api/ask":
                aid = body.get("agent_id")
                prompt = body.get("prompt", "")
                decision = WORLD.ask_agent(aid, prompt)
                self._send_json({"decision": decision})

            elif path == "/api/act":
                aid = body.get("agent_id")
                prompt = body.get("prompt", "")
                decision, step = WORLD.act_with_ai(aid, prompt)
                self._send_json({
                    "decision": decision,
                    "tick": step.world.tick,
                    "accepted": list(step.accepted),
                })

            elif path == "/api/set_ai":
                prov = body.get("provider", "heuristic")
                key = body.get("api_key")
                model = body.get("model")
                WORLD.ai = AIBrain(provider=prov, model=model, api_key=key)
                self._send_json({"ok": True, "provider": prov})

            elif path == "/api/reset":
                WORLD.reset()
                self._send_json({"ok": True})

            else:
                self.send_error(404, "Unknown API")

        except Exception as e:
            self._send_json({"error": str(e)}, status=400)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    global WORLD
    WORLD = PlaygroundWorld()
    server = HTTPServer((host, port), OpenWorldWebHandler)
    url = f"http://{host}:{port}"
    print(f"\n=================================================================")
    print(f"  OPENWORLD WEB UI RUNNING AT: {url}")
    print(f"  Open your browser (Chrome/Edge) to view the visual dashboard.")
    print(f"  Press Ctrl+C in this console to stop the server.")
    print(f"=================================================================\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping OpenWorld Web Server...")
    finally:
        server.server_close()
        WORLD.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenWorld Visual Web UI")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    run_server(args.host, args.port)
