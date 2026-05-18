"""
screener/ai_assistant.py
Phronesis Screener — Assistant IA via DeepSeek API
Modèle : deepseek-chat (gratuit, mais nécessite un crédit)
"""

import streamlit as st
import requests
import json
import time

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL   = "deepseek-chat"
MAX_TOKENS       = 600
TEMPERATURE      = 0.4
SESSION_LIMIT    = 20
RATE_LIMIT_SEC   = 3

SYSTEM_PROMPT = """Tu es l'assistant IA du Club Phronesis, spécialisé en analyse financière et investissement value.
Tu dois :
- Répondre en français, de manière concise et professionnelle (max 300 mots)
- Expliquer les données financières de façon accessible
- Contextualiser les signaux du Phronesis Score (Value, Quality, Momentum, Risk)
- Ne jamais donner de conseil d'investissement direct ("achetez", "vendez")
- Toujours rappeler qu'il s'agit d'une analyse algorithmique, pas d'un conseil personnalisé
- Terminer par une question de relance pour encourager l'exploration
Format : utilise des puces courtes, du gras pour les chiffres clés, et reste factuel."""


# ---------------------------------------------------------------------------
# RATE LIMITING
# ---------------------------------------------------------------------------

def _init_session():
    if "ai_request_count" not in st.session_state:
        st.session_state["ai_request_count"] = 0
    if "ai_last_request_time" not in st.session_state:
        st.session_state["ai_last_request_time"] = 0.0
    if "ai_history" not in st.session_state:
        st.session_state["ai_history"] = []

def _check_rate_limit():
    _init_session()
    if st.session_state["ai_request_count"] >= SESSION_LIMIT:
        return False, f"Limite de {SESSION_LIMIT} questions atteinte pour cette session. Rechargez la page."
    elapsed = time.time() - st.session_state["ai_last_request_time"]
    if elapsed < RATE_LIMIT_SEC:
        wait = round(RATE_LIMIT_SEC - elapsed, 1)
        return False, f"Veuillez attendre {wait}s avant la prochaine question."
    return True, ""


# ---------------------------------------------------------------------------
# BUILD CONTEXT
# ---------------------------------------------------------------------------

def _build_asset_context(row: dict) -> str:
    ticker  = row.get("ticker", "?")
    name    = row.get("name", ticker)
    price   = row.get("price", 0)
    fv      = row.get("fair_value")
    upside  = row.get("upside_pct", 0)
    score   = row.get("score", 0)
    signal  = row.get("signal", "Neutre")
    risk    = row.get("risk", "Moyen")
    sector  = row.get("sector", "—")
    asset   = row.get("asset_type", "Action")
    pe      = row.get("pe")
    pb      = row.get("pb")
    roe     = row.get("roe")
    debt    = row.get("debt_eq")
    fcf     = row.get("fcf")
    rsi     = row.get("rsi", 50)
    mom_1m  = row.get("momentum_1m", 0)
    mom_3m  = row.get("momentum_3m", 0)
    vol     = row.get("volatility", 0)
    draw    = row.get("drawdown", 0)
    sv      = row.get("score_value", 0)
    sq      = row.get("score_quality", 0)
    sm      = row.get("score_momentum", 0)
    sr      = row.get("score_risk", 0)

    fv_str  = f"{fv:.2f}" if fv else "non calculée"
    pe_str  = f"{pe:.1f}x" if pe else "N/D"
    pb_str  = f"{pb:.2f}x" if pb else "N/D"
    roe_str = f"{roe*100:.1f}%" if roe else "N/D"
    debt_str= f"{debt:.0f}%" if debt else "N/D"
    fcf_str = f"${fcf/1e9:.1f}Md" if fcf and fcf > 1e8 else ("Négatif" if fcf and fcf < 0 else "N/D")

    return f"""
=== DONNÉES PHRONESIS — {ticker} ({name}) ===
Type d'actif   : {asset} | Secteur : {sector}
Prix actuel    : {price:.2f} | Fair Value estimée : {fv_str} | Upside : {upside:+.1f}%

PHRONESIS SCORE : {score}/100 — {signal} | Risque : {risk}
  • Valeur        : {sv:.0f}/25
  • Qualité       : {sq:.0f}/25
  • Momentum      : {sm:.0f}/25
  • Risque-sécurité: {sr:.0f}/25

FONDAMENTAUX :
  P/E : {pe_str} | P/B : {pb_str} | ROE : {roe_str}
  Dette/Equity : {debt_str} | FCF : {fcf_str}

TECHNIQUE :
  RSI 14j : {rsi:.0f} | Momentum 1M : {mom_1m:+.1f}% | Momentum 3M : {mom_3m:+.1f}%
  Volatilité annualisée : {vol:.1f}% | Drawdown max 3M : {draw:.1f}%
=== FIN DONNÉES ===
"""


# ---------------------------------------------------------------------------
# API CALL DEEPSEEK
# ---------------------------------------------------------------------------

def call_deepseek(question: str, asset_context: str = "") -> str | None:
    api_key = st.secrets.get("DEEPSEEK_API_KEY", None)
    if not api_key:
        return "_⚠️ Clé API DeepSeek non configurée. Ajoute `DEEPSEEK_API_KEY` dans les secrets Streamlit._"

    user_content = question
    if asset_context:
        user_content = f"{asset_context}\n\nQuestion de l'analyste : {question}"

    payload = {
        "model": DEEPSEEK_MODEL,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        elif resp.status_code == 402:
            return (
                "⚠️ **Crédits DeepSeek insuffisants.**\n"
                "Votre compte a été rechargé récemment, cette erreur ne devrait plus apparaître.\n"
                "Si elle persiste, vérifiez votre solde sur platform.deepseek.com."
            )
        elif resp.status_code == 429:
            return "_⚠️ Limite de requêtes DeepSeek atteinte. Réessaie dans quelques secondes._"
        elif resp.status_code == 401:
            return "_⚠️ Clé API DeepSeek invalide. Vérifie ta clé sur platform.deepseek.com._"
        else:
            return f"_⚠️ Erreur API DeepSeek : {resp.status_code} — {resp.text[:200]}_"
    except Exception as e:
        return f"_⚠️ Erreur de connexion : {str(e)[:150]}_"


# ---------------------------------------------------------------------------
# UI PRINCIPALE
# ---------------------------------------------------------------------------

def show_ai_assistant(df_row: dict = None, ticker: str = None):
    _init_session()
    remaining = SESSION_LIMIT - st.session_state["ai_request_count"]

    # Header
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
        <div style="width:8px;height:8px;background:#10B981;border-radius:50%"></div>
        <span style="font-size:13px;font-weight:600;color:#F9FAFB;letter-spacing:.5px">
            ASSISTANT IA PHRONESIS
        </span>
        <span style="font-size:11px;color:#4B5563;margin-left:auto">
            Propulsé par DeepSeek
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Compteur
    counter_color = "#10B981" if remaining > 10 else ("#EAB308" if remaining > 3 else "#EF4444")
    st.markdown(
        f'<div style="font-size:11px;color:{counter_color};margin-bottom:10px">'
        f'{remaining} question{"s" if remaining > 1 else ""} restante{"s" if remaining > 1 else ""} cette session'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Suggestions
    ticker_label = ticker or "cet actif"
    suggestions = [
        f"Pourquoi {ticker_label} est-il {df_row.get('signal','noté ainsi').lower() if df_row else 'ainsi noté'} ?",
        f"Explique le Phronesis Score de {ticker_label}",
        f"Quels sont les risques principaux de {ticker_label} ?",
        "Explique la méthode de fair value utilisée",
    ]

    st.markdown('<div style="font-size:11px;color:#6B7280;margin-bottom:6px">Suggestions rapides :</div>', unsafe_allow_html=True)
    sug_cols = st.columns(2)
    for i, sug in enumerate(suggestions[:4]):
        with sug_cols[i % 2]:
            if st.button(sug, key=f"sug_{i}", width="stretch", disabled=(remaining <= 0)):
                st.session_state["ai_prefill"] = sug

    # Formulaire avec validation par Entrée
    prefill = st.session_state.pop("ai_prefill", "")
    with st.form(key="ai_form"):
        question = st.text_input(
            "Pose ta question :",
            value=prefill,
            placeholder=f"Ex: Pourquoi {ticker_label} a-t-il ce score ?",
            key="ai_question_input"
        )
        send_clicked = st.form_submit_button(
            "Analyser avec l'IA →",
            type="primary",
            width="stretch",
            disabled=(remaining <= 0 or not question.strip())
        )

    # Traitement
    if send_clicked and question.strip():
        ok, msg = _check_rate_limit()
        if not ok:
            st.warning(msg)
        else:
            context = _build_asset_context(df_row) if df_row else ""
            with st.spinner("Analyse en cours..."):
                answer = call_deepseek(question.strip(), context)

            st.session_state["ai_request_count"] += 1
            st.session_state["ai_last_request_time"] = time.time()
            st.session_state["ai_history"].append({
                "q": question.strip(),
                "a": answer,
                "ticker": ticker or "—",
                "ts": time.strftime("%H:%M"),
            })

    # Historique
    history = st.session_state.get("ai_history", [])
    if history:
        for entry in reversed(history[-5:]):
            st.markdown(f"""
            <div style="background:#1F2937;border-radius:8px 8px 0 0; padding:10px 14px;margin-top:12px;border-left:3px solid #3B82F6">
                <span style="font-size:11px;color:#6B7280">{entry['ts']} · {entry['ticker']}</span><br>
                <span style="font-size:13px;color:#93C5FD;font-weight:500">{entry['q']}</span>
            </div>
            """, unsafe_allow_html=True)
            with st.container():
                st.markdown(f"""
                <div style="background:#111827;border-radius:0 0 8px 8px; padding:14px 16px;border-left:3px solid #10B981;margin-bottom:4px">
                """, unsafe_allow_html=True)
                st.markdown(entry["a"])
                st.markdown("</div>", unsafe_allow_html=True)

        if st.button("Effacer l'historique", key="clear_ai_history"):
            st.session_state["ai_history"] = []
            st.toast("Historique effacé", icon="🗑️")


# ---------------------------------------------------------------------------
# GUIDE DE CONFIGURATION (si clé absente)
# ---------------------------------------------------------------------------

def show_setup_guide():
    st.markdown("""
    <div style="background:#1F2937;border:1px solid #374151;border-radius:10px;padding:16px 20px">
        <div style="font-weight:600;color:#F9FAFB;margin-bottom:10px">
            ⚙️ Configurer l'Assistant IA
        </div>
        <div style="font-size:13px;color:#9CA3AF;line-height:1.8">
            1. Crée un compte gratuit sur <strong>platform.deepseek.com</strong><br>
            2. Génère une clé API dans ton dashboard<br>
            3. Dans Streamlit Cloud → <strong>App settings → Secrets</strong><br>
            4. Ajoute : <code>DEEPSEEK_API_KEY = "sk-..."</code><br>
            5. Redémarre l'application
        </div>
    </div>
    """, unsafe_allow_html=True)