// Valorant Voice AI - LAN Dashboard Client

let ws = null;
let currentDraftId = null;

// Elements
const connPill = document.getElementById("conn-pill");
const hpSlider = document.getElementById("hp-slider");
const hpVal = document.getElementById("hp-val");
const micSlider = document.getElementById("mic-slider");
const micVal = document.getElementById("mic-val");
const btnMute = document.getElementById("btn-mute");
const muteLabel = document.getElementById("mute-label");

const chatDraftBox = document.getElementById("chat-draft-box");
const noChatMsg = document.getElementById("no-chat-msg");
const draftText = document.getElementById("draft-text");
const btnApproveChat = document.getElementById("btn-approve-chat");
const btnRejectChat = document.getElementById("btn-reject-chat");

const voiceSelect = document.getElementById("voice-select");
const fpsBtns = document.querySelectorAll(".fps-btn");

// Connect WebSocket
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

  ws.onopen = () => {
    connPill.textContent = "CONNECTED (LAN)";
    connPill.className = "pill pill-online";
    fetchStatus();
  };

  ws.onclose = () => {
    connPill.textContent = "DISCONNECTED";
    connPill.className = "pill pill-offline";
    setTimeout(initWebSocket, 2000);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "volume_update") {
        updateSlidersUI(data.headphone, data.game_mic, data.mute_game_mic);
      } else if (data.type === "chat_draft") {
        showChatDraft(data.draft_id, data.content);
      }
    } catch (e) {}
  };
}

// Fetch Initial Status
async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    updateSlidersUI(data.headphone_volume, data.game_mic_volume, data.mute_game_mic);
    if (data.pending_chat) {
      showChatDraft(data.pending_chat.draft_id, data.pending_chat.content);
    }
    if (data.voice_name) {
      voiceSelect.value = data.voice_name;
    }
  } catch (e) {}
}

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
      muteLabel.textContent = "MUTE GIỌNG AI VÀO GAME";
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
  const isCurrentlyMuted = btnMute.classList.contains("active");
  postVolume({ mute_game_mic: !isCurrentlyMuted });
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

// FPS Selector
fpsBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    fpsBtns.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const fps = parseInt(btn.dataset.fps);
    fetch("/api/screen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fps })
    });
  });
});

// Voice Select
voiceSelect.addEventListener("change", (e) => {
  fetch("/api/voice", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ voice_name: e.target.value })
  });
});

// Chat Draft Approval
function showChatDraft(draftId, content) {
  currentDraftId = draftId;
  draftText.textContent = `"${content}"`;
  chatDraftBox.style.display = "block";
  noChatMsg.style.display = "none";
}

function hideChatDraft() {
  currentDraftId = null;
  chatDraftBox.style.display = "none";
  noChatMsg.style.display = "block";
}

btnApproveChat.addEventListener("click", async () => {
  if (!currentDraftId) return;
  await fetch("/api/chat/action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draft_id: currentDraftId, action: "approve" })
  });
  hideChatDraft();
});

btnRejectChat.addEventListener("click", async () => {
  if (!currentDraftId) return;
  await fetch("/api/chat/action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draft_id: currentDraftId, action: "reject" })
  });
  hideChatDraft();
});

// Start WebSocket on Load
window.addEventListener("DOMContentLoaded", initWebSocket);
