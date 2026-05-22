# generate_parquet.py
import yfinance as yf
import pandas as pd
import time
import os

def fetch_batch(tickers, delay=0.3):
    """Récupère les données de base pour chaque ticker."""
    rows = []
    for tk in tickers:
        try:
            ticker = yf.Ticker(tk)
            info = ticker.info
            price = info.get('currentPrice') or info.get('regularMarketPrice') or 0
            if price:
                rows.append({"ticker": tk, "price": price, "name": info.get('shortName', tk)})
            else:
                print(f"⚠️ {tk}: prix non trouvé")
        except Exception as e:
            print(f"❌ {tk}: {e}")
        time.sleep(delay)
    return pd.DataFrame(rows)

def build_ticker_list():
    # S&P 500 (Wikipedia)
    try:
        sp500 = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        tickers = sp500['Symbol'].tolist()
    except Exception:
        print("Erreur chargement S&P 500, utilisation liste partielle")
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM", "JNJ", "V"]
    
    # Nasdaq 100
    try:
        nasdaq100 = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")[4]
        tickers += nasdaq100['Ticker'].tolist()
    except Exception:
        print("Erreur chargement Nasdaq 100")
    
    # ETF
    etf = [
        "SPY", "QQQ", "IVV", "VOO", "VTI", "VT", "BND", "AGG", "TLT", "IEF",
        "LQD", "HYG", "GLD", "IAU", "SLV", "USO", "EEM", "VWO", "EWZ", "FXI",
        "EFA", "VGK", "EWJ", "INDA", "ARKK", "ARKW", "QCLN", "ICLN", "XLE", "XLF",
        "XLK", "XLV", "XLI", "XLY", "XLP", "XLU", "IBB", "XBI", "SMH", "SOXX",
        "VTWO", "IWM", "IJH", "IJR", "EZA", "AFK", "NGE"
    ]
    tickers += etf
    
    # Crypto
    crypto = [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD", "XRP-USD",
        "DOGE-USD", "DOT-USD", "AVAX-USD", "MATIC-USD", "LINK-USD", "LTC-USD",
        "BCH-USD", "UNI-USD", "ATOM-USD", "XLM-USD", "ALGO-USD", "VET-USD",
        "FIL-USD", "ICP-USD", "NEAR-USD", "APT-USD", "ARB-USD", "OP-USD"
    ]
    tickers += crypto
    
    # Forex
    forex = [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X",
        "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "CADJPY=X",
        "CHFJPY=X", "EURCHF=X", "GBPCHF=X"
    ]
    tickers += forex
    
    # Commodities
    commodities = [
        "GC=F", "SI=F", "CL=F", "NG=F", "HO=F", "RB=F", "ZW=F", "ZC=F", "ZS=F",
        "KC=F", "CT=F", "SB=F", "CC=F", "HG=F", "LB=F", "LE=F"
    ]
    tickers += commodities
    
    # Extra
    extra = [
        "NIO", "RIVN", "RKLB", "SOFI", "JOBY", "PLTR", "SNOW", "DDOG", "NET",
        "HOOD", "COIN", "SQ", "SHOP", "ZM", "UBER", "LYFT", "ABNB", "RBLX"
    ]
    tickers += extra
    
    # Dédoublonner et filtrer
    tickers = list(set(tickers))
    tickers = [t for t in tickers if isinstance(t, str) and t != '']
    return tickers

if __name__ == "__main__":
    tickers = build_ticker_list()
    print(f"🔍 Chargement de {len(tickers)} tickers...")
    df = fetch_batch(tickers, delay=0.3)
    os.makedirs("data", exist_ok=True)
    df.to_parquet("data/latest.parquet", index=False)
    print(f"✅ Parquet généré avec {len(df)} actifs dans data/latest.parquet")