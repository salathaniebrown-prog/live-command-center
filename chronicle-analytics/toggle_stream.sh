#!/usr/bin/env bash
# ==============================================================================
# System Architecture: STREAMING_ONE_COMMAND_TOGGLE_TOOL
# Executive Authority: SALATHANIEL S A BROWN SR
# Purpose:             Instant Broadcast Controller (On/Off/Reset)
# ==============================================================================

ENV_FILE="$HOME/.alstra_persistence/.env"
LOG_FILE="$HOME/.alstra_persistence/cluster_health.log"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

[ -z "$KICK_STREAM_URL" ] && KICK_STREAM_URL="rtmps://fa723fc1b171.global-contribute.live-video.net/"
[ -z "$KICK_STREAM_KEY" ] && KICK_STREAM_KEY="sk_us-west-2_grpgs8SCA01h_n6tZZfihmHQ4JikG4sv6uSjTiNLsWz"

clear
echo "======================================================================"
echo "    SALATHANIEL S A BROWN SR - STREAM CONTROLLER DASHBOARD            "
echo "======================================================================"

if pgrep ffmpeg > /dev/null; then
    echo -e "\e[32m[STATUS] Broadcast Core is currently LIVE and streaming.\e[0m"
    echo "----------------------------------------------------------------------"
    read -p "Would you like to STOP the live stream? (y/n): " action
    if [[ "$action" == "y" || "$action" == "Y" ]]; then
        echo "[-] Terminating video pipeline links safely..."
        pkill -f ffmpeg
        echo "[$((date +%Y-%m-%d\ %H:%M:%S))] WARNING: Stream stopped manually by Executive Authority." >> "$LOG_FILE"
    fi
else
    echo -e "\e[31m[STATUS] Broadcast Core is currently STANDBY / OFFLINE.\e[0m"
    echo "----------------------------------------------------------------------"
    read -p "Would you like to START the live stream? (y/n): " action
    if [[ "$action" == "y" || "$action" == "Y" ]]; then
        echo "[+] Launching hardware video pipeline..."
        # Low-overhead minimal test card pattern streaming layout to match 8000Kbps CBR targets
        ffmpeg -f lavfi -i testsrc=size=1920x1080:rate=60 -f lavfi -i sine=frequency=1000 \
               -c:v libx264 -b:v 8000k -maxrate 8000k -bufsize 16000k -pix_fmt yuv420p -g 120 \
               -c:a aac -b:a 160k -f flv "$KICK_STREAM_URL$KICK_STREAM_KEY" > /dev/null 2>&1 &
               
        echo "[$((date +%Y-%m-%d\ %H:%M:%S))] SUCCESS: Stream initialized manually over secure RTMP node." >> "$LOG_FILE"
        echo -e "\e[32m[✔] Stream broadcast sequence triggered successfully!\e[0m"
    fi
fi
