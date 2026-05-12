"""
screener/valuation.py
Phronesis Screener — moteur de valorisation multi-actifs v9
Avec garde-fou pivot average, détection EPS invalide, et retour None au lieu de NaN.
"""

import math
from typing import Optional, Dict, Any

# ---------------------------------------------------------------------------
# CONSTANTES SECTORIELLES
# ---------------------------------------------------------------------------
SECTOR_PE = {
    "Technology": 28.0, "Communication Services": 22.0, "Consumer Cyclical": 20.0,
    "Consumer Defensive": 22.0, "Healthcare": 20.0, "Financial Services": 13.0,
    "Industrials": 18.0, "Basic Materials": 15.0, "Real Estate": 35.0,
    "Utilities": 17.0, "Energy": 12.0, "ETF": 18.0,
    "Crypto": None, "Forex": None, "Commodité": None,
}

SECTOR_GROWTH = {
    "Technology": 0.10, "Communication Services": 0.08, "Consumer Cyclical": 0.07,
    "Consumer Defensive": 0.05, "Healthcare": 0.08, "Financial Services": 0.06,
    "Industrials": 0.06, "Basic Materials": 0.04, "Real Estate": 0.04,
    "Utilities": 0.03, "Energy": 0.04,
}

# ---------------------------------------------------------------------------
# LAYER 1 — CLASSIFICATION
# ---------------------------------------------------------------------------
def classify_company(row: Dict[str, Any]) -> str:
    revenue_growth = row.get("revenue_growth", row.get("momentum_1m", 0))
    eps_growth = row.get("eps_growth", 0)
    pe = row.get("pe", 999)
    volatility = row.get("volatility", 20)
    sector = row.get("sector", "")
    operating_margin = row.get("operating_margin", 0)

    if revenue_growth > 25 or (eps_growth > 30 and pe > 30):
        return "hypergrowth"
    if (eps_growth is None or eps_growth <= 0) and pe > 40 and volatility > 50:
        return "speculative"
    if sector in ("Energy", "Basic Materials", "Industrials", "Consumer Cyclical") and volatility > 35:
        return "cyclical"
    if revenue_growth > 10 and roic(row) > 15 and operating_margin > 15:
        return "compounder"
    if (pe is not None and 0 < pe < 15) or (row.get("pb") and row.get("pb") < 1.5) or revenue_growth < 5:
        return "value"
    return "value"

def roic(row: Dict[str, Any]) -> float:
    roe = row.get("roe")
    if roe:
        return roe * 0.8
    return 10.0

# ---------------------------------------------------------------------------
# LAYER 2 — DYNAMIC PE
# ---------------------------------------------------------------------------
def dynamic_pe(row: Dict[str, Any], profile: str) -> float:
    growth_rate = row.get("revenue_growth", row.get("eps_growth", 5))
    quality = row.get("quality_score", 50) / 100
    sector_pe = SECTOR_PE.get(row.get("sector", "Technology"), 18)

    if profile == "hypergrowth":
        base = max(40, min(80, 15 + growth_rate * 1.2))
    elif profile == "compounder":
        base = max(25, min(60, 20 + growth_rate * 0.8))
    elif profile == "value":
        base = max(8, min(20, sector_pe * 0.7))
    elif profile == "cyclical":
        base = max(10, min(25, sector_pe * 0.9))
    else:
        base = max(30, min(120, 25 + growth_rate * 1.5))

    quality_premium = 1 + (quality - 0.5) * 0.5
    return round(base * quality_premium, 1)

# ---------------------------------------------------------------------------
# LAYER 3 — GRAHAM FORMULA
# ---------------------------------------------------------------------------
def graham_formula(eps: float, sector: str = "Technology", risk_free: float = 0.044) -> Optional[float]:
    if not eps or eps <= 0:
        return None
    g = SECTOR_GROWTH.get(sector, 0.06) * 100
    return round(eps * (8.5 + 2 * g) * (4.4 / (risk_free * 100)), 2)

# ---------------------------------------------------------------------------
# LAYER 4 — DCF MODERN
# ---------------------------------------------------------------------------
def dcf_modern(
    fcf: float, shares: float, revenue_growth: float = 5.0,
    high_growth_years: int = 5, transition_years: int = 5,
    terminal_growth: float = 0.025, wacc: float = 0.09
) -> Optional[float]:
    if not fcf or not shares or fcf <= 0 or shares <= 0:
        return None
    pv = 0.0
    cf = float(fcf)
    growth_rates = [revenue_growth / 100] * high_growth_years
    start_rate = revenue_growth / 100
    end_rate = terminal_growth
    decel = [(start_rate - (i+1) * (start_rate - end_rate) / transition_years) for i in range(transition_years)]
    all_rates = growth_rates + decel
    for i, g in enumerate(all_rates, start=1):
        cf *= (1 + g)
        pv += cf / ((1 + wacc) ** i)
    final_cf = cf * (1 + terminal_growth)
    terminal_value = final_cf / (wacc - terminal_growth)
    pv += terminal_value / ((1 + wacc) ** (high_growth_years + transition_years))
    return round(pv / shares, 2)

# ---------------------------------------------------------------------------
# LAYER 5 — QUALITY
# ---------------------------------------------------------------------------
def quality_score(row: Dict[str, Any]) -> float:
    roic_val = roic(row)
    gross_margin = row.get("gross_margin", 0)
    op_margin = row.get("operating_margin", 0)
    fcf = row.get("fcf", 0)
    debt_eq = row.get("debt_eq", 0) or 0
    eps = row.get("eps", 0)
    score = 0
    if roic_val > 20: score += 25
    elif roic_val > 15: score += 20
    elif roic_val > 10: score += 10
    if gross_margin > 0.4: score += 20
    elif gross_margin > 0.3: score += 15
    elif gross_margin > 0.2: score += 10
    if op_margin > 0.2: score += 20
    elif op_margin > 0.1: score += 15
    elif op_margin > 0.05: score += 10
    if fcf and fcf > 0: score += 15
    if debt_eq < 30: score += 20
    elif debt_eq < 60: score += 15
    elif debt_eq < 100: score += 10
    if eps and eps > 0: score += 10
    return min(100, score)

def quality_premium(score: float) -> float:
    if score >= 80: return 1.25
    elif score >= 60: return 1.10
    elif score >= 40: return 1.00
    else: return 0.85

# ---------------------------------------------------------------------------
# LAYER 6 — MOAT & NARRATIVE
# ---------------------------------------------------------------------------
def moat_score(row: Dict[str, Any]) -> float:
    gross_margin = row.get("gross_margin", 0)
    revenue_growth = row.get("revenue_growth", 0)
    score = 0
    if gross_margin > 0.4: score += 40
    elif gross_margin > 0.3: score += 25
    if revenue_growth > 20: score += 35
    elif revenue_growth > 10: score += 20
    sector = row.get("sector", "")
    if sector in ("Technology", "Communication Services"): score += 25
    return min(100, score)

def narrative_premium(score: float, profile: str) -> float:
    if profile not in ("hypergrowth", "speculative"):
        return 1.0
    if score >= 70: return 1.25
    elif score >= 50: return 1.12
    elif score >= 30: return 1.03
    else: return 1.0

# ---------------------------------------------------------------------------
# LAYER 7 — MARKET REGIME
# ---------------------------------------------------------------------------
def market_regime_adjustment(row: Dict[str, Any]) -> float:
    volatility = row.get("volatility", 20)
    beta = row.get("beta", 1.0)
    if volatility < 15:
        factor = 1.05
    elif volatility > 40:
        factor = 0.90
    else:
        factor = 1.00
    if beta > 1.5:
        factor *= 0.95
    elif beta < 0.8:
        factor *= 1.02
    return max(0.80, min(1.20, factor))

# ---------------------------------------------------------------------------
# LAYER 8 — PIVOT AVERAGE
# ---------------------------------------------------------------------------
def compute_pivot_average(row: Dict[str, Any]) -> Optional[float]:
    highs = row.get("hist_highs")
    lows = row.get("hist_lows")
    closes = row.get("hist_closes")
    if not highs or not lows or not closes:
        return None
    n = min(len(closes), 20)
    if n < 2:
        return None
    recent_high = highs[-n:]
    recent_low = lows[-n:]
    recent_close = closes[-n:]

    pivots = []
    for i in range(n):
        h = recent_high[i]
        l = recent_low[i]
        c = recent_close[i]
        if h is not None and l is not None and c is not None:
            pp = (h + l + c) / 3
            s1 = 2 * pp - h
            r1 = 2 * pp - l
            pivots.extend([pp, s1, r1])
    if not pivots:
        return None
    return round(sum(pivots) / len(pivots), 2)

# ---------------------------------------------------------------------------
# LAYER 9 — VALUATION AGGREGATOR
# ---------------------------------------------------------------------------
def compute_sales_based_fair_value(row: Dict[str, Any]) -> Optional[float]:
    revenue = row.get("revenue")
    shares = row.get("shares_outstanding") or _estimate_shares(row)
    if not revenue or not shares or revenue <= 0 or shares <= 0:
        return None
    sales_per_share = revenue / shares
    profile = row.get("profile", "value")
    if profile == "hypergrowth":
        multiple = 5.0
    elif profile == "speculative":
        multiple = 4.0
    elif profile == "compounder":
        multiple = 3.0
    else:
        multiple = 1.5
    return round(sales_per_share * multiple, 2)

def _estimate_shares(row: Dict[str, Any]) -> Optional[float]:
    mc = row.get("market_cap")
    price = row.get("price", 0)
    if mc and price and price > 0:
        return mc / price
    return None

def compute_fair_value_action(row: Dict[str, Any]) -> Optional[float]:
    eps = row.get("eps")
    price = row.get("price", 0)

    # Détection EPS invalide
    eps_invalid = False
    if eps is not None and eps > 0 and price > 0:
        pe_ratio = price / eps
        if pe_ratio > 80:
            eps_invalid = True
        elif eps < 0.5 and price > 100:
            eps_invalid = True
    elif not eps or eps <= 0:
        eps_invalid = True

    # Fallback en cas d'EPS invalide
    if eps_invalid:
        fv_sales = compute_sales_based_fair_value(row)
        if fv_sales is not None:
            if price > 0:
                fv_sales = max(price * 0.3, min(price * 2.5, fv_sales))
            return round(fv_sales, 2)
        pivot_avg = compute_pivot_average(row)
        if pivot_avg is not None:
            return pivot_avg
        return None

    # EPS normal
    profile = classify_company(row)
    row["profile"] = profile
    sector = row.get("sector", "Technology")

    target_pe = dynamic_pe(row, profile)
    fv_pe = round(eps * target_pe, 2)
    fv_graham = graham_formula(eps, sector)

    fcf = row.get("fcf")
    shares = row.get("shares_outstanding") or _estimate_shares(row)
    fv_dcf = None
    if fcf and shares and fcf > 0 and shares > 0:
        revenue_growth = row.get("revenue_growth", 5.0)
        high_growth_years = 5 if profile in ("hypergrowth", "speculative") else 3
        transition_years = 5 if profile in ("hypergrowth", "compounder") else 3
        fv_dcf = dcf_modern(
            fcf, shares,
            revenue_growth=max(5.0, min(30.0, revenue_growth)),
            high_growth_years=high_growth_years,
            transition_years=transition_years
        )

    fv_sales = compute_sales_based_fair_value(row) if profile in ("hypergrowth", "speculative") else None

    # Pondérations
    if profile == "value":
        weights = {"pe": 0.40, "graham": 0.30, "dcf": 0.30}
    elif profile == "compounder":
        weights = {"pe": 0.25, "graham": 0.15, "dcf": 0.60}
    elif profile == "hypergrowth":
        weights = {"pe": 0.15, "graham": 0.10, "dcf": 0.50, "sales": 0.25}
    elif profile == "speculative":
        weights = {"pe": 0.10, "graham": 0.10, "dcf": 0.40, "sales": 0.40}
    else:
        weights = {"pe": 0.35, "graham": 0.25, "dcf": 0.40}

    candidates = []
    weights_list = []
    if fv_pe is not None:
        candidates.append(fv_pe); weights_list.append(weights.get("pe", 0))
    if fv_graham is not None:
        candidates.append(fv_graham); weights_list.append(weights.get("graham", 0))
    if fv_dcf is not None:
        candidates.append(fv_dcf); weights_list.append(weights.get("dcf", 0))
    if fv_sales is not None:
        candidates.append(fv_sales); weights_list.append(weights.get("sales", 0))

    if not candidates:
        return None

    total_w = sum(weights_list)
    norm_weights = [w / total_w for w in weights_list]
    fv_composite = sum(v * w for v, w in zip(candidates, norm_weights))

    # Primes
    q_score = quality_score(row)
    q_premium = quality_premium(q_score)
    m_score = moat_score(row)
    n_premium = narrative_premium(m_score, profile)
    regime_factor = market_regime_adjustment(row)
    fv_composite = fv_composite * q_premium * n_premium * regime_factor

    # Garde-fou pivot en cas d'écart excessif
    pivot_avg = compute_pivot_average(row)
    if pivot_avg is not None and price > 0:
        ratio = fv_composite / price
        if ratio > 3.0 or ratio < 0.33:
            fv_composite = pivot_avg

    # Bornage final
    if price > 0:
        fv_composite = max(price * 0.1, min(price * 4.0, fv_composite))
    return round(fv_composite, 2)

# ---------------------------------------------------------------------------
# MULTI-ASSETS
# ---------------------------------------------------------------------------
def compute_fair_value_crypto(row: Dict[str, Any]) -> Optional[float]:
    nvt = row.get("nvt")
    price = row.get("price", 0)
    if not price:
        return None
    if nvt:
        if nvt < 20: mult = 1.35
        elif nvt < 40: mult = 1.15
        elif nvt < 65: mult = 1.00
        elif nvt < 100: mult = 0.88
        else: mult = 0.72
    else:
        mom = row.get("momentum_1m", 0)
        if mom < -25: mult = 1.20
        elif mom < -15: mult = 1.10
        elif mom > 30: mult = 0.85
        else: return None
    return round(price * mult, 2)

def compute_fair_value_forex(row: Dict[str, Any]) -> Optional[float]:
    price = row.get("price", 0)
    mom_1m = row.get("momentum_1m", 0)
    mom_3m = row.get("momentum_3m", 0)
    if not price:
        return None
    if mom_1m < -3 and mom_3m < -6:
        return round(price * 1.04, 5)
    elif mom_1m > 3 and mom_3m > 6:
        return round(price * 0.96, 5)
    return None

def compute_fair_value_commodity(row: Dict[str, Any]) -> Optional[float]:
    price = row.get("price", 0)
    drawdown = row.get("drawdown", 0)
    rsi = row.get("rsi", 50)
    mom_1m = row.get("momentum_1m", 0)
    if not price:
        return None
    if drawdown < -20 and rsi < 35:
        return round(price * 1.22, 2)
    elif drawdown < -12 and rsi < 45:
        return round(price * 1.10, 2)
    elif rsi > 75 and mom_1m > 15:
        return round(price * 0.88, 2)
    return None

def compute_fair_value_etf(row: Dict[str, Any]) -> Optional[float]:
    return None

def compute_fair_value(row: Dict[str, Any]) -> Optional[float]:
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
    if price and fair_value and price > 0 and fair_value > 0:
        return round((fair_value / price - 1) * 100, 1)
    return 0.0

def margin_of_safety(fair_value: float, price: float, margin: float = 0.25) -> Optional[float]:
    if fair_value and price and price > 0:
        return round(fair_value * (1 - margin), 2)
    return None