"""
screener/valuation.py
Phronesis Screener — moteur de valorisation multi-actifs v3
────────────────────────────────────────────────────────────
CHANGELOG v3 :
  - Suppression de TOUS les plafonnements (±60% actions, ±40% crypto,
    ±8% forex, ±25% commodités). La fair value est désormais brute.
  - Clarification logique signal / upside :
      upside_pct = (FV / Prix - 1) × 100
      → FV > Prix  → upside POSITIF  → actif SOUS-ÉVALUÉ  ✅
      → FV < Prix  → upside NÉGATIF  → actif SURÉVALUÉ    ✅
"""

import math


# ---------------------------------------------------------------------------
# PER SECTORIELS MOYENS (médiane historique S&P 500 par secteur)
# Sources : Damodaran NYU, Yardeni Research — mis à jour 2024
# ---------------------------------------------------------------------------

SECTOR_PE = {
    "Technology":              28.0,
    "Communication Services":  22.0,
    "Consumer Cyclical":       20.0,
    "Consumer Defensive":      22.0,
    "Healthcare":              20.0,
    "Financial Services":      13.0,
    "Industrials":             18.0,
    "Basic Materials":         15.0,
    "Real Estate":             35.0,
    "Utilities":               17.0,
    "Energy":                  12.0,
    "ETF":                     18.0,
    "Crypto":                  None,
    "Forex":                   None,
    "Commodité":               None,
}

# Taux de croissance moyen implicite par secteur
SECTOR_GROWTH = {
    "Technology":              0.10,
    "Communication Services":  0.08,
    "Consumer Cyclical":       0.07,
    "Consumer Defensive":      0.05,
    "Healthcare":              0.08,
    "Financial Services":      0.06,
    "Industrials":             0.06,
    "Basic Materials":         0.04,
    "Real Estate":             0.04,
    "Utilities":               0.03,
    "Energy":                  0.04,
}


# ---------------------------------------------------------------------------
# MÉTHODE 1 — Multiple EPS sectoriel (P/E peer)
# Fair Value = EPS × PER_sectoriel_moyen
# ---------------------------------------------------------------------------

def fair_value_pe_multiple(eps: float, sector: str,
                            pe_override: float = None) -> float | None:
    """
    Fair Value = EPS × PER sectoriel moyen.
    Méthode principale : ancre la valorisation sur les attentes
    réelles du marché par industrie (ex : Tech 28x, Energy 12x).

    Interprétation upside résultant :
      upside > 0 → Prix < FV → actif sous-évalué vs ses pairs
      upside < 0 → Prix > FV → actif surévalué vs ses pairs
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
# ---------------------------------------------------------------------------

def graham_formula(eps: float, sector: str = "Technology",
                   risk_free: float = 0.044) -> float | None:
    """
    Formule Graham (1962) actualisée avec taux de croissance sectoriel.
    Taux sans risque ~4.4% (T-Bond US 10 ans).
    g est exprimé en pourcentage dans la formule originale.
    """
    if not eps or eps <= 0:
        return None
    g   = SECTOR_GROWTH.get(sector, 0.06) * 100
    raw = eps * (8.5 + 2 * g) * (4.4 / (risk_free * 100))
    return round(raw, 2)


# ---------------------------------------------------------------------------
# MÉTHODE 3 — DCF simplifié (FCF-based)
# ---------------------------------------------------------------------------

def dcf_simple(fcf: float, shares: float,
               sector: str = "Technology",
               wacc: float = 0.09,
               terminal_growth: float = 0.025,
               years: int = 10) -> float | None:
    """
    DCF 10 ans + valeur terminale Gordon Growth.
    Croissance FCF calée sur le secteur (SECTOR_GROWTH).
    WACC 9% = prime de risque actions US ~5% + taux sans risque ~4%.
    """
    if not fcf or not shares or fcf <= 0 or shares <= 0:
        return None
    growth = SECTOR_GROWTH.get(sector, 0.06)
    pv     = 0.0
    cf     = float(fcf)
    for i in range(1, years + 1):
        cf *= (1 + growth)
        pv += cf / ((1 + wacc) ** i)
    terminal_value = cf * (1 + terminal_growth) / (wacc - terminal_growth)
    pv += terminal_value / ((1 + wacc) ** years)
    return round(pv / shares, 2)


# ---------------------------------------------------------------------------
# MÉTHODE 4 — Graham Number (usage restreint aux secteurs value)
# ---------------------------------------------------------------------------

def graham_number(eps: float, bvps: float,
                  sector: str = "Industrials") -> float | None:
    """
    Graham Number = sqrt(22.5 × EPS × BVPS).

    RÉSERVÉ aux secteurs value dont les actifs au bilan reflètent
    fidèlement la valeur : Industrials, Financial Services, Energy,
    Basic Materials, Utilities, Consumer Defensive.

    DÉSACTIVÉ pour Tech/Growth : leur P/B peut dépasser 30-50x
    (brevets, marques) → résultat absurde sinon.
    Ex AAPL : sqrt(22.5 × 6.5 × 4) ≈ 24$ au lieu de ~200$.
    """
    VALUE_SECTORS = {
        "Industrials", "Financial Services", "Energy",
        "Basic Materials", "Utilities", "Consumer Defensive",
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

    Pondérations selon disponibilité des données :
      Méthode 1 — P/E sectoriel  : 45%  (toujours si EPS > 0)
      Méthode 2 — Graham Formula : 25%
      Méthode 3a — DCF           : 30%  (si FCF > 0 disponible)
      Méthode 3b — Graham Number : 30%  (fallback value sectors)

    Aucun plafonnement appliqué. Fair value brute.
    Une FV très éloignée du prix reflète soit une vraie décote/surcote,
    soit des données yfinance incomplètes — à interpréter avec discernement.
    """
    eps    = row.get("eps")
    bvps   = row.get("bvps")
    fcf    = row.get("fcf")
    shares = row.get("shares_outstanding") or _estimate_shares(row)
    sector = row.get("sector", "Technology")

    candidates = []
    weights    = []

    # Méthode 1
    fv_pe = fair_value_pe_multiple(eps, sector)
    if fv_pe and fv_pe > 0:
        candidates.append(fv_pe)
        weights.append(0.45)

    # Méthode 2
    fv_gf = graham_formula(eps, sector)
    if fv_gf and fv_gf > 0:
        candidates.append(fv_gf)
        weights.append(0.25)

    # Méthode 3a : DCF
    fv_dcf = dcf_simple(fcf, shares, sector) if shares else None
    if fv_dcf and fv_dcf > 0:
        candidates.append(fv_dcf)
        weights.append(0.30)
    else:
        # Méthode 3b : Graham Number (fallback)
        fv_gn = graham_number(eps, bvps, sector)
        if fv_gn and fv_gn > 0:
            candidates.append(fv_gn)
            weights.append(0.30)

    if not candidates:
        return None

    # Normalisation des poids
    total_w    = sum(weights)
    normalized = [w / total_w for w in weights]

    # Fair value composite — SANS aucun plafonnement
    fv_composite = sum(v * w for v, w in zip(candidates, normalized))
    return round(fv_composite, 2)


def _estimate_shares(row: dict) -> float | None:
    """Estime le nombre d'actions = market_cap / price."""
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
    ETF : pas de fair value fondamentale calculable.
    Le score repose sur momentum + risque uniquement.
    Retourne None → upside affiché "—" dans le tableau.
    """
    return None


# ---------------------------------------------------------------------------
# CRYPTO
# ---------------------------------------------------------------------------

def compute_fair_value_crypto(row: dict) -> float | None:
    """
    Proxy fair value crypto via NVT (Network Value to Transactions).
    NVT = Market Cap / Volume 24h.

    Échelle NVT :
      < 20  → Très sous-utilisé vs valeur  → FV = Prix × 1.35 → upside +35%
      < 40  → Légèrement sous-utilisé      → FV = Prix × 1.15 → upside +15%
      40-65 → Zone neutre                  → FV = Prix × 1.00 → upside 0%
      65-100→ Légèrement surévalué         → FV = Prix × 0.88 → upside -12%
      > 100 → Fortement surévalué          → FV = Prix × 0.72 → upside -28%

    Rappel : upside > 0 → FV > Prix → sous-évalué ✅
             upside < 0 → FV < Prix → surévalué   ✅
    """
    nvt   = row.get("nvt")
    price = row.get("price", 0)
    if not price:
        return None

    multiplier = None
    if nvt:
        if nvt < 20:    multiplier = 1.35
        elif nvt < 40:  multiplier = 1.15
        elif nvt < 65:  multiplier = 1.00
        elif nvt < 100: multiplier = 0.88
        else:           multiplier = 0.72

    if multiplier is None:
        # Fallback mean-reversion momentum
        mom = row.get("momentum_1m", 0)
        if mom < -25:   multiplier = 1.20
        elif mom < -15: multiplier = 1.10
        elif mom > 30:  multiplier = 0.85
        else:
            return None

    return round(price * multiplier, 2)


# ---------------------------------------------------------------------------
# FOREX
# ---------------------------------------------------------------------------

def compute_fair_value_forex(row: dict) -> float | None:
    """
    Proxy fair value Forex : mean-reversion momentum 1M + 3M.

    Oversold (mom_1m < -3 ET mom_3m < -6) :
      FV = Prix × 1.04  → upside +4% → paire sous-évaluée ✅

    Overbought (mom_1m > 3 ET mom_3m > 6) :
      FV = Prix × 0.96  → upside -4% → paire surévaluée   ✅

    Aucun plafonnement. Signal insuffisant → None.
    """
    price  = row.get("price", 0)
    mom_1m = row.get("momentum_1m", 0)
    mom_3m = row.get("momentum_3m", 0)
    if not price:
        return None

    if mom_1m < -3 and mom_3m < -6:
        return round(price * 1.04, 5)
    elif mom_1m > 3 and mom_3m > 6:
        return round(price * 0.96, 5)
    return None


# ---------------------------------------------------------------------------
# COMMODITÉS
# ---------------------------------------------------------------------------

def compute_fair_value_commodity(row: dict) -> float | None:
    """
    Proxy fair value commodités : cycles drawdown + RSI.

    Oversold → FV > Prix → upside positif → sous-évaluée ✅
    Overbought → FV < Prix → upside négatif → surévaluée ✅

    Aucun plafonnement appliqué.
    """
    price    = row.get("price", 0)
    drawdown = row.get("drawdown", 0)
    rsi      = row.get("rsi", 50)
    mom_1m   = row.get("momentum_1m", 0)
    if not price:
        return None

    if drawdown < -20 and rsi < 35:
        return round(price * 1.22, 2)
    elif drawdown < -12 and rsi < 45:
        return round(price * 1.10, 2)
    elif rsi > 75 and mom_1m > 15:
        return round(price * 0.88, 2)
    return None


# ---------------------------------------------------------------------------
# DISPATCHER PRINCIPAL
# ---------------------------------------------------------------------------

def compute_fair_value(row: dict) -> float | None:
    """
    Route vers la méthode adaptée au type d'actif.
    Retourne la fair value brute, sans aucun plafonnement.
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
    """
    Upside potentiel en % = (FV / Prix - 1) × 100

    ┌──────────────────────────────────────────────────────────┐
    │  RÈGLE D'OR — sens du signal                             │
    │                                                          │
    │  FV > Prix → upside POSITIF  → actif SOUS-ÉVALUÉ  ✅   │
    │  FV < Prix → upside NÉGATIF  → actif SURÉVALUÉ    ✅   │
    │                                                          │
    │  Exemples :                                              │
    │    Prix=100$, FV=130$ → upside=+30% → sous-évalué       │
    │    Prix=293$, FV=200$ → upside=-32% → surévalué         │
    └──────────────────────────────────────────────────────────┘
    """
    if price and price > 0 and fair_value and fair_value > 0:
        return round((fair_value / price - 1) * 100, 1)
    return 0.0


def margin_of_safety(fair_value: float, price: float,
                     margin: float = 0.25) -> float | None:
    """
    Prix d'achat cible avec marge de sécurité = FV × (1 - margin).
    Graham recommande 25% à 50% selon la qualité de l'actif.
    Ex : FV=200$, margin=25% → prix cible=150$
    """
    if fair_value and price and price > 0:
        return round(fair_value * (1 - margin), 2)
    return None


def valuation_method_used(row: dict) -> str:
    """
    Label lisible des méthodes utilisées — pour la fiche détail.
    """
    asset  = row.get("asset_type", "Action")
    sector = row.get("sector", "—")

    if asset == "Crypto":
        return "NVT + Momentum mean-reversion"
    elif asset == "Forex":
        return "Momentum mean-reversion"
    elif asset == "Commodité":
        return "Drawdown + RSI cyclique"
    elif asset in ("ETF", "ETF Afrique"):
        return "Pas de Fair Value (momentum uniquement)"
    else:
        has_fcf     = bool(row.get("fcf") and row.get("fcf", 0) > 0)
        gn_eligible = sector in {
            "Industrials", "Financial Services", "Energy",
            "Basic Materials", "Utilities", "Consumer Defensive",
        }
        methods = ["P/E sectoriel", "Graham Formula"]
        if has_fcf:
            methods.append("DCF")
        elif gn_eligible:
            methods.append("Graham Number")
        return " + ".join(methods)