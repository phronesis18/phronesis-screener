"""
clean_and_refresh_brvm.py
Nettoie l'historique BRVM (valeurs aberrantes) et reconstruit les données BRVM
dans le Parquet principal.

Usage :
    python clean_and_refresh_brvm.py
"""

import pandas as pd
from screener.brvm_fetcher import compute_technical_indicators, load_history, save_history

HISTORY_PATH = "data/brvm_history.parquet"
OUTLIER_FACTOR = 5.0  # Une valeur > 5× la médiane locale est rejetée


def clean_history() -> pd.DataFrame:
    """Nettoie l'historique BRVM des valeurs aberrantes."""
    print("🧹 Nettoyage de l'historique BRVM...")
    df = pd.read_parquet(HISTORY_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    total_fixed = 0

    for ticker in df["ticker"].unique():
        mask = df["ticker"] == ticker
        sub = df.loc[mask].copy()

        if len(sub) < 5:
            continue

        # Médiane mobile sur 7 jours (robuste aux outliers)
        median_rolling = sub["close"].rolling(window=7, center=True, min_periods=3).median()

        # Détection outliers : close > 5× médiane OU < médiane / 5
        outliers = sub["close"] > (median_rolling * OUTLIER_FACTOR)
        outliers |= sub["close"] < (median_rolling / OUTLIER_FACTOR)

        n_outliers = outliers.sum()
        if n_outliers > 0:
            fixed_prices = sub["close"].copy()
            fixed_prices[outliers] = median_rolling[outliers]
            fixed_prices = fixed_prices.ffill().bfill()
            sub.loc[outliers, "close"] = fixed_prices[outliers].round(2)

            print(f"  {ticker} : {n_outliers} valeurs corrigées")
            total_fixed += n_outliers

        df.loc[mask, "close"] = sub["close"].values

    save_history(df)
    print(f"\n✅ Historique nettoyé : {total_fixed} valeurs aberrantes corrigées\n")
    return df


def refresh_brvm_in_parquet() -> None:
    """Reconstruit les données BRVM dans le Parquet principal."""
    print("🔄 Reconstruction des données BRVM dans le Parquet...")

    # Charge le Parquet principal
    df = pd.read_parquet("data/latest.parquet")

    # Retire les anciennes lignes BRVM
    df = df[df["exchange"] != "BRVM"]

    # Recalcule les indicateurs BRVM avec l'historique nettoyé
    df_hist = load_history()
    df_brvm = compute_technical_indicators(df_hist)

    # Concatène
    df_final = pd.concat([df, df_brvm], ignore_index=True)
    df_final.to_parquet("data/latest.parquet", index=False)

    print(f"✅ Parquet reconstruit : {len(df_final)} actifs (dont {len(df_brvm)} BRVM)\n")

    # Vérification ciblée
    print("=== Vérification tickers sensibles ===")
    for t in ["BNBC", "CABC", "BOAM", "SNTS", "ORAC"]:
        row = df_brvm[df_brvm["ticker"] == t]
        if not row.empty:
            r = row.iloc[0]
            print(f"  {t:<8} | price={r['price']:>10.2f} | rsi={r['rsi']:>5.1f} | mom_1m={r['momentum_1m']:>7.2f}%")


if __name__ == "__main__":
    clean_history()
    refresh_brvm_in_parquet()
    print("🎉 Terminé !")