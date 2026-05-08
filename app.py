"""
app.py
Phronesis Screener — Application principale Streamlit
Stack : Streamlit + yfinance + Plotly + Google Sheets
Hébergement : Streamlit Community Cloud (gratuit)
"""

import streamlit as st
import pandas as pd
import time

from screener.data_fetcher import (
    fetch_batch, fetch_crypto_metrics,
    ASSET_TYPES, DISPLAY_NAMES
)
from screener.scoring import compute_phronesis_score, get_signal_emoji
from screener.lead_capture import is_lead_captured, show_lead_form
from screener.charts import (
    price_chart, score_radar, score_distribution, top_opportunities_bar
)

# ---------------------------------------------------------------------------
# CONFIG PAGE
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Phronesis Screener — Actifs Sous-évalués",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "**Phronesis** — Club d'investissement. Méthodologie propriétaire multi-actifs.",
    }
)

# ---------------------------------------------------------------------------
# CSS GLOBAL
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* Police + fond global */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
}
[data-testid="stAppViewContainer"] {
    background: #0A0E1A;
}
[data-testid="stHeader"] {
    background: transparent;
}

/* Masquer le menu hamburger et le footer Streamlit */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #111827;
    border: 1px solid #1F2937;
    border-radius: 12px;
    padding: 16px 20px;
}
[data-testid="metric-container"] label {
    color: #6B7280 !important;
    font-size: 12px !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #F9FAFB !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
}

/* Tableau */
[data-testid="stDataFrame"] {
    border: 1px solid #1F2937;
    border-radius: 10px;
    overflow: hidden;
}

/* Boutons */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s;
}

/* Inputs */
.stTextInput > div > div > input,
.stSelectbox > div > div > div {
    background: #111827 !important;
    border: 1px solid #1F2937 !important;
    color: #F9FAFB !important;
    border-radius: 8px !important;
}

/* Signal badges */
.badge-green  { background:#064E3B; color:#6EE7B7; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.badge-blue   { background:#1E3A5F; color:#93C5FD; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.badge-gray   { background:#1F2937; color:#9CA3AF; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.badge-orange { background:#431407; color:#FDBA74; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.badge-red    { background:#450A0A; color:#FCA5A5; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }

/* Divider custom */
.ph-divider {
    border: none;
    border-top: 1px solid #1F2937;
    margin: 24px 0;
}

/* CTA section */
.cta-section {
    background: linear-gradient(135deg, #064E3B 0%, #1E3A5F 100%);
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    margin-top: 32px;
}
</style>
""", unsafe_allow_html=True)


def _gen_ai_conclusion(r):
    """Génère une conclusion textuelle basée sur le score et les signaux."""
    score  = int(r.get("score", 50))
    signal = r.get("signal", "Neutre")
    ticker = r["ticker"]
    up     = r.get("upside_pct", 0)
    risk   = r.get("risk", "Moyen")
    rsi    = r.get("rsi", 50)
    mom    = r.get("momentum_1m", 0)

    if score >= 75:
        verdict = f"**{ticker} présente un profil très attractif** selon notre méthodologie."
        action  = f"L'upside estimé de {up:+.0f}% offre une marge de sécurité confortable."
    elif score >= 60:
        verdict = f"**{ticker} semble sous-évalué** par rapport à sa valeur intrinsèque estimée."
        action  = "La combinaison valeur + momentum est favorable."
    elif score >= 45:
        verdict = f"**{ticker} se situe en zone neutre** — ni clairement sous-évalué, ni surévalué."
        action  = "Attendre un meilleur point d'entrée ou une confirmation du momentum."
    elif score >= 30:
        verdict = f"**{ticker} montre des signes de surévaluation** relative."
        action  = "Prudence — le ratio risque/rendement n'est pas favorable actuellement."
    else:
        verdict = f"**{ticker} semble fortement surévalué** selon notre scoring."
        action  = "À éviter ou à shorter si la stratégie le permet."

    rsi_comment = ""
    if rsi > 70:
        rsi_comment = f" Le RSI à {rsi:.0f} signale un territoire overbought — risque de correction."
    elif rsi < 35:
        rsi_comment = f" Le RSI à {rsi:.0f} indique un oversold — possible opportunité de rebond."

    mom_comment = f" Momentum 1 mois : {mom:+.1f}%." if abs(mom) > 3 else ""

    st.markdown(f"""
    <div style="background:#111827;border-left:3px solid #10B981;border-radius:0 10px 10px 0;padding:16px 20px;margin-top:8px">
        <div style="font-size:12px;font-weight:600;color:#10B981;margin-bottom:6px;letter-spacing:1px">ANALYSE PHRONESIS</div>
        <div style="font-size:14px;color:#F9FAFB;line-height:1.7">
            {verdict} {action}{rsi_comment}{mom_comment}
            <br><br>
            <span style="color:#6B7280;font-size:12px">
            ⚠️ Cette analyse est générée algorithmiquement. Elle ne constitue pas un conseil en investissement.
            Toujours compléter avec votre propre analyse avant toute décision.
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# DONNÉES PAR DÉFAUT
# ---------------------------------------------------------------------------

DEFAULT_TICKERS = [
    # Actions US majeures
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "JPM", "JNJ", "V",
    # ETF
    "SPY", "QQQ", "GLD", "EEM", "EZA",
    # Crypto
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD",
    # Forex
    "EURUSD=X", "GBPUSD=X",
    # Commodités
    "GC=F", "CL=F",
]

WHATSAPP_URL = "https://wa.me/VOTRE_NUMERO?text=Bonjour%20Phronesis%2C%20je%20veux%20d%C3%A9couvrir%20le%20Club%20Priv%C3%A9%20%F0%9F%8F%9B"

ASSET_TYPE_FILTER = {
    "Tous":         None,
    "Actions US":   "Action",
    "ETF":          ["ETF", "ETF Afrique"],
    "Crypto":       "Crypto",
    "Forex":        "Forex",
    "Commodités":   "Commodité",
    "Afrique":      "ETF Afrique",
}


# ---------------------------------------------------------------------------
# CACHE DATA
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)   # Cache 15 min
def load_screener_data(tickers: tuple) -> pd.DataFrame:
    """Charge et score les données. Mis en cache 15 min."""
    df = fetch_batch(list(tickers), delay=0.2)
    if df.empty:
        return pd.DataFrame()
    return compute_phronesis_score(df)


# ---------------------------------------------------------------------------
# GATE : Capture lead avant accès
# ---------------------------------------------------------------------------

if not is_lead_captured():
    show_lead_form()
    st.stop()


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

h_col1, h_col2, h_col3 = st.columns([3, 4, 3])

with h_col1:
    st.markdown("""
    <div style="padding-top:8px">
        <span style="font-size:1.3rem;font-weight:800;letter-spacing:3px;color:#10B981">PHRONESIS</span>
        <span style="font-size:11px;color:#4B5563;margin-left:8px">SCREENER</span>
    </div>
    """, unsafe_allow_html=True)

with h_col2:
    ticker_search = st.text_input(
        "",
        placeholder="🔍  Rechercher un ticker (AAPL, BTC-USD, EURUSD=X...)",
        label_visibility="collapsed",
        key="search_input"
    )

with h_col3:
    st.markdown("""
    <div style="text-align:right;padding-top:12px;font-size:12px;color:#4B5563">
        Données yfinance · Mise à jour toutes les 15 min
    </div>
    """, unsafe_allow_html=True)

st.markdown('<hr class="ph-divider">', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# CHARGEMENT DES DONNÉES
# ---------------------------------------------------------------------------

with st.spinner("⏳ Chargement des données marché..."):
    df_raw = load_screener_data(tuple(DEFAULT_TICKERS))

if df_raw.empty:
    st.error("⚠️ Impossible de charger les données. Vérifiez votre connexion.")
    st.stop()


# ---------------------------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------------------------

n_total       = len(df_raw)
n_undervalued = len(df_raw[df_raw["signal"].str.contains("Sous-évalué", na=False)])
n_overvalued  = len(df_raw[df_raw["signal"].str.contains("Surévalué", na=False)])
top_ticker    = df_raw.sort_values("score", ascending=False).iloc[0]
top_score     = int(top_ticker["score"])
top_name      = top_ticker["ticker"]
top_upside    = top_ticker.get("upside_pct", 0)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Actifs scannés",  n_total,       help="Nombre d'actifs dans le screener")
kpi2.metric("Sous-évalués",    n_undervalued, help="Score ≥ 60 — Opportunité détectée")
kpi3.metric("Surévalués",      n_overvalued,  help="Score ≤ 45 — Prudence recommandée")
kpi4.metric(
    "Top Opportunité",
    f"{top_name}",
    delta=f"Score {top_score} · Upside {top_upside:+.0f}%",
    delta_color="normal",
    help="Actif avec le meilleur Phronesis Score"
)

st.markdown('<hr class="ph-divider">', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# FILTRES
# ---------------------------------------------------------------------------

f_col1, f_col2, f_col3, f_col4 = st.columns([2, 2, 2, 2])

with f_col1:
    asset_filter = st.selectbox(
        "Type d'actif",
        list(ASSET_TYPE_FILTER.keys()),
        index=0,
    )
with f_col2:
    signal_filter = st.selectbox(
        "Signal",
        ["Tous les signaux", "Fortement sous-évalué", "Sous-évalué",
         "Neutre", "Surévalué", "Fortement surévalué"],
    )
with f_col3:
    risk_filter = st.selectbox(
        "Niveau de risque",
        ["Tous niveaux", "Faible", "Moyen", "Élevé", "Très élevé"],
    )
with f_col4:
    score_min = st.slider("Score minimum", 0, 100, 0, step=5)


# ---------------------------------------------------------------------------
# FILTRAGE
# ---------------------------------------------------------------------------

df = df_raw.copy()

# Filtre type d'actif
asset_val = ASSET_TYPE_FILTER.get(asset_filter)
if asset_val:
    if isinstance(asset_val, list):
        df = df[df["asset_type"].isin(asset_val)]
    else:
        df = df[df["asset_type"] == asset_val]

# Filtre signal
if signal_filter != "Tous les signaux":
    df = df[df["signal"] == signal_filter]

# Filtre risque
if risk_filter != "Tous niveaux":
    df = df[df["risk"] == risk_filter]

# Filtre score
df = df[df["score"] >= score_min]

# Filtre recherche ticker
if ticker_search and ticker_search.strip():
    search = ticker_search.strip().upper()
    df = df[
        df["ticker"].str.upper().str.contains(search, na=False) |
        df["name"].str.upper().str.contains(search, na=False)
    ]


# ---------------------------------------------------------------------------
# TABLEAU PRINCIPAL
# ---------------------------------------------------------------------------

st.subheader(f"Screener — {len(df)} actifs")

if df.empty:
    st.info("Aucun actif ne correspond aux filtres sélectionnés.")
else:
    # Colonnes à afficher
    display_cols = {
        "signal_emoji":  "  ",
        "ticker":        "Ticker",
        "name":          "Nom",
        "asset_type":    "Type",
        "price":         "Prix",
        "fair_value":    "Fair Value",
        "upside_pct":    "Upside %",
        "score":         "Phronesis Score",
        "risk":          "Risque",
        "signal":        "Signal",
        "rsi":           "RSI",
        "momentum_1m":   "Mom. 1M",
        "market_cap_fmt":"Mkt Cap",
    }

    # Sélectionner et renommer
    available = [c for c in display_cols.keys() if c in df.columns]
    df_display = df[available].rename(columns=display_cols)

    # Formater les nombres
    if "Prix" in df_display.columns:
        df_display["Prix"] = df_display["Prix"].apply(
            lambda x: f"{x:,.4f}" if x < 10 else f"{x:,.2f}"
        )
    if "Fair Value" in df_display.columns:
        df_display["Fair Value"] = df_display["Fair Value"].apply(
            lambda x: f"{x:,.2f}" if pd.notna(x) and x else "—"
        )
    if "Upside %" in df_display.columns:
        df_display["Upside %"] = df_display["Upside %"].apply(
            lambda x: f"{x:+.1f}%" if x != 0 else "—"
        )
    if "Mom. 1M" in df_display.columns:
        df_display["Mom. 1M"] = df_display["Mom. 1M"].apply(
            lambda x: f"{x:+.1f}%"
        )

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            "Phronesis Score": st.column_config.ProgressColumn(
                "Phronesis Score",
                min_value=0,
                max_value=100,
                format="%d",
            ),
        }
    )

st.markdown('<hr class="ph-divider">', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# FICHE DÉTAIL ACTIF
# ---------------------------------------------------------------------------

st.subheader("Analyse détaillée d'un actif")

ticker_detail = st.selectbox(
    "Choisir un actif à analyser",
    options=df_raw["ticker"].tolist(),
    format_func=lambda t: f"{t} — {df_raw[df_raw['ticker']==t]['name'].values[0] if len(df_raw[df_raw['ticker']==t]) > 0 else t}",
    key="detail_select"
)

if ticker_detail:
    row = df_raw[df_raw["ticker"] == ticker_detail]
    if not row.empty:
        r = row.iloc[0]

        # Header fiche
        d_col1, d_col2, d_col3 = st.columns([2, 2, 2])
        with d_col1:
            st.markdown(f"""
            <div style="background:#111827;border:1px solid #1F2937;border-radius:12px;padding:20px">
                <div style="font-size:1.5rem;font-weight:800;color:#F9FAFB">{r['ticker']}</div>
                <div style="font-size:13px;color:#6B7280;margin-bottom:12px">{r.get('name','')}</div>
                <div style="font-size:2rem;font-weight:700;color:#10B981">{r['price']:,.2f}</div>
                <div style="font-size:12px;color:#4B5563">{r.get('currency','USD')}</div>
            </div>
            """, unsafe_allow_html=True)

        with d_col2:
            fv = r.get("fair_value")
            up = r.get("upside_pct", 0)
            up_color = "#10B981" if up >= 0 else "#EF4444"
            fv_display = f"{fv:,.2f}" if fv else "—"
            st.markdown(f"""
            <div style="background:#111827;border:1px solid #1F2937;border-radius:12px;padding:20px">
                <div style="font-size:12px;color:#6B7280;margin-bottom:4px">PHRONESIS SCORE</div>
                <div style="font-size:2.5rem;font-weight:800;color:#10B981">{int(r['score'])}</div>
                <div style="font-size:12px;color:#6B7280;margin:8px 0 4px">FAIR VALUE ESTIMÉE</div>
                <div style="font-size:1.3rem;font-weight:600;color:#F9FAFB">{fv_display}</div>
                <div style="font-size:13px;color:{up_color};font-weight:600">Upside : {up:+.1f}%</div>
            </div>
            """, unsafe_allow_html=True)

        with d_col3:
            signal = r.get("signal", "Neutre")
            risk   = r.get("risk", "Moyen")
            rsi_val = r.get("rsi", 50)
            mom    = r.get("momentum_1m", 0)
            st.markdown(f"""
            <div style="background:#111827;border:1px solid #1F2937;border-radius:12px;padding:20px">
                <div style="font-size:12px;color:#6B7280;margin-bottom:6px">SIGNAL</div>
                <div style="font-size:1rem;font-weight:700;color:#F9FAFB;margin-bottom:12px">{get_signal_emoji(signal)} {signal}</div>
                <div style="font-size:12px;color:#6B7280">RSI 14j</div>
                <div style="font-size:1.1rem;font-weight:600;color:#F9FAFB">{rsi_val:.0f}</div>
                <div style="font-size:12px;color:#6B7280;margin-top:6px">Momentum 1 mois</div>
                <div style="font-size:1.1rem;font-weight:600;color:{'#10B981' if mom>=0 else '#EF4444'}">{mom:+.1f}%</div>
                <div style="font-size:12px;color:#6B7280;margin-top:6px">Risque</div>
                <div style="font-size:1rem;font-weight:600;color:{r.get('risk_color','#9CA3AF')}">{risk}</div>
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        # Graphiques
        g_col1, g_col2 = st.columns([3, 2])

        with g_col1:
            dates  = r.get("hist_dates", [])
            closes = r.get("hist_closes", [])
            if dates and closes:
                fig = price_chart(dates, closes, ticker_detail, r.get("fair_value"))
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with g_col2:
            fig_radar = score_radar(
                r.get("score_value", 0),
                r.get("score_quality", 0),
                r.get("score_momentum", 0),
                r.get("score_risk", 0),
            )
            st.plotly_chart(fig_radar, use_container_width=True, config={"displayModeBar": False})

        # Ratios fondamentaux
        st.markdown("**Ratios fondamentaux**")
        ratio_cols = st.columns(6)
        ratios = [
            ("P/E",        r.get("pe"),       lambda x: f"{x:.1f}x"),
            ("P/B",        r.get("pb"),       lambda x: f"{x:.2f}x"),
            ("ROE",        r.get("roe"),      lambda x: f"{x*100:.1f}%"),
            ("Dette/EQ",   r.get("debt_eq"),  lambda x: f"{x:.0f}%"),
            ("EV/EBITDA",  r.get("ev_ebitda"),lambda x: f"{x:.1f}x"),
            ("RSI",        r.get("rsi"),      lambda x: f"{x:.0f}"),
        ]
        for col, (label, val, fmt) in zip(ratio_cols, ratios):
            display = fmt(val) if val is not None else "—"
            col.metric(label, display)

        # Conclusion IA (simulée)
        _gen_ai_conclusion(r)





st.markdown('<hr class="ph-divider">', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# GRAPHIQUES GLOBAUX
# ---------------------------------------------------------------------------

g2_col1, g2_col2 = st.columns([1, 1])

with g2_col1:
    fig_dist = score_distribution(df_raw)
    st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar": False})

with g2_col2:
    fig_top = top_opportunities_bar(df_raw)
    st.plotly_chart(fig_top, use_container_width=True, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# CTA — REJOINDRE LE CLUB
# ---------------------------------------------------------------------------

st.markdown('<hr class="ph-divider">', unsafe_allow_html=True)

cta_col1, cta_col2, cta_col3 = st.columns([1, 3, 1])
with cta_col2:
    st.markdown("""
    <div style="background:#0F2027;border:1px solid #1F2937;border-radius:16px;padding:36px;text-align:center">
        <div style="font-size:1.3rem;font-weight:800;color:#F9FAFB;margin-bottom:8px">
            Rejoignez le Club Phronesis
        </div>
        <div style="font-size:14px;color:#6B7280;margin-bottom:24px;line-height:1.7">
            Accédez aux analyses complètes, aux alertes WhatsApp en temps réel<br>
            et aux discussions privées avec les membres du club.
        </div>
    </div>
    """, unsafe_allow_html=True)

    cta_a, cta_b = st.columns(2)
    with cta_a:
        if st.button("💬 Rejoindre via WhatsApp", type="primary", use_container_width=True):
            st.markdown(f"**[Cliquer ici pour ouvrir WhatsApp]({WHATSAPP_URL})**")
    with cta_b:
        if st.button("📅 Réserver un appel découverte", use_container_width=True):
            st.markdown("**[Réserver sur cal.com/phronesis](https://cal.com)**")

    st.markdown("""
    <div style="text-align:center;font-size:12px;color:#374151;margin-top:16px">
        Club privé · Nombre de places limité · Sans engagement
    </div>
    """, unsafe_allow_html=True)