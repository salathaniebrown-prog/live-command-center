#!/usr/bin/env python3
import time, sys, urllib.request, json

def fetch_crypto_price(coin_id):
    """Fetches high-fidelity spot values from decentralized asset pools."""
    try:
        url = f"https://coingecko.com{coin_id}&vs_currencies=usd"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=5).read().decode()
        return float(json.loads(res)[coin_id]['usd'])
    except:
        return None

def fetch_stock_price(ticker):
    """Queries open equity pricing indices for global market frames."""
    try:
        url = f"https://yahoo.com{ticker}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=5).read().decode()
        data = json.loads(res)
        return float(data['chart']['result'][0]['meta']['regularMarketPrice'])
    except:
        return None

def render_dashboard():
    CYAN, GREEN, GOLD, RED, RESET = "\033[1;36m", "\033[1;32m", "\033[1;33m", "\033[1;31m", "\033[0m"
    
    # Define tracking profile targets
    assets = {
        "BTC": ("bitcoin", "crypto"),
        "ETH": ("ethereum", "crypto"),
        "SOL": ("solana", "crypto"),
        "TSLA": ("TSLA", "stock"),
        "NVDA": ("NVDA", "stock"),
        "AAPL": ("AAPL", "stock")
    }
    
    # Store historic frames to measure immediate delta direction trends
    last_prices = {}
    print("\033[?25l") # Suppress blinking block cursor
    
    try:
        while True:
            sys.stdout.write("\033[H\033[J")
            sys.stdout.write(f"{CYAN}+-----------------------------------------------------------+{RESET}\n")
            sys.stdout.write(f"{CYAN}|{RESET}     JARVIS SOVEREIGN INTERNET MARKET DATA TICKER DISPLAY  {CYAN}|{RESET}\n")
            sys.stdout.write(f"{CYAN}+-----------------------------------------------------------+{RESET}\n")
            sys.stdout.write(f" TIMESTAMP RECORD LEDGER: {GOLD}{time.strftime('%Y-%m-%d %X')}{RESET}\n\n")
            
            for symbol, (target, asset_type) in assets.items():
                current = fetch_crypto_price(target) if asset_type == "crypto" else fetch_stock_price(target)
                
                if current is not None:
                    prev = last_prices.get(symbol, current)
                    delta = current - prev
                    trend = f"{GREEN}▲" if delta > 0 else (f"{RED}▼" if delta < 0 else " ")
                    color = GREEN if delta >= 0 else RED
                    
                    # Format pricing matrices cleanly based on scale
                    price_str = f"${current:,.2f}" if current >= 1 else f"${current:.4f}"
                    sys.stdout.write(f"  [{GOLD}{symbol:5s}{RESET}] -> Price: {color}{price_str:14s}{RESET} {trend}\n")
                    last_prices[symbol] = current
                else:
                    sys.stdout.write(f"  [{GOLD}{symbol:5s}{RESET}] -> Connection sync pending...\n")
            
            sys.stdout.write(f"\n{CYAN}+-----------------------------------------------------------+{RESET}\n")
            sys.stdout.write("  [ Streaming Live Data Profiles via Public API Matrix Loops ]\n")
            sys.stdout.flush()
            time.sleep(6) # Rate limit security safety buffer window
            
    except KeyboardInterrupt:
        print("\033[?25h\n[-] Market data streaming core suspended.")

if __name__ == "__main__":
    render_dashboard()
