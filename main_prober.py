"""One measured HTTP health sweep; exit nonzero for unavailable or degraded results."""
import argparse
import concurrent.futures
import json
import time
import urllib.error
import urllib.request


def probe(base_url, path):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(base_url.rstrip('/') + path, timeout=20) as response:
            data = json.load(response)
            healthy = data.get('ok') is True if path == '/api/health' else data.get('systemState') == 'LIVE'
            status = 'ONLINE' if healthy else 'DEGRADED'
    except (OSError, urllib.error.URLError, ValueError, AttributeError):
        status = 'UNAVAILABLE'
    return {'path': path, 'status': status, 'round_trip_ms': round((time.perf_counter() - started) * 1000, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda endpoint: probe(args.url, endpoint), ['/api/health', '/api/deployment-center/status']))
    print(json.dumps({'results': results}, indent=2))
    return 0 if all(result['status'] == 'ONLINE' for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
