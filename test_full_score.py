from screener.data_fetcher import fetch_ticker
from screener.valuation import compute_fair_value
from screener.scoring import score_value, score_quality, score_momentum, score_risk

def compute_score_for_ticker(ticker):
    data = fetch_ticker(ticker)
    if not data:
        print(f"Ticker {ticker} non trouvé")
        return None

    # Ajoute la fair value (utilisée par les fonctions de scoring)
    fv = compute_fair_value(data)
    data["_fair_value"] = fv
    data["asset_type"] = data.get("asset_type", "Action")  # valeur par défaut

    # Calcul des sous-scores
    v = score_value(data)
    q = score_quality(data)
    m = score_momentum(data)
    r = score_risk(data)
    total = v + q + m + r

    print(f"\n📊 {ticker} - {data.get('name', ticker)}")
    print(f"  Prix: {data['price']:.2f} {data.get('currency', 'USD')}")
    print(f"  Fair Value estimée: {fv if fv else 'N/A'}")
    print(f"  Score Value: {v:.1f}/25")
    print(f"  Score Quality: {q:.1f}/25")
    print(f"  Score Momentum: {m:.1f}/25")
    print(f"  Score Risk: {r:.1f}/25")
    print(f"  ✅ Phronesis Score total: {total:.1f}/100")
    return total

if __name__ == "__main__":
    compute_score_for_ticker("AAPL")