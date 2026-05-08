"""
screener/scoring.py
Phronesis Score = Value(25) + Quality(25) + Momentum(25) + Risk(25)
Score total : 0 → 100
"""

import pandas as pd
from screener.valuation import compute_fair_value, upside_pct


# ---------------------------------------------------------------------------
# COMPOSANTES DU SCORE
# ---------------------------------------------------------------------------

def score_value(row: dict) -> float:
    """
    Score Valeur — 0 à 25 pts
    Mesure si l'actif est sous-évalué par rapport à sa valeur intrinsèque.
    """
    score = 0.0
    asset = row.get("asset_type", "Action")

    fv = row.get("_fair_value")
    price = row.get("price", 0)

    # --- Upside potentiel (12 pts max) ---
    if fv and price > 0:
        up = upside_pct(price, fv)
        if up >= 40:    score += 12
        elif up >= 20:  score += 9
        elif up >= 10:  score += 6
        elif up >= 0:   score += 3
        elif up < -20:  score -= 3  # Fortement surévalué

    # --- P/E (6 pts max) — actions seulement ---
    if asset in ("Action",):
        pe = row.get("pe")
        if pe and pe > 0:
            if pe < 12:   score += 6
            elif pe < 18: score += 4
            elif pe < 25: score += 2
            elif pe > 40: score -= 2

    # --- P/B (4 pts max) — actions + REITs ---
    if asset in ("Action",):
        pb = row.get("pb")
        if pb and pb > 0:
            if pb < 1.0:   score += 4
            elif pb < 1.5: score += 3
            elif pb < 3.0: score += 1
            elif pb > 5.0: score -= 1

    # --- EV/EBITDA (3 pts max) ---
    ev_ebitda = row.get("ev_ebitda")
    if ev_ebitda and ev_ebitda > 0:
        if ev_ebitda < 8:    score += 3
        elif ev_ebitda < 15: score += 1
        elif ev_ebitda > 30: score -= 1

    return max(0.0, min(25.0, score))


def score_quality(row: dict) -> float:
    """
    Score Qualité — 0 à 25 pts
    Mesure la solidité financière de l'entreprise.
    """
    score = 0.0
    asset = row.get("asset_type", "Action")

    if asset in ("Forex", "ETF", "ETF Afrique", "Commodité"):
        return 12.5  # Score neutre pour actifs sans fondamentaux

    # --- ROE (10 pts max) ---
    roe = row.get("roe")
    if roe is not None:
        if roe > 0.25:    score += 10
        elif roe > 0.15:  score += 7
        elif roe > 0.08:  score += 4
        elif roe < 0:     score -= 3

    # --- Dette / Equity (8 pts max) ---
    debt = row.get("debt_eq")
    if debt is not None:
        if debt < 30:     score += 8
        elif debt < 60:   score += 6
        elif debt < 100:  score += 3
        elif debt < 200:  score += 1
        else:             score -= 3

    # --- FCF positif (7 pts max) ---
    fcf = row.get("fcf")
    if fcf is not None:
        if fcf > 5_000_000_000:   score += 7   # > 5Md FCF
        elif fcf > 1_000_000_000: score += 5   # > 1Md FCF
        elif fcf > 0:             score += 3   # FCF positif
        else:                     score -= 2   # FCF négatif

    return max(0.0, min(25.0, score))


def score_momentum(row: dict) -> float:
    """
    Score Momentum — 0 à 25 pts
    Mesure la tendance technique de l'actif.
    Zone idéale : momentum positif modéré + RSI entre 40 et 65.
    """
    score = 0.0

    rsi    = row.get("rsi", 50)
    mom_1m = row.get("momentum_1m", 0)
    mom_3m = row.get("momentum_3m", 0)

    # --- RSI (12 pts max) ---
    if 40 <= rsi <= 60:    score += 12   # Zone neutre idéale
    elif 30 <= rsi < 40:   score += 9    # Légèrement oversold
    elif 60 < rsi <= 70:   score += 7    # Bull momentum
    elif rsi < 30:         score += 5    # Oversold — potentiel rebond
    elif rsi > 75:         score += 2    # Overbought — risque correction

    # --- Momentum 1 mois (8 pts max) ---
    if 2 <= mom_1m <= 10:   score += 8   # Momentum positif sain
    elif 0 <= mom_1m < 2:   score += 5   # Légèrement positif
    elif -5 <= mom_1m < 0:  score += 3   # Légère correction
    elif -15 <= mom_1m < -5: score += 4  # Correction — mean reversion
    elif mom_1m > 20:        score += 3  # Trop fort = risque retournement
    elif mom_1m < -15:       score += 1  # Fort recul

    # --- Momentum 3 mois (5 pts max) ---
    if mom_3m > 5:    score += 5
    elif mom_3m > 0:  score += 3
    elif mom_3m < -15: score -= 1

    return max(0.0, min(25.0, score))


def score_risk(row: dict) -> float:
    """
    Score Risk — 0 à 25 pts (plus le score est élevé, moins le risque est élevé)
    Pénalise les actifs risqués. Score de sécurité.
    """
    score = 25.0  # Commence au maximum, déduit les risques

    volatility = row.get("volatility", 20)
    drawdown   = row.get("drawdown", 0)
    debt       = row.get("debt_eq")
    rsi        = row.get("rsi", 50)
    asset      = row.get("asset_type", "Action")

    # --- Volatilité annualisée ---
    if asset == "Crypto":
        # Crypto : standards plus élevés
        if volatility > 100:   score -= 12
        elif volatility > 60:  score -= 7
        elif volatility > 40:  score -= 3
    else:
        if volatility > 50:    score -= 10
        elif volatility > 35:  score -= 6
        elif volatility > 25:  score -= 3
        elif volatility < 10:  score += 2   # Très stable = bonus

    # --- Drawdown max 3 mois ---
    if drawdown < -40:    score -= 8
    elif drawdown < -25:  score -= 5
    elif drawdown < -15:  score -= 3
    elif drawdown < -8:   score -= 1

    # --- Levier financier ---
    if debt is not None:
        if debt > 300:    score -= 8
        elif debt > 200:  score -= 5
        elif debt > 150:  score -= 2

    # --- RSI extrêmes = risque de retournement ---
    if rsi > 80:     score -= 5
    elif rsi > 75:   score -= 3
    elif rsi < 20:   score -= 3  # Aussi risqué en crash

    return max(0.0, min(25.0, score))


# ---------------------------------------------------------------------------
# LABELS & SIGNAUX
# ---------------------------------------------------------------------------

def get_signal(score: int) -> str:
    if score >= 75: return "Fortement sous-évalué"
    elif score >= 60: return "Sous-évalué"
    elif score >= 45: return "Neutre"
    elif score >= 30: return "Surévalué"
    else: return "Fortement surévalué"


def get_signal_emoji(signal: str) -> str:
    mapping = {
        "Fortement sous-évalué": "🟢",
        "Sous-évalué":           "🔵",
        "Neutre":                "⚪",
        "Surévalué":             "🟠",
        "Fortement surévalué":   "🔴",
    }
    return mapping.get(signal, "⚪")


def get_risk_label(row: dict) -> str:
    debt = row.get("debt_eq") or 0
    rsi  = row.get("rsi", 50)
    vol  = row.get("volatility", 20)
    asset = row.get("asset_type", "")

    risk_pts = 0
    if asset == "Crypto":         risk_pts += 2
    if vol > 50:                  risk_pts += 2
    elif vol > 30:                risk_pts += 1
    if debt and debt > 150:       risk_pts += 2
    elif debt and debt > 80:      risk_pts += 1
    if rsi > 75 or rsi < 25:      risk_pts += 1

    if risk_pts >= 4: return "Très élevé"
    elif risk_pts >= 3: return "Élevé"
    elif risk_pts >= 2: return "Moyen"
    else: return "Faible"


def get_risk_color(risk_label: str) -> str:
    mapping = {
        "Très élevé": "#EF4444",
        "Élevé":      "#F97316",
        "Moyen":      "#EAB308",
        "Faible":     "#10B981",
    }
    return mapping.get(risk_label, "#9CA3AF")


def format_market_cap(mc) -> str:
    if not mc:
        return "—"
    if mc >= 1e12:
        return f"${mc/1e12:.1f}T"
    elif mc >= 1e9:
        return f"${mc/1e9:.1f}Md"
    elif mc >= 1e6:
        return f"${mc/1e6:.0f}M"
    return f"${mc:,.0f}"


# ---------------------------------------------------------------------------
# CALCUL PRINCIPAL
# ---------------------------------------------------------------------------

def compute_phronesis_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule le Phronesis Score pour chaque ligne du DataFrame.
    Ajoute : fair_value, upside_pct, score, signal, risk, composantes.
    """
    if df.empty:
        return df

    records = df.to_dict("records")
    results = []

    for row in records:
        # Pré-calcul fair value (mis en cache dans la row)
        fv = compute_fair_value(row)
        row["_fair_value"] = fv

        # Composantes
        v = score_value(row)
        q = score_quality(row)
        m = score_momentum(row)
        r = score_risk(row)

        total = int(round(v + q + m + r))
        total = max(0, min(100, total))

        price = row.get("price", 0)
        up    = upside_pct(price, fv) if fv else 0.0
        sig   = get_signal(total)

        results.append({
            **row,
            "fair_value":     fv,
            "upside_pct":     up,
            "score":          total,
            "score_value":    round(v, 1),
            "score_quality":  round(q, 1),
            "score_momentum": round(m, 1),
            "score_risk":     round(r, 1),
            "signal":         sig,
            "signal_emoji":   get_signal_emoji(sig),
            "risk":           get_risk_label(row),
            "risk_color":     get_risk_color(get_risk_label(row)),
            "market_cap_fmt": format_market_cap(row.get("market_cap")),
        })

    return pd.DataFrame(results)