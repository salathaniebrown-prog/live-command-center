#!/usr/bin/env python3
import time, os, sys

LOG_FILE = "/tmp/telemetry_clean.log"
# Fallback to direct memory scanning if log file is empty
def get_mem_metric():
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if "Memory loading at" in line:
                        # Extract the MB count string cleanly
                        part = line.split("Memory loading at")[-1]
                        return int(''.join(filter(str.isdigit, part)))
    except:
        pass
    # Live fallback calculation from proc state
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
            tot = int(lines[0].split()[1])
            fre = int(lines[1].split()[1])
            return int((tot - fre) / 1024)
    except:
        return 2048

def run_chart():
    # ANSI Color Code mappings
    CYAN, GREEN, RESET = "\033[1;36m", "\033[1;32m", "\033[0m"
    history = [0] * 40 # Chart width columns
    
    print("\033[?25l") # Hide default cursor blinking block
    try:
        while True:
            val = get_mem_metric()
            history.append(val)
            history.pop(0)
            
            # Clear window frames and redraw header info
            sys.stdout.write("\033[H\033[J")
            sys.stdout.write(f"{CYAN}+-----------------------------------------------------------+{RESET}\n")
            sys.stdout.write(f"{CYAN}|{RESET}  JARVIS SOVEREIGN CORE HUD - REALTIME TELEMETRY PLOTTER   {CYAN}|{RESET}\n")
            sys.stdout.write(f"{CYAN}+-----------------------------------------------------------+{RESET}\n")
            sys.stdout.write(f" Current Memory Pressure Loading: {GREEN}{val} MB{RESET}\n\n")
            
            # Dynamic Bar Axis Rendering (Max cap normalized to 4000MB)
            max_val = max(max(history), 4000)
            for row in range(12, 0, -1):
                threshold = (max_val / 12) * row
                sys.stdout.write(f" {int(threshold):4d}MB ┃ ")
                for col in history:
                    if col >= threshold:
                        sys.stdout.write(f"{GREEN}█{RESET}")
                    elif col >= threshold * 0.85:
                        sys.stdout.write(f"{GREEN}▄{RESET}")
                    else:
                        sys.stdout.write(" ")
                sys.stdout.write("\n")
                
            sys.stdout.write("       ┗" + "━" * 40 + ">\n")
            sys.stdout.write("         [ Real-time Sampling Interval Stream Grid Index ]\n")
            sys.stdout.flush()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\033[?25h\n[-] Chart visualization array paused.") # Restore default cursor behavior

if __name__ == "__main__":
    run_chart()
