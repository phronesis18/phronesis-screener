"""
tickers_lists.py
Phronesis Screener — Base de données des tickers multi-bourses.

Structure :
- Récupération DYNAMIQUE (via Wikipedia) pour les indices US : S&P 500, Nasdaq 100, Russell 2000
- Listes STATIQUES pour l'Europe, l'Asie, l'Afrique, les ETF, Crypto, Forex, Commodités

Objectif : ~1800 tickers toutes classes d'actifs et places boursières confondues.
"""

import io
import logging
import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ============================================================================
# HEADERS WIKIPEDIA (contourne le blocage HTTP 403)
# ============================================================================

WIKI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _read_html_with_headers(url: str) -> list:
    """Récupère les tableaux d'une page Wikipedia en contournant le blocage 403."""
    resp = requests.get(url, headers=WIKI_HEADERS, timeout=30)
    resp.raise_for_status()
    return pd.read_html(io.StringIO(resp.text))


# ============================================================================
# SECTION 1 — ÉTATS-UNIS (récupération dynamique + extras statiques)
# ============================================================================

def fetch_sp500() -> list[str]:
    """Récupère les 500 composants du S&P 500 depuis Wikipedia."""
    try:
        tables = _read_html_with_headers("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        df = tables[0]
        tickers = df['Symbol'].tolist()
        # Yahoo Finance utilise '-' au lieu de '.' pour les classes d'actions (BRK.B → BRK-B)
        tickers = [str(t).replace('.', '-') for t in tickers]
        logging.info(f"✅ S&P 500 : {len(tickers)} tickers")
        return tickers
    except Exception as e:
        logging.warning(f"⚠️ Erreur récupération S&P 500 : {e}")
        return []


def fetch_nasdaq100() -> list[str]:
    """Récupère les 100 composants du Nasdaq 100 depuis Wikipedia."""
    try:
        tables = _read_html_with_headers("https://en.wikipedia.org/wiki/Nasdaq-100")
        for table in tables:
            if 'Ticker' in table.columns:
                tickers = table['Ticker'].tolist()
                tickers = [str(t).replace('.', '-') for t in tickers]
                logging.info(f"✅ Nasdaq 100 : {len(tickers)} tickers")
                return tickers
        return []
    except Exception as e:
        logging.warning(f"⚠️ Erreur récupération Nasdaq 100 : {e}")
        return []


def fetch_russell2000_sample() -> list[str]:
    """
    Récupère un échantillon de mid-caps US (non exhaustif du Russell 2000,
    mais suffisant pour enrichir la couverture).
    """
    try:
        tables = _read_html_with_headers("https://en.wikipedia.org/wiki/Russell_2000_Index")
        for table in tables:
            if 'Symbol' in table.columns or 'Ticker' in table.columns:
                col = 'Symbol' if 'Symbol' in table.columns else 'Ticker'
                tickers = table[col].tolist()
                tickers = [str(t).replace('.', '-') for t in tickers if isinstance(t, str)]
                logging.info(f"✅ Russell 2000 (échantillon) : {len(tickers)} tickers")
                return tickers
        return []
    except Exception as e:
        logging.warning(f"⚠️ Erreur récupération Russell 2000 : {e}")
        return []


# Extras US non couverts par les indices (tech, growth, small caps populaires)
US_EXTRAS = [
    # Mega/Large caps tech supplémentaires
    "PLTR", "SNOW", "DDOG", "NET", "CRWD", "ZS", "OKTA", "MDB", "TEAM", "HUBS",
    "VEEV", "WDAY", "NOW", "INTU", "ADSK", "ANSS", "CDNS", "SNPS", "KLAC", "LRCX",
    "AMAT", "MRVL", "ON", "NXPI", "QRVO", "SWKS", "MPWR", "TER", "ENTG", "AZTA",
    # Fintech / néo-banques
    "SOFI", "HOOD", "AFRM", "UPST", "LC", "MQ", "NU", "STNE", "PAGS",
    "COIN", "MARA", "RIOT", "CLSK", "HUT", "BITF", "CIFR",
    # EV / Mobility / Space
    "RIVN", "LCID", "NIO", "XPEV", "LI", "FSR", "GOEV", "RIDE", "MULN",
    "RKLB", "ASTR", "SPCE", "JOBY", "ACHR", "LILM",
    # Biotech / Small caps santé
    "MRNA", "BNTX", "NVAX", "OCGN", "VXRT", "SRPT", "CRSP", "NTLA", "BEAM",
    "EDIT", "VERV", "SGMO", "BLUE", "SAGE", "ACAD", "IONS", "ALNY",
    # Consumer / Retail / Divers
    "ABNB", "UBER", "LYFT", "DASH", "CART", "INST", "W", "CHWY", "ETSY", "EBAY",
    "PINS", "SNAP", "SPOT", "ROKU", "TTD", "MGNI", "PUBM", "APPS", "DOCN",
    # Industrials / Defense / Materials
    "AXON", "LDOS", "SAIC", "CACI", "BAH", "LHX", "HII", "GD", "NOC", "RTX",
    "LMT", "TDG", "HEI", "TDY", "AMETEK", "ROK", "DOV", "PH", "ETN", "EMR",
    # REIT / Utilities
    "O", "PLD", "SPG", "AMT", "CCI", "EQIX", "DLR", "PSA", "EXR", "AVB",
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "PEG", "ED",
]


# ============================================================================
# SECTION 2 — EUROPE
# ============================================================================

EUROPE_TICKERS = [
    # --- France (Euronext Paris) .PA ---
    "AIR.PA", "SAN.PA", "OR.PA", "SU.PA", "TTE.PA", "CAP.PA", "SGO.PA",
    "BNP.PA", "ACA.PA", "CA.PA", "GLE.PA", "KER.PA", "PRTP.PA", "LR.PA",
    "VIE.PA", "PUB.PA", "BVI.PA", "EN.PA", "ENGI.PA", "RNO.PA",
    "ML.PA", "STM.PA", "DSY.PA", "STLAP.PA", "SAF.PA", "TRI.PA", "EL.PA",
    "MC.PA", "RMS.PA", "CDI.PA", "BB.PA", "ALO.PA", "UG.PA",
    "HO.PA", "AI.PA", "BN.PA", "DG.PA", "ERF.PA", "FR.PA", "GTT.PA",
    "IPH.PA", "LEG.PA", "MERY.PA", "NEX.PA", "ORA.PA", "RI.PA", "SOP.PA",
    "SW.PA", "TEP.PA", "URW.PA", "VIV.PA", "WAVE.PA", "AKE.PA", "ELIS.PA",
    "TE.PA", "RCO.PA", "SESG.PA", "VK.PA", "FDJ.PA", "GET.PA", "ATO.PA",

    # --- Allemagne (Deutsche Börse XETRA) .DE ---
    "SAP.DE", "SIEM.DE", "ALV.DE", "DTE.DE", "BAS.DE", "BAYN.DE", "BMW.DE",
    "MBG.DE", "VOW3.DE", "ADS.DE", "MUV2.DE", "FRE.DE", "HEI.DE", "HEN3.DE",
    "IFX.DE", "LIN.DE", "P911.DE", "QIA.DE", "RWE.DE", "SIE.DE",
    "AIR.DE", "BEI.DE", "BNR.DE", "CBK.DE", "CON.DE", "DB1.DE", "DBK.DE",
    "DPW.DE", "EOAN.DE", "FME.DE", "G24.DE", "HNR1.DE", "HRX.DE",
    "MTX.DE", "PAH3.DE", "PUM.DE", "RHM.DE", "SHL.DE", "SY1.DE", "VNA.DE",
    "ZAL.DE", "1COV.DE", "AFX.DE", "BOSS.DE", "ENR.DE", "KGX.DE", "LXS.DE",
    "NDX1.DE", "SZG.DE", "TKA.DE", "WCH.DE", "WDI.DE", "ZOE.DE",

    # --- Royaume-Uni (London Stock Exchange) .L ---
    "HSBA.L", "SHEL.L", "GSK.L", "AZN.L", "DGE.L", "BP.L", "RIO.L",
    "BHP.L", "REL.L", "CPG.L", "ULVR.L", "LSEG.L", "NG.L",
    "VOD.L", "BT-A.L", "LLOY.L", "BARC.L", "STAN.L", "PRU.L",
    "ABF.L", "AHT.L", "ANTO.L", "AAL.L", "AV.L", "BA.L", "BATS.L",
    "BLND.L", "BNZL.L", "BRBY.L", "CCH.L", "CNA.L", "CRDA.L", "DCC.L",
    "EDV.L", "EXPN.L", "FERG.L", "FLTR.L", "FRAS.L", "FRES.L", "GLEN.L",
    "HIK.L", "HLMA.L", "HLN.L", "III.L", "IMB.L", "IMI.L", "INF.L",
    "IHG.L", "ITRK.L", "JD.L", "KGF.L", "LAND.L", "LGEN.L", "MKS.L",
    "MNDI.L", "MNG.L", "MRO.L", "NXT.L", "OCDO.L", "PHNX.L", "PSON.L",
    "PSN.L", "RKT.L", "RMV.L", "RR.L", "SBRY.L", "SDR.L", "SGE.L",
    "SGRO.L", "SJP.L", "SKG.L", "SMDS.L", "SMIN.L", "SMT.L", "SPX.L",
    "SSE.L", "STJ.L", "SVT.L", "TSCO.L", "TW.L", "UU.L", "WTB.L", "WPP.L",

    # --- Italie (Borsa Italiana) .MI ---
    "ENEL.MI", "ENI.MI", "ISP.MI", "UCG.MI", "STM.MI", "PRY.MI",
    "MONC.MI", "RACE.MI", "PST.MI", "TIT.MI", "A2A.MI", "AMP.MI",
    "AZM.MI", "BAMI.MI", "BPE.MI", "BPER.MI", "BZU.MI", "CPR.MI",
    "DIA.MI", "FBK.MI", "G.MI", "HER.MI", "IG.MI", "IP.MI",
    "IT.MI", "LDO.MI", "MB.MI", "MED.MI", "NEXI.MI", "PIRC.MI",
    "REC.MI", "SPM.MI", "SRG.MI", "TEN.MI", "TRN.MI", "UNI.MI",

    # --- Espagne (Bolsa de Madrid) .MC ---
    "SAN.MC", "BBVA.MC", "TEF.MC", "IBE.MC", "REP.MC", "AENA.MC",
    "FER.MC", "ACS.MC", "ELE.MC", "CABK.MC", "ACX.MC",
    "AMS.MC", "ANA.MC", "BKT.MC", "CAF.MC", "CIE.MC", "COL.MC",
    "ENG.MC", "FDR.MC", "GRF.MC", "IAG.MC", "IDR.MC", "ITX.MC",
    "LOG.MC", "MAP.MC", "MEL.MC", "MRL.MC", "MTS.MC", "NTGY.MC",
    "RED.MC", "ROVI.MC", "SAB.MC", "SCYR.MC", "SLR.MC", "TRE.MC",
    "UNI.MC", "VIS.MC",

    # --- Pays-Bas (Euronext Amsterdam) .AS ---
    "INGA.AS", "ASML.AS", "PHIA.AS", "UNI.AS", "ABN.AS", "AD.AS",
    "RAND.AS", "HEIA.AS", "KPN.AS", "AKZA.AS", "ASM.AS", "BESI.AS",
    "DSFIR.AS", "EXO.AS", "FUR.AS", "HEIJM.AS", "IMCD.AS", "JDEP.AS",
    "NN.AS", "OCI.AS", "SIGN.AS", "TKWY.AS", "VPK.AS", "WKL.AS",

    # --- Belgique (Euronext Bruxelles) .BR ---
    "ABI.BR", "UCB.BR", "SOLB.BR", "KBC.BR", "AGE.BR", "BAR.BR",
    "ACKB.BR", "AEDS.BR", "APAM.BR", "BEKB.BR", "COFB.BR", "COLR.BR",
    "DIE.BR", "ELI.BR", "GBLB.BR", "ING.BR", "KBCA.BR", "LOTB.BR",
    "MELE.BR", "ONTEX.BR", "PROX.BR", "REC.BR", "SOF.BR", "TNET.BR",
    "TESB.BR", "UMI.BR", "WDP.BR",

    # --- Suisse (SIX Swiss Exchange) .SW ---
    "NOVN.SW", "ROG.SW", "NESN.SW", "UBSG.SW", "ABBN.SW", "SCHN.SW",
    "LONN.SW", "CFR.SW", "SREN.SW", "GEBN.SW", "ZURN.SW", "BAER.SW",
    "GIVN.SW", "HOLN.SW", "KNIN.SW", "LOGN.SW", "SGSN.SW", "SIKA.SW",
    "SLHN.SW", "STMN.SW", "TEMN.SW", "ALC.SW", "BUCN.SW", "DAE.SW",
    "EMMN.SW", "FHZN.SW", "GALE.SW", "HELN.SW", "IMPN.SW", "KUE.SW",

    # --- Portugal (Euronext Lisbon) .LS ---
    "EDP.LS", "GALP.LS", "JMT.LS", "BCP.LS", "SON.LS", "SEM.LS",
    "EGL.LS", "CTT.LS", "NOS.LS", "ALTR.LS", "COR.LS", "IBS.LS",
    "NBA.LS", "RAM.LS",

    # --- Suède (.ST), Danemark (.CO), Norvège (.OL), Finlande (.HE) ---
    "VOLV-B.ST", "ERIC-B.ST", "ATCO-A.ST", "SAND.ST", "HM-B.ST",
    "SEB-A.ST", "SWED-A.ST", "SHB-A.ST", "INVE-B.ST", "ESSITY-B.ST",
    "NOVO-B.CO", "MAERSK-B.CO", "DSV.CO", "ORSTED.CO", "VWS.CO",
    "EQNR.OL", "DNB.OL", "TEL.OL", "MOWI.OL", "AKRBP.OL",
    "NOKIA.HE", "FORTUM.HE", "UPM.HE", "SAMPO.HE", "NESTE.HE",

    # --- Autres places européennes (Irlande .IR, Autriche .VI, Pologne .WA, Grèce .AT) ---
    "RYA.IR", "KRZ.IR", "KRX.IR", "GL9.IR", "DQ7A.IR",
    "OMV.VI", "EBS.VI", "VIG.VI", "ANDR.VI", "WIE.VI",
    "PKN.WA", "PKO.WA", "PEO.WA", "PGE.WA", "KGH.WA", "LPP.WA",
    "OTP.AT", "MOL.AT", "RICHTER.AT", "OPAP.AT", "ALPHA.AT",
]


# ============================================================================
# SECTION 3 — ASIE & OCÉANIE
# ============================================================================

ASIA_TICKERS = [
    # --- Japon (Tokyo Stock Exchange) .T ---
    "9984.T", "8035.T", "8306.T", "6758.T", "9983.T", "9432.T",
    "9433.T", "6861.T", "9201.T", "7267.T", "8316.T", "4503.T",
    "4519.T", "4689.T", "6701.T", "7974.T", "8001.T", "8058.T",
    "6501.T", "6503.T", "6594.T", "6902.T", "6954.T", "7203.T",
    "7741.T", "7751.T", "8031.T", "8053.T", "8267.T", "8411.T",
    "8591.T", "8604.T", "8766.T", "8801.T", "8802.T", "8830.T",
    "9020.T", "9022.T", "9064.T", "9101.T", "9104.T", "9107.T",
    "9531.T", "9532.T", "9613.T", "9735.T", "9843.T", "6098.T",
    "4063.T", "4901.T", "5108.T", "5401.T", "5713.T", "5802.T",
    "6273.T", "6301.T", "6367.T", "6479.T", "6645.T", "6981.T",
    "7270.T", "7733.T", "7832.T", "8015.T", "8113.T", "8233.T",

    # --- Chine continentale (Shanghai .SS / Shenzhen .SZ) ---
    "600519.SS", "600036.SS", "601398.SS", "601939.SS", "600000.SS",
    "601288.SS", "601988.SS", "601857.SS", "600028.SS", "601088.SS",
    "600030.SS", "601166.SS", "600887.SS", "600276.SS", "600585.SS",
    "601318.SS", "601628.SS", "601336.SS", "601601.SS", "601066.SS",
    "000858.SZ", "002594.SZ", "300750.SZ", "000333.SZ", "000651.SZ",
    "000002.SZ", "000001.SZ", "000063.SZ", "000725.SZ", "002415.SZ",
    "002304.SZ", "002714.SZ", "300059.SZ", "300015.SZ", "300124.SZ",
    "002460.SZ", "002466.SZ", "002049.SZ", "000568.SZ", "000538.SZ",

    # --- Hong Kong (HKEX) .HK — 4 chiffres, sans zéro en tête ---
    "0700.HK", "9988.HK", "9999.HK", "1810.HK", "0388.HK", "0005.HK",
    "0011.HK", "0016.HK", "0027.HK", "0175.HK", "3690.HK",
    "0939.HK", "1398.HK", "3988.HK", "0883.HK", "0857.HK",
    "2318.HK", "2628.HK", "1299.HK", "0003.HK", "0006.HK",
    "0012.HK", "0066.HK", "0291.HK", "1044.HK",
    "1109.HK", "1113.HK", "1211.HK", "2020.HK", "2331.HK",
    "2382.HK", "9618.HK", "9888.HK", "9961.HK",

    # --- Inde (National Stock Exchange) .NS ---
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "KOTAKBANK.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS", "SBIN.NS",
    "LT.NS", "AXISBANK.NS", "WIPRO.NS", "SUNPHARMA.NS", "TITAN.NS",
    "ASIANPAINT.NS", "MARUTI.NS", "ULTRACEMCO.NS", "NTPC.NS", "POWERGRID.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "HCLTECH.NS", "TECHM.NS", "NESTLEIND.NS",
    "TATAMOTORS.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "GRASIM.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "COALINDIA.NS", "ONGC.NS", "BPCL.NS", "IOC.NS",
    "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "BRITANNIA.NS",
    "EICHERMOT.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "INDUSINDBK.NS", "SHREECEM.NS",

    # --- Corée du Sud (Korea Exchange) .KS ---
    "005930.KS", "000660.KS", "005380.KS", "051910.KS", "005490.KS",
    "035420.KS", "005935.KS", "012330.KS", "055550.KS", "105560.KS",
    "068270.KS", "006400.KS", "000270.KS", "096770.KS", "017670.KS",
    "015760.KS", "032830.KS", "086790.KS", "316140.KS", "009150.KS",

    # --- Taïwan (Taiwan Stock Exchange) .TW ---
    "2330.TW", "2317.TW", "2454.TW", "2412.TW", "2308.TW",
    "2303.TW", "2881.TW", "2882.TW", "1301.TW", "1303.TW",
    "2002.TW", "1216.TW", "2207.TW", "2382.TW", "2891.TW",
    "2886.TW", "3711.TW", "2884.TW", "2892.TW", "5871.TW",

    # --- Singapour (SGX) .SI ---
    "D05.SI", "O39.SI", "U11.SI", "Z74.SI", "C6L.SI",
    "S68.SI", "A17U.SI", "C38U.SI", "G13.SI", "H78.SI",
    "BN4.SI", "F34.SI", "T39.SI", "Y92.SI", "BS6.SI",

    # --- Indonésie (.JK), Malaisie (.KL), Thaïlande (.BK), Philippines (.PS) ---
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK",
    "UNVR.JK", "ICBP.JK", "INDF.JK", "KLBF.JK", "HMSP.JK",
    "1155.KL", "1023.KL", "1295.KL", "5347.KL", "5183.KL",
    "PTT.BK", "ADVANC.BK", "AOT.BK", "SCB.BK", "KBANK.BK",
    "SM.PS", "BDO.PS", "TEL.PS", "ALI.PS", "JFC.PS",

    # --- Australie (ASX) .AX ---
    "BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX", "WBC.AX",
    "ANZ.AX", "WES.AX", "MQG.AX", "WOW.AX", "TLS.AX",
    "RIO.AX", "FMG.AX", "TCL.AX", "GMG.AX", "ALL.AX",
    "REA.AX", "COL.AX", "SUN.AX", "QBE.AX", "AMC.AX",

    # --- Nouvelle-Zélande (NZX) .NZ ---
    "AIR.NZ", "ANZ.NZ", "FPH.NZ", "MEL.NZ", "SPK.NZ",
    "RYM.NZ", "FBU.NZ", "SKC.NZ", "POT.NZ", "VCT.NZ",
]


# ============================================================================
# SECTION 4 — AFRIQUE
# ============================================================================

AFRICA_TICKERS = [
    # --- Afrique du Sud (Johannesburg Stock Exchange) .JO ---
    "NPN.JO", "CPHP.JO", "SHP.JO", "SBK.JO", "FSR.JO", "AGL.JO",
    "BIL.JO", "MTN.JO", "VOD.JO", "TGA.JO", "ABG.JO", "NED.JO", "INL.JO", "SAP.JO",
    "SOL.JO", "AMS.JO", "BID.JO", "BVT.JO", "CLS.JO", "DSY.JO",
    "EXX.JO", "GFI.JO", "HAR.JO", "IMP.JO", "KIO.JO", "MCG.JO",
    "MNP.JO", "MRP.JO", "MTA.JO", "NHM.JO", "OMN.JO", "PPH.JO",
    "RDF.JO", "REM.JO", "RNI.JO", "SLM.JO", "SNT.JO", "SPP.JO",
    "TFG.JO", "TRU.JO", "WHL.JO", "ZED.JO",

    # --- Nigéria (Nigerian Exchange Group) .NG ---
    "DANGCEM.NG", "MTNN.NG", "ZENITHBANK.NG", "UBA.NG", "GTCO.NG",
    "NESTLE.NG", "BUACEMENT.NG", "SEPLAT.NG", "OANDO.NG", "WAPCO.NG",
    "ACCESS.NG", "FBNH.NG", "FIDELITYBK.NG", "STANBIC.NG", "UBN.NG",
    "NB.NG", "GUINNESS.NG", "UNILEVER.NG", "CADBURY.NG", "TOTAL.NG",
    "TRANSCORP.NG", "CONOIL.NG", "ETERNA.NG", "FO.NG", "PRESCO.NG",

    # --- Maroc (Casablanca Stock Exchange) .MA ---
    "ATW.MA", "IMM.MA", "BCP.MA", "BMCE.MA", "SNI.MA", "LHM.MA",
    "MNG.MA", "SAMIR.MA", "HPS.MA", "NEXANS.MA", "BOA.MA",
    "CIH.MA", "ADH.MA", "TQM.MA", "SID.MA", "CSR.MA",
    "AFI.MA", "CMA.MA", "CTM.MA", "DHO.MA", "FBR.MA",
    "GAZ.MA", "IMO.MA", "LBV.MA", "MUT.MA", "SBM.MA",
    "SGTM.MA", "TMA.MA", "WAA.MA", "ZEL.MA",

    # --- Égypte (Egyptian Exchange) .CA ---
    "CCAP.CA", "CIB.CA", "EMFD.CA", "ESRS.CA", "KIMA.CA",
    "ORWE.CA", "PHDC.CA", "SWDY.CA", "TMGH.CA", "UEEG.CA",
    "ABUK.CA", "ADIB.CA", "AMOC.CA", "EFIH.CA", "EGAL.CA",
    "ELSH.CA", "ETEL.CA", "HRHO.CA", "ISPH.CA", "JUFO.CA",
    "MFPC.CA", "MNHD.CA", "MTIE.CA", "OCDI.CA", "SKPC.CA",

    # --- Kenya (Nairobi Securities Exchange) .NK ---
    "EQTY.NK", "SCOM.NK", "KCB.NK", "BAT.NK", "COOP.NK",
    "KPL.NK", "KEG.NK", "SASN.NK", "ABSA.NK", "BKG.NK",
    "BRIT.NK", "CARB.NK", "CIC.NK", "DTK.NK", "EABL.NK",
    "HFCK.NK", "IMH.NK", "JUB.NK", "KNRE.NK", "NMG.NK",
    "SBIC.NK", "SCAN.NK", "TPSE.NK", "UMME.NK", "WTK.NK",

    # --- Ghana (Ghana Stock Exchange) .GH ---
    "GCB.GH", "EGH.GH", "SOGEGH.GH", "TOTAL.GH", "UNIL.GH",
    "CLYD.GH", "GOIL.GH", "MMH.GH", "PBC.GH", "SCB.GH",

    # --- Tunisie (Bourse de Tunis) .TN ---
    "BIAT.TN", "SFBT.TN", "Poulina.TN", "SAH.TN", "TLNET.TN",
    "ATB.TN", "BNA.TN", "BH.TN", "STB.TN", "UIB.TN",
    "AB.TN", "AMI.TN", "ASSAD.TN", "BTE.TN", "CIL.TN",
    "DH.TN", "ELECTROSTAR.TN", "ESSOUKNA.TN", "ICF.TN", "LandOr.TN",
    "MAGHREBIN.TN", "MPBS.TN", "NAKL.TN", "OTH.TN", "PLAST.TN",
    "SIPH.TN", "SIAME.TN", "SITEX.TN", "SOTETEL.TN", "SOTUVER.TN",
    "STAR.TN", "TGH.TN", "TPR.TN", "UADH.TN", "WIFAK.TN",

    # --- Maurice (.MU), Botswana (.BW) — quelques exemples ---
    "MCB.MU", "SBM.MU", "CIEL.MU", "ENL.MU", "IBL.MU",
    "BAT.MU", "NMH.MU", "PAD.MU", "PIM.MU", "SUN.MU",
]


# ============================================================================
# SECTION 5 — ETF (US + International)
# ============================================================================

ETF_TICKERS = [
    # --- ETF US broad market ---
    "SPY", "QQQ", "IVV", "VOO", "VTI", "VT", "ITOT", "SCHB", "RSP", "SPLG",
    # --- Obligations ---
    "BND", "AGG", "TLT", "IEF", "SHY", "LQD", "HYG", "JNK", "MUB", "BIL",
    "VCIT", "VCSH", "EMB", "TIP", "GOVT", "SCHZ", "IGSB", "SPSB",
    # --- Or & matières premières ---
    "GLD", "IAU", "SLV", "USO", "UNG", "DBA", "DBC", "PPLT", "PALL", "GDX",
    "GDXJ", "SIL", "COPX", "URA", "LIT", "REMX", "XME",
    # --- International ---
    "EEM", "VWO", "IEMG", "EWZ", "FXI", "MCHI", "KWEB", "CQQQ", "EFA",
    "VGK", "EWJ", "DXJ", "INDA", "SMIN", "EWT", "EWY", "EWW", "EWC",
    "EZU", "IEV", "FEZ", "EWG", "EWQ", "EWU", "EWL", "EWI", "EWP", "EWD",
    "EWN", "EWK", "EPOL", "TUR", "EZA", "EIS", "AFK", "NGE",
    # --- Sectoriels US ---
    "XLE", "XLF", "XLK", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE",
    "XLC", "VDE", "VFH", "VGT", "VHT", "VIS", "VCR", "VDC", "VPU", "VAW",
    "IYE", "IYF", "IYW", "IYH", "IYJ", "IYC", "IYK", "IDU", "IYM", "IYR",
    # --- Biotech & Santé ---
    "IBB", "XBI", "LABU", "LABD", "IHI", "XHE", "PPH", "FBT",
    # --- Tech & Semi ---
    "SMH", "SOXX", "IGV", "FTEC", "CIBR", "HACK", "BOTZ", "ROBO",
    "ARKK", "ARKW", "ARKG", "ARKF", "ARKQ", "ARKX",
    # --- Small/Mid Caps ---
    "VTWO", "IWM", "IJH", "IJR", "VB", "VO", "VBR", "VBK", "IWO", "IWN",
    "MDY", "IJJ", "IJK", "SLY", "SCHM", "SCHA",
    # --- Dividendes ---
    "VYM", "VIG", "SCHD", "DVY", "HDV", "SPHD", "SDY", "DGRO", "NOBL",
    # --- Thématiques ---
    "QCLN", "ICLN", "TAN", "FAN", "PBW", "ACES", "ESGU", "ESGV", "SUSA",
    # --- Emerging & Frontier ---
    "FM", "FRDM", "EEMS", "VSS", "SCZ", "GWX", "DGS", "DEM", "DVYE",
]


# ============================================================================
# SECTION 6 — CRYPTO
# ============================================================================

CRYPTO_TICKERS = [
    # --- Top 10 ---
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD", "XRP-USD",
    "DOGE-USD", "DOT-USD", "AVAX-USD", "MATIC-USD",
    # --- Large caps ---
    "LINK-USD", "LTC-USD", "BCH-USD", "UNI-USD", "ATOM-USD", "XLM-USD",
    "ALGO-USD", "VET-USD", "FIL-USD", "ICP-USD", "NEAR-USD", "APT-USD",
    "ARB-USD", "OP-USD", "ETC-USD", "HBAR-USD", "FTM-USD",
    # --- DeFi ---
    "AAVE-USD", "MKR-USD", "COMP-USD", "CRV-USD", "SNX-USD", "SUSHI-USD",
    "YFI-USD", "1INCH-USD", "CAKE-USD", "RUNE-USD", "KAVA-USD",
    # --- Gaming & Metaverse ---
    "MANA-USD", "SAND-USD", "GALA-USD", "AXS-USD", "SLP-USD", "ENJ-USD",
    "IMX-USD", "APE-USD", "CHZ-USD", "ILV-USD",
    # --- Layer 1 & 2 ---
    "ZEC-USD", "DASH-USD", "XTZ-USD", "EOS-USD", "NEO-USD", "IOTA-USD",
    "THETA-USD", "FLOW-USD", "MINA-USD", "CELO-USD", "ONE-USD", "KDA-USD",
    # --- AI & Data ---
    "FET-USD", "AGIX-USD", "OCEAN-USD", "GRT-USD", "RNDR-USD",
    # --- Stablecoins (indicatif) ---
    "USDT-USD", "USDC-USD", "DAI-USD", "BUSD-USD", "TUSD-USD",
]


# ============================================================================
# SECTION 7 — FOREX
# ============================================================================

FOREX_TICKERS = [
    # --- Majeures ---
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X",
    "USDCAD=X", "NZDUSD=X",
    # --- Croisées majeures ---
    "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "CADJPY=X",
    "CHFJPY=X", "EURCHF=X", "GBPCHF=X", "EURAUD=X", "EURCAD=X",
    "EURNZD=X", "GBPAUD=X", "GBPCAD=X", "GBPNZD=X", "AUDNZD=X",
    "AUDCAD=X", "AUDCHF=X", "NZDCAD=X", "NZDCHF=X", "CADCHF=X",
    # --- Émergentes ---
    "USDMXN=X", "USDBRL=X", "USDZAR=X", "USDTRY=X", "USDINR=X",
    "USDCNY=X", "USDKRW=X", "USDSGD=X", "USDHKD=X", "USDPLN=X",
    "USDNOK=X", "USDSEK=X", "USDDKK=X", "USDHUF=X", "USDCZK=X",
    # --- Africaines ---
    "USDNGN=X", "USDXOF=X", "USDKES=X", "USDGHS=X", "USDMAD=X",
    "USDTND=X", "USDEGP=X",
]


# ============================================================================
# SECTION 8 — COMMODITÉS
# ============================================================================

COMMODITY_TICKERS = [
    # --- Métaux précieux ---
    "GC=F",  # Or
    "SI=F",  # Argent
    "PL=F",  # Platine
    "PA=F",  # Palladium
    # --- Métaux industriels ---
    "HG=F",  # Cuivre
    "ALI=F", # Aluminium
    # --- Énergie ---
    "CL=F",  # Pétrole WTI
    "BZ=F",  # Pétrole Brent
    "NG=F",  # Gaz naturel
    "HO=F",  # Fioul de chauffage
    "RB=F",  # Essence RBOB
    # --- Agricoles ---
    "ZW=F",  # Blé
    "ZC=F",  # Maïs
    "ZS=F",  # Soja
    "ZM=F",  # Tourteau de soja
    "ZL=F",  # Huile de soja
    "KC=F",  # Café
    "CT=F",  # Coton
    "SB=F",  # Sucre
    "CC=F",  # Cacao
    "LE=F",  # Bétail
    "HE=F",  # Porc
    "LB=F",  # Bois
    "OJ=F",  # Jus d'orange
]


# ============================================================================
# SECTION 9 — FONCTION D'AGRÉGATION
# ============================================================================

def build_all_tickers(include_dynamic: bool = True) -> list[str]:
    """
    Construit la liste finale de tous les tickers, dédoublonnée et nettoyée.

    Args:
        include_dynamic: si True, récupère S&P 500, Nasdaq 100, Russell 2000 depuis Wikipedia.

    Returns:
        Liste de tickers unique.
    """
    all_tickers = []

    # --- Récupération dynamique US ---
    if include_dynamic:
        all_tickers += fetch_sp500()
        all_tickers += fetch_nasdaq100()
        all_tickers += fetch_russell2000_sample()

    # --- Listes statiques ---
    all_tickers += US_EXTRAS
    all_tickers += EUROPE_TICKERS
    all_tickers += ASIA_TICKERS
    all_tickers += AFRICA_TICKERS
    all_tickers += ETF_TICKERS
    all_tickers += CRYPTO_TICKERS
    all_tickers += FOREX_TICKERS
    all_tickers += COMMODITY_TICKERS

    # --- Nettoyage ---
    all_tickers = [str(t).strip() for t in all_tickers if t and isinstance(t, str)]
    all_tickers = list(set(all_tickers))  # Dédoublonnage
    all_tickers.sort()

    logging.info(f"🎯 Total : {len(all_tickers)} tickers uniques")
    return all_tickers


def count_by_category() -> dict:
    """Retourne le compte de tickers par catégorie (pour audit)."""
    return {
        "US (dynamique + extras)": (
            len(fetch_sp500()) + len(fetch_nasdaq100())
            + len(fetch_russell2000_sample()) + len(US_EXTRAS)
        ),
        "Europe": len(EUROPE_TICKERS),
        "Asie & Océanie": len(ASIA_TICKERS),
        "Afrique": len(AFRICA_TICKERS),
        "ETF": len(ETF_TICKERS),
        "Crypto": len(CRYPTO_TICKERS),
        "Forex": len(FOREX_TICKERS),
        "Commodités": len(COMMODITY_TICKERS),
    }


if __name__ == "__main__":
    counts = count_by_category()
    print("\n📊 Répartition des tickers par catégorie :")
    print("=" * 50)
    total = 0
    for category, count in counts.items():
        print(f"  {category:<30} : {count:>5}")
        total += count
    print("=" * 50)
    print(f"  {'TOTAL':<30} : {total:>5}")