"""Send one signed device heartbeat using separately provisioned device credentials."""
import argparse
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
import urllib.request

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--device', required=True)
    parser.add_argument('--slot', type=int, required=True)
    parser.add_argument('--status', choices=['PASS', 'FAIL'], required=True)
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.url)
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')):
        raise SystemExit('Use HTTPS for remote devices.')
    secret = os.environ.get('EAGLE_EYES_DEVICE_SECRET', '')
    if len(secret) < 64 or not 1 <= args.slot <= 32:
        raise SystemExit('A provisioned secret of at least 64 characters and a slot from 1 to 32 are required.')
    payload = json.dumps({'device_id': args.device, 'target_cluster_slot': args.slot, 'status_flag': args.status}, separators=(',', ':')).encode()
    timestamp, nonce = str(time.time_ns() // 1000000), secrets.token_hex(16)
    signature = hmac.new(secret.encode(), f'{timestamp}.{nonce}.'.encode() + payload, hashlib.sha256).hexdigest()
    request = urllib.request.Request(args.url.rstrip('/') + '/api/mobile/telemetry', data=payload, headers={
        'Content-Type': 'application/json', 'X-Eagle-Eyes-Device': args.device,
        'X-Eagle-Eyes-Timestamp': timestamp, 'X-Eagle-Eyes-Nonce': nonce, 'X-Eagle-Eyes-Signature': signature})
    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.read().decode())
