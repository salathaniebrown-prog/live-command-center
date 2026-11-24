# AUTO-GENERATED RUNTIME CVE SANDBOX
import os
MAX_MULTIPART_BYTES = 10 * 1024 * 1024
BLOCKED_PATH_TOKENS = ('..', '\x00', '~')
def sanitize_bound_path(raw_path: str) -> str:
    if any(tok in raw_path for tok in BLOCKED_PATH_TOKENS):
        raise PermissionError(f'[CVE-GUARD] Blocked traversal payload: {raw_path}')
    return os.path.abspath(raw_path)
DETECTED_SINKS = [('astra_ai_brain.py', 11, 'requests.post'), ('model_router.py', 3, 'aiohttp.web'), ('model_router.py', 3, 'aiohttp.ClientSession'), ('webhook_node.py', 7, 'aiohttp.web'), ('webhook_node.py', 7, 'aiohttp.ClientSession')]
