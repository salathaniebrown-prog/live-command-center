"""Wait for the exact requested revision and Deployment Center on Railway."""
import argparse
import json
import time
import urllib.request


def read(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--attempts', type=int, default=60)
    args = parser.parse_args()
    base = args.url.rstrip('/')
    for attempt in range(args.attempts):
        try:
            health = read(base + '/api/health')
            revision = read(base + '/api/deployment')
            if health.get('ok') is True and revision.get('commitSha') == args.sha:
                center = read(base + '/api/deployment-center/status')
                if center.get('schemaVersion') == 1 and center.get('simulated') is False and len(center.get('nodes', [])) == 32:
                    print(json.dumps({'verified': True, 'commit': args.sha, 'url': base, 'feed_state': center['systemState']}))
                    raise SystemExit(0)
        except (OSError, ValueError, AttributeError):
            pass
        print(f'Waiting for requested revision, attempt {attempt + 1}/{args.attempts}', flush=True)
        if attempt + 1 < args.attempts:
            time.sleep(10)
    raise SystemExit('Requested deployment revision was not verified.')
