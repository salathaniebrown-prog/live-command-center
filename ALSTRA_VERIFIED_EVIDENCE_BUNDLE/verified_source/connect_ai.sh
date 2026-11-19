#!/bin/bash
termux-wake-lock
while true; do
    echo "Connecting to AI Supercomputer..."
    autossh -M 0 \
        -o "ServerAliveInterval 30" \
        -o "ServerAliveCountMax 3" \
        -o "ExitOnForwardFailure yes" \
        -p 22 \
        YOUR_SERVER_IP \
        -t "tmux attach-session -t ai_session || tmux new-session -s ai_session"
    echo "Connection dropped. Retrying in 5 seconds..."
    sleep 5
done
