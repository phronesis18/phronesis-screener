"""
screener/lead_capture.py
Phronesis Screener — capture leads → Google Sheets
Formulaire Streamlit affiché avant accès au dashboard.
"""

import streamlit as st
import datetime

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

SHEET_ID = "VOTRE_GOOGLE_SHEET_ID"   # ← Remplacer par l'ID de ta Google Sheet
SHEET_NAME = "Leads"                  # Nom de l'onglet


# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------

def is_lead_captured() -> bool:
    """Vérifie si le lead a déjà rempli le formulaire dans cette session."""
    return st.session_state.get("lead_captured", False)


def mark_lead_captured():
    st.session_state["lead_captured"] = True


# ---------------------------------------------------------------------------
# SAUVEGARDE GOOGLE SHEETS
# ---------------------------------------------------------------------------

def save_lead_to_sheets(data: dict) -> bool:
    """
    Sauvegarde un lead dans Google Sheets via gspread.
    Nécessite le secret GOOGLE_CREDS dans Streamlit Cloud.
    """
    try:
        import gspread
        import json
        from google.oauth2.service_account import Credentials

        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        # Lecture des credentials depuis Streamlit secrets
        creds_raw = st.secrets.get("GOOGLE_CREDS", None)
        if not creds_raw:
            # Mode démo : pas de credentials → juste marquer le lead
            return True

        creds_dict = json.loads(creds_raw) if isinstance(creds_raw, str) else dict(creds_raw)
        creds  = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

        row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("prenom", ""),
            data.get("email", ""),
            data.get("whatsapp", ""),
            data.get("pays", ""),
            data.get("profil", ""),
            data.get("objectif", ""),
        ]
        sheet.append_row(row)
        return True

    except Exception as e:
        # En cas d'erreur Sheets, on laisse quand même passer l'utilisateur
        st.warning(f"⚠️ Sauvegarde lead partielle : {e}", icon="⚠️")
        return True  # Ne pas bloquer l'accès pour autant


# ---------------------------------------------------------------------------
# FORMULAIRE
# ---------------------------------------------------------------------------

def show_lead_form():
    """
    Affiche le formulaire de capture avant accès au screener.
    Layout : centré, premium, mobile-first.
    """
    # CSS gate page
    st.markdown("""
    <style>
    .gate-hero {
        text-align: center;
        padding: 32px 0 24px;
    }
    .gate-logo {
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: 4px;
        color: #10B981;
        margin-bottom: 6px;
    }
    .gate-tagline {
        font-size: 1.05rem;
        color: #9CA3AF;
        margin-bottom: 4px;
    }
    .gate-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #F9FAFB;
        margin: 20px 0 8px;
    }
    .gate-sub {
        font-size: 0.95rem;
        color: #6B7280;
        margin-bottom: 28px;
    }
    .features-row {
        display: flex;
        justify-content: center;
        gap: 24px;
        flex-wrap: wrap;
        margin-bottom: 32px;
    }
    .feature-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: #9CA3AF;
    }
    .feature-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: #10B981;
        flex-shrink: 0;
    }
    </style>

    <div class="gate-hero">
        <div class="gate-logo">PHRONESIS</div>
        <div class="gate-tagline">Club d'Investissement · Screener Multi-Actifs</div>
        <div class="gate-title">Accédez au Screener Gratuit</div>
        <div class="gate-sub">
            Détectez les actifs sous-évalués et surévalués en temps réel.<br>
            Alimenté par la méthodologie propriétaire Phronesis Score.
        </div>
        <div class="features-row">
            <div class="feature-item"><div class="feature-dot"></div>Actions US, ETF, Crypto, Forex</div>
            <div class="feature-item"><div class="feature-dot"></div>Score propriétaire 0-100</div>
            <div class="feature-item"><div class="feature-dot"></div>Mis à jour en temps réel</div>
            <div class="feature-item"><div class="feature-dot"></div>100% gratuit</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Formulaire centré
    col_l, col_form, col_r = st.columns([1, 2, 1])
    with col_form:
        with st.form("lead_form", clear_on_submit=False):
            prenom = st.text_input("Prénom *", placeholder="Ex : Jean-Baptiste")
            email  = st.text_input("Email *", placeholder="nom@exemple.com")
            whatsapp = st.text_input(
                "WhatsApp (avec indicatif) *",
                placeholder="+229 97 00 00 00"
            )
            pays = st.selectbox("Pays de résidence", [
                "Bénin", "Côte d'Ivoire", "Sénégal", "Togo", "Cameroun",
                "Mali", "Burkina Faso", "Guinée", "Niger", "RDC",
                "France", "Belgique", "Suisse", "Canada",
                "États-Unis", "Maroc", "Tunisie", "Algérie",
                "Nigeria", "Ghana", "Kenya", "Autre"
            ])
            profil = st.selectbox("Ton niveau en investissement", [
                "Débutant — je commence tout juste",
                "Intermédiaire — 1 à 5 ans d'expérience",
                "Expérimenté — plus de 5 ans",
                "Professionnel (finance, gestion de portefeuille)"
            ])
            objectif = st.selectbox("Ton objectif principal", [
                "Faire croître mon capital",
                "Générer des revenus passifs",
                "Préparer ma retraite",
                "Diversifier mon patrimoine",
                "Apprendre à investir"
            ])

            submitted = st.form_submit_button(
                "Accéder au Screener Gratuit →",
                type="primary",
                use_container_width=True
            )

            if submitted:
                # Validation
                errors = []
                if not prenom.strip():
                    errors.append("Le prénom est obligatoire.")
                if not email.strip() or "@" not in email:
                    errors.append("Merci d'entrer un email valide.")
                if not whatsapp.strip():
                    errors.append("Le numéro WhatsApp est obligatoire.")

                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    with st.spinner("Enregistrement en cours..."):
                        save_lead_to_sheets({
                            "prenom":    prenom.strip(),
                            "email":     email.strip().lower(),
                            "whatsapp":  whatsapp.strip(),
                            "pays":      pays,
                            "profil":    profil,
                            "objectif":  objectif,
                        })
                    mark_lead_captured()
                    # Utilisation d'un toast non-bloquant (pas de st.success)
                    st.toast("✅ Bienvenue ! Chargement du screener...", icon="🏛")

        # Footer
        st.markdown("""
        <div style="text-align:center;font-size:12px;color:#4B5563;margin-top:16px;line-height:1.6">
            Tes données sont confidentielles et ne seront jamais revendues.<br>
            En accédant au screener, tu acceptes de recevoir nos analyses hebdomadaires.
        </div>
        """, unsafe_allow_html=True)