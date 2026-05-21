"""
screener/data_fetcher.py
Phronesis Screener — couche data 100% gratuite
Sources : yfinance (actions/ETF/forex), CoinGecko (crypto)
Ajout : chargement de données pré-calculées depuis fichier Parquet pour éviter rate-limit.
"""

import yfinance as yf
import pandas as pd
import requests
import time
import os

import os
import pandas as pd

def load_precomputed_data() -> pd.DataFrame:
    """Charge les données depuis data/latest.parquet (généré par GitHub Actions)"""
    filepath = "data/latest.parquet"
    if os.path.exists(filepath):
        return pd.read_parquet(filepath)
    else:
        # Fallback local (si le fichier n'existe pas)
        from .data_fetcher import fetch_batch, get_default_tickers
        return fetch_batch(get_default_tickers())

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

COINGECKO_IDS = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "BNB-USD": "binancecoin",
    "SOL-USD": "solana",
    "ADA-USD": "cardano",
    "XRP-USD": "ripple",
}

ASSET_TYPES = {
    # Actions US
    "AAPL": "Action", "MSFT": "Action", "GOOGL": "Action", "AMZN": "Action",
    "META": "Action", "TSLA": "Action", "BRK-B": "Action", "JPM": "Action",
    "JNJ": "Action", "WMT": "Action", "V": "Action", "MA": "Action",
    "PG": "Action", "UNH": "Action", "HD": "Action", "DIS": "Action",
    "NFLX": "Action", "ADBE": "Action", "CRM": "Action", "NVDA": "Action",
    "AMD": "Action", "INTC": "Action", "CSCO": "Action", "IBM": "Action",
    "ORCL": "Action", "KO": "Action", "PEP": "Action", "COST": "Action",
    "CVX": "Action", "XOM": "Action", "BAC": "Action", "WFC": "Action",
    "C": "Action", "GS": "Action", "MS": "Action", "AXP": "Action",
    "CAT": "Action", "GE": "Action", "BA": "Action", "MMM": "Action",
    "HON": "Action", "UPS": "Action", "FDX": "Action", "NKE": "Action",
    "SBUX": "Action", "MCD": "Action", "CMCSA": "Action", "T": "Action",
    "VZ": "Action", "TMUS": "Action", "ABT": "Action", "TMO": "Action",
    "MRK": "Action", "PFE": "Action", "ABBV": "Action", "LLY": "Action",
    "BMY": "Action", "GILD": "Action", "REGN": "Action", "VRTX": "Action",
    "SPGI": "Action", "BLK": "Action", "SCHW": "Action", "ICE": "Action",
    "DE": "Action", "LMT": "Action", "NOC": "Action", "RTX": "Action",
    "GD": "Action", "LHX": "Action", "ADP": "Action", "PAYX": "Action",
    "CTSH": "Action", "IT": "Action", "AON": "Action", "MMC": "Action",
    "ZTS": "Action", "EW": "Action", "ISRG": "Action", "SYK": "Action",
    "MDT": "Action", "BSX": "Action", "ALGN": "Action", "IDXX": "Action",
    "CHTR": "Action", "ROP": "Action", "SHW": "Action", "PPG": "Action",
    "ECL": "Action", "APD": "Action", "LIN": "Action", "DOW": "Action",
    "DD": "Action", "FCX": "Action", "NEM": "Action", "GDX": "Action",
    "PLTR": "Action", "SNOW": "Action", "DDOG": "Action", "NET": "Action",
    "UBER": "Action", "LYFT": "Action", "ABNB": "Action", "RBLX": "Action",
    "COIN": "Action", "SQ": "Action", "PYPL": "Action", "SHOP": "Action",
    "SPOT": "Action", "ROKU": "Action", "TTD": "Action", "ZS": "Action",
    "MRNA": "Action", "BIIB": "Action", "ILMN": "Action", "WBA": "Action",
    "NIO": "Action","RIVN": "Action","RKLB": "Action","SOFI": "Action",
    # === ETF ===
    "SPY": "ETF", "QQQ": "ETF", "IVV": "ETF", "VOO": "ETF",
    "VTI": "ETF", "VT": "ETF", "BND": "ETF", "AGG": "ETF",
    "TLT": "ETF", "IEF": "ETF", "LQD": "ETF", "HYG": "ETF",
    "GLD": "ETF", "IAU": "ETF", "SLV": "ETF", "USO": "ETF",
    "EEM": "ETF", "VWO": "ETF", "EWZ": "ETF", "FXI": "ETF",
    "EFA": "ETF", "VGK": "ETF", "EWJ": "ETF", "INDA": "ETF",
    "ARKK": "ETF", "ARKW": "ETF", "QCLN": "ETF", "ICLN": "ETF",
    "XLE": "ETF", "XLF": "ETF", "XLK": "ETF", "XLV": "ETF",
    "XLI": "ETF", "XLY": "ETF", "XLP": "ETF", "XLU": "ETF",
    "IBB": "ETF", "XBI": "ETF", "SMH": "ETF", "SOXX": "ETF",
    "VTWO": "ETF", "IWM": "ETF", "IJH": "ETF", "IJR": "ETF",
    "EZA": "ETF Afrique", "AFK": "ETF Afrique", "NGE": "ETF Afrique",
    "FLZA": "ETF Afrique", "DBZA": "ETF Afrique", "GAF": "ETF Afrique",
    # === Crypto ===
    "BTC-USD": "Crypto", "ETH-USD": "Crypto", "BNB-USD": "Crypto",
    "SOL-USD": "Crypto", "ADA-USD": "Crypto", "XRP-USD": "Crypto",
    "DOGE-USD": "Crypto", "DOT-USD": "Crypto", "AVAX-USD": "Crypto",
    "MATIC-USD": "Crypto", "LINK-USD": "Crypto", "LTC-USD": "Crypto",
    "BCH-USD": "Crypto", "UNI-USD": "Crypto", "ATOM-USD": "Crypto",
    "XLM-USD": "Crypto", "ALGO-USD": "Crypto", "VET-USD": "Crypto",
    "FIL-USD": "Crypto", "ICP-USD": "Crypto", "NEAR-USD": "Crypto",
    "APT-USD": "Crypto", "ARB-USD": "Crypto", "OP-USD": "Crypto",
    # === Forex ===
    "EURUSD=X": "Forex", "GBPUSD=X": "Forex", "USDJPY=X": "Forex",
    "USDCHF=X": "Forex", "AUDUSD=X": "Forex", "USDCAD=X": "Forex",
    "NZDUSD=X": "Forex", "EURGBP=X": "Forex", "EURJPY=X": "Forex",
    "GBPJPY=X": "Forex", "AUDJPY=X": "Forex", "CADJPY=X": "Forex",
    "CHFJPY=X": "Forex", "EURCHF=X": "Forex", "GBPCHF=X": "Forex",
    # === Commodités ===
    "GC=F": "Commodité", "SI=F": "Commodité", "CL=F": "Commodité",
    "NG=F": "Commodité", "HO=F": "Commodité", "RB=F": "Commodité",
    "ZW=F": "Commodité", "ZC=F": "Commodité", "ZS=F": "Commodité",
    "KC=F": "Commodité", "CT=F": "Commodité", "SB=F": "Commodité",
    "CC=F": "Commodité", "HG=F": "Commodité", "LB=F": "Commodité",
    "LE=F": "Commodité",
}

DISPLAY_NAMES = {
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY", "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD",
    "GC=F": "Or (Gold)", "SI=F": "Argent (Silver)",
    "CL=F": "Pétrole (WTI)", "NG=F": "Gaz Naturel",
    "EZA": "ETF Afrique Sud", "AFK": "ETF Afrique",
    "NGE": "ETF Nigeria",
}

# ---------------------------------------------------------------------------
# FONCTION POUR CHARGER LES DONNÉES PRÉ-CALCULÉES (via GitHub Actions)
# ---------------------------------------------------------------------------
def load_precomputed_data() -> pd.DataFrame:
    """
    Charge les données depuis data/latest.parquet (généré par GitHub Actions).
    Si le fichier n'existe pas (développement local), utilise fetch_batch sur une liste réduite.
    """
    filepath = "data/latest.parquet"
    if os.path.exists(filepath):
        df = pd.read_parquet(filepath)
        return df
    else:
        # Fallback pour le développement local
        from .data_fetcher import fetch_batch, get_default_tickers
        return fetch_batch(get_default_tickers())

# ---------------------------------------------------------------------------
# FETCH SINGLE TICKER (yfinance) - conservé pour usage éventuel
# ---------------------------------------------------------------------------
def fetch_ticker(ticker: str) -> dict | None:
    """
    Récupère toutes les données nécessaires pour un ticker via yfinance.
    Retourne None si le ticker est invalide ou les données manquantes.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info

        # Prix courant (plusieurs fallbacks)
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("ask")
            or info.get("bid")
            or 0
        )
        if not price or price == 0:
            return None

        # Historique 3 mois pour calculs techniques
        hist = t.history(period="3mo", interval="1d")
        if hist.empty or len(hist) < 5:
            return None

        # --- Fondamentaux ---
        pe         = info.get("trailingPE")
        pb         = info.get("priceToBook")
        roe        = info.get("returnOnEquity")
        debt_eq    = info.get("debtToEquity")
        fcf        = info.get("freeCashflow")
        eps        = info.get("trailingEps")
        bvps       = info.get("bookValue")
        ev_ebitda  = info.get("enterpriseToEbitda")
        revenue    = info.get("totalRevenue")
        market_cap = info.get("marketCap")
        sector     = info.get("sector", "—")
        short_name = info.get("shortName", ticker)
        currency   = info.get("currency", "USD")

        # --- Indicateurs techniques ---
        closes = hist["Close"]
        volumes = hist["Volume"] if "Volume" in hist.columns else pd.Series([0])

        # RSI 14 jours
        rsi = _calc_rsi(closes, 14)

        # Momentum
        mom_1m = _calc_momentum(closes, 22)
        mom_3m = _calc_momentum(closes, len(closes) - 1)

        # Volatilité annualisée
        volatility = float(closes.pct_change().dropna().std() * (252 ** 0.5) * 100)

        # Drawdown max 3 mois
        rolling_max = closes.cummax()
        drawdown = float(((closes - rolling_max) / rolling_max).min() * 100)

        # Volume moyen 20j
        vol_avg_20 = float(volumes.tail(20).mean()) if len(volumes) >= 20 else 0

        return {
            "ticker":      ticker,
            "name":        DISPLAY_NAMES.get(ticker, short_name),
            "asset_type":  ASSET_TYPES.get(ticker, "Action"),
            "sector":      sector,
            "currency":    currency,
            "price":       round(float(price), 4),
            "market_cap":  market_cap,
            # Fondamentaux
            "pe":          _safe(pe),
            "pb":          _safe(pb),
            "roe":         _safe(roe),
            "debt_eq":     _safe(debt_eq),
            "fcf":         fcf,
            "eps":         _safe(eps),
            "bvps":        _safe(bvps),
            "ev_ebitda":   _safe(ev_ebitda),
            "revenue":     revenue,
            # Techniques
            "rsi":         round(rsi, 1),
            "momentum_1m": round(mom_1m, 2),
            "momentum_3m": round(mom_3m, 2),
            "volatility":  round(volatility, 1),
            "drawdown":    round(drawdown, 1),
            "vol_avg_20":  round(vol_avg_20, 0),
            # Historique pour graphiques
            "hist_closes": closes.tail(60).tolist(),
            "hist_dates":  [str(d.date()) for d in closes.tail(60).index],
        }
    except Exception:
        return None

# ---------------------------------------------------------------------------
# FETCH BATCH (avec délai) - conservé pour fallback local
# ---------------------------------------------------------------------------
def fetch_batch(tickers: list, delay: float = 0.5) -> pd.DataFrame:
    """
    Fetche une liste de tickers avec délai pour éviter le rate-limit yfinance.
    """
    rows = []
    for tk in tickers:
        data = fetch_ticker(tk)
        if data:
            rows.append(data)
        time.sleep(delay)
    return pd.DataFrame(rows) if rows else pd.DataFrame()

# ---------------------------------------------------------------------------
# CRYPTO via CoinGecko (données supplémentaires NVT proxy)
# ---------------------------------------------------------------------------
def fetch_crypto_metrics(ticker: str) -> dict:
    """
    Récupère market_cap, volume 24h via CoinGecko pour proxy NVT.
    NVT = Market Cap / Volume 24h (simplifié)
    """
    cg_id = COINGECKO_IDS.get(ticker)
    if not cg_id:
        return {}
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{cg_id}?localization=false&tickers=false&community_data=false&developer_data=false"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        mkt = data.get("market_data", {})
        mc  = mkt.get("market_cap", {}).get("usd", 0)
        vol = mkt.get("total_volume", {}).get("usd", 1)
        nvt = round(mc / vol, 2) if vol > 0 else None
        return {
            "nvt":             nvt,
            "circulating_supply": mkt.get("circulating_supply"),
            "ath":             mkt.get("ath", {}).get("usd"),
            "ath_change_pct":  mkt.get("ath_change_percentage", {}).get("usd"),
        }
    except Exception:
        return {}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def get_default_tickers():
    """Liste de tickers par défaut (utilisée en fallback)."""
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META",
        "JPM", "JNJ", "V", "NVDA", "TSLA",
        "NIO", "RIVN", "RKLB", "SOFI",
        "SPY", "QQQ", "GLD",
        "BTC-USD", "ETH-USD",
        "EURUSD=X", "GBPUSD=X",
        "GC=F",
    ]

def _calc_rsi(closes: pd.Series, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    delta = closes.diff().dropna()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, 1e-9)
    rsi   = 100 - 100 / (1 + rs)
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0

def _calc_momentum(closes: pd.Series, periods: int) -> float:
    if len(closes) < periods + 1:
        return 0.0
    try:
        return float((closes.iloc[-1] / closes.iloc[-periods - 1] - 1) * 100)
    except Exception:
        return 0.0

def _safe(val) -> float | None:
    """Retourne None si la valeur est invalide (inf, nan, None)."""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f or abs(f) > 1e15:  # NaN ou inf
            return None
        return round(f, 4)
    except Exception:
        return None
    
    
