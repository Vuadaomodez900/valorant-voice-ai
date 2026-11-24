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
      } else if (data.type === "lipsync") {
        updateAvatarLipsync(data.data);
      } else if (data.type === "ai_reply") {
        if (avatarSpeechText) avatarSpeechText.textContent = `"${data.response}"`;
      } else if (data.type === "neuro_commentary") {
        if (avatarSpeechText) avatarSpeechText.textContent = `"${data.text}"`;
        appendSubtitleFeed("[Minecraft Neuro]", data.text);
      } else if (data.type === "neuro_chat_reply") {
        if (avatarSpeechText) avatarSpeechText.textContent = `"${data.reply}"`;
        appendSubtitleFeed("[Neuro-sama]", data.reply);
      } else if (data.type === "profile_changed") {
        updateActiveProfilePill(data.id);
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

// 12. Sakura Live2D / SVG Avatar Lip-Sync & Emotion
const mouthPath = document.getElementById("avatar-mouth-path");
const eyesGroup = document.getElementById("avatar-eyes");
const eyesClosedGroup = document.getElementById("avatar-eyes-closed");
const avatarStatusPill = document.getElementById("avatar-status-pill");
const avatarSpeechText = document.getElementById("avatar-speech-text");
const fastAiPrompt = document.getElementById("fast-ai-prompt");
const btnFastAiSend = document.getElementById("btn-fast-ai-send");
const aiProviderSelect = document.getElementById("ai-provider-select");

function updateAvatarLipsync(state) {
  if (!state) return;
  const mouthOpen = state.mouth_open || 0.0;
  const blink = state.blink || false;
  const emotion = state.emotion || "neutral";

  // Blinking
  if (eyesGroup && eyesClosedGroup) {
    if (blink) {
      eyesGroup.style.display = "none";
      eyesClosedGroup.style.display = "block";
    } else {
      eyesGroup.style.display = "block";
      eyesClosedGroup.style.display = "none";
    }
  }

  // Mouth morphing
  if (mouthPath) {
    if (mouthOpen > 0.45) {
      // Wide open (A, O)
      const h = 140 + Math.round(mouthOpen * 14);
      mouthPath.setAttribute("d", `M 90 138 Q 100 ${h} 110 138 Z`);
    } else if (mouthOpen > 0.15) {
      // Partial open (E, I, U)
      const h = 140 + Math.round(mouthOpen * 8);
      mouthPath.setAttribute("d", `M 92 139 Q 100 ${h} 108 139`);
    } else {
      // Closed smile
      mouthPath.setAttribute("d", "M 93 140 Q 100 144 107 140");
    }
  }

  // Emotion status badge
  if (avatarStatusPill) {
    if (emotion === "speaking") {
      avatarStatusPill.textContent = "💬 ĐANG NÓI";
      avatarStatusPill.className = "pane-tag tag-sakura";
    } else if (emotion === "listening") {
      avatarStatusPill.textContent = "👂 ĐANG NGHE";
      avatarStatusPill.className = "pane-tag tag-blue";
    } else if (emotion === "alert") {
      avatarStatusPill.textContent = "🚨 BÁO ĐỘNG";
      avatarStatusPill.className = "pane-tag tag-red";
    } else {
      avatarStatusPill.textContent = "🌸 SẴN SÀNG";
      avatarStatusPill.className = "pane-tag tag-green";
    }
  }
}

// Fast AI Chat
if (btnFastAiSend && fastAiPrompt) {
  btnFastAiSend.addEventListener("click", async () => {
    const text = fastAiPrompt.value.trim();
    if (!text) return;
    fastAiPrompt.value = "";
    if (avatarSpeechText) avatarSpeechText.textContent = "Đang phân tích chiến thuật (<15ms)...";
    try {
      const res = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text })
      });
      const data = await res.json();
      if (avatarSpeechText && data.response) {
        avatarSpeechText.textContent = `"${data.response}"`;
      }
    } catch (e) {
      if (avatarSpeechText) avatarSpeechText.textContent = "Lỗi kết nối: " + e;
    }
  });

  fastAiPrompt.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnFastAiSend.click();
  });
}

// AI Provider Selector
if (aiProviderSelect) {
  fetch("/api/ai/provider")
    .then(r => r.json())
    .then(data => {
      if (data.provider) aiProviderSelect.value = data.provider;
    })
    .catch(() => {});

  aiProviderSelect.addEventListener("change", async (e) => {
    const provider = e.target.value;
    try {
      await fetch("/api/ai/provider", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider })
      });
      alert(`Đã chuyển đổi AI Backend sang: ${e.target.options[e.target.selectedIndex].text}`);
    } catch (err) {}
  });
}

// ========================================================
// GAME PROFILE & MINECRAFT NEURO-SAMA COPILOT LOGIC
// ========================================================

const mcPane = document.getElementById("minecraft-copilot-pane");
let mcPollInterval = null;

function updateActiveProfilePill(profileId) {
  const pills = document.querySelectorAll(".profile-pill");
  pills.forEach(p => {
    if (p.getAttribute("data-profile") === profileId) {
      p.classList.add("active");
    } else {
      p.classList.remove("active");
    }
  });

  if (profileId === "minecraft") {
    if (mcPane) mcPane.style.display = "block";
    startMinecraftPolling();
  } else {
    if (mcPane) mcPane.style.display = "none";
    stopMinecraftPolling();
  }
}

async function switchGameProfile(profileId) {
  try {
    const res = await fetch("/api/game/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId })
    });
    const data = await res.json();
    if (data.status === "ok") {
      updateActiveProfilePill(profileId);
    }
  } catch (e) {
    console.error("Failed to switch game profile:", e);
  }
}

// Setup Game Profile Click Listeners
document.querySelectorAll(".profile-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    const pid = pill.getAttribute("data-profile");
    switchGameProfile(pid);
  });
});

// Setup Minecraft Actions
async function sendMcAction(action, params = {}) {
  try {
    const res = await fetch("/api/minecraft/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, params })
    });
    return await res.json();
  } catch (e) {
    console.error("MC action failed:", e);
  }
}

const btnMcAutopilot = document.getElementById("btn-mc-autopilot");
let mcAutopilotState = false;
if (btnMcAutopilot) {
  btnMcAutopilot.addEventListener("click", async () => {
    mcAutopilotState = !mcAutopilotState;
    await sendMcAction("autopilot", { enable: mcAutopilotState });
    btnMcAutopilot.textContent = mcAutopilotState ? "⏹️ Dừng AutoPilot" : "🏃 AutoPilot Roam";
  });
}

const btnMcJump = document.getElementById("btn-mc-jump");
if (btnMcJump) btnMcJump.addEventListener("click", () => sendMcAction("jump"));

const btnMcEat = document.getElementById("btn-mc-eat");
if (btnMcEat) btnMcEat.addEventListener("click", () => sendMcAction("eat"));

const btnMcShield = document.getElementById("btn-mc-shield");
if (btnMcShield) btnMcShield.addEventListener("click", () => sendMcAction("use_shield", { duration: 2.0 }));

const btnMcMine = document.getElementById("btn-mc-mine");
if (btnMcMine) btnMcMine.addEventListener("click", () => sendMcAction("attack", { duration: 1.5 }));

const btnMcBeacon = document.getElementById("btn-mc-beacon");
if (btnMcBeacon) {
  btnMcBeacon.addEventListener("click", async () => {
    await fetch("/api/minecraft/particle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ beacon: true, trail: true, aura: "soul_flame" })
    });
    alert("✨ Đã kích hoạt cột sáng chỉ điểm quặng quý (Ore Beacon) & Hào quang!");
  });
}

// Minecraft Copilot Toggles
const checkMcAuto = document.getElementById("mc-check-autonomous");
const checkMcShield = document.getElementById("mc-check-autoshield");
const checkMcEat = document.getElementById("mc-check-autoeat");
const checkMcReactive = document.getElementById("mc-check-reactive");

async function updateMcCopilotSettings() {
  await fetch("/api/minecraft/copilot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      autonomous: checkMcAuto ? checkMcAuto.checked : true,
      auto_shield: checkMcShield ? checkMcShield.checked : true,
      auto_eat: checkMcEat ? checkMcEat.checked : true,
      reactive_voice: checkMcReactive ? checkMcReactive.checked : true,
    })
  });
}

[checkMcAuto, checkMcShield, checkMcEat, checkMcReactive].forEach(chk => {
  if (chk) chk.addEventListener("change", updateMcCopilotSettings);
});

// Neuro-sama Chat
const mcNeuroInput = document.getElementById("mc-neuro-input");
const btnMcSendChat = document.getElementById("btn-mc-send-chat");

async function handleNeuroChat() {
  if (!mcNeuroInput) return;
  const prompt = mcNeuroInput.value.trim();
  if (!prompt) return;
  mcNeuroInput.value = "";
  if (avatarSpeechText) avatarSpeechText.textContent = "Neuro-sama đang suy nghĩ...";
  try {
    const res = await fetch("/api/minecraft/neuro_chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt })
    });
    const data = await res.json();
    if (avatarSpeechText && data.reply) {
      avatarSpeechText.textContent = `"${data.reply}"`;
    }
  } catch (e) {
    if (avatarSpeechText) avatarSpeechText.textContent = "Lỗi kết nối Neuro: " + e;
  }
}

if (btnMcSendChat) btnMcSendChat.addEventListener("click", handleNeuroChat);
if (mcNeuroInput) {
  mcNeuroInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleNeuroChat();
  });
}

// Telemetry Poller
async function fetchMinecraftState() {
  try {
    const res = await fetch("/api/minecraft/state");
    const data = await res.json();
    const st = data.state || {};
    const player = st.player || {};
    const danger = st.danger || {};
    const radar = st.radar || {};
    const target = st.target || {};

    const pill = document.getElementById("mc-status-pill");
    if (pill) {
      if (data.connected && data.in_game) {
        pill.textContent = `🟢 TRONG GAME (${player.name || 'Player'})`;
        pill.className = "pane-tag tag-green";
      } else if (data.connected) {
        pill.textContent = "🟡 ONLINE (CHỜ VÀO GAME)";
        pill.className = "pane-tag tag-yellow";
      } else {
        pill.textContent = "📡 DÒ MOD (PORT 28888)";
        pill.className = "pane-tag tag-blue";
      }
    }

    const hpEl = document.getElementById("mc-hp-val");
    if (hpEl) {
      const hp = player.health !== undefined ? player.health : 20;
      hpEl.textContent = `${hp} / ${player.max_health || 20}`;
      hpEl.className = hp <= 6 ? "mc-stat-val text-red" : (hp <= 12 ? "mc-stat-val text-yellow" : "mc-stat-val text-green");
    }

    const foodEl = document.getElementById("mc-food-val");
    if (foodEl) foodEl.textContent = `${player.food_level !== undefined ? player.food_level : 20} / 20`;

    const coordsEl = document.getElementById("mc-coords-val");
    if (coordsEl && player.x !== undefined) {
      coordsEl.textContent = `X: ${player.x.toFixed(1)} | Y: ${player.y.toFixed(1)} | Z: ${player.z.toFixed(1)}`;
    }

    const dangerEl = document.getElementById("mc-danger-val");
    if (dangerEl) {
      const lvl = danger.level || "SAFE";
      if (lvl === "CRITICAL") {
        dangerEl.textContent = "🔴 NGUY CƠ CAO!";
        dangerEl.className = "mc-stat-val text-red";
      } else if (lvl === "WARNING") {
        dangerEl.textContent = "🟡 CẢNH BÁO";
        dangerEl.className = "mc-stat-val text-yellow";
      } else {
        dangerEl.textContent = "🟢 AN TOÀN";
        dangerEl.className = "mc-stat-val text-green";
      }
    }

    const hostCountEl = document.getElementById("mc-hostiles-count");
    if (hostCountEl) hostCountEl.textContent = radar.hostile_count || 0;

    const targetEl = document.getElementById("mc-target-looking");
    if (targetEl) {
      if (target.type === "BLOCK") {
        targetEl.textContent = `👁️ Khối: ${target.block ? target.block.id : 'None'}`;
      } else if (target.type === "ENTITY") {
        targetEl.textContent = `👁️ Thực thể: ${target.entity ? target.entity.name : 'None'}`;
      } else {
        targetEl.textContent = "👁️ Không có mục tiêu";
      }
    }

    const hostListEl = document.getElementById("mc-hostiles-list");
    if (hostListEl) {
      const hostiles = radar.hostiles || [];
      if (hostiles.length === 0) {
        hostListEl.innerHTML = '<span class="radar-tag">Không có quái vật</span>';
      } else {
        hostListEl.innerHTML = hostiles.slice(0, 5).map(h => 
          `<span class="radar-tag">👾 ${h.name} (${h.distance}m)</span>`
        ).join("");
      }
    }
  } catch (e) {}
}

function startMinecraftPolling() {
  if (mcPollInterval) return;
  fetchMinecraftState();
  mcPollInterval = setInterval(fetchMinecraftState, 1500);
}

function stopMinecraftPolling() {
  if (mcPollInterval) {
    clearInterval(mcPollInterval);
    mcPollInterval = null;
  }
}

// Fetch active profile on load
fetch("/api/game/profiles")
  .then(r => r.json())
  .then(data => {
    if (data.active_profile) {
      updateActiveProfilePill(data.active_profile.id);
    }
  })
  .catch(() => {});

// ========================================================
// USER AUTH & SECURITY STATUS
// ========================================================

const userProfileBox = document.getElementById("user-profile-box");
const loginButtonsBox = document.getElementById("login-buttons-box");
const userAvatarImg = document.getElementById("user-avatar-img");
const userDisplayName = document.getElementById("user-display-name");
const userProviderBadge = document.getElementById("user-provider-badge");
const btnAuthLogout = document.getElementById("btn-auth-logout");

async function fetchUserProfile() {
  try {
    const res = await fetch("/api/auth/me");
    const data = await res.json();
    if (data.authenticated && data.user) {
      if (userProfileBox) userProfileBox.style.display = "flex";
      if (loginButtonsBox) loginButtonsBox.style.display = "none";
      if (userDisplayName) userDisplayName.textContent = data.user.display_name || data.user.username;
      if (userProviderBadge) userProviderBadge.textContent = data.user.provider.toUpperCase();
      if (userAvatarImg) {
        userAvatarImg.src = data.user.avatar_url || "https://cdn.discordapp.com/embed/avatars/0.png";
      }
    } else {
      if (userProfileBox) userProfileBox.style.display = "none";
      if (loginButtonsBox) loginButtonsBox.style.display = "flex";
    }
  } catch (e) {
    if (loginButtonsBox) loginButtonsBox.style.display = "flex";
  }
}

if (btnAuthLogout) {
  btnAuthLogout.addEventListener("click", async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      fetchUserProfile();
    } catch (e) {}
  });
}

async function fetchSecurityStatus() {
  try {
    const res = await fetch("/api/security/status");
    const data = await res.json();
    const secAntiDebug = document.getElementById("sec-anti-debug");
    if (secAntiDebug) {
      if (data.debugger_detected) {
        secAntiDebug.innerHTML = "🚨 Debugger: <strong>Detected!</strong>";
        secAntiDebug.style.color = "#f87171";
      } else {
        secAntiDebug.innerHTML = "🛡️ Anti-Debugger: <strong>Active</strong>";
        secAntiDebug.style.color = "#4ade80";
      }
    }
  } catch (e) {}
}

// Initialize on Load
document.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
  fetchUserProfile();
  fetchSecurityStatus();
});
