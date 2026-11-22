// Valorant Voice AI - Tactical Controller Client v2.0

let ws = null;
let currentDraftId = null;

// UI Elements
const connPill = document.getElementById("conn-pill");
const connText = document.getElementById("conn-text");
const healthPill = document.getElementById("health-pill");
const healthText = document.getElementById("health-text");

const hpSlider = document.getElementById("hp-slider");
const hpVal = document.getElementById("hp-val");
const micSlider = document.getElementById("mic-slider");
const micVal = document.getElementById("mic-val");
const btnMute = document.getElementById("btn-mute");
const muteLabel = document.getElementById("mute-label");

const subFeed = document.getElementById("sub-feed");
const feedEmpty = document.getElementById("feed-empty");

const chatDraftBox = document.getElementById("chat-draft-box");
const noChatMsg = document.getElementById("no-chat-msg");
const draftText = document.getElementById("draft-text");
const draftIdLabel = document.getElementById("draft-id-label");
const draftChannel = document.getElementById("draft-channel");
const btnApproveChat = document.getElementById("btn-approve-chat");
const btnRejectChat = document.getElementById("btn-reject-chat");

const voiceSelect = document.getElementById("voice-select");
const overlayModeSelect = document.getElementById("overlay-mode-select");
const fpsBtns = document.querySelectorAll(".fps-btn");
const btnTeammateTrigger = document.getElementById("btn-teammate-trigger");
const teammateTriggerLabel = document.getElementById("teammate-trigger-label");

const btnAutoFix = document.getElementById("btn-auto-fix");
const diagMic = document.getElementById("diag-mic");
const diagFps = document.getElementById("diag-fps");
const diagGame = document.getElementById("diag-game");

const btnCopyLink = document.getElementById("btn-copy-link");
const remoteLinkInput = document.getElementById("remote-link-input");

// 1. WebSocket Connection
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

  ws.onopen = () => {
    connPill.className = "status-pill pill-online";
    connText.textContent = "CONNECTED";
    fetchStatus();
    fetchDiagnostics();
  };

  ws.onclose = () => {
    connPill.className = "status-pill pill-offline";
    connText.textContent = "DISCONNECTED";
    setTimeout(initWebSocket, 2000);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "volume_update") {
        updateSlidersUI(data.headphone, data.game_mic, data.mute_game_mic);
      } else if (data.type === "chat_draft") {
        showChatDraft(data.draft_id, data.content, data.channel);
      } else if (data.type === "subtitle") {
        appendSubtitleFeed(data.original, data.translated);
      } else if (data.type === "system_healed" || data.type === "config_updated") {
        fetchStatus();
        fetchDiagnostics();
      } else if (data.type === "game_status") {
        diagGame.textContent = data.running ? `IN-GAME (#${data.pid})` : "Chờ mở...";
      }
    } catch (e) {}
  };
}

// 2. Fetch Initial Status
async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    updateSlidersUI(data.headphone_volume, data.game_mic_volume, data.mute_game_mic);
    if (data.pending_chat) {
      showChatDraft(data.pending_chat.draft_id, data.pending_chat.content, data.pending_chat.channel);
    }
    if (data.voice_name) {
      voiceSelect.value = data.voice_name;
    }
    if (data.teammate_voice_trigger !== undefined) {
      updateTeammateTriggerUI(data.teammate_voice_trigger);
    }
    if (data.screen_fps) {
      updateFpsActiveBtn(data.screen_fps);
    }
    if (data.overlay_mode && overlayModeSelect) {
      overlayModeSelect.value = data.overlay_mode;
    }
  } catch (e) {}
}

// 3. Fetch Diagnostics
async function fetchDiagnostics() {
  try {
    const res = await fetch("/api/diagnostics");
    const d = await res.json();
    const score = d.health_score !== undefined ? d.health_score : 100;
    healthText.textContent = `${score}% ${d.status || 'OK'}`;
    
    if (d.subsystems) {
      if (d.subsystems.screen) {
        diagFps.textContent = `${d.subsystems.screen.fps || 2} FPS`;
      }
      if (d.subsystems.game) {
        diagGame.textContent = d.subsystems.game.valorant_running ? `IN-GAME (#${d.subsystems.game.pid})` : "Chờ mở...";
      }
      if (d.subsystems.audio) {
        diagMic.textContent = d.subsystems.audio.running ? "Hoạt động" : "Dừng";
      }
      if (d.subsystems.tunnel && d.subsystems.tunnel.url) {
        if (remoteLinkInput) remoteLinkInput.value = d.subsystems.tunnel.url;
      }
    }
  } catch (e) {}
}

// 4. Update Audio Sliders UI
function updateSlidersUI(hp, mic, muted) {
  if (hp !== undefined) {
    const pctHp = Math.round(hp * 100);
    hpSlider.value = pctHp;
    hpVal.textContent = `${pctHp}%`;
  }
  if (mic !== undefined) {
    const pctMic = Math.round(mic * 100);
    micSlider.value = pctMic;
    micVal.textContent = `${pctMic}%`;
  }
  if (muted !== undefined) {
    if (muted) {
      btnMute.classList.add("active");
      muteLabel.textContent = "UNMUTE GIỌNG AI VÀO GAME";
    } else {
      btnMute.classList.remove("active");
      muteLabel.textContent = "MUTE GIỌNG AI VÀO GAME (YÊN TÂM CLUTCH)";
    }
  }
}

// Sliders Event Handlers
hpSlider.addEventListener("input", (e) => {
  const val = e.target.value;
  hpVal.textContent = `${val}%`;
  postVolume({ headphone: val / 100.0 });
});

micSlider.addEventListener("input", (e) => {
  const val = e.target.value;
  micVal.textContent = `${val}%`;
  postVolume({ game_mic: val / 100.0 });
});

btnMute.addEventListener("click", () => {
  const isMuted = btnMute.classList.contains("active");
  postVolume({ mute_game_mic: !isMuted });
});

async function postVolume(payload) {
  try {
    await fetch("/api/volume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (e) {}
}

// 5. Subtitle Stream Feed
function appendSubtitleFeed(orig, trans) {
  if (!orig && !trans) return;
  if (feedEmpty) feedEmpty.style.display = "none";

  const item = document.createElement("div");
  item.className = "sub-item";
  item.innerHTML = `
    <div class="sub-orig">🗣️ "${escapeHtml(orig)}"</div>
    <div class="sub-trans">👉 "${escapeHtml(trans)}"</div>
  `;
  subFeed.appendChild(item);
  subFeed.scrollTop = subFeed.scrollHeight;

  // Limit feed to last 15 items
  while (subFeed.children.length > 16) {
    if (subFeed.children[1] !== feedEmpty) {
      subFeed.removeChild(subFeed.children[1]);
    } else {
      break;
    }
  }
}

// 6. Permission-Gated Chat Approval
function showChatDraft(draftId, content, channel) {
  currentDraftId = draftId;
  draftText.textContent = `"${content}"`;
  draftIdLabel.textContent = `ID: #${draftId}`;
  draftChannel.textContent = (channel || "TEAM").toUpperCase() + " CHAT";
  chatDraftBox.style.display = "block";
  noChatMsg.style.display = "none";
}

function hideChatDraft() {
  currentDraftId = null;
  chatDraftBox.style.display = "none";
  noChatMsg.style.display = "flex";
}

btnApproveChat.addEventListener("click", () => {
  if (!currentDraftId) return;
  sendChatAction("approve", currentDraftId);
  hideChatDraft();
});

btnRejectChat.addEventListener("click", () => {
  if (!currentDraftId) return;
  sendChatAction("reject", currentDraftId);
  hideChatDraft();
});

async function sendChatAction(action, draftId) {
  try {
    await fetch("/api/chat/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, draft_id: draftId })
    });
  } catch (e) {}
}

// 7. Tactical Quick Callouts
document.querySelectorAll(".callout-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    const text = pill.getAttribute("data-text");
    sendTacticalCallout(text);
  });
});

const customCalloutInput = document.getElementById("custom-callout-text");
const btnSendCustomCallout = document.getElementById("btn-send-custom-callout");

if (btnSendCustomCallout) {
  btnSendCustomCallout.addEventListener("click", () => {
    const text = customCalloutInput.value.trim();
    if (text) {
      sendTacticalCallout(text);
      customCalloutInput.value = "";
    }
  });
}

async function sendTacticalCallout(text) {
  try {
    await fetch("/api/callout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, channel: "team" })
    });
    alert(`📢 Đã gửi callout vào game: "${text}"`);
  } catch (e) {
    alert("Không thể gửi callout: " + e);
  }
}

// 8. Self-Healing Button
btnAutoFix.addEventListener("click", async () => {
  btnAutoFix.disabled = true;
  btnAutoFix.innerHTML = '<span class="icon">⏳</span> ĐANG TỰ SỬA LỖI...';
  try {
    const res = await fetch("/api/auto-fix", { method: "POST" });
    const data = await res.json();
    alert(`✅ TỰ SỬA LỖI HOÀN TẤT!\nĐiểm sức khỏe: ${data.health_after_fix}/100\nCác hành động:\n` + (data.actions_taken || []).map(a => `- ${a}`).join("\n"));
    fetchDiagnostics();
  } catch (e) {
    alert("Lỗi khi tự sửa: " + e);
  } finally {
    btnAutoFix.disabled = false;
    btnAutoFix.innerHTML = '<span class="icon">🔧</span> TỰ SỬA LỖI (SELF-HEAL)';
  }
});

// 9. Vision & Voice Settings
fpsBtns.forEach(btn => {
  btn.addEventListener("click", async () => {
    const fps = parseInt(btn.getAttribute("data-fps"));
    try {
      await fetch("/api/screen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fps })
      });
      updateFpsActiveBtn(fps);
    } catch (e) {}
  });
});

function updateFpsActiveBtn(fps) {
  fpsBtns.forEach(btn => {
    if (parseInt(btn.getAttribute("data-fps")) === fps) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
}

btnTeammateTrigger.addEventListener("click", async () => {
  const currentActive = btnTeammateTrigger.classList.contains("active");
  const nextVal = !currentActive;
  try {
    await fetch("/api/teammate-trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: nextVal })
    });
    updateTeammateTriggerUI(nextVal);
  } catch (e) {}
});

function updateTeammateTriggerUI(enabled) {
  if (enabled) {
    btnTeammateTrigger.classList.add("active");
    teammateTriggerLabel.textContent = "BẬT (ĐỒNG ĐỘI ĐƯỢC GỌI AI)";
  } else {
    btnTeammateTrigger.classList.remove("active");
    teammateTriggerLabel.textContent = "TẮT (CHỈ BẠN ĐƯỢC GỌI AI)";
  }
}

voiceSelect.addEventListener("change", async (e) => {
  try {
    await fetch("/api/voice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice_name: e.target.value })
    });
  } catch (e) {}
});

if (overlayModeSelect) {
  overlayModeSelect.addEventListener("change", async (e) => {
    try {
      await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates: { "overlay.mode": e.target.value } })
      });
      alert(`Đã đổi kiểu Overlay sang: ${e.target.options[e.target.selectedIndex].text}`);
    } catch (e) {}
  });
}

// 10. Copy Remote Link
if (btnCopyLink && remoteLinkInput) {
  btnCopyLink.addEventListener("click", () => {
    remoteLinkInput.select();
    navigator.clipboard.writeText(remoteLinkInput.value).then(() => {
      btnCopyLink.textContent = "COPIED! ✔";
      setTimeout(() => { btnCopyLink.textContent = "COPY LINK"; }, 2000);
    });
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.innerText = text;
  return div.innerHTML;
}

// 11. Navigation Tabs Filtering
const navTabs = document.querySelectorAll(".nav-tab");
const sectionCards = document.querySelectorAll(".main-grid .pane");

navTabs.forEach(tab => {
  tab.addEventListener("click", () => {
    const target = tab.getAttribute("data-target");
    navTabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");

    sectionCards.forEach(card => {
      if (target === "all" || card.getAttribute("data-section") === target) {
        card.style.display = "flex";
      } else {
        card.style.display = "none";
      }
    });
  });
});

// Initialize on Load
document.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
});
