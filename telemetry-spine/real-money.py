import requests, time, json
print("REAL LIFE MONEY TRACKER - live prices")
while True:
    try:
        r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=10)
        btc = r.json()['data']['amount']
        print(f"{time.ctime()} REAL BTC: ${btc} | log -> REAL.log")
        with open("REAL.log","a") as f:
            f.write(f"{time.ctime()} BTC ${btc}\n")
    except Exception as e:
        print(f"error {e} retrying")
    time.sleep(30)
