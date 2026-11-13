#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
pkill -f "legal_brain.py|astra_brain.py|ooda_os_core.py|bi_superintelligence.py|dealership_core.py|astra_177b_nexus.py|unified_brain_os.py|autonomous_workflows_backup.py|location_intel_engine.py" || true

setsid nohup python3 ~/ai-studio-legal/legal_brain.py > ~/ai-studio-legal/legal.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-memory-brain/astra_brain.py > ~/astra-memory-brain/brain.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-ooda-os/ooda_os_core.py > ~/astra-ooda-os/ooda.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-bi-engine/bi_superintelligence.py > ~/astra-bi-engine/bi.log 2>&1 < /dev/null &
setsid nohup python3 ~/ai-studio-dealership/dealership_core.py > ~/ai-studio-dealership/server.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-177b-nexus/astra_177b_nexus.py > ~/astra-177b-nexus/nexus.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-unified-brain/unified_brain_os.py > ~/astra-unified-brain/unified.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-workflows/autonomous_workflows_backup.py > ~/astra-workflows/wf.log 2>&1 < /dev/null &
setsid nohup python3 ~/astra-location-intel/location_intel_engine.py > ~/astra-location-intel/geo.log 2>&1 < /dev/null &

sleep 2
bash ~/check_all.sh
