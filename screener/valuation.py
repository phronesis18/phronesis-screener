"""
screener/valuation.py
Phronesis Screener — moteur de valorisation multi-actifs v2
────────────────────────────────────────────────────────────
CORRECTIF MAJEUR v2 :
  Le Graham Number pur (sqrt(22.5 × EPS × BVPS)) est inadapté aux
  tech / growth (AAPL P/B ~50x → fair value absurde de ~24$).
  Nouveau moteur : Composite sectoriel = DCF + Multiple EPS sectoriel
  + Graham Formula (3e composante, pondération réduite).
  Résultat : fair values réalistes pour toutes les industries.
"""

import math


# ---------------------------------------------------------------------------
# PER SECTORIELS MOYENS (médiane historique S&P 500 par secteur)
# Sources : Damodaran NYU, Yardeni Research — mis à jour 2024
# ---------------------------------------------------------------------------

SECTOR_PE = {
    "Technology":               28.0,
    "Communication Services":   22.0,
    "Consumer Cyclical":        20.0,
    "Consumer Defensive":       22.0,
    "Healthcare":               20.0,
    "Financial Services":       13.0,
    "Industrials":              18.0,
    "Basic Materials":          15.0,
    "Real Estate":              35.0,   # REIT : utilise FFO
    "Utilities":                17.0,
    "Energy":                   12.0,
    "ETF":                      18.0,   # Proxy marché large
    "Crypto":                   None,
    "Forex":                    None,
    "Commodité":                None,
}

# Taux de croissance moyen implicite par secteur (pour Graham Formula)
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

# Plafond d'upside/downside pour éviter les extrêmes (±60%)
MAX_UPSIDE   =  0.60
MAX_DOWNSIDE = -0.60


# ---------------------------------------------------------------------------
# MÉTHODE 1 — Multiple EPS sectoriel (P/E peer)
# Fair Value = EPS × PER_sectoriel
# Avantage : ancré sur les attentes réelles du marché par industrie
# ---------------------------------------------------------------------------

def fair_value_pe_multiple(eps: float, sector: str,
                            pe_override: float = None) -> float | None:
    """
    Fair Value = EPS × PER sectoriel moyen.
    La méthode la plus directe et la moins sujette aux biais de Graham.
    pe_override permet d'injecter un PER personnalisé.
    """
    if not eps or eps <= 0:
        return None
    pe = pe_override or SECTOR_PE.get(sector, 18.0)
    if not pe:
        return None
    return round(eps * pe, 2)


# ---------------------------------------------------------------------------
# MÉTHODE 2 — Graham Formula modernisée
# V = EPS × (8.5 + 2g) × (4.4 / Y)
# Utilise le taux de croissance sectoriel au lieu d'un g générique
# ---------------------------------------------------------------------------

def graham_formula(eps: float, sector: str = "Technology",
                   risk_free: float = 0.044) -> float | None:
    """
    Formule Graham (1962) actualisée avec taux sectoriel.
    Taux sans risque courant ~4.4% (T-Bond US 10 ans).
    """
    if not eps or eps <= 0:
        return None
    g = SECTOR_GROWTH.get(sector, 0.06) * 100  # En pourcentage
    raw = eps * (8.5 + 2 * g) * (4.4 / (risk_free * 100))
    return round(raw, 2)


# ---------------------------------------------------------------------------
# MÉTHODE 3 — DCF simplifié (FCF-based)
# Utilisé comme troisième pilier quand FCF disponible
# Paramètres adaptés au secteur
# ---------------------------------------------------------------------------

def dcf_simple(fcf: float, shares: float,
               sector: str = "Technology",
               wacc: float = 0.09,
               terminal_growth: float = 0.025,
               years: int = 10) -> float | None:
    """
    DCF 10 ans + valeur terminale Gordon Growth.
    Taux de croissance FCF calé sur le secteur.
    WACC 9% (marché actions US actuel, prime risque ~5%).
    """
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
# MÉTHODE 4 — Graham Number (usage restreint)
# Uniquement pour secteurs value classiques (industriels, financiers, énergie)
# NE PAS utiliser sur tech/growth
# ---------------------------------------------------------------------------

def graham_number(eps: float, bvps: float,
                  sector: str = "Industrials") -> float | None:
    """
    Graham Number = sqrt(22.5 × EPS × BVPS).
    Valide uniquement pour : Industrials, Financial Services, Energy,
    Basic Materials, Utilities, Consumer Defensive.
    Désactivé pour Tech / Growth (P/B élevé rend le résultat absurde).
    """
    VALUE_SECTORS = {
        "Industrials", "Financial Services", "Energy",
        "Basic Materials", "Utilities", "Consumer Defensive"
    }
    if sector not in VALUE_SECTORS:
        return None
    if eps and bvps and eps > 0 and bvps > 0:
        return round(math.sqrt(22.5 * eps * bvps), 2)
    return None


# ---------------------------------------------------------------------------
# COMPOSITE ACTIONS — Agrégateur pondéré multi-méthodes
# ---------------------------------------------------------------------------

def compute_fair_value_action(row: dict) -> float | None:
    """
    Fair Value composite pour les actions.

    Pondérations selon la disponibilité :
      - Multiple EPS sectoriel  : 45%  (méthode principale)
      - Graham Formula sectorielle : 25%
      - DCF (si FCF disponible) : 30%
      - Graham Number (value sectors uniquement) : remplace DCF si pas de FCF

    Plafonnement de l'upside/downside à ±60% du prix de marché
    pour éviter les fair values extrêmes dues à des données yfinance imparfaites.
    """
    eps    = row.get("eps")
    bvps   = row.get("bvps")
    fcf    = row.get("fcf")
    shares = row.get("shares_outstanding") or _estimate_shares(row)
    sector = row.get("sector", "Technology")
    price  = row.get("price", 0)

    candidates = []
    weights    = []

    # Méthode 1 : P/E multiple sectoriel (toujours calculée si EPS > 0)
    fv_pe = fair_value_pe_multiple(eps, sector)
    if fv_pe and fv_pe > 0:
        candidates.append(fv_pe)
        weights.append(0.45)

    # Méthode 2 : Graham Formula sectorielle
    fv_gf = graham_formula(eps, sector)
    if fv_gf and fv_gf > 0:
        candidates.append(fv_gf)
        weights.append(0.25)

    # Méthode 3a : DCF si FCF disponible
    fv_dcf = dcf_simple(fcf, shares, sector) if shares else None
    if fv_dcf and fv_dcf > 0:
        candidates.append(fv_dcf)
        weights.append(0.30)
    else:
        # Méthode 3b : Graham Number (fallback, uniquement value sectors)
        fv_gn = graham_number(eps, bvps, sector)
        if fv_gn and fv_gn > 0:
            candidates.append(fv_gn)
            weights.append(0.30)

    if not candidates:
        return None

    # Normaliser les poids selon les méthodes disponibles
    total_w = sum(weights)
    normalized = [w / total_w for w in weights]

    # Fair value composite pondérée
    fv_composite = sum(v * w for v, w in zip(candidates, normalized))

    # ── Plafonnement anti-extrêmes ──────────────────────────────────────
    # Si la FV s'écarte de plus de 60% du prix → cap conservateur
    # Évite les anomalies dues aux données EPS/BVPS manquantes ou négatives
    if price and price > 0:
        max_fv = price * (1 + MAX_UPSIDE)
        min_fv = price * (1 + MAX_DOWNSIDE)
        fv_composite = max(min_fv, min(max_fv, fv_composite))

    return round(fv_composite, 2)


def _estimate_shares(row: dict) -> float | None:
    """Estime le nombre d'actions via market_cap / price si disponible."""
    mc    = row.get("market_cap")
    price = row.get("price", 0)
    if mc and price and price > 0:
        return mc / price
    return None


# ---------------------------------------------------------------------------
# ETF
# ---------------------------------------------------------------------------

def compute_fair_value_etf(row: dict) -> float | None:
    """
    ETF : pas de fair value fondamentale directe.
    On utilise le prix comme ancre et le momentum comme signal.
    La fair value reste None → le score repose sur momentum + risque.
    """
    return None


# ---------------------------------------------------------------------------
# CRYPTO
# ---------------------------------------------------------------------------

def compute_fair_value_crypto(row: dict) -> float | None:
    """
    Proxy fair value crypto : NVT + momentum mean-reversion.
    NVT = Market Cap / Volume 24h (proxy d'utilisation du réseau).
    Plafonnement à ±40% (crypto plus volatile = plage plus large).
    """
    nvt   = row.get("nvt")
    price = row.get("price", 0)
    if not price:
        return None

    multiplier = None
    if nvt:
        if nvt < 20:     multiplier = 1.35   # Très sous-utilisé → upside
        elif nvt < 40:   multiplier = 1.15
        elif nvt < 65:   multiplier = 1.00   # Zone neutre
        elif nvt < 100:  multiplier = 0.88
        else:            multiplier = 0.72   # Surévalué vs utilisation

    if multiplier is None:
        # Fallback : mean-reversion momentum
        mom = row.get("momentum_1m", 0)
        if mom < -25:   multiplier = 1.20
        elif mom < -15: multiplier = 1.10
        elif mom > 30:  multiplier = 0.85
        else:           return None

    fv = round(price * multiplier, 2)
    # Cap ±40% pour crypto
    fv = max(price * 0.60, min(price * 1.40, fv))
    return fv


# ---------------------------------------------------------------------------
# FOREX
# ---------------------------------------------------------------------------

def compute_fair_value_forex(row: dict) -> float | None:
    """
    Forex : signal mean-reversion basé sur momentum court + moyen terme.
    Plafonnement ±8% (paires majeures rarement >8% d'écart PPP court terme).
    """
    price  = row.get("price", 0)
    mom_1m = row.get("momentum_1m", 0)
    mom_3m = row.get("momentum_3m", 0)
    if not price:
        return None

    # Oversold fort → mean reversion haussière
    if mom_1m < -3 and mom_3m < -6:
        fv = price * 1.04
    elif mom_1m > 3 and mom_3m > 6:
        fv = price * 0.96
    else:
        return None

    # Cap ±8%
    fv = max(price * 0.92, min(price * 1.08, fv))
    return round(fv, 5)


# ---------------------------------------------------------------------------
# COMMODITÉS
# ---------------------------------------------------------------------------

def compute_fair_value_commodity(row: dict) -> float | None:
    """
    Commodités : signal drawdown + RSI (oversold/overbought cyclique).
    Plafonnement ±25%.
    """
    price    = row.get("price", 0)
    drawdown = row.get("drawdown", 0)
    rsi      = row.get("rsi", 50)
    mom_1m   = row.get("momentum_1m", 0)
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
# DISPATCHER PRINCIPAL
# ---------------------------------------------------------------------------

def compute_fair_value(row: dict) -> float | None:
    """
    Route vers la méthode de valorisation adaptée au type d'actif.
    """
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


# ---------------------------------------------------------------------------
# UTILITAIRES
# ---------------------------------------------------------------------------

def upside_pct(price: float, fair_value: float) -> float:
    """Upside potentiel en % = (FV / Prix - 1) × 100"""
    if price and price > 0 and fair_value and fair_value > 0:
        return round((fair_value / price - 1) * 100, 1)
    return 0.0


def margin_of_safety(fair_value: float, price: float,
                     margin: float = 0.25) -> float | None:
    """Prix cible avec marge de sécurité = FV × (1 - margin)."""
    if fair_value and price and price > 0:
        return round(fair_value * (1 - margin), 2)
    return None


def valuation_method_used(row: dict) -> str:
    """
    Retourne un label lisible indiquant quelle(s) méthode(s) ont été utilisées.
    Utile pour l'affichage dans la fiche détail.
    """
    asset = row.get("asset_type", "Action")
    sector = row.get("sector", "—")
    if asset == "Crypto":
        return "NVT + Momentum"
    elif asset == "Forex":
        return "Mean-Reversion Momentum"
    elif asset == "Commodité":
        return "Drawdown + RSI cyclique"
    elif asset in ("ETF", "ETF Afrique"):
        return "Momentum (pas de FV)"
    else:
        has_fcf = bool(row.get("fcf") and row.get("fcf", 0) > 0)
        gn_eligible = sector in {
            "Industrials","Financial Services","Energy",
            "Basic Materials","Utilities","Consumer Defensive"
        }
        methods = ["P/E sectoriel", "Graham Formula"]
        if has_fcf:
            methods.append("DCF")
        elif gn_eligible:
            methods.append("Graham Number")
        return " + ".join(methods)