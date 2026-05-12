"""
app.py
Phronesis Screener — Application principale Streamlit
Avec mode dark (toggle sidebar) + assistant IA contextuel + recherche dynamique.
"""

import streamlit as st
import pandas as pd
import time

from screener.data_fetcher import (
    fetch_batch, fetch_ticker, fetch_crypto_metrics,
    ASSET_TYPES, DISPLAY_NAMES, get_default_tickers
)
from screener.scoring import compute_phronesis_score, get_signal_emoji
from screener.lead_capture import is_lead_captured, show_lead_form
from screener.charts import (
    price_chart, score_radar, score_distribution, top_opportunities_bar
)
from screener.ai_assistant import show_ai_assistant

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
# GESTION DU MODE DARK (SESSION STATE + TOGGLE SIDEBAR)
# ---------------------------------------------------------------------------
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

# Sidebar pour les filtres et mode dark
with st.sidebar:
    st.title("⚙️ Paramètres")
    dark_mode_toggle = st.toggle("🌙 Mode sombre", value=st.session_state.dark_mode)
    if dark_mode_toggle != st.session_state.dark_mode:
        st.session_state.dark_mode = dark_mode_toggle
        st.rerun()
    st.markdown("---")
    st.subheader("Filtres")
    # Les filtres seront définis plus bas après chargement des données,
    # mais on les place ici pour l'organisation.

# Appliquer le thème CSS selon le mode
if st.session_state.dark_mode:
    st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
    }
    [data-testid="stAppViewContainer"] {
        background: #0A0E1A;
    }
    [data-testid="stHeader"] {
        background: transparent;
    }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
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
    [data-testid="stDataFrame"] {
        border: 1px solid #1F2937;
        border-radius: 10px;
        overflow: hidden;
    }
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div {
        background: #111827 !important;
        border: 1px solid #1F2937 !important;
        color: #F9FAFB !important;
        border-radius: 8px !important;
    }
    .badge-green  { background:#064E3B; color:#6EE7B7; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
    .badge-blue   { background:#1E3A5F; color:#93C5FD; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
    .badge-gray   { background:#1F2937; color:#9CA3AF; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
    .badge-orange { background:#431407; color:#FDBA74; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
    .badge-red    { background:#450A0A; color:#FCA5A5; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
    .ph-divider {
        border: none;
        border-top: 1px solid #1F2937;
        margin: 24px 0;
    }
    .cta-section {
        background: linear-gradient(135deg, #064E3B 0%, #1E3A5F 100%);
        border-radius: 16px;
        padding: 32px;
        text-align: center;
        margin-top: 32px;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
    }
    [data-testid="stAppViewContainer"] {
        background: #FFFFFF;
    }
    [data-testid="stHeader"] {
        background: transparent;
    }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    [data-testid="metric-container"] {
        background: #F3F4F6;
        border: 1px solid #D1D5DB;
        border-radius: 12px;
        padding: 16px 20px;
    }
    [data-testid="metric-container"] label {
        color: #4B5563 !important;
        font-size: 12px !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #111827 !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }
    .ph-divider {
        border: none;
        border-top: 1px solid #E5E7EB;
        margin: 24px 0;
    }
    </style>
    """, unsafe_allow_html=True)

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
# CHARGEMENT INITIAL (liste restreinte)
# ---------------------------------------------------------------------------
with st.spinner("⏳ Chargement des données marché..."):
    default_tickers = get_default_tickers()
    df_raw = fetch_batch(default_tickers, delay=0.2)

if df_raw.empty:
    st.error("⚠️ Impossible de charger les données. Vérifiez votre connexion.")
    st.stop()

# ---------------------------------------------------------------------------
# AJOUT D'UN TICKER SUPPLÉMENTAIRE (recherche manuelle)
# ---------------------------------------------------------------------------
if ticker_search and ticker_search.strip():
    extra_ticker = ticker_search.strip().upper()
    if extra_ticker not in df_raw["ticker"].values:
        with st.spinner(f"Recherche de {extra_ticker}..."):
            extra_data = fetch_ticker(extra_ticker)
            if extra_data:
                if "asset_type" not in extra_data:
                    extra_data["asset_type"] = ASSET_TYPES.get(extra_ticker, "Action")
                extra_df = pd.DataFrame([extra_data])
                df_raw = pd.concat([df_raw, extra_df], ignore_index=True)
                st.success(f"✅ {extra_ticker} ajouté au screener")
                st.rerun()
            else:
                st.warning(f"⚠️ Ticker {extra_ticker} non trouvé ou données indisponibles")

# ---------------------------------------------------------------------------
# SCORING
# ---------------------------------------------------------------------------
df_scored = compute_phronesis_score(df_raw)

# Stocker df_scored dans session_state pour l'assistant IA
st.session_state.df_scored = df_scored

# ---------------------------------------------------------------------------
# FILTRES (placés dans la sidebar)
# ---------------------------------------------------------------------------
with st.sidebar:
    ASSET_TYPE_FILTER = {
        "Tous": None,
        "Actions US": "Action",
        "ETF": ["ETF", "ETF Afrique"],
        "Crypto": "Crypto",
        "Forex": "Forex",
        "Commodités": "Commodité",
        "Afrique": "ETF Afrique",
    }
    asset_filter = st.selectbox("Type d'actif", list(ASSET_TYPE_FILTER.keys()), index=0)
    signal_filter = st.selectbox(
        "Signal",
        ["Tous les signaux", "Fortement sous-évalué", "Sous-évalué",
         "Neutre", "Surévalué", "Fortement surévalué"],
    )
    risk_filter = st.selectbox(
        "Niveau de risque",
        ["Tous niveaux", "Faible", "Moyen", "Élevé", "Très élevé"],
    )
    score_min = st.slider("Score minimum", 0, 100, 0, step=5)

# Appliquer les filtres sur df_scored
df = df_scored.copy()
asset_val = ASSET_TYPE_FILTER.get(asset_filter)
if asset_val:
    if isinstance(asset_val, list):
        df = df[df["asset_type"].isin(asset_val)]
    else:
        df = df[df["asset_type"] == asset_val]
if signal_filter != "Tous les signaux":
    df = df[df["signal"] == signal_filter]
if risk_filter != "Tous niveaux":
    df = df[df["risk"] == risk_filter]
df = df[df["score"] >= score_min]

# ---------------------------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------------------------
n_total = len(df_scored)
n_undervalued = len(df_scored[df_scored["signal"].str.contains("Sous-évalué", na=False)])
n_overvalued = len(df_scored[df_scored["signal"].str.contains("Surévalué", na=False)])
if n_total > 0:
    top_ticker = df_scored.sort_values("score", ascending=False).iloc[0]
    top_score = int(top_ticker["score"])
    top_name = top_ticker["ticker"]
    top_upside = top_ticker.get("upside_pct", 0)
else:
    top_name = "—"
    top_score = 0
    top_upside = 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Actifs scannés", n_total, help="Nombre d'actifs dans le screener")
kpi2.metric("Sous-évalués", n_undervalued, help="Score ≥ 60 — Opportunité détectée")
kpi3.metric("Surévalués", n_overvalued, help="Score ≤ 45 — Prudence recommandée")
kpi4.metric(
    "Top Opportunité",
    f"{top_name}",
    delta=f"Score {top_score} · Upside {top_upside:+.0f}%",
    delta_color="normal",
    help="Actif avec le meilleur Phronesis Score"
)

st.markdown('<hr class="ph-divider">', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TABLEAU PRINCIPAL
# ---------------------------------------------------------------------------
st.subheader(f"Screener — {len(df)} actifs")
if df.empty:
    st.info("Aucun actif ne correspond aux filtres sélectionnés.")
else:
    display_cols = {
        "signal_emoji": "  ",
        "ticker": "Ticker",
        "name": "Nom",
        "asset_type": "Type",
        "price": "Prix",
        "fair_value": "Fair Value",
        "upside_pct": "Upside %",
        "score": "Phronesis Score",
        "risk": "Risque",
        "signal": "Signal",
        "rsi": "RSI",
        "momentum_1m": "Mom. 1M",
        "market_cap_fmt": "Mkt Cap",
    }
    available = [c for c in display_cols.keys() if c in df.columns]
    df_display = df[available].rename(columns=display_cols)
    # Formatage
    for col in ["Prix", "Fair Value"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) else x
            )
    if "Upside %" in df_display.columns:
        df_display["Upside %"] = df_display["Upside %"].apply(
            lambda x: f"{x:+.1f}%" if isinstance(x, (int, float)) and x != 0 else "—"
        )
    if "Mom. 1M" in df_display.columns:
        df_display["Mom. 1M"] = df_display["Mom. 1M"].apply(
            lambda x: f"{x:+.1f}%" if isinstance(x, (int, float)) else x
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
# FICHE DÉTAIL ACTIF (avec session_state.selected_ticker et assistant IA)
# ---------------------------------------------------------------------------
st.subheader("Analyse détaillée d'un actif")
ticker_detail = st.selectbox(
    "Choisir un actif à analyser",
    options=df_scored["ticker"].tolist(),
    format_func=lambda t: f"{t} — {df_scored[df_scored['ticker']==t]['name'].values[0] if len(df_scored[df_scored['ticker']==t]) > 0 else t}",
    key="detail_select"
)

# Mettre à jour la session_state pour l'assistant IA
st.session_state.selected_ticker = ticker_detail

if ticker_detail:
    row = df_scored[df_scored["ticker"] == ticker_detail]
    if not row.empty:
        r = row.iloc[0]

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

        st.markdown("**Ratios fondamentaux**")
        ratio_cols = st.columns(6)
        ratios = [
            ("P/E",        r.get("pe"),       lambda x: f"{x:.1f}x" if x else "—"),
            ("P/B",        r.get("pb"),       lambda x: f"{x:.2f}x" if x else "—"),
            ("ROE",        r.get("roe"),      lambda x: f"{x*100:.1f}%" if x and x<1 else f"{x:.1f}%" if x else "—"),
            ("Dette/EQ",   r.get("debt_eq"),  lambda x: f"{x:.0f}%" if x else "—"),
            ("EV/EBITDA",  r.get("ev_ebitda"),lambda x: f"{x:.1f}x" if x else "—"),
            ("RSI",        r.get("rsi"),      lambda x: f"{x:.0f}" if x else "—"),
        ]
        for col, (label, val, fmt) in zip(ratio_cols, ratios):
            display = fmt(val) if val is not None else "—"
            col.metric(label, display)

        st.markdown("""
        <div style="background:#111827;border-left:3px solid #10B981;border-radius:0 10px 10px 0;padding:16px 20px;margin-top:8px">
            <div style="font-size:12px;font-weight:600;color:#10B981;margin-bottom:6px;letter-spacing:1px">ANALYSE PHRONESIS</div>
            <div style="font-size:14px;color:#F9FAFB;line-height:1.7">
                Analyse basée sur le score Phronesis. Un score élevé indique une sous-évaluation potentielle. Complétez par votre propre analyse.
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<hr class="ph-divider">', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# ASSISTANT IA (avec contexte de l'actif sélectionné)
# ---------------------------------------------------------------------------
# Récupérer les données de l'actif sélectionné (si existant)
selected_ticker = st.session_state.get("selected_ticker", None)
df_row = None
if selected_ticker and "df_scored" in st.session_state:
    df = st.session_state.df_scored
    row = df[df["ticker"] == selected_ticker]
    if not row.empty:
        df_row = row.iloc[0].to_dict()
show_ai_assistant(df_row=df_row, ticker=selected_ticker)

# ---------------------------------------------------------------------------
# GRAPHIQUES GLOBAUX
# ---------------------------------------------------------------------------
g2_col1, g2_col2 = st.columns([1, 1])
with g2_col1:
    fig_dist = score_distribution(df_scored)
    st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar": False})
with g2_col2:
    fig_top = top_opportunities_bar(df_scored)
    st.plotly_chart(fig_top, use_container_width=True, config={"displayModeBar": False})

# ---------------------------------------------------------------------------
# CTA — REJOINDRE LE CLUB
# ---------------------------------------------------------------------------
st.markdown('<hr class="ph-divider">', unsafe_allow_html=True)
WHATSAPP_URL = "https://wa.me/22997000000?text=Bonjour%20Phronesis%2C%20je%20veux%20d%C3%A9couvrir%20le%20Club%20Priv%C3%A9"
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
            st.markdown(f"[Cliquer ici pour ouvrir WhatsApp]({WHATSAPP_URL})")
    with cta_b:
        if st.button("📅 Réserver un appel découverte", use_container_width=True):
            st.markdown("[Réserver sur cal.com/phronesis](https://cal.com)")
    st.markdown("""
    <div style="text-align:center;font-size:12px;color:#374151;margin-top:16px">
        Club privé · Nombre de places limité · Sans engagement
    </div>
    """, unsafe_allow_html=True)