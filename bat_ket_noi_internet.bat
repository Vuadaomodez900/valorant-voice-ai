@echo off
chcp 65001 >nul
title Valorant Voice AI - Kích Hoạt Kết Nối Internet (Không Cần Chung Wi-Fi)
color 0B

echo ======================================================================
echo    🎮 VALORANT VOICE AI - KÍCH HOẠT KẾT NỐI INTERNET TỪ XA
echo ======================================================================
echo.
echo  Đang kiểm tra ứng dụng ValorantVoiceAI trên cổng 8000...
echo.

set SSH_CMD=ssh
if exist "%SystemRoot%\System32\OpenSSH\ssh.exe" (
    set SSH_CMD=%SystemRoot%\System32\OpenSSH\ssh.exe
)

echo  Đang khởi tạo đường truyền HTTPS bảo mật ra ngoài Internet...
echo  (Không cần mở port router, không cần đăng ký tài khoản)
echo.
echo ----------------------------------------------------------------------
echo  👉 HƯỚNG DẪN:
echo   1. Khi màn hình hiện ra đường link dạng: https://xxxx.a.pinggy.link
echo   2. Hãy COPY đường link đó và gửi cho AGY trên điện thoại:
echo      "Kết nối PC https://xxxx.a.pinggy.link"
echo   3. Hoặc dùng camera điện thoại quét trực tiếp mã QR trên cửa sổ này!
echo ----------------------------------------------------------------------
echo.

%SSH_CMD% -p 443 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R0:localhost:8000 a.pinggy.io

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ Thử phương án dự phòng qua Localhost.run...
    %SSH_CMD% -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:localhost:8000 nokey@localhost.run
)

pause
