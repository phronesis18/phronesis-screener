"""Diagnostic ciblé — voir comment SONATEL, ETI, SIB apparaissent dans le PDF."""
import pandas as pd
import requests
import re
from screener.brvm_fetcher import _extract_boc_tables

url = "https://bfin.brvm.org/boc/BOC_JOUR/BOC_20261009.pdf"
resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})

tables = _extract_boc_tables(resp.content)
non_empty = [t for t in tables if not t.empty]
merged = pd.concat(non_empty, ignore_index=True).fillna("").astype(str)
merged = merged.apply(lambda x: x.str.strip())

# Mots-clés à chercher
keywords = ["SONATEL", "ECOBANK", "SIB", "SICABLE", "ETI", "SAPH", "PALM", "TOTAL",
            "ORANGE", "VIVO", "UNIWAX", "SIFCA", "SITAB", "SITAF", "TRITURAF",
            "SMB", "SERVAIR", "SODECI", "CIE", "BICICI"]

print("=== LIGNES CONTENANT CES MOTS-CLÉS ===")
for _, row in merged.iterrows():
    joined = " ".join(str(v) for v in row.tolist()).upper()
    if any(kw in joined for kw in keywords):
        vals = [str(v)[:40] for v in row.tolist()]
        # Afficher seulement les cellules non vides
        non_empty_cells = [v for v in vals if v.strip()]
        if non_empty_cells:
            print(" | ".join(non_empty_cells))

print("\n\n=== TOUTES LES LIGNES CONTENANT '(' (parenthèses) ===")
count = 0
for _, row in merged.iterrows():
    joined = " ".join(str(v) for v in row.tolist())
    if "(" in joined and ")" in joined:
        vals = [str(v)[:50] for v in row.tolist()]
        non_empty_cells = [v for v in vals if v.strip()]
        if non_empty_cells:
            print(f"[{count:03d}] " + " | ".join(non_empty_cells))
            count += 1
            if count > 80:
                print("... (tronqué)")
                break