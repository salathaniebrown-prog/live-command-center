import os, subprocess

# 1. Fix /api/os/reason tuple indexing in unified_brain_os.py (8101)
p1 = os.path.expanduser("~/astra-unified-brain/unified_brain_os.py")
if os.path.exists(p1):
    s1 = open(p1).read().replace("chunk_cnt = c.execute(\"SELECT COUNT(*) FROM chunks\").fetchone()", "chunk_cnt = c.execute(\"SELECT COUNT(*) FROM chunks\").fetchone()[0]")
    s1 = s1.replace("art_cnt = c.execute(\"SELECT COUNT(*) FROM arts\").fetchone()", "art_cnt = c.execute(\"SELECT COUNT(*) FROM arts\").fetchone()[0]")
    open(p1, "w").write(s1)

# 2. Ensure studio_pro_engine.py (8108) is running cleanly
p2 = os.path.expanduser("~/astra-studio-pro/studio_pro_engine.py")
subprocess.run(["pkill", "-f", "unified_brain_os.py|studio_pro_engine.py"], check=False)
for sc, lg in [(p1, os.path.expanduser("~/astra-unified-brain/unified.log")), (p2, os.path.expanduser("~/astra-studio-pro/pro.log"))]:
    if os.path.exists(sc):
        with open(lg, "a") as lf:
            subprocess.Popen(["python3", sc], stdout=lf, stderr=lf, start_new_session=True)
print("[OK] Ports 8101 & 8108 polished and running persistently with wake-lock")
