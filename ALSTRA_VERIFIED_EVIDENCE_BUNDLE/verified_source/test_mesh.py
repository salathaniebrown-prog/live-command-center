"""Measure actual per-request HTTP round trips to the configured gateway."""
import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.request


def sample(url):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url.rstrip('/') + '/api/health', timeout=10) as response:
            ok = json.load(response).get('ok') is True
    except (OSError, ValueError, AttributeError):
        ok = False
    return {'ok': ok, 'round_trip_ms': round((time.perf_counter() - started) * 1000, 3)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    args = parser.parse_args()
    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        rows = list(executor.map(sample, [args.url] * 10))
    elapsed = (time.perf_counter() - start) * 1000
    latencies = sorted(row['round_trip_ms'] for row in rows if row['ok'])
    print(json.dumps({'url': args.url, 'samples': rows, 'success_count': len(latencies),
                      'wall_time_ms': round(elapsed, 3),
                      'median_round_trip_ms': statistics.median(latencies) if latencies else None,
                      'max_round_trip_ms': max(latencies) if latencies else None}, indent=2))
    raise SystemExit(0 if len(latencies) == 10 else 1)
