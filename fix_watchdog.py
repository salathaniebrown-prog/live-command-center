import os
fn = '/data/data/com.termux/files/home/astra-unified-brain/auto_correct_brain.py'
lines = open(fn).readlines()
for i in range(len(lines)):
    if 'if fix_result.returncode == 0:' in lines[i]:
        lines[i] = '                if fix_result.returncode == 0:\n'
        lines[i+1] = '                    print("[WALTCHDOG] Auto-fix applied. Reloading...")\n'
        lines[i+2] = '                else:\n'
        lines[i+3] = '                    print("[WALTCHDOG] Auto-fix failed. Manual intervention required.")\n'
        lines[i+4] = '                    continue\n'
        break
open(fn, 'w').writelines(lines)
print('Success! Watchdog indentation repaired.')
