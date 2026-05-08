"""
screener/valuation.py
Phronesis Screener — moteur de valorisation multi-actifs
Modèles : Graham Number, Graham Formula, DCF simplifié, NAV proxy, NVT crypto
"""

import math


# ---------------------------------------------------------------------------
# ACTIONS
# ---------------------------------------------------------------------------

def graham_number(eps: float, bvps: float) -> float | None:
    """
    Graham Number = sqrt(22.5 × EPS × BVPS)
    Valeur intrinsèque conservative de Benjamin Graham.
    Limite : ne fonctionne que si EPS > 0 et BVPS > 0.
    """
    if eps and bvps and eps > 0 and bvps > 0:
        return round(math.sqrt(22.5 * eps * bvps), 2)
    return None


def graham_formula(eps: float, growth_rate: float = 0.05,
                   risk_free: float = 0.044) -> float | None:
    """
    Formule Graham modernisée : V = EPS × (8.5 + 2g) × (4.4 / Y)
    g = taux de croissance estimé (défaut 5%)
    Y = taux sans risque courant (défaut ~4.4% T-Bond US)
    Limite : très sensible à g, à utiliser avec prudence.
    """
    if eps and eps > 0:
        raw = eps * (8.5 + 2 * growth_rate * 100) * (4.4 / (risk_free * 100))
        return round(raw, 2)
    return None


def dcf_simple(fcf: float, shares: float,
               growth: float = 0.05,
               wacc: float = 0.10,
               terminal_growth: float = 0.025,
               years: int = 10) -> float | None:
    """
    DCF simplifié sur 10 ans + valeur terminale Gordon Growth.
    Hypothèses conservatrices : croissance 5%, WACC 10%.
    Limite : sensible aux hypothèses, ne pas utiliser seul.
    """
    if not fcf or not shares or fcf <= 0 or shares <= 0:
        return None
    pv = 0.0
    cf = float(fcf)
    for i in range(1, years + 1):
        cf *= (1 + growth)
        pv += cf / ((1 + wacc) ** i)
    # Valeur terminale
    terminal_value = cf * (1 + terminal_growth) / (wacc - terminal_growth)
    pv += terminal_value / ((1 + wacc) ** years)
    return round(pv / shares, 2)


def margin_of_safety(fair_value: float, price: float,
                     margin: float = 0.25) -> float | None:
    """
    Prix avec marge de sécurité = Fair Value × (1 - margin).
    Graham recommande 25-50% de marge.
    """
    if fair_value and price and price > 0:
        return round(fair_value * (1 - margin), 2)
    return None


def compute_fair_value_action(row: dict) -> float | None:
    """
    Agrège Graham Number + Graham Formula pour actions.
    Moyenne pondérée si les deux sont disponibles.
    """
    gn = graham_number(row.get("eps"), row.get("bvps"))
    gf = graham_formula(row.get("eps"))
    candidates = [v for v in [gn, gf] if v and v > 0]
    if not candidates:
        return None
    # Pondération : Graham Number (60%) + Formula (40%)
    if len(candidates) == 2:
        return round(candidates[0] * 0.6 + candidates[1] * 0.4, 2)
    return round(candidates[0], 2)


# ---------------------------------------------------------------------------
# ETF
# ---------------------------------------------------------------------------

def compute_fair_value_etf(row: dict) -> float | None:
    """
    Pour les ETF : pas de fair value fondamentale directe.
    On compare le prix à sa moyenne mobile 200j comme proxy NAV relatif.
    Retourne None (la valeur sera le prix lui-même avec upside = momentum).
    """
    return None  # Géré via momentum dans scoring


# ---------------------------------------------------------------------------
# CRYPTO
# ---------------------------------------------------------------------------

def compute_fair_value_crypto(row: dict) -> float | None:
    """
    Proxy fair value crypto basé sur NVT + Metcalfe simplifié.
    NVT élevé (> 100) = surévalué par rapport au volume d'utilisation.
    NVT bas (< 25)   = sous-évalué.
    Retourne un signal NVT, pas un prix absolu.
    """
    nvt = row.get("nvt")
    price = row.get("price", 0)
    if nvt and price > 0:
        # Ajustement de prix selon NVT
        if nvt < 25:
            return round(price * 1.3, 2)   # Sous-évalué : upside estimé +30%
        elif nvt < 50:
            return round(price * 1.1, 2)   # Légèrement sous-évalué
        elif nvt > 100:
            return round(price * 0.7, 2)   # Surévalué : downside estimé -30%
        elif nvt > 65:
            return round(price * 0.85, 2)  # Légèrement surévalué
    # Fallback : utiliser momentum
    mom = row.get("momentum_1m", 0)
    if mom < -20:
        return round(price * 1.15, 2)   # Mean reversion possible
    return None


# ---------------------------------------------------------------------------
# FOREX
# ---------------------------------------------------------------------------

def compute_fair_value_forex(row: dict) -> float | None:
    """
    Proxy Forex : basé sur momentum uniquement (pas de PPP en temps réel gratuit).
    Si momentum fortement négatif → possible oversold = sous-évalué.
    """
    price = row.get("price", 0)
    mom_1m = row.get("momentum_1m", 0)
    mom_3m = row.get("momentum_3m", 0)
    if not price:
        return None
    # Signal mean-reversion si fort oversold
    if mom_1m < -4 and mom_3m < -8:
        return round(price * 1.05, 5)
    elif mom_1m > 4 and mom_3m > 8:
        return round(price * 0.95, 5)
    return None


# ---------------------------------------------------------------------------
# COMMODITÉS
# ---------------------------------------------------------------------------

def compute_fair_value_commodity(row: dict) -> float | None:
    """
    Commodités : signal basé sur momentum et drawdown.
    Fort drawdown + RSI bas = oversold = opportunité.
    """
    price     = row.get("price", 0)
    drawdown  = row.get("drawdown", 0)
    rsi       = row.get("rsi", 50)
    if not price:
        return None
    if drawdown < -20 and rsi < 35:
        return round(price * 1.20, 2)
    elif drawdown < -10 and rsi < 45:
        return round(price * 1.08, 2)
    return None


# ---------------------------------------------------------------------------
# DISPATCHER
# ---------------------------------------------------------------------------

def compute_fair_value(row: dict) -> float | None:
    """
    Dispatch vers la bonne méthode selon le type d'actif.
    """
    asset_type = row.get("asset_type", "Action")

    if asset_type in ("Crypto",):
        return compute_fair_value_crypto(row)
    elif asset_type in ("Forex",):
        return compute_fair_value_forex(row)
    elif asset_type in ("Commodité",):
        return compute_fair_value_commodity(row)
    elif asset_type in ("ETF", "ETF Afrique"):
        return compute_fair_value_etf(row)
    else:
        return compute_fair_value_action(row)


def upside_pct(price: float, fair_value: float) -> float:
    """Upside potentiel en % = (FV / Prix - 1) × 100"""
    if price and price > 0 and fair_value and fair_value > 0:
        return round((fair_value / price - 1) * 100, 1)
    return 0.0