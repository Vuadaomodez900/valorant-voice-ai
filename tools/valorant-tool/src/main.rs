use std::env;
use std::fs;
use std::io::{self, BufRead, Write};
use std::path::PathBuf;
use std::time::Duration;
use serde_json::{json, Value};

const DEFAULT_PORT: u16 = 8000;

fn get_config_path() -> PathBuf {
    let home = env::var("HOME").unwrap_or_else(|_| "/data/data/com.termux/files/home".to_string());
    PathBuf::from(home).join(".gemini").join("config").join("valorant_pc.json")
}

fn get_configured_host() -> String {
    if let Ok(env_ip) = env::var("VALORANT_PC_IP") {
        if !env_ip.trim().is_empty() {
            return env_ip.trim().to_string();
        }
    }
    let path = get_config_path();
    if path.exists() {
        if let Ok(content) = fs::read_to_string(&path) {
            if let Ok(val) = serde_json::from_str::<Value>(&content) {
                if let Some(host) = val.get("host").and_then(|h| h.as_str()) {
                    return host.trim().to_string();
                }
            }
        }
    }
    "127.0.0.1".to_string()
}

fn get_configured_token() -> Option<String> {
    let path = get_config_path();
    if path.exists() {
        if let Ok(content) = fs::read_to_string(&path) {
            if let Ok(val) = serde_json::from_str::<Value>(&content) {
                if let Some(tok) = val.get("token").and_then(|t| t.as_str()) {
                    if !tok.trim().is_empty() {
                        return Some(tok.trim().to_string());
                    }
                }
            }
        }
    }
    None
}

fn save_configured_token(token: &str) -> io::Result<()> {
    let path = get_config_path();
    let mut data = if path.exists() {
        fs::read_to_string(&path)
            .ok()
            .and_then(|c| serde_json::from_str::<Value>(&c).ok())
            .unwrap_or_else(|| json!({}))
    } else {
        json!({})
    };
    if let Some(obj) = data.as_object_mut() {
        obj.insert("token".to_string(), json!(token.trim()));
    }
    fs::write(&path, serde_json::to_string_pretty(&data)?)
}

fn save_configured_host(host: &str) -> io::Result<()> {
    let path = get_config_path();
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let mut data = if path.exists() {
        fs::read_to_string(&path)
            .ok()
            .and_then(|c| serde_json::from_str::<Value>(&c).ok())
            .unwrap_or_else(|| json!({}))
    } else {
        json!({})
    };
    if let Some(obj) = data.as_object_mut() {
        obj.insert("host".to_string(), json!(host.trim()));
        obj.insert("port".to_string(), json!(DEFAULT_PORT));
    }
    fs::write(&path, serde_json::to_string_pretty(&data)?)
}

fn resolve_base_url(host: &str) -> String {
    let target = if host.trim().is_empty() {
        get_configured_host()
    } else {
        host.trim().to_string()
    };

    if target.starts_with("http://") || target.starts_with("https://") {
        target.trim_end_matches('/').to_string()
    } else if target.contains(':') {
        format!("http://{}", target)
    } else {
        format!("http://{}:{}", target, DEFAULT_PORT)
    }
}

fn http_get(url: &str) -> Result<Value, String> {
    let agent = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(3)))
        .build()
        .new_agent();

    let mut req = agent.get(url);
    if let Some(token) = get_configured_token() {
        req = req.header("Authorization", &format!("Bearer {}", token));
    }

    let mut response = req
        .call()
        .map_err(|e| format!("HTTP GET error ({}): {}", url, e))?;

    let body_str = response.body_mut().read_to_string()
        .map_err(|e| format!("Read body error: {}", e))?;

    serde_json::from_str::<Value>(&body_str)
        .map_err(|e| format!("JSON parse error: {} (raw: {})", e, body_str))
}

fn http_post(url: &str, payload: &Value) -> Result<Value, String> {
    let agent = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(4)))
        .build()
        .new_agent();

    let body_bytes = serde_json::to_vec(payload)
        .map_err(|e| format!("JSON serialize error: {}", e))?;

    let mut req = agent.post(url).header("Content-Type", "application/json");
    if let Some(token) = get_configured_token() {
        req = req.header("Authorization", &format!("Bearer {}", token));
    }

    let mut response = req
        .send(&body_bytes)
        .map_err(|e| format!("HTTP POST error ({}): {}", url, e))?;

    let body_str = response.body_mut().read_to_string()
        .map_err(|e| format!("Read body error: {}", e))?;

    serde_json::from_str::<Value>(&body_str)
        .map_err(|e| format!("JSON parse error: {} (raw: {})", e, body_str))
}

// ----------------- Command Handlers -----------------

fn cmd_status(host: &str) {
    let base = resolve_base_url(host);
    let url = format!("{}/api/status", base);
    println!("Connecting to {}...", url);

    match http_get(&url) {
        Ok(data) => {
            let hp = (data.get("headphone_volume").and_then(|v| v.as_f64()).unwrap_or(1.0) * 100.0) as i32;
            let mic = (data.get("game_mic_volume").and_then(|v| v.as_f64()).unwrap_or(1.0) * 100.0) as i32;
            let muted = data.get("mute_game_mic").and_then(|v| v.as_bool()).unwrap_or(false);
            let cable = data.get("has_virtual_cable").and_then(|v| v.as_bool()).unwrap_or(false);
            let gemini = data.get("gemini_connected").and_then(|v| v.as_bool()).unwrap_or(false);
            let tm = data.get("teammate_voice_trigger").and_then(|v| v.as_bool()).unwrap_or(true);
            let fps = data.get("screen_fps").and_then(|v| v.as_i64()).unwrap_or(2);

            println!("============================================================");
            println!("  VALORANT VOICE AI (RUST NATIVE CLIENT)");
            println!("  Target: {}", base);
            println!("============================================================");
            println!("  - Âm lượng Tai nghe: {}%", hp);
            println!("  - Âm lượng Mic Game: {}% [{}]", mic, if muted { "🔇 MUTED" } else { "🔊 ACTIVE" });
            println!("  - Live Screen Stream: {} FPS", fps);
            println!("  - Đồng đội gọi AI:   {}", if tm { "BẬT" } else { "TẮT" });
            println!("  - Driver VB-Cable:   {}", if cable { "✅ ĐÃ CÀI ĐẶT" } else { "❌ CHƯA CÓ" });
            println!("  - Gemini Live API:   {}", if gemini { "✅ CONNECTED" } else { "⚠️ WAITING/OFFLINE" });

            if let Some(draft) = data.get("pending_chat").filter(|d| !d.is_null()) {
                println!("\n  ⚠️ CÓ BẢN NHÁP CHAT CHỜ DUYỆT:");
                println!("     ID: [{}] -> \"{}\"", 
                    draft.get("draft_id").and_then(|v| v.as_str()).unwrap_or(""),
                    draft.get("content").and_then(|v| v.as_str()).unwrap_or("")
                );
            }
        }
        Err(e) => {
            eprintln!("❌ {}", e);
            eprintln!("💡 Mẹo: Chạy 'valorant-tool scan' để quét tìm IP PC.");
        }
    }
}

fn cmd_mute(host: &str, mute: bool) {
    let base = resolve_base_url(host);
    let url = format!("{}/api/volume", base);
    let payload = json!({ "mute_game_mic": mute });
    match http_post(&url, &payload) {
        Ok(_) => {
            if mute {
                println!("🔇 Đã MUTE giọng AI phát vào Mic game (yên tâm clutch)!");
            } else {
                println!("🔊 Đã MỞ LẠI giọng AI phát vào Mic game!");
            }
        }
        Err(e) => eprintln!("❌ {}", e),
    }
}

fn cmd_volume(host: &str, hp: Option<f64>, mic: Option<f64>) {
    let base = resolve_base_url(host);
    let url = format!("{}/api/volume", base);
    let mut payload = serde_json::Map::new();
    if let Some(h) = hp {
        payload.insert("headphone".to_string(), json!(h));
    }
    if let Some(m) = mic {
        payload.insert("game_mic".to_string(), json!(m));
    }
    match http_post(&url, &Value::Object(payload)) {
        Ok(_) => println!("✅ Đã cập nhật âm lượng thành công!"),
        Err(e) => eprintln!("❌ {}", e),
    }
}

fn cmd_chat_action(host: &str, action: &str, draft_id: Option<&str>) {
    let base = resolve_base_url(host);
    let target_id = if let Some(id) = draft_id {
        id.to_string()
    } else {
        // Fetch current draft
        let status_url = format!("{}/api/status", base);
        match http_get(&status_url) {
            Ok(data) => {
                if let Some(draft) = data.get("pending_chat").filter(|d| !d.is_null()) {
                    draft.get("draft_id").and_then(|v| v.as_str()).unwrap_or("").to_string()
                } else {
                    println!("ℹ️ Không có bản nháp tin nhắn nào đang chờ duyệt.");
                    return;
                }
            }
            Err(e) => {
                eprintln!("❌ {}", e);
                return;
            }
        }
    };

    let url = format!("{}/api/chat/action", base);
    let payload = json!({ "draft_id": target_id, "action": action });
    match http_post(&url, &payload) {
        Ok(_) => {
            if action == "approve" {
                println!("✅ ĐÃ DUYỆT GỬI TIN NHẮN [{}] VÀO TRẬN ĐẤU VALORANT!", target_id);
            } else {
                println!("🗑️ Đã từ chối / hủy bỏ bản nháp [{}].", target_id);
            }
        }
        Err(e) => eprintln!("❌ {}", e),
    }
}

fn cmd_callout(host: &str, text: &str) {
    let base = resolve_base_url(host);
    let url = format!("{}/api/callout", base);
    let payload = json!({ "text": text, "channel": "team" });
    match http_post(&url, &payload) {
        Ok(res) => {
            let id = res.get("draft_id").and_then(|v| v.as_str()).unwrap_or("");
            println!("📢 Đã gửi callout vào game: \"{}\" (Draft ID: {})", text, id);
        }
        Err(e) => eprintln!("❌ {}", e),
    }
}

fn cmd_diagnostics(host: &str) {
    let base = resolve_base_url(host);
    let url = format!("{}/api/diagnostics", base);
    match http_get(&url) {
        Ok(d) => {
            let score = d.get("health_score").and_then(|v| v.as_i64()).unwrap_or(100);
            let status = d.get("status").and_then(|v| v.as_str()).unwrap_or("OK");
            println!("============================================================");
            println!("  VALORANT VOICE AI - BÁO CÁO CHẨN ĐOÁN HỆ THỐNG");
            println!("============================================================");
            println!("Điểm sức khỏe: {}/100 [{}]", score, status);

            if let Some(sub) = d.get("subsystems") {
                let cable = sub.get("driver").and_then(|d| d.get("vbcable_installed")).and_then(|v| v.as_bool()).unwrap_or(false);
                let audio = sub.get("audio").and_then(|a| a.get("running")).and_then(|v| v.as_bool()).unwrap_or(false);
                let screen = sub.get("screen").and_then(|s| s.get("fps")).and_then(|v| v.as_i64()).unwrap_or(2);
                let gemini = sub.get("gemini").and_then(|g| g.get("connected")).and_then(|v| v.as_bool()).unwrap_or(false);
                let tunnel_url = sub.get("tunnel").and_then(|t| t.get("url")).and_then(|v| v.as_str()).unwrap_or("CHƯA BẬT");

                println!("  - Virtual Cable:    {}", if cable { "✅ ĐÃ CÀI ĐẶT" } else { "❌ CHƯA CÓ" });
                println!("  - Audio Streams:    {}", if audio { "✅ HOẠT ĐỘNG" } else { "❌ DỪNG" });
                println!("  - Screen Capture:   {} FPS", screen);
                println!("  - Gemini Live API:  {}", if gemini { "✅ CONNECTED" } else { "⚠️ CHỜ/OFFLINE" });
                println!("  - Internet Tunnel:  🌐 {}", tunnel_url);
            }

            if let Some(issues) = d.get("issues").and_then(|v| v.as_array()) {
                if !issues.is_empty() {
                    println!("\n🚨 Vấn đề phát hiện:");
                    for iss in issues {
                        if let Some(txt) = iss.as_str() {
                            println!("  - ❌ {}", txt);
                        }
                    }
                }
            }
        }
        Err(e) => eprintln!("❌ {}", e),
    }
}

fn cmd_auto_fix(host: &str) {
    let base = resolve_base_url(host);
    let url = format!("{}/api/auto-fix", base);
    println!("🔧 Đang gửi lệnh tự động sửa lỗi và phục hồi hệ thống (Self-Healing)...");
    match http_post(&url, &json!({})) {
        Ok(res) => {
            let health = res.get("health_after_fix").and_then(|v| v.as_i64()).unwrap_or(100);
            let status = res.get("status").and_then(|v| v.as_str()).unwrap_or("HEALTHY");
            println!("✅ SỨC KHỎE SAU KHI SỬA LỖI: {}/100 [{}]", health, status);
            if let Some(actions) = res.get("actions_taken").and_then(|v| v.as_array()) {
                for act in actions {
                    if let Some(txt) = act.as_str() {
                        println!("  + {}", txt);
                    }
                }
            }
        }
        Err(e) => eprintln!("❌ {}", e),
    }
}

fn cmd_provider(host: &str, provider: Option<&str>) {
    let base = resolve_base_url(host);
    if let Some(p) = provider {
        let url = format!("{}/api/ai/provider", base);
        println!("Đang đổi AI Provider sang: {}...", p);
        match http_post(&url, &json!({ "provider": p })) {
            Ok(_) => println!("✅ Đã chuyển đổi AI Provider sang: '{}' thành công!", p),
            Err(e) => eprintln!("❌ {}", e),
        }
    } else {
        let url = format!("{}/api/ai/provider", base);
        match http_get(&url) {
            Ok(d) => {
                let p = d.get("provider").and_then(|v| v.as_str()).unwrap_or("antigravity_cli");
                let m = d.get("model").and_then(|v| v.as_str()).unwrap_or("gemini-2.0-flash");
                let gw = d.get("gateway_url").and_then(|v| v.as_str()).unwrap_or("http://127.0.0.1:20128/v1");
                println!("🤖 AI BACKEND INFERENCE:");
                println!("  - Provider: {}", p);
                println!("  - Model:    {}", m);
                println!("  - Gateway:  {}", gw);
            }
            Err(e) => eprintln!("❌ {}", e),
        }
    }
}

fn cmd_pet(host: &str, mode: Option<&str>) {
    let base = resolve_base_url(host);
    let target_mode = mode.unwrap_or("tamagotchi");
    let url = format!("{}/api/tamagotchi/mode", base);
    println!("Đang chuyển đổi kiểu Overlay sang: {}...", target_mode);
    match http_post(&url, &json!({ "mode": target_mode })) {
        Ok(_) => println!("✅ Đã chuyển đổi kiểu Desktop Overlay sang: '{}'!", target_mode),
        Err(e) => eprintln!("❌ {}", e),
    }
}

fn cmd_fast_chat(host: &str, prompt: &str) {
    let base = resolve_base_url(host);
    let url = format!("{}/api/ai/chat", base);
    println!("💬 Hỏi Sakura AI: \"{}\"...", prompt);
    match http_post(&url, &json!({ "prompt": prompt })) {
        Ok(res) => {
            let reply = res.get("response").and_then(|v| v.as_str()).unwrap_or("");
            println!("🌸 SAKURA AI: {}", reply);
        }
        Err(e) => eprintln!("❌ {}", e),
    }
}

fn cmd_scan(target: Option<&str>) {
    if let Some(tgt) = target {
        let base = resolve_base_url(tgt);
        let url = format!("{}/api/status", base);
        println!("Đang kiểm tra kết nối đến: {}...", url);
        match http_get(&url) {
            Ok(_) => {
                let _ = save_configured_host(tgt);
                println!("✅ KẾT NỐI THÀNH CÔNG! Đã lưu địa chỉ '{}' làm mặc định.", tgt);
            }
            Err(e) => {
                eprintln!("❌ Không thể kết nối: {}", e);
            }
        }
    } else {
        println!("🔍 Đang quét và kiểm tra máy tính...");
        let curr = get_configured_host();
        let base = resolve_base_url(&curr);
        let url = format!("{}/api/status", base);
        match http_get(&url) {
            Ok(_) => println!("✅ PC hiện tại đang hoạt động tại: {}", base),
            Err(_) => {
                println!("⚠️ Chưa kết nối được PC tại: {}", base);
                println!("💡 Hướng dẫn kết nối không cần chung Wi-Fi:");
                println!("   valorant-tool scan 100.x.y.z (Tailscale IP)");
                println!("   valorant-tool scan https://xxx.trycloudflare.com (Tunnel URL)");
            }
        }
    }
}

fn cmd_game(host: &str, profile: Option<&str>) {
    let base = resolve_base_url(host);
    if let Some(p) = profile {
        let url = format!("{}/api/game/profile", base);
        println!("Đang đổi hồ sơ Game sang: {}...", p);
        match http_post(&url, &json!({ "profile_id": p })) {
            Ok(res) => {
                let name = res.get("active_profile").and_then(|ap| ap.get("name")).and_then(|n| n.as_str()).unwrap_or(p);
                println!("✅ Đã chuyển đổi Hồ sơ Game sang: '{}' thành công!", name);
            }
            Err(e) => eprintln!("❌ {}", e),
        }
    } else {
        let url = format!("{}/api/game/profiles", base);
        match http_get(&url) {
            Ok(d) => {
                let active = d.get("active_profile").cloned().unwrap_or(json!({}));
                let act_name = active.get("name").and_then(|v| v.as_str()).unwrap_or("Desktop");
                let act_icon = active.get("icon").and_then(|v| v.as_str()).unwrap_or("🌸");
                println!("🎮 HỒ SƠ GAME ĐANG HOẠT ĐỘNG: {} {}", act_icon, act_name);
                println!("------------------------------------------------------------");
                if let Some(list) = d.get("profiles").and_then(|v| v.as_array()) {
                    for prof in list {
                        let id = prof.get("id").and_then(|v| v.as_str()).unwrap_or("");
                        let name = prof.get("name").and_then(|v| v.as_str()).unwrap_or("");
                        let icon = prof.get("icon").and_then(|v| v.as_str()).unwrap_or("");
                        let is_act = prof.get("is_active").and_then(|v| v.as_bool()).unwrap_or(false);
                        let mark = if is_act { "👉 [ĐANG CHỌN]" } else { "  " };
                        println!("{} {} {:<12} - {}", mark, icon, id, name);
                    }
                }
            }
            Err(e) => eprintln!("❌ {}", e),
        }
    }
}

fn cmd_minecraft(host: &str, subcmd: &str, extra: &[String]) {
    let base = resolve_base_url(host);
    match subcmd {
        "status" | "state" => {
            let url = format!("{}/api/minecraft/state", base);
            println!("Đang đọc dữ liệu Minecraft Copilot từ {}...", url);
            match http_get(&url) {
                Ok(res) => {
                    let connected = res.get("connected").and_then(|v| v.as_bool()).unwrap_or(false);
                    let in_game = res.get("in_game").and_then(|v| v.as_bool()).unwrap_or(false);
                    let state = res.get("state").cloned().unwrap_or(json!({}));
                    let player = state.get("player").cloned().unwrap_or(json!({}));
                    let danger = state.get("danger").cloned().unwrap_or(json!({}));
                    let radar = state.get("radar").cloned().unwrap_or(json!({}));

                    println!("============================================================");
                    println!("  MINECRAFT COPILOT • NEURO-SAMA RUNTIME");
                    println!("============================================================");
                    println!("  - Trạng thái kết nối Mod : {}", if connected { "🟢 CONNECTED (Port 28888)" } else { "🔴 OFFLINE" });
                    println!("  - Trạng thái trong game  : {}", if in_game { "🎮 IN-GAME" } else { "⏸️ MENU / WAITING" });
                    if in_game {
                        let name = player.get("name").and_then(|v| v.as_str()).unwrap_or("Player");
                        let hp = player.get("health").and_then(|v| v.as_f64()).unwrap_or(20.0);
                        let food = player.get("food_level").and_then(|v| v.as_i64()).unwrap_or(20);
                        let x = player.get("x").and_then(|v| v.as_f64()).unwrap_or(0.0);
                        let y = player.get("y").and_then(|v| v.as_f64()).unwrap_or(64.0);
                        let z = player.get("z").and_then(|v| v.as_f64()).unwrap_or(0.0);
                        let danger_lvl = danger.get("level").and_then(|v| v.as_str()).unwrap_or("SAFE");
                        let hostiles = radar.get("hostile_count").and_then(|v| v.as_i64()).unwrap_or(0);

                        println!("  - Nhân vật               : {}", name);
                        println!("  - Sinh lực (HP)          : {:.1}/20 | Đói: {}/20", hp, food);
                        println!("  - Tọa độ (XYZ)           : X={:.1}, Y={:.1}, Z={:.1}", x, y, z);
                        println!("  - Mức độ nguy cơ         : {}", danger_lvl);
                        println!("  - Quái vật quanh 32m     : {}", hostiles);
                    }
                }
                Err(e) => eprintln!("❌ {}", e),
            }
        }
        "action" => {
            let act = extra.first().map(|s| s.as_str()).unwrap_or("jump");
            let url = format!("{}/api/minecraft/action", base);
            println!("⚡ Gửi hành động '{}' vào Minecraft...", act);
            match http_post(&url, &json!({ "action": act })) {
                Ok(_) => println!("✅ Đã gửi thao tác '{}' thành công!", act),
                Err(e) => eprintln!("❌ {}", e),
            }
        }
        "chat" => {
            let msg = if extra.is_empty() { "Hello from AGY!".to_string() } else { extra.join(" ") };
            let url = format!("{}/api/minecraft/action", base);
            println!("💬 Gửi chat vào Minecraft: \"{}\"...", msg);
            match http_post(&url, &json!({ "action": "send_chat", "params": { "text": msg } })) {
                Ok(_) => println!("✅ Đã phát chat vào game!"),
                Err(e) => eprintln!("❌ {}", e),
            }
        }
        "neuro" => {
            let prompt = if extra.is_empty() { "Neuro ơi tình hình thế nào?".to_string() } else { extra.join(" ") };
            let url = format!("{}/api/minecraft/neuro_chat", base);
            println!("💬 Hỏi Neuro-sama trong Minecraft: \"{}\"...", prompt);
            match http_post(&url, &json!({ "prompt": prompt })) {
                Ok(res) => {
                    let reply = res.get("reply").and_then(|v| v.as_str()).unwrap_or("");
                    println!("⛏️ NEURO-SAMA: {}", reply);
                }
                Err(e) => eprintln!("❌ {}", e),
            }
        }
        "beacon" => {
            let url = format!("{}/api/minecraft/particle", base);
            println!("✨ Bật hiệu ứng cột sáng Ore Beacon & Hào quang Soul Flame...");
            match http_post(&url, &json!({ "beacon": true, "trail": true, "aura": "soul_flame" })) {
                Ok(_) => println!("✅ Đã kích hoạt Ore Beacon & Hào quang!"),
                Err(e) => eprintln!("❌ {}", e),
            }
        }
        _ => {
            eprintln!("Lệnh mc không hợp lệ: '{}'. Dùng: status, action, chat, neuro, beacon", subcmd);
        }
    }
}

fn cmd_auth(host: &str, subcmd: &str, token_arg: Option<&str>) {
    let base = resolve_base_url(host);
    match subcmd {
        "status" | "me" => {
            let url = format!("{}/api/auth/me", base);
            println!("Đang kiểm tra tài khoản đăng nhập từ {}...", url);
            match http_get(&url) {
                Ok(res) => {
                    let auth = res.get("authenticated").and_then(|v| v.as_bool()).unwrap_or(false);
                    if auth {
                        let user = res.get("user").cloned().unwrap_or(json!({}));
                        let name = user.get("display_name").or_else(|| user.get("username")).and_then(|v| v.as_str()).unwrap_or("Commander");
                        let prv = user.get("provider").and_then(|v| v.as_str()).unwrap_or("guest");
                        let role = user.get("role").and_then(|v| v.as_str()).unwrap_or("admin");
                        println!("👤 TÀI KHOẢN: {} [{}] (Quyền: {})", name, prv.to_uppercase(), role);
                    } else {
                        println!("⚪ Chưa đăng nhập (Đang dùng chế độ Khách Guest / Cục bộ).");
                    }
                }
                Err(e) => eprintln!("❌ {}", e),
            }
        }
        "token" => {
            if let Some(tok) = token_arg {
                if let Err(e) = save_configured_token(tok) {
                    eprintln!("❌ Lỗi lưu token: {}", e);
                } else {
                    println!("✅ Đã lưu token chứng thực bảo mật thành công!");
                }
            } else if let Some(tok) = get_configured_token() {
                println!("🔑 Token hiện tại: {}...", &tok[..tok.len().min(12)]);
            } else {
                println!("⚪ Chưa có token nào được lưu.");
            }
        }
        "providers" => {
            let url = format!("{}/api/auth/providers", base);
            match http_get(&url) {
                Ok(res) => {
                    println!("🌐 CỔNG ĐĂNG NHẬP OAUTH2:");
                    if let Some(prvs) = res.get("providers").and_then(|v| v.as_object()) {
                        for (k, v) in prvs {
                            let has = v.get("has_credentials").and_then(|h| h.as_bool()).unwrap_or(false);
                            let status = if has { "✅ Đã cấu hình Cloud Secret" } else { "💡 Sẵn sàng Dev/Mock Login" };
                            println!("  - {:<10}: {}", k.to_uppercase(), status);
                        }
                    }
                }
                Err(e) => eprintln!("❌ {}", e),
            }
        }
        _ => {
            eprintln!("Lệnh auth không hợp lệ: '{}'. Dùng: status, token [val], providers", subcmd);
        }
    }
}

fn cmd_security(host: &str) {
    let base = resolve_base_url(host);
    let url = format!("{}/api/security/status", base);
    println!("🛡️ Đang kiểm tra trạng thái bảo vệ chống crack & anti-tamper tại {}...", url);
    match http_get(&url) {
        Ok(res) => {
            let is_sec = res.get("is_secure").and_then(|v| v.as_bool()).unwrap_or(true);
            let dbg = res.get("debugger_detected").and_then(|v| v.as_bool()).unwrap_or(false);
            let timing = res.get("timing_integrity").and_then(|v| v.as_bool()).unwrap_or(true);
            let frozen = res.get("is_packaged_bundle").and_then(|v| v.as_bool()).unwrap_or(false);

            println!("============================================================");
            println!("  ANTI-TAMPER & REVERSE ENGINEERING AUDIT");
            println!("============================================================");
            println!("  - Tổng quan bảo mật      : {}", if is_sec { "🟢 AN TOÀN (SECURE)" } else { "🔴 NGUY HIỂM / TAMPERED" });
            println!("  - Trình gỡ lỗi (Debugger): {}", if dbg { "🚨 PHÁT HIỆN DEBUGGER ĐANG KẾT NỐI!" } else { "🛡️ KHÔNG PHÁT HIỆN DEBUGGER" });
            println!("  - Tính toàn vẹn thời gian: {}", if timing { "✅ CHUẨN XÁC" } else { "⚠️ BỊ TRÌ HOÃN (BREAKPOINT DETECTED)" });
            println!("  - Định dạng gói nạp      : {}", if frozen { "📦 ĐÓNG GÓI BINARY BẢO VỆ" } else { "🐍 MÃ NGUỒN RUNTIME" });
        }
        Err(e) => eprintln!("❌ {}", e),
    }
}

// ----------------- MCP Server Mode (JSON-RPC 2.0) -----------------

fn run_mcp_server() {
    let stdin = io::stdin();
    let mut stdout = io::stdout();

    for line in stdin.lock().lines() {
        let line_str = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        let trimmed = line_str.trim();
        if trimmed.is_empty() {
            continue;
        }

        let req: Value = match serde_json::from_str(trimmed) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let method = req.get("method").and_then(|m| m.as_str()).unwrap_or("");
        let req_id = req.get("id").cloned();

        match method {
            "initialize" => {
                let resp = json!({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": { "tools": {} },
                        "serverInfo": {
                            "name": "valorant-voice-ops-rust",
                            "version": "2.0.0"
                        }
                    }
                });
                let _ = writeln!(stdout, "{}", resp);
                let _ = stdout.flush();
            }
            "notifications/initialized" => {}
            "tools/list" => {
                let tools = json!({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "get_valorant_status",
                                "description": "Lấy trạng thái vận hành của Valorant Voice AI trên Windows PC (Âm lượng tai nghe/mic, Mute, FPS màn hình, Trạng thái Gemini, Đang chạy Valorant hay không, và Bản nháp chat chờ duyệt).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "host": { "type": "string", "description": "IP PC hoặc URL (tùy chọn)" }
                                    }
                                }
                            },
                            {
                                "name": "set_audio_volume",
                                "description": "Điều chỉnh âm lượng tai nghe (0.0-2.0), âm lượng mic game (0.0-2.0), hoặc bật/tắt Mute giọng AI vào game.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "headphone": { "type": "number", "description": "Âm lượng tai nghe (0.0 đến 2.0)" },
                                        "game_mic": { "type": "number", "description": "Âm lượng mic game (0.0 đến 2.0)" },
                                        "mute_game_mic": { "type": "boolean", "description": "True để Mute, False để Unmute" },
                                        "host": { "type": "string" }
                                    }
                                }
                            },
                            {
                                "name": "handle_chat_draft",
                                "description": "Duyệt hoặc từ chối gửi tin nhắn chat do AI đề xuất vào Valorant (Permission-gated chat).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "draft_id": { "type": "string" },
                                        "action": { "type": "string", "enum": ["approve", "reject"] },
                                        "host": { "type": "string" }
                                    },
                                    "required": ["draft_id", "action"]
                                }
                            },
                            {
                                "name": "send_tactical_callout",
                                "description": "Gửi một chỉ thị chiến thuật hoặc nội dung callout từ điện thoại sang máy tính in-game.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "text": { "type": "string", "description": "Nội dung callout" },
                                        "channel": { "type": "string", "enum": ["team", "all"] },
                                        "host": { "type": "string" }
                                    },
                                    "required": ["text"]
                                }
                            },
                            {
                                "name": "scan_and_connect_pc",
                                "description": "Quét hoặc kết nối và lưu cấu hình PC chạy Valorant Voice AI (hỗ trợ IP LAN, Tailscale 100.x.y.z, domain Cloudflare Tunnel).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "pc_ip": { "type": "string", "description": "Địa chỉ IP hoặc URL của PC" }
                                    }
                                }
                            },
                            {
                                "name": "auto_fix_valorant_app",
                                "description": "Tự động kích hoạt cơ chế Self-Healing trên PC: tự cài driver Virtual Cable còn thiếu, tự kết nối lại thiết bị âm thanh, tự khôi phục tunnel Internet và sửa lỗi hệ thống tức thì.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "host": { "type": "string" }
                                    }
                                }
                            },
                            {
                                "name": "get_app_diagnostics",
                                "description": "Lấy báo cáo chẩn đoán chi tiết tình trạng sức khỏe của từng thành phần trên PC (Driver, Audio Router, Screen DXGI, Gemini Live API, Game process, Internet tunnel) kèm điểm sức khỏe và danh sách vấn đề phát hiện.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "host": { "type": "string" }
                                    }
                                }
                            },
                            {
                                "name": "update_app_config",
                                "description": "Cho phép AI trực tiếp thay đổi và nạp nóng bất kỳ cấu hình nào của ứng dụng trên PC ngay lập tức mà không cần khởi động lại.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "updates": { "type": "object", "description": "Từ điển key-value chứa các cài đặt cần cập nhật" },
                                        "host": { "type": "string" }
                                    },
                                    "required": ["updates"]
                                }
                            },
                            {
                                "name": "set_ai_provider",
                                "description": "Chuyển đổi backend AI (antigravity_cli, claude_code, codex, gemini_live, direct_api) để giao tiếp nhanh hơn.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "provider": { "type": "string", "enum": ["antigravity_cli", "claude_code", "codex", "gemini_live", "direct_api"] },
                                        "host": { "type": "string" }
                                    },
                                    "required": ["provider"]
                                }
                            },
                            {
                                "name": "set_desktop_pet_mode",
                                "description": "Chuyển đổi kiểu Desktop Overlay: tamagotchi (nuôi pet ảo trong suốt có lip-sync), notification (toast tự ẩn), hoặc card.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "mode": { "type": "string", "enum": ["tamagotchi", "notification", "card"] },
                                        "host": { "type": "string" }
                                    },
                                    "required": ["mode"]
                                }
                            },
                            {
                                "name": "fast_tactical_chat",
                                "description": "Hỏi đáp chiến thuật in-game siêu tốc (<15ms) qua cache hoặc Antigravity CLI / Gemini.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": { "type": "string", "description": "Câu hỏi chiến thuật cần AI giải đáp" },
                                        "host": { "type": "string" }
                                    },
                                    "required": ["prompt"]
                                }
                            },
                            {
                                "name": "get_game_profile",
                                "description": "Lấy thông tin hồ sơ Game hiện tại (Valorant, Minecraft Neuro-sama, Roblox, Desktop Pet).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "host": { "type": "string" }
                                    }
                                }
                            },
                            {
                                "name": "set_game_profile",
                                "description": "Chuyển đổi hồ sơ Game đang chơi: valorant, minecraft, roblox, hoặc desktop.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "profile_id": { "type": "string", "enum": ["valorant", "minecraft", "roblox", "desktop"] },
                                        "host": { "type": "string" }
                                    },
                                    "required": ["profile_id"]
                                }
                            },
                            {
                                "name": "get_minecraft_state",
                                "description": "Đọc dữ liệu Minecraft theo thời gian thực (Tọa độ XYZ, Máu HP, Độ đói, Mức độ nguy cơ, Quái vật xung quanh, Khối đang nhìn).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "host": { "type": "string" }
                                    }
                                }
                            },
                            {
                                "name": "send_minecraft_action",
                                "description": "Thực thi hành động can thiệp trực tiếp vào Minecraft (jump, eat, attack, use_shield, autopilot, send_chat).",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "action": { "type": "string", "description": "Tên hành động (jump, eat, attack, use_shield, autopilot, send_chat)" },
                                        "params": { "type": "object", "description": "Tham số bổ sung (ví dụ: duration, text, enable)" },
                                        "host": { "type": "string" }
                                    },
                                    "required": ["action"]
                                }
                            },
                            {
                                "name": "chat_with_neuro",
                                "description": "Trò chuyện trực tiếp với AI Neuro-sama trong Minecraft với nhận thức sâu sắc về thế giới in-game.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": { "type": "string", "description": "Lời nhắn hoặc câu hỏi cho Neuro-sama" },
                                        "host": { "type": "string" }
                                    },
                                    "required": ["prompt"]
                                }
                            },
                            {
                                "name": "get_auth_user",
                                "description": "Lấy thông tin tài khoản đang đăng nhập (Discord, GitHub, Google, Guest) trên PC.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "host": { "type": "string" }
                                    }
                                }
                            },
                            {
                                "name": "get_security_status",
                                "description": "Kiểm tra mức độ an toàn chống dịch ngược và chống crack (Anti-Debugger, Timing Integrity, Anti-Tamper) trên PC.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "host": { "type": "string" }
                                    }
                                }
                            }
                        ]
                    }
                });
                let _ = writeln!(stdout, "{}", tools);
                let _ = stdout.flush();
            }
            "tools/call" => {
                let params = req.get("params").cloned().unwrap_or(json!({}));
                let name = params.get("name").and_then(|n| n.as_str()).unwrap_or("");
                let args = params.get("arguments").cloned().unwrap_or(json!({}));
                let host = args.get("host").and_then(|h| h.as_str()).unwrap_or("");
                let base = resolve_base_url(host);

                let text_res = match name {
                    "get_valorant_status" => {
                        let url = format!("{}/api/status", base);
                        match http_get(&url) {
                            Ok(data) => {
                                let hp = (data.get("headphone_volume").and_then(|v| v.as_f64()).unwrap_or(1.0) * 100.0) as i32;
                                let mic = (data.get("game_mic_volume").and_then(|v| v.as_f64()).unwrap_or(1.0) * 100.0) as i32;
                                let muted = if data.get("mute_game_mic").and_then(|v| v.as_bool()).unwrap_or(false) { "🔇 MUTED" } else { "🔊 ACTIVE" };
                                let cable = if data.get("has_virtual_cable").and_then(|v| v.as_bool()).unwrap_or(false) { "✅ ĐÃ CÀI ĐẶT" } else { "❌ CHƯA CÓ" };
                                let gemini = if data.get("gemini_connected").and_then(|v| v.as_bool()).unwrap_or(false) { "✅ CONNECTED" } else { "⚠️ OFFLINE" };
                                format!(
                                    "🎮 VALORANT VOICE AI (PC: {}):\n- Tai nghe: {}%\n- Mic Game: {}% [{}]\n- VB-Cable: {}\n- Gemini Live API: {}",
                                    base, hp, mic, muted, cable, gemini
                                )
                            }
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "set_audio_volume" => {
                        let url = format!("{}/api/volume", base);
                        let mut map = serde_json::Map::new();
                        if let Some(hp) = args.get("headphone") { map.insert("headphone".to_string(), hp.clone()); }
                        if let Some(gm) = args.get("game_mic") { map.insert("game_mic".to_string(), gm.clone()); }
                        if let Some(m) = args.get("mute_game_mic") { map.insert("mute_game_mic".to_string(), m.clone()); }
                        match http_post(&url, &Value::Object(map)) {
                            Ok(_) => "✅ Đã cập nhật âm lượng thành công!".to_string(),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "handle_chat_draft" => {
                        let draft_id = args.get("draft_id").and_then(|v| v.as_str()).unwrap_or("");
                        let action = args.get("action").and_then(|v| v.as_str()).unwrap_or("approve");
                        let url = format!("{}/api/chat/action", base);
                        let payload = json!({ "draft_id": draft_id, "action": action });
                        match http_post(&url, &payload) {
                            Ok(_) => format!("✅ Đã xử lý bản nháp [{}] với hành động: {}", draft_id, action),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "send_tactical_callout" => {
                        let text = args.get("text").and_then(|v| v.as_str()).unwrap_or("");
                        let channel = args.get("channel").and_then(|v| v.as_str()).unwrap_or("team");
                        let url = format!("{}/api/callout", base);
                        let payload = json!({ "text": text, "channel": channel });
                        match http_post(&url, &payload) {
                            Ok(res) => format!("✅ Đã gửi callout: \"{}\" (Draft ID: {})", text, res.get("draft_id").and_then(|v| v.as_str()).unwrap_or("")),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "auto_fix_valorant_app" => {
                        let url = format!("{}/api/auto-fix", base);
                        match http_post(&url, &json!({})) {
                            Ok(res) => {
                                let health = res.get("health_after_fix").and_then(|v| v.as_i64()).unwrap_or(100);
                                format!("🔧 Đã tự động sửa lỗi thành công! Điểm sức khỏe sau khi fix: {}/100", health)
                            }
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "get_app_diagnostics" => {
                        let url = format!("{}/api/diagnostics", base);
                        match http_get(&url) {
                            Ok(d) => format!("📊 Báo cáo chẩn đoán:\n{}", serde_json::to_string_pretty(&d).unwrap_or_default()),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "update_app_config" => {
                        let updates = args.get("updates").cloned().unwrap_or(json!({}));
                        let url = format!("{}/api/config", base);
                        let payload = json!({ "updates": updates });
                        match http_post(&url, &payload) {
                            Ok(_) => format!("✅ AI đã nạp nóng cấu hình mới thành công!"),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "set_ai_provider" => {
                        let provider = args.get("provider").and_then(|v| v.as_str()).unwrap_or("antigravity_cli");
                        let url = format!("{}/api/ai/provider", base);
                        match http_post(&url, &json!({ "provider": provider })) {
                            Ok(_) => format!("✅ Đã chuyển đổi AI Backend sang: {}", provider),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "set_desktop_pet_mode" => {
                        let mode = args.get("mode").and_then(|v| v.as_str()).unwrap_or("tamagotchi");
                        let url = format!("{}/api/tamagotchi/mode", base);
                        match http_post(&url, &json!({ "mode": mode })) {
                            Ok(_) => format!("✅ Đã chuyển đổi Desktop Overlay sang: {}", mode),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "fast_tactical_chat" => {
                        let prompt = args.get("prompt").and_then(|v| v.as_str()).unwrap_or("");
                        let url = format!("{}/api/ai/chat", base);
                        match http_post(&url, &json!({ "prompt": prompt })) {
                            Ok(res) => {
                                let reply = res.get("response").and_then(|v| v.as_str()).unwrap_or("");
                                format!("🌸 SAKURA AI: {}", reply)
                            }
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "scan_and_connect_pc" => {
                        if let Some(target) = args.get("pc_ip").and_then(|v| v.as_str()) {
                            let b = resolve_base_url(target);
                            let url = format!("{}/api/status", b);
                            match http_get(&url) {
                                Ok(_) => {
                                    let _ = save_configured_host(target);
                                    format!("✅ Kết nối thành công đến PC tại {} và đã lưu làm mặc định!", b)
                                }
                                Err(e) => format!("❌ Không thể kết nối đến {}: {}", b, e),
                            }
                        } else {
                            format!("ℹ️ Địa chỉ hiện tại: {}", base)
                        }
                    }
                    "get_game_profile" => {
                        let url = format!("{}/api/game/profiles", base);
                        match http_get(&url) {
                            Ok(d) => {
                                let active = d.get("active_profile").cloned().unwrap_or(json!({}));
                                let name = active.get("name").and_then(|v| v.as_str()).unwrap_or("Desktop");
                                let icon = active.get("icon").and_then(|v| v.as_str()).unwrap_or("🌸");
                                format!("🎮 Hồ sơ Game hiện tại: {} {}", icon, name)
                            }
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "set_game_profile" => {
                        let pid = args.get("profile_id").and_then(|v| v.as_str()).unwrap_or("desktop");
                        let url = format!("{}/api/game/profile", base);
                        match http_post(&url, &json!({ "profile_id": pid })) {
                            Ok(res) => {
                                let name = res.get("active_profile").and_then(|ap| ap.get("name")).and_then(|n| n.as_str()).unwrap_or(pid);
                                format!("✅ Đã chuyển đổi Hồ sơ Game sang: {}", name)
                            }
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "get_minecraft_state" => {
                        let url = format!("{}/api/minecraft/state", base);
                        match http_get(&url) {
                            Ok(d) => format!("⛏️ MINECRAFT STATE:\n{}", serde_json::to_string_pretty(&d).unwrap_or_default()),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "send_minecraft_action" => {
                        let action = args.get("action").and_then(|v| v.as_str()).unwrap_or("jump");
                        let params = args.get("params").cloned().unwrap_or(json!({}));
                        let url = format!("{}/api/minecraft/action", base);
                        match http_post(&url, &json!({ "action": action, "params": params })) {
                            Ok(_) => format!("✅ Đã thực thi thao tác Minecraft: '{}'", action),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "chat_with_neuro" => {
                        let prompt = args.get("prompt").and_then(|v| v.as_str()).unwrap_or("");
                        let url = format!("{}/api/minecraft/neuro_chat", base);
                        match http_post(&url, &json!({ "prompt": prompt })) {
                            Ok(res) => {
                                let reply = res.get("reply").and_then(|v| v.as_str()).unwrap_or("");
                                format!("⛏️ NEURO-SAMA: {}", reply)
                            }
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "get_auth_user" => {
                        let url = format!("{}/api/auth/me", base);
                        match http_get(&url) {
                            Ok(d) => format!("👤 THÔNG TIN USER:\n{}", serde_json::to_string_pretty(&d).unwrap_or_default()),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    "get_security_status" => {
                        let url = format!("{}/api/security/status", base);
                        match http_get(&url) {
                            Ok(d) => format!("🛡️ BẢO MẬT & ANTI-TAMPER:\n{}", serde_json::to_string_pretty(&d).unwrap_or_default()),
                            Err(e) => format!("❌ {}", e),
                        }
                    }
                    _ => format!("Lỗi: Không tìm thấy tool '{}'", name),
                };

                let resp = json!({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": text_res
                            }
                        ]
                    }
                });
                let _ = writeln!(stdout, "{}", resp);
                let _ = stdout.flush();
            }
            "ping" => {
                let resp = json!({ "jsonrpc": "2.0", "id": req_id, "result": {} });
                let _ = writeln!(stdout, "{}", resp);
                let _ = stdout.flush();
            }
            _ => {
                if req_id.is_some() {
                    let err = json!({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": { "code": -32601, "message": format!("Method '{}' not found", method) }
                    });
                    let _ = writeln!(stdout, "{}", err);
                    let _ = stdout.flush();
                }
            }
        }
    }
}

// ----------------- Main Entry Point -----------------

fn print_usage() {
    println!("🎮 VALORANT VOICE AI - RUST CLI CONTROLLER v2.2");
    println!("------------------------------------------------------------");
    println!("Cách dùng:");
    println!("  valorant-tool status            Xem trạng thái kết nối và âm lượng");
    println!("  valorant-tool game [profile]    Xem hoặc đổi hồ sơ Game (desktop/valorant/minecraft/roblox)");
    println!("  valorant-tool mc <cmd> [args]   Minecraft Copilot & Neuro-sama (status/action/chat/neuro/beacon)");
    println!("  valorant-tool auth [cmd]        Quản lý tài khoản (status/token [val]/providers)");
    println!("  valorant-tool sec               Kiểm tra bảo mật & chống crack (Anti-Tamper & Anti-Debug)");
    println!("  valorant-tool provider [name]   Xem hoặc đổi AI Backend (antigravity_cli/claude_code/codex/gemini_live)");
    println!("  valorant-tool pet [mode]        Đổi chế độ Desktop Pet (tamagotchi/notification/card)");
    println!("  valorant-tool chat <prompt>     Hỏi đáp chiến thuật nhanh (<15ms)");
    println!("  valorant-tool mute              Mute giọng AI vào mic game");
    println!("  valorant-tool unmute            Unmute giọng AI vào mic game");
    println!("  valorant-tool vol <hp> [mic]    Chỉnh âm lượng (ví dụ: 1.2 là 120%)");
    println!("  valorant-tool approve           Duyệt gửi tin nhắn chat game");
    println!("  valorant-tool reject            Hủy bản nháp chat game");
    println!("  valorant-tool callout <text>    Gửi chỉ thị chiến thuật vào game");
    println!("  valorant-tool diag              Xem báo cáo chẩn đoán chi tiết");
    println!("  valorant-tool fix               Tự động sửa lỗi hệ thống (Self-Heal)");
    println!("  valorant-tool scan [target]     Kiểm tra hoặc lưu IP/URL PC");
    println!("  valorant-tool mcp               Chạy MCP Server cho AGY CLI");
}

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() > 1 && (args[1] == "mcp" || args[1] == "--mcp") {
        run_mcp_server();
        return;
    }

    if args.len() < 2 || args[1] == "help" || args[1] == "--help" || args[1] == "-h" {
        print_usage();
        return;
    }

    let cmd = &args[1];
    let host = "";

    match cmd.as_str() {
        "status" => cmd_status(host),
        "game" | "profile" => {
            let prof = args.get(2).map(|s| s.as_str());
            cmd_game(host, prof);
        }
        "mc" | "minecraft" => {
            let subcmd = args.get(2).map(|s| s.as_str()).unwrap_or("status");
            let extra = if args.len() > 3 { args[3..].to_vec() } else { vec![] };
            cmd_minecraft(host, subcmd, &extra);
        }
        "auth" | "login" | "user" => {
            let subcmd = args.get(2).map(|s| s.as_str()).unwrap_or("status");
            let tok = args.get(3).map(|s| s.as_str());
            cmd_auth(host, subcmd, tok);
        }
        "sec" | "security" | "integrity" => cmd_security(host),
        "provider" | "backend" => {
            let prov = args.get(2).map(|s| s.as_str());
            cmd_provider(host, prov);
        }
        "pet" | "tamagotchi" => {
            let mode = args.get(2).map(|s| s.as_str());
            cmd_pet(host, mode);
        }
        "chat" | "ask" => {
            let prompt = args.get(2).map(|s| s.as_str()).unwrap_or("Tình hình chiến thuật?");
            cmd_fast_chat(host, prompt);
        }
        "mute" => cmd_mute(host, true),
        "unmute" => cmd_mute(host, false),
        "vol" | "volume" => {
            let hp = args.get(2).and_then(|v| v.parse::<f64>().ok());
            let mic = args.get(3).and_then(|v| v.parse::<f64>().ok());
            cmd_volume(host, hp, mic);
        }
        "approve" => {
            let draft_id = args.get(2).map(|s| s.as_str());
            cmd_chat_action(host, "approve", draft_id);
        }
        "reject" => {
            let draft_id = args.get(2).map(|s| s.as_str());
            cmd_chat_action(host, "reject", draft_id);
        }
        "callout" => {
            let text = args.get(2).map(|s| s.as_str()).unwrap_or("Địch xuất hiện!");
            cmd_callout(host, text);
        }
        "diag" | "diagnostics" => cmd_diagnostics(host),
        "fix" | "auto-fix" => cmd_auto_fix(host),
        "scan" => {
            let target = args.get(2).map(|s| s.as_str());
            cmd_scan(target);
        }
        _ => {
            eprintln!("Lệnh không hợp lệ: '{}'. Gõ 'valorant-tool' để xem trợ giúp.", cmd);
            print_usage();
        }
    }
}
