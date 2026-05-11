"""
screener/valuation.py
Phronesis Screener — moteur de valorisation multi-actifs v2
────────────────────────────────────────────────────────────
MODIFICATION : suppression du plafonnement ±60% et suppression du Graham Number.
Garde : P/E sectoriel, Graham Formula, DCF.
"""

import math

# PER sectoriels (inchangés)
SECTOR_PE = {
    "Technology":               28.0,
    "Communication Services":   22.0,
    "Consumer Cyclical":        20.0,
    "Consumer Defensive":       22.0,
    "Healthcare":               20.0,
    "Financial Services":       13.0,
    "Industrials":              18.0,
    "Basic Materials":          15.0,
    "Real Estate":              35.0,
    "Utilities":                17.0,
    "Energy":                   12.0,
    "ETF":                      18.0,
    "Crypto":                   None,
    "Forex":                    None,
    "Commodité":                None,
}

SECTOR_GROWTH = {
    "Technology":               0.10,
    "Communication Services":   0.08,
    "Consumer Cyclical":        0.07,
    "Consumer Defensive":       0.05,
    "Healthcare":               0.08,
    "Financial Services":       0.06,
    "Industrials":              0.06,
    "Basic Materials":          0.04,
    "Real Estate":              0.04,
    "Utilities":                0.03,
    "Energy":                   0.04,
}

# ---------------------------------------------------------------------------
# MÉTHODE 1 — Multiple EPS sectoriel
# ---------------------------------------------------------------------------
def fair_value_pe_multiple(eps: float, sector: str, pe_override: float = None) -> float | None:
    if not eps or eps <= 0:
        return None
    pe = pe_override or SECTOR_PE.get(sector, 18.0)
    if not pe:
        return None
    return round(eps * pe, 2)

# ---------------------------------------------------------------------------
# MÉTHODE 2 — Graham Formula sectorielle
# ---------------------------------------------------------------------------
def graham_formula(eps: float, sector: str = "Technology", risk_free: float = 0.044) -> float | None:
    if not eps or eps <= 0:
        return None
    g = SECTOR_GROWTH.get(sector, 0.06) * 100
    return round(eps * (8.5 + 2 * g) * (4.4 / (risk_free * 100)), 2)

# ---------------------------------------------------------------------------
# MÉTHODE 3 — DCF simplifié (FCF-based)
# ---------------------------------------------------------------------------
def dcf_simple(fcf: float, shares: float, sector: str = "Technology",
               wacc: float = 0.09, terminal_growth: float = 0.025, years: int = 10) -> float | None:
    if not fcf or not shares or fcf <= 0 or shares <= 0:
        return None
    growth = SECTOR_GROWTH.get(sector, 0.06)
    pv = 0.0
    cf = float(fcf)
    for i in range(1, years + 1):
        cf *= (1 + growth)
        pv += cf / ((1 + wacc) ** i)
    terminal_value = cf * (1 + terminal_growth) / (wacc - terminal_growth)
    pv += terminal_value / ((1 + wacc) ** years)
    return round(pv / shares, 2)

# ---------------------------------------------------------------------------
# COMPOSITE ACTIONS (sans plafonnement, sans Graham Number)
# ---------------------------------------------------------------------------
def compute_fair_value_action(row: dict) -> float | None:
    eps    = row.get("eps")
    sector = row.get("sector", "Technology")
    fcf    = row.get("fcf")
    shares = row.get("shares_outstanding") or _estimate_shares(row)

    candidates = []
    weights    = []

    # P/E multiple sectoriel
    fv_pe = fair_value_pe_multiple(eps, sector)
    if fv_pe and fv_pe > 0:
        candidates.append(fv_pe)
        weights.append(0.45)

    # Graham Formula sectorielle
    fv_gf = graham_formula(eps, sector)
    if fv_gf and fv_gf > 0:
        candidates.append(fv_gf)
        weights.append(0.25)

    # DCF si disponible
    fv_dcf = dcf_simple(fcf, shares, sector) if shares else None
    if fv_dcf and fv_dcf > 0:
        candidates.append(fv_dcf)
        weights.append(0.30)
    # NOTA : plus de fallback Graham Number → pas de troisième pilier si pas de DCF

    if not candidates:
        return None

    total_w = sum(weights)
    normalized = [w / total_w for w in weights]
    fv_composite = sum(v * w for v, w in zip(candidates, normalized))

    # Plus de plafonnement à ±60% → on retourne la valeur brute
    return round(fv_composite, 2)

def _estimate_shares(row: dict) -> float | None:
    mc = row.get("market_cap")
    price = row.get("price", 0)
    if mc and price and price > 0:
        return mc / price
    return None

# ---------------------------------------------------------------------------
# ETF, CRYPTO, FOREX, COMMODITÉS (inchangés)
# ---------------------------------------------------------------------------
def compute_fair_value_etf(row: dict) -> float | None:
    return None

def compute_fair_value_crypto(row: dict) -> float | None:
    nvt = row.get("nvt")
    price = row.get("price", 0)
    if not price:
        return None
    multiplier = None
    if nvt:
        if nvt < 20:     multiplier = 1.35
        elif nvt < 40:   multiplier = 1.15
        elif nvt < 65:   multiplier = 1.00
        elif nvt < 100:  multiplier = 0.88
        else:            multiplier = 0.72
    if multiplier is None:
        mom = row.get("momentum_1m", 0)
        if mom < -25:   multiplier = 1.20
        elif mom < -15: multiplier = 1.10
        elif mom > 30:  multiplier = 0.85
        else:           return None
    fv = round(price * multiplier, 2)
    # Crypto conserve un petit cap à ±40% (car très volatil)
    fv = max(price * 0.60, min(price * 1.40, fv))
    return fv

def compute_fair_value_forex(row: dict) -> float | None:
    price = row.get("price", 0)
    mom_1m = row.get("momentum_1m", 0)
    mom_3m = row.get("momentum_3m", 0)
    if not price:
        return None
    if mom_1m < -3 and mom_3m < -6:
        fv = price * 1.04
    elif mom_1m > 3 and mom_3m > 6:
        fv = price * 0.96
    else:
        return None
    fv = max(price * 0.92, min(price * 1.08, fv))
    return round(fv, 5)

def compute_fair_value_commodity(row: dict) -> float | None:
    price = row.get("price", 0)
    drawdown = row.get("drawdown", 0)
    rsi = row.get("rsi", 50)
    mom_1m = row.get("momentum_1m", 0)
    if not price:
        return None
    if drawdown < -20 and rsi < 35:
        fv = price * 1.22
    elif drawdown < -12 and rsi < 45:
        fv = price * 1.10
    elif rsi > 75 and mom_1m > 15:
        fv = price * 0.88
    else:
        return None
    fv = max(price * 0.75, min(price * 1.25, fv))
    return round(fv, 2)

# ---------------------------------------------------------------------------
# DISPATCHER
# ---------------------------------------------------------------------------
def compute_fair_value(row: dict) -> float | None:
    asset_type = row.get("asset_type", "Action")
    if asset_type == "Crypto":
        return compute_fair_value_crypto(row)
    elif asset_type == "Forex":
        return compute_fair_value_forex(row)
    elif asset_type == "Commodité":
        return compute_fair_value_commodity(row)
    elif asset_type in ("ETF", "ETF Afrique"):
        return compute_fair_value_etf(row)
    else:
        return compute_fair_value_action(row)

def upside_pct(price: float, fair_value: float) -> float:
    if price and price > 0 and fair_value and fair_value > 0:
        return round((fair_value / price - 1) * 100, 1)
    return 0.0