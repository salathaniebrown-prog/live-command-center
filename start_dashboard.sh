#!/bin/bash
SESSION="ALSTRA_CONTROL"

tmux has-session -t $SESSION 2>/dev/null

if [ $? != 0 ]; then
    tmux new-session -d -s $SESSION -n "Telemetry"
    tmux send-keys -t $SESSION:0 "tail -f ~/astra-enterprise-core/telemetry.log" C-m
    tmux split-window -v -t $SESSION:0
    tmux send-keys -t $SESSION:0.1 "ping -i 2 8.8.8.8" C-m

    tmux new-window -t $SESSION:1 -n "CLI"
    tmux send-keys -t $SESSION:1 "python3 ~/astra-enterprise-core/astra_ai_assistant.py" C-m
fi

tmux attach-session -t $SESSION
nohup python3 ~/ai-studio-dealership/dealership_core.py > ~/ai-studio-dealership/server.log 2>&1 &
bash ~/start_tunnel.sh
setsid nohup python3 ~/ai-studio-legal/legal_brain.py > ~/ai-studio-legal/legal.log 2>&1 < /dev/null &
