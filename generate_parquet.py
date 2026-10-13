"""
generate_parquet.py
Phronesis Screener — Génération du fichier de données principal.

Pipeline :
    1. Récupère les données de ~1800 tickers multi-bourses via yfinance
    2. Enrichit avec les données BRVM (PDF officiel + historique local)
    3. Sauvegarde le tout dans data/latest.parquet

Modes :
    - python generate_parquet.py --test   → ~50 tickers (test rapide, ~2 min)
    - python generate_parquet.py          → liste complète (~30-45 min)
"""

import sys
import io

# --- Force UTF-8 pour la sortie console (Windows cp1252 fix) ---
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
import time
import os
import logging
from datetime import datetime

from tickers_lists import (
    US_EXTRAS, EUROPE_TICKERS, ASIA_TICKERS, AFRICA_TICKERS,
    ETF_TICKERS, CRYPTO_TICKERS, FOREX_TICKERS, COMMODITY_TICKERS,
    build_all_tickers,
)
from screener.brvm_fetcher import enrich_with_brvm_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ---------------------------------------------------------------------------
# TABLE DE CLASSIFICATION (suffixe → asset_type, exchange)
# ---------------------------------------------------------------------------

# Ensemble des tickers ETF (US + International) — maintenir en cohérence avec tickers_lists
ETF_TICKERS_SET = {
    # US broad market
    "SPY", "QQQ", "IVV", "VOO", "VTI", "VT", "ITOT", "SCHB", "RSP", "SPLG",
    # Obligations
    "BND", "AGG", "TLT", "IEF", "SHY", "LQD", "HYG", "JNK", "MUB", "BIL",
    "VCIT", "VCSH", "EMB", "TIP", "GOVT", "SCHZ", "IGSB", "SPSB",
    # Or & matières premières
    "GLD", "IAU", "SLV", "USO", "UNG", "DBA", "DBC", "PPLT", "PALL",
    "GDX", "GDXJ", "SIL", "COPX", "URA", "LIT", "REMX", "XME",
    # International
    "EEM", "VWO", "IEMG", "EWZ", "FXI", "MCHI", "KWEB", "CQQQ", "EFA",
    "VGK", "EWJ", "DXJ", "INDA", "SMIN", "EWT", "EWY", "EWW", "EWC",
    "EZU", "IEV", "FEZ", "EWG", "EWQ", "EWU", "EWL", "EWI", "EWP", "EWD",
    "EWN", "EWK", "EPOL", "TUR", "EZA", "EIS", "AFK", "NGE",
    # Sectoriels US
    "XLE", "XLF", "XLK", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE",
    "XLC", "VDE", "VFH", "VGT", "VHT", "VIS", "VCR", "VDC", "VPU", "VAW",
    "IYE", "IYF", "IYW", "IYH", "IYJ", "IYC", "IYK", "IDU", "IYM", "IYR",
    # Biotech & Santé
    "IBB", "XBI", "LABU", "LABD", "IHI", "XHE", "PPH", "FBT",
    # Tech & Semi
    "SMH", "SOXX", "IGV", "FTEC", "CIBR", "HACK", "BOTZ", "ROBO",
    "ARKK", "ARKW", "ARKG", "ARKF", "ARKQ", "ARKX",
    # Small/Mid caps
    "VTWO", "IWM", "IJH", "IJR", "VB", "VO", "VBR", "VBK", "IWO", "IWN",
    "MDY", "IJJ", "IJK", "SLY", "SCHM", "SCHA",
    # Dividendes
    "VYM", "VIG", "SCHD", "DVY", "HDV", "SPHD", "SDY", "DGRO", "NOBL",
    # Thématiques
    "QCLN", "ICLN", "TAN", "FAN", "PBW", "ACES", "ESGU", "ESGV", "SUSA",
    # Emerging & Frontier
    "FM", "FRDM", "EEMS", "VSS", "SCZ", "GWX", "DGS", "DEM", "DVYE",
}

SUFFIX_TO_TYPE = {
    # Europe
    ".PA": ("Action", "EURONEXT_PARIS"),
    ".DE": ("Action", "XETRA"),
    ".L":  ("Action", "LSE"),
    ".MI": ("Action", "BORSA_ITALIANA"),
    ".MC": ("Action", "BME"),
    ".AS": ("Action", "EURONEXT_AMSTERDAM"),
    ".BR": ("Action", "EURONEXT_BRUSSELS"),
    ".SW": ("Action", "SIX"),
    ".LS": ("Action", "EURONEXT_LISBON"),
    ".ST": ("Action", "NASDAQ_STOCKHOLM"),
    ".CO": ("Action", "NASDAQ_COPENHAGEN"),
    ".OL": ("Action", "OSLO"),
    ".HE": ("Action", "NASDAQ_HELSINKI"),
    ".IR": ("Action", "EURONEXT_DUBLIN"),
    ".VI": ("Action", "WIENER_BORSE"),
    ".WA": ("Action", "GPW_WARSAW"),
    ".AT": ("Action", "ATHEX"),
    # Asie
    ".T":  ("Action", "TSE"),
    ".SS": ("Action", "SSE"),
    ".SZ": ("Action", "SZSE"),
    ".HK": ("Action", "HKEX"),
    ".NS": ("Action", "NSE_INDIA"),
    ".KS": ("Action", "KRX"),
    ".TW": ("Action", "TWSE"),
    ".SI": ("Action", "SGX"),
    ".JK": ("Action", "IDX"),
    ".KL": ("Action", "BURSA_MALAYSIA"),
    ".BK": ("Action", "SET_THAILAND"),
    ".PS": ("Action", "PSE_PHILIPPINES"),
    ".AX": ("Action", "ASX"),
    ".NZ": ("Action", "NZX"),
    # Afrique
    ".JO": ("Action", "JSE"),
    ".NG": ("Action", "NGX"),
    ".MA": ("Action", "CSE_MOROCCO"),
    ".CA": ("Action", "EGX"),
    ".NK": ("Action", "NSE_KENYA"),
    ".GH": ("Action", "GSE_GHANA"),
    ".TN": ("Action", "BVMT"),
    ".MU": ("Action", "SEM_MAURITIUS"),
    ".BW": ("Action", "BSE_BOTSWANA"),
    # Crypto
    "-USD": ("Crypto", "CRYPTO"),
    # Forex
    "=X":  ("Forex", "FOREX"),
    # Commodités
    "=F":  ("Commodité", "COMMODITY"),
}


def _classify_ticker(ticker: str) -> tuple[str, str]:
    """Détermine (asset_type, exchange) à partir du ticker."""
    # ETF : liste explicite
    if ticker in ETF_TICKERS_SET:
        return "ETF", "US_ETF"

    # Détection par suffixe (ordre du dict préservé — tester les suffixes longs en premier)
    for suffix, (atype, exchange) in SUFFIX_TO_TYPE.items():
        if ticker.endswith(suffix):
            return atype, exchange

    # Par défaut : action US
    return "Action", "US"


# ---------------------------------------------------------------------------
# INDICATEURS TECHNIQUES
# ---------------------------------------------------------------------------

def _calc_rsi(closes: pd.Series, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    rsi = 100 - 100 / (1 + rs)
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0


def _calc_momentum(closes: pd.Series, periods: int) -> float:
    if len(closes) < periods + 1:
        return 0.0
    try:
        return float((closes.iloc[-1] / closes.iloc[-periods - 1] - 1) * 100)
    except Exception:
        return 0.0


def _safe(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if f != f or abs(f) > 1e15:
            return None
        return round(f, 4)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# FETCH TICKER
# ---------------------------------------------------------------------------

def fetch_ticker(ticker: str) -> dict | None:
    """Récupère les données complètes d'un ticker via yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("ask")
            or info.get("bid")
            or 0
        )
        if not price or price == 0:
            return None

        hist = t.history(period="3mo", interval="1d")
        if hist.empty or len(hist) < 5:
            return None

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

        # --- Classification automatique ---
        asset_type, exchange = _classify_ticker(ticker)

        closes = hist["Close"]
        volumes = hist["Volume"] if "Volume" in hist.columns else pd.Series([0])

        rsi = _calc_rsi(closes, 14)
        mom_1m = _calc_momentum(closes, 22)
        mom_3m = _calc_momentum(closes, len(closes) - 1)
        volatility = float(closes.pct_change().dropna().std() * (252 ** 0.5) * 100) if len(closes) > 1 else 0.0
        rolling_max = closes.cummax()
        drawdown = float(((closes - rolling_max) / rolling_max).min() * 100)
        vol_avg_20 = float(volumes.tail(20).mean()) if len(volumes) >= 20 else 0

        return {
            "ticker":      ticker,
            "name":        short_name,
            "asset_type":  asset_type,
            "exchange":    exchange,
            "market":      exchange,
            "sector":      sector,
            "currency":    currency,
            "price":       round(float(price), 4),
            "market_cap":  market_cap,
            "pe":          _safe(pe),
            "pb":          _safe(pb),
            "roe":         _safe(roe),
            "debt_eq":     _safe(debt_eq),
            "fcf":         fcf,
            "eps":         _safe(eps),
            "bvps":        _safe(bvps),
            "ev_ebitda":   _safe(ev_ebitda),
            "revenue":     revenue,
            "rsi":         round(rsi, 1),
            "momentum_1m": round(mom_1m, 2),
            "momentum_3m": round(mom_3m, 2),
            "volatility":  round(volatility, 1),
            "drawdown":    round(drawdown, 1),
            "vol_avg_20":  round(vol_avg_20, 0),
            "hist_closes": closes.tail(60).tolist(),
            "hist_dates":  [str(d.date()) for d in closes.tail(60).index],
        }
    except Exception as e:
        logging.debug(f"   ⚠️ {ticker} : {e}")
        return None


# ---------------------------------------------------------------------------
# BATCH FETCH
# ---------------------------------------------------------------------------

def fetch_batch(tickers: list, delay: float = 1.0) -> pd.DataFrame:
    """Récupère les données de tous les tickers avec pause anti-blocage."""
    rows = []
    total = len(tickers)
    errors = 0

    for idx, tk in enumerate(tickers, 1):
        data = fetch_ticker(tk)
        if data:
            rows.append(data)
        else:
            errors += 1

        if idx % 10 == 0 or idx == total:
            logging.info(f"   → Progression : {idx}/{total} ({len(rows)} OK, {errors} échecs)")

        time.sleep(delay)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# CONSTRUCTION DE LA LISTE DE TICKERS
# ---------------------------------------------------------------------------

def build_ticker_list(test_mode: bool = False) -> list:
    """Construit la liste finale des tickers (test réduit ou complet)."""
    if test_mode:
        test_tickers = [
            # US (10)
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM", "JNJ", "V",
            # Europe (10)
            "AIR.PA", "SAN.PA", "SAP.DE", "SIEM.DE", "HSBA.L", "SHEL.L",
            "ASML.AS", "NESN.SW", "ENEL.MI", "SAN.MC",
            # Asie (10)
            "9984.T", "6758.T", "0700.HK", "9988.HK", "RELIANCE.NS",
            "TCS.NS", "2330.TW", "005930.KS", "BHP.AX", "D05.SI",
            # Afrique (10)
            "NPN.JO", "SBK.JO", "MTN.JO", "DANGCEM.NG", "ZENITHBANK.NG",
            "ATW.MA", "CIB.CA", "EQTY.NK", "GCB.GH", "BIAT.TN",
            # ETF (5)
            "SPY", "QQQ", "GLD", "TLT", "EEM",
            # Crypto (5)
            "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD",
            # Forex (3)
            "EURUSD=X", "GBPUSD=X", "USDJPY=X",
            # Commodités (3)
            "GC=F", "CL=F", "NG=F",
        ]
        logging.info(f"🧪 Mode TEST : {len(test_tickers)} tickers sélectionnés")
        return test_tickers

    logging.info("🚀 Mode COMPLET : construction de la liste des 1800+ tickers")
    return build_all_tickers(include_dynamic=True)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    test_mode = "--test" in sys.argv
    delay = 0.3 if test_mode else 1.0

    print("=" * 60)
    print(f"Phronesis Screener - Generation du Parquet")
    print(f"Mode : {'TEST (reduit)' if test_mode else 'COMPLET'}")
    print(f"Demarre a : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # --- Étape 1 : construire la liste ---
    tickers = build_ticker_list(test_mode=test_mode)
    logging.info(f"📋 {len(tickers)} tickers à traiter")

    # --- Étape 2 : fetch yfinance ---
    logging.info("📊 Récupération des données yfinance...")
    df = fetch_batch(tickers, delay=delay)
    logging.info(f"✅ yfinance : {len(df)} tickers récupérés")

    # --- Étape 3 : enrichissement BRVM ---
    logging.info("📊 Enrichissement avec les données BRVM...")
    df = enrich_with_brvm_data(df)
    brvm_count = len(df[df["exchange"] == "BRVM"]) if "exchange" in df.columns and not df.empty else 0
    logging.info(f"✅ BRVM : {brvm_count} actifs ajoutés")

    # --- Étape 4 : sauvegarde ---
    os.makedirs("data", exist_ok=True)
    output_path = "data/latest.parquet"
    df.to_parquet(output_path, index=False)

    size_kb = os.path.getsize(output_path) / 1024
    print("=" * 60)
    print(f"Parquet genere : {output_path}")
    print(f"   - {len(df)} actifs au total")
    print(f"   - {brvm_count} actifs BRVM")
    print(f"   - Taille : {size_kb:.1f} Ko")
    print(f"   - Termine a : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Répartition par type d'actif
    if not df.empty and "asset_type" in df.columns:
        print("\nRepartition par type :")
        for atype, count in df["asset_type"].value_counts().items():
            print(f"   - {atype:<12} : {count}")

    # Aperçu
    if not df.empty:
        print("\nApercu :")
        cols = ["ticker", "name", "price", "asset_type", "exchange"]
        cols = [c for c in cols if c in df.columns]
        print(df[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()