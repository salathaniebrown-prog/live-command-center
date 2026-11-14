import sys
import ast

def fix_indentation(filepath, error_line):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    if error_line >= len(lines):
        return False
        
    target_idx = error_line - 1
    prev_idx = target_idx - 1
    
    # If the previous line was a return, the current line is likely over-indented
    if prev_idx >= 0 and lines[prev_idx].strip() == "return":
        print(f"[AUTO-FIXER] Detected over-indentation after 'return' on line {error_line}")
        lines[target_idx] = "    " + lines[target_idx].lstrip()
        with open(filepath, 'w') as f:
            f.writelines(lines)
        return True
        
    # If the previous line ends with a colon (:, else:, etc), current line is under-indented
    if prev_idx >= 0 and lines[prev_idx].strip().endswith(":"):
        print(f"[AUTO-FIXER] Detected missing indentation after ':' on line {error_line}")
        lines[target_idx] = "    " + lines[target_idx].lstrip()
        with open(filepath, 'w') as f:
            f.writelines(lines)
        return True
        
    return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)
    filename = sys.argv[1]
    err_line = int(sys.argv[2])
    
    if fix_indentation(filename, err_line):
        print("[AUTO-FIXER] Patch applied successfully.")
        sys.exit(0)
    else:
        print("[AUTO-FIXER] Could not determine fix.")
        sys.exit(1)
