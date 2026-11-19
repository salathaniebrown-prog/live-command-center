#!/data/data/com.termux/files/usr/bin/bash
GREEN="\033[0;32m"; BLUE="\033[0;34m"; RED="\033[0;31m"; NC="\033[0m"
MODEL="qwen2.5:1.5b"
API_URL="http://127.0.0.1:11434/api/generate"
if [ -z "$1" ]; then echo "Usage: ./astra-pilot.sh \"your task\""; exit 1; fi
PROMPT="You are Astra, a Linux Termux expert. The user wants to: $1. Reply with ONLY the exact bash command to do this. Do not use markdown, do not explain, do not add backticks. Just the command."
echo -e "${BLUE}🤖 Astra is thinking...${NC}"
RESPONSE=$(curl -s $API_URL -d "{\"model\": \"$MODEL\", \"prompt\": \"$PROMPT\", \"stream\": false, \"options\": {\"temperature\": 0.1}}")
COMMAND=$(echo "$RESPONSE" | sed -n "s/.*\"response\":\"\([^\"]*\)\".*/\1/p" | sed "s/```bash//g" | sed "s/```//g" | xargs)
if [ -z "$COMMAND" ]; then echo -e "${RED}❌ Astra got confused.${NC}"; exit 1; fi
echo -e "${GREEN}✅ Suggested Command:${NC}\n${BLUE}   $COMMAND${NC}\n"
read -p "⚠️  Run this command? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then eval "$COMMAND"; else echo -e "${RED}🛑 Cancelled.${NC}"; fi
