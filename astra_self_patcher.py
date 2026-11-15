#!/usr/bin/env python3
import os, sys, py_compile, subprocess

def self_patch_and_verify(target_file="astra_spatial_assistant.py", enhancement_comment="# [Self-Optimized by Astra AI Model Assistant]"):
    target_path = os.path.join(os.path.expanduser("~"), target_file)
    if not os.path.exists(target_path):
        return {"status": "ERROR", "message": f"Target {target_file} not found"}
    
    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if enhancement_comment not in content:
        content = enhancement_comment + "\n" + content
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
            
    try:
        py_compile.compile(target_path, doraise=True)
        # Run TDD Guardrails
        tdd_res = subprocess.run(["python3", os.path.join(os.path.expanduser("~"), "astra_tdd_guardrails.py")], capture_output=True, text=True)
        passed = tdd_res.returncode == 0
        return {
            "status": "SUCCESS" if passed else "GUARDRAIL_REJECTED",
            "file": target_file,
            "tdd_output": tdd_res.stdout.splitlines()[-1] if tdd_res.stdout else "No output"
        }
    except Exception as e:
        return {"status": "SYNTAX_ERROR", "error": str(e)}

if __name__ == "__main__":
    print(self_patch_and_verify())
