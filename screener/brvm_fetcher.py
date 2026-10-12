"""
screener/brvm_fetcher.py
Phronesis Screener — Récupération des données BRVM.

Source : Bulletin Officiel de la Cote (BOC) PDF
URL    : https://bfin.brvm.org/boc/BOC_JOUR/BOC_YYYYMMDD.pdf

IMPORTANT — Décalage de publication :
    Le BOC d'une séance de cotation (date J) n'est mis en ligne que le jour
    ouvré suivant (J+1) à 00h00.

Fonctionnalités :
- Recherche en cascade (J-1, J-2, ... J-5) du dernier BOC disponible
- Saut automatique des week-ends
- Parsing multi-format des tableaux (3 layouts différents dans le BOC)
- Historique local persisté dans data/brvm_history.parquet
- Calcul des indicateurs techniques (RSI, momentum, volatilité, drawdown)
- Amorçage rétroactif de l'historique (bootstrap)
- Enrichissement du DataFrame principal pour le screener
"""

import requests
import pandas as pd
import io
import logging
from datetime import datetime, timedelta
import os
import time
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HISTORY_PATH = "data/brvm_history.parquet"
BOC_URL_TEMPLATE = "https://bfin.brvm.org/boc/BOC_JOUR/BOC_{date}.pdf"

# ---------------------------------------------------------------------------
# CODES OFFICIELS BRVM (tels qu'ils apparaissent dans le BOC)
# ---------------------------------------------------------------------------
BRVM_TICKERS = [
    # Consumer Basic (CB)
    "ABJC", "BNBC", "FTSC", "PALC", "SPHC", "SOGC", "SCRC", "SICC", "STBC", "UNXC",
    # Consumer Disc / Télécoms
    "ONTBF", "ORAC", "SNTS", "TTLC", "TTLS",
    # Financial (FIN)
    "BICC", "BOAB", "BOABF", "BOAC", "BOAM", "BOAN", "BOAS", "CBIBF",
    "ECOC", "ETIT", "NSBC", "SGBC", "SIBC",
    # Industrials (IND)
    "CABC", "CIEC", "SDCC", "SDSC", "SIVC", "STAC",
    # Services Publics (SPU) / Énergie (ENE)
    "SHEC", "SMBC",
    # Autres
    "IBFL", "NEIC", "ORGT", "PRSC", "SLBC",
]

# Codes secteur utilisés par la BRVM dans le BOC (colonne 0 du format "table")
SECTEURS_BOC = {"CB", "CD", "ENE", "FIN", "IND", "SPU", "TEL", "MAT", "AUT"}


# ---------------------------------------------------------------------------
# UTILITAIRES
# ---------------------------------------------------------------------------

def clean_french_number(value) -> float:
    """Convertit un nombre au format français ('1 234,56' ou '12,5%') en float."""
    if value is None or not isinstance(value, str):
        return 0.0
    cleaned = value.strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
    cleaned = cleaned.replace('%', '').replace('(', '').replace(')', '')
    cleaned = re.sub(r'[^0-9.\-]', '', cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def generate_boc_url(date: datetime) -> str:
    return BOC_URL_TEMPLATE.format(date=date.strftime('%Y%m%d'))


# ---------------------------------------------------------------------------
# TÉLÉCHARGEMENT — Recherche en cascade du dernier BOC disponible
# ---------------------------------------------------------------------------

def download_boc_pdf(reference_date: datetime = None, max_days_back: int = 5) -> tuple[bytes | None, datetime | None]:
    if reference_date is None:
        reference_date = datetime.now()

    start_date = reference_date - timedelta(days=1)

    for offset in range(max_days_back):
        candidate_date = start_date - timedelta(days=offset)

        if candidate_date.weekday() >= 5:
            continue

        url = generate_boc_url(candidate_date)
        logging.info(f"📥 Recherche du BOC du {candidate_date.strftime('%Y-%m-%d')}...")

        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and len(resp.content) > 10000:
                logging.info(f"✅ BOC trouvé pour la séance du {candidate_date.strftime('%Y-%m-%d')} ({len(resp.content)} octets)")
                return resp.content, candidate_date
            elif resp.status_code == 404:
                logging.debug(f"   → 404 pour {candidate_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            logging.warning(f"   → Erreur réseau : {e}")

    logging.error(f"❌ Aucun BOC trouvé dans les {max_days_back} derniers jours ouvrés.")
    return None, None


# ---------------------------------------------------------------------------
# PARSING PDF — Gestion des 3 formats BOC
# ---------------------------------------------------------------------------

def _extract_boc_tables(pdf_content: bytes) -> list:
    """Essaie lattice (recommandé pour BOC), puis fallback sur stream."""
    import tabula

    try:
        tables = tabula.read_pdf(
            io.BytesIO(pdf_content),
            pages="all",
            multiple_tables=True,
            lattice=True,
            pandas_options={"header": None},
        )
        total_rows = sum(len(t) for t in tables) if tables else 0
        logging.info(f"🔍 Mode lattice : {len(tables)} tableaux, {total_rows} lignes")
        if total_rows >= 30:
            return tables
    except Exception as e:
        logging.warning(f"Mode lattice échoué : {e}")

    try:
        tables = tabula.read_pdf(
            io.BytesIO(pdf_content),
            pages="all",
            multiple_tables=True,
            stream=True,
            guess=True,
            pandas_options={"header": None},
        )
        logging.info(f"🔍 Mode stream : {len(tables)} tableaux")
        return tables
    except Exception as e:
        logging.error(f"❌ Mode stream échoué : {e}")
        return []


def _parse_boc_row(values: list) -> dict | None:
    """
    Parse une ligne du BOC en testant 3 formats :

    Format A (top variations) :
        "BICI CI (BICC)32 945" → nom + (CODE) + cours collé

    Format B (table principale) :
        [CB] [PALC] [PALM CI] [prec] [ouv] [clot] [var%] [vol] [val] ...

    Format C (marché des actions en bas de page) :
        [ABJC] [SERVAIR ABIDJAN CI] [...] [cours]
    """
    if len(values) < 2:
        return None

    # --- Format B : table principale ---
    if len(values) >= 6:
        sect = str(values[0]).strip().upper()
        code = str(values[1]).strip().upper()
        if sect in SECTEURS_BOC and code in BRVM_TICKERS:
            name = str(values[2]).strip()
            cloture = clean_french_number(str(values[5]))
            volume = 0
            if len(values) > 7:
                vol = clean_french_number(str(values[7]))
                if 1000 < vol < 1e12:
                    volume = int(vol)
            if cloture > 0:
                return {"ticker": code, "name": name, "close": cloture, "volume": volume}

    # --- Format A : "NOM COMPLET (CODE)COURS" ---
    joined = " ".join(str(v) for v in values)
    paren = re.search(r'\(([A-Z]{2,6})\)\s*([\d\s.,]+)', joined)
    if paren:
        code = paren.group(1).strip()
        price = clean_french_number(paren.group(2))
        if price > 0 and code in BRVM_TICKERS:
            return {"ticker": code, "name": code, "close": price, "volume": 0}

    # --- Format C : CODE en col 0, cours à la fin ---
    if len(values) >= 6:
        code = str(values[0]).strip().upper()
        if code in BRVM_TICKERS:
            name = str(values[1]).strip()
            price = 0.0
            for v in reversed(values):
                n = clean_french_number(str(v))
                if 0 < n < 100000:
                    price = n
                    break
            if price > 0:
                return {"ticker": code, "name": name, "close": price, "volume": 0}

    return None


def parse_boc_pdf(pdf_content: bytes) -> pd.DataFrame:
    """Extrait les cours du PDF. Retourne : ticker, name, close, volume."""
    try:
        import tabula  # noqa: F401
    except ImportError:
        logging.error("❌ tabula-py manquant.")
        return pd.DataFrame()

    tables = _extract_boc_tables(pdf_content)
    if not tables:
        return pd.DataFrame()

    non_empty = [t for t in tables if not t.empty]
    if not non_empty:
        return pd.DataFrame()

    merged = pd.concat(non_empty, ignore_index=True)
    merged = merged.fillna("").astype(str).apply(lambda x: x.str.strip())
    logging.info(f"📊 Tableau fusionné : {len(merged)} lignes × {len(merged.columns)} colonnes")

    all_rows = []
    for _, row in merged.iterrows():
        parsed = _parse_boc_row([str(v) for v in row.tolist()])
        if parsed:
            all_rows.append(parsed)

    if not all_rows:
        logging.warning("⚠️ Aucune ligne BRVM parsée")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    # Déduplication : garder la ligne avec le volume le plus élevé (Format B > A/C)
    df = df.sort_values("volume", ascending=False).drop_duplicates(subset="ticker").reset_index(drop=True)
    logging.info(f"✅ {len(df)} tickers BRVM parsés")
    return df


# ---------------------------------------------------------------------------
# HISTORIQUE LOCAL
# ---------------------------------------------------------------------------

def load_history() -> pd.DataFrame:
    if not os.path.exists(HISTORY_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_parquet(HISTORY_PATH)
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        logging.error(f"Erreur chargement historique BRVM : {e}")
        return pd.DataFrame()


def save_history(df: pd.DataFrame) -> None:
    os.makedirs("data", exist_ok=True)
    df.to_parquet(HISTORY_PATH, index=False)
    logging.info(f"💾 Historique BRVM sauvegardé ({len(df)} lignes)")


def update_history() -> pd.DataFrame:
    df_hist = load_history()

    pdf_content, session_date = download_boc_pdf()
    if not pdf_content or not session_date:
        logging.warning("❌ Pas de PDF disponible, historique inchangé")
        return df_hist

    session_date_str = session_date.strftime("%Y-%m-%d")

    if not df_hist.empty:
        already_present = (df_hist["date"] == pd.to_datetime(session_date_str)).any()
        if already_present:
            logging.info(f"ℹ️ La séance du {session_date_str} est déjà dans l'historique")
            return df_hist

    df_new = parse_boc_pdf(pdf_content)
    if df_new.empty:
        return df_hist

    df_new["date"] = session_date_str

    if not df_hist.empty:
        df_hist = pd.concat([df_hist, df_new], ignore_index=True)
    else:
        df_hist = df_new

    df_hist["date"] = pd.to_datetime(df_hist["date"])
    df_hist = df_hist.sort_values(["ticker", "date"]).reset_index(drop=True)
    save_history(df_hist)
    return df_hist


# ---------------------------------------------------------------------------
# AMORÇAGE DE L'HISTORIQUE
# ---------------------------------------------------------------------------

def bootstrap_history(n_days: int = 60, delay: float = 1.0) -> pd.DataFrame:
    logging.info(f"🚀 Amorçage : {n_days} jours ouvrés à récupérer")
    df_hist = load_history()
    existing_dates = set(df_hist["date"].dt.strftime("%Y-%m-%d")) if not df_hist.empty else set()

    today = datetime.now()
    collected = 0
    skipped = 0

    for offset in range(1, n_days * 2):
        if collected >= n_days:
            break
        candidate = today - timedelta(days=offset)
        if candidate.weekday() >= 5:
            continue
        date_str = candidate.strftime("%Y-%m-%d")
        if date_str in existing_dates:
            skipped += 1
            continue

        url = generate_boc_url(candidate)
        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200 or len(resp.content) < 10000:
                continue
            df_day = parse_boc_pdf(resp.content)
            if df_day.empty:
                continue
            df_day["date"] = date_str
            df_hist = pd.concat([df_hist, df_day], ignore_index=True) if not df_hist.empty else df_day
            collected += 1
            if collected % 10 == 0:
                logging.info(f"   → {collected}/{n_days} séances récupérées")
            time.sleep(delay)
        except Exception as e:
            logging.warning(f"   ⚠️ Erreur pour {date_str} : {e}")

    if df_hist.empty:
        logging.error("❌ Aucune donnée collectée")
        return df_hist

    df_hist["date"] = pd.to_datetime(df_hist["date"])
    df_hist = df_hist.drop_duplicates(subset=["ticker", "date"]).sort_values(["ticker", "date"]).reset_index(drop=True)
    save_history(df_hist)
    logging.info(f"✅ Amorçage terminé : {collected} séances, {skipped} déjà présentes, {len(df_hist)} lignes")
    return df_hist


# ---------------------------------------------------------------------------
# INDICATEURS TECHNIQUES
# ---------------------------------------------------------------------------

def compute_technical_indicators(df_hist: pd.DataFrame) -> pd.DataFrame:
    if df_hist.empty:
        return pd.DataFrame()

    results = []
    for ticker in df_hist["ticker"].unique():
        df_t = df_hist[df_hist["ticker"] == ticker].sort_values("date")
        if len(df_t) < 1:
            continue

        closes = df_t["close"]
        dates = df_t["date"]
        price = float(closes.iloc[-1])

        rsi = 50.0
        if len(closes) >= 15:
            delta = closes.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, 1e-9)
            rsi = float(100 - 100 / (1 + rs.iloc[-1]))

        mom_1m = ((closes.iloc[-1] / closes.iloc[-23]) - 1) * 100 if len(closes) >= 23 else 0.0
        mom_3m = ((closes.iloc[-1] / closes.iloc[-67]) - 1) * 100 if len(closes) >= 67 else 0.0

        volatility = (closes.pct_change().dropna().std() * (252 ** 0.5) * 100 if len(closes) > 1 else 0.0)
        rolling_max = closes.cummax()
        drawdown = float(((closes - rolling_max) / rolling_max).min() * 100)

        # Nom lisible : prendre le dernier nom connu (colonne "name" du df_hist)
        name = str(df_t["name"].iloc[-1]) if "name" in df_t.columns else ticker

        results.append({
            "ticker": ticker,
            "name": name,
            "price": round(price, 2),
            "rsi": round(rsi, 1),
            "momentum_1m": round(mom_1m, 2),
            "momentum_3m": round(mom_3m, 2),
            "volatility": round(volatility, 1),
            "drawdown": round(drawdown, 1),
            "hist_closes": closes.tail(60).tolist(),
            "hist_dates": dates.tail(60).dt.strftime("%Y-%m-%d").tolist(),
            "asset_type": "Action",
            "sector": "BRVM",
            "currency": "XOF",
            "exchange": "BRVM",
            "market": "BRVM",
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# ENRICHISSEMENT DU DATAFRAME PRINCIPAL
# ---------------------------------------------------------------------------

def enrich_with_brvm_data(df_existing: pd.DataFrame = None) -> pd.DataFrame:
    df_hist = update_history()
    if df_hist.empty:
        logging.warning("⚠️ Historique BRVM vide")
        return df_existing if df_existing is not None else pd.DataFrame()

    df_brvm = compute_technical_indicators(df_hist)
    if df_brvm.empty:
        return df_existing if df_existing is not None else pd.DataFrame()

    logging.info(f"✅ {len(df_brvm)} actifs BRVM enrichis")

    if df_existing is not None and not df_existing.empty:
        if "exchange" in df_existing.columns:
            df_existing = df_existing[df_existing["exchange"] != "BRVM"]
        df_combined = pd.concat([df_existing, df_brvm], ignore_index=True)
    else:
        df_combined = df_brvm

    return df_combined


# ---------------------------------------------------------------------------
# POINT D'ENTRÉE
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--bootstrap" in sys.argv:
        print("🧪 Amorçage de l'historique BRVM...")
        df = bootstrap_history(n_days=60)
        if not df.empty:
            print(
                f"\n✅ Historique : {len(df)} lignes, "
                f"{df['ticker'].nunique()} tickers, "
                f"du {df['date'].min().date()} au {df['date'].max().date()}"
            )
        else:
            print("❌ Aucune donnée collectée")
    else:
        print("🧪 Test du module BRVM...")
        df = enrich_with_brvm_data()
        if not df.empty:
            brvm = df[df["exchange"] == "BRVM"] if "exchange" in df.columns else df
            print(f"\n✅ {len(brvm)} actifs BRVM récupérés")
            print(brvm[["ticker", "name", "price", "rsi"]].head(15).to_string(index=False))
        else:
            print("❌ Aucune donnée BRVM récupérée")