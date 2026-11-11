import os
import json
import time

KEY_STORE_PATH = os.path.expanduser("~/alstra-langgraph/ledger/key_vault.json")

class SovereignKeyManager:
    def __init__(self):
        os.makedirs(os.path.dirname(KEY_STORE_PATH), exist_ok=True)
        if not os.path.exists(KEY_STORE_PATH):
            self.save_keys({"active_key": "AQ.Ab8RN6JfjBb1cFU1yHPVa-uKrBGe65pFe_5U2dq50elQbvs4Q", "type": "OAUTH_BEARER", "updated_at": time.time()})

    def get_active_credentials(self):
        with open(KEY_STORE_PATH, "r") as f:
            return json.load(f)

    def save_keys(self, data):
        with open(KEY_STORE_PATH, "w") as f:
            json.dump(data, f, indent=2)

if __name__ == "__main__":
    km = SovereignKeyManager()
    print("[+] Key Manager Active:", km.get_active_credentials())
