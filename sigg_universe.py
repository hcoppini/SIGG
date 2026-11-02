"""
Official SIGG 24 (Szkolna Internetowa Gra Giełdowa) Universe Definition
Verified directly against sigg.gpw.pl platform instruments (Equities & ETFs).

Maps:
- GPWTr@der Symbol (e.g. DINOPL, BOGDANKA, KOGENERA, CDPROJEKT, BENEFIT, ETFBNQ3LV)
- Yahoo Finance Ticker (.WA)
- Full Polish / Company Name
"""

SIGG_UNIVERSE = [
    # --- AKCJE / EQUITIES (140 SPÓŁEK) ---
    {"symbol": "11BIT", "ticker": "11B.WA", "name": "11 bit studios"},
    {"symbol": "ABPL", "ticker": "ABE.WA", "name": "AB S.A."},
    {"symbol": "AGORA", "ticker": "AGO.WA", "name": "Agora"},
    {"symbol": "ALIOR", "ticker": "ALR.WA", "name": "Alior Bank"},
    {"symbol": "ALLEGRO", "ticker": "ALE.WA", "name": "Allegro.eu"},
    {"symbol": "AMBRA", "ticker": "AMB.WA", "name": "Ambra"},
    {"symbol": "AMICA", "ticker": "AMC.WA", "name": "Amica"},
    {"symbol": "AMREST", "ticker": "EAT.WA", "name": "AmRest Holdings"},
    {"symbol": "ANSWEAR", "ticker": "ANR.WA", "name": "Answear.com"},
    {"symbol": "APATOR", "ticker": "APT.WA", "name": "Apator"},
    {"symbol": "ARCHICOM", "ticker": "ARH.WA", "name": "Archicom"},
    {"symbol": "ARCTIC", "ticker": "ATC.WA", "name": "Arctic Paper"},
    {"symbol": "ARLEN", "ticker": "ARL.WA", "name": "Arlen Textile Group"},
    {"symbol": "ASBIS", "ticker": "ASB.WA", "name": "ASBISc Enterprises"},
    {"symbol": "ASSECOBS", "ticker": "ABS.WA", "name": "Asseco Business Solutions"},
    {"symbol": "ASSECOPOL", "ticker": "ACP.WA", "name": "Asseco Poland"},
    {"symbol": "ASSECOSEE", "ticker": "ASE.WA", "name": "Asseco South Eastern Europe"},
    {"symbol": "ASTARTA", "ticker": "AST.WA", "name": "Astarta Holding"},
    {"symbol": "ATAL", "ticker": "1AT.WA", "name": "Atal"},
    {"symbol": "ATREM", "ticker": "ATR.WA", "name": "Atrem"},
    {"symbol": "AUTOPARTN", "ticker": "APR.WA", "name": "Auto Partner"},
    {"symbol": "BENEFIT", "ticker": "BFT.WA", "name": "Benefit Systems"},
    {"symbol": "BIOCELTIX", "ticker": "BCX.WA", "name": "Bioceltix"},
    {"symbol": "BIOTON", "ticker": "BIO.WA", "name": "Bioton"},
    {"symbol": "BLOOBER", "ticker": "BLO.WA", "name": "Bloober Team"},
    {"symbol": "BNPPPL", "ticker": "BNP.WA", "name": "BNP Paribas Bank Polska"},
    {"symbol": "BOGDANKA", "ticker": "LWB.WA", "name": "LW Bogdanka"},
    {"symbol": "BORYSZEW", "ticker": "BRS.WA", "name": "Boryszew"},
    {"symbol": "BOS", "ticker": "BOS.WA", "name": "Bank Ochrony Środowiska"},
    {"symbol": "BUDIMEX", "ticker": "BDX.WA", "name": "Budimex"},
    {"symbol": "BUMECH", "ticker": "BMC.WA", "name": "Bumech"},
    {"symbol": "CAPTORTX", "ticker": "CTX.WA", "name": "Captor Therapeutics"},
    {"symbol": "CDPROJEKT", "ticker": "CDR.WA", "name": "CD Projekt"},
    {"symbol": "CIGAMES", "ticker": "CIG.WA", "name": "CI Games"},
    {"symbol": "CLNPHARMA", "ticker": "CLN.WA", "name": "Celon Pharma"},
    {"symbol": "COGNOR", "ticker": "COG.WA", "name": "Cognor Holding"},
    {"symbol": "COMP", "ticker": "CMP.WA", "name": "Comp"},
    {"symbol": "CREEPYJAR", "ticker": "CRJ.WA", "name": "Creepy Jar"},
    {"symbol": "CREOTECH", "ticker": "CRI.WA", "name": "Creotech Instruments"},
    {"symbol": "CRQUANTUM", "ticker": "CRQ.WA", "name": "Creotech Quantum"},
    {"symbol": "CYBERFLKS", "ticker": "CBF.WA", "name": "Cyberfolks"},
    {"symbol": "CYFRPLSAT", "ticker": "CPS.WA", "name": "Cyfrowy Polsat"},
    {"symbol": "DADELO", "ticker": "DAD.WA", "name": "Dadelo"},
    {"symbol": "DATAWALK", "ticker": "DAT.WA", "name": "DataWalk"},
    {"symbol": "DECORA", "ticker": "DCR.WA", "name": "Decora"},
    {"symbol": "DEVELIA", "ticker": "DVL.WA", "name": "Develia"},
    {"symbol": "DIAG", "ticker": "DIA.WA", "name": "Diagnostyka"},
    {"symbol": "DIGITANET", "ticker": "DIG.WA", "name": "Digital Network"},
    {"symbol": "DINOPL", "ticker": "DNP.WA", "name": "Dino Polska"},
    {"symbol": "DOMDEV", "ticker": "DOM.WA", "name": "Dom Development"},
    {"symbol": "ECHO", "ticker": "ECH.WA", "name": "Echo Investment"},
    {"symbol": "ELEKTROTI", "ticker": "ELT.WA", "name": "Elektrotim"},
    {"symbol": "ENEA", "ticker": "ENA.WA", "name": "Enea"},
    {"symbol": "ENTER", "ticker": "ENT.WA", "name": "Enter Air"},
    {"symbol": "ERSTEPL", "ticker": "EBP.WA", "name": "Erste Group Bank"},
    {"symbol": "EUROCASH", "ticker": "EUR.WA", "name": "Eurocash"},
    {"symbol": "FERRO", "ticker": "FRO.WA", "name": "Ferro"},
    {"symbol": "FORTE", "ticker": "FTE.WA", "name": "Fabryki Mebli Forte"},
    {"symbol": "GPW", "ticker": "GPW.WA", "name": "Giełda Papierów Wartościowych"},
    {"symbol": "GREENX", "ticker": "GRX.WA", "name": "GreenX Metals"},
    {"symbol": "GRUPAAZOTY", "ticker": "ATT.WA", "name": "Grupa Azoty"},
    {"symbol": "GRUPRACUJ", "ticker": "GPP.WA", "name": "Grupa Pracuj"},
    {"symbol": "HANDLOWY", "ticker": "BHW.WA", "name": "Bank Handlowy"},
    {"symbol": "HUUUGE", "ticker": "HUG.WA", "name": "Huuuge Inc."},
    {"symbol": "IMCOMPANY", "ticker": "IMC.WA", "name": "IMC S.A."},
    {"symbol": "INGBSK", "ticker": "ING.WA", "name": "ING Bank Śląski"},
    {"symbol": "INTERCARS", "ticker": "CAR.WA", "name": "Inter Cars"},
    {"symbol": "JSW", "ticker": "JSW.WA", "name": "Jastrzębska Spółka Węglowa"},
    {"symbol": "KETY", "ticker": "KTY.WA", "name": "Grupa Kęty"},
    {"symbol": "KGHM", "ticker": "KGH.WA", "name": "KGHM Polska Miedź"},
    {"symbol": "KOGENERA", "ticker": "KGN.WA", "name": "ZEW Kogeneracja"},
    {"symbol": "KRUK", "ticker": "KRU.WA", "name": "Kruk S.A."},
    {"symbol": "LPP", "ticker": "LPP.WA", "name": "LPP"},
    {"symbol": "LUBAWA", "ticker": "LBW.WA", "name": "Lubawa"},
    {"symbol": "MBANK", "ticker": "MBK.WA", "name": "mBank"},
    {"symbol": "MCI", "ticker": "MCI.WA", "name": "MCI Capital"},
    {"symbol": "MEDICALG", "ticker": "MDG.WA", "name": "Medicalgorithmics"},
    {"symbol": "MEDINICE", "ticker": "ICE.WA", "name": "Medinice"},
    {"symbol": "MENNICA", "ticker": "MNC.WA", "name": "Mennica Polska"},
    {"symbol": "MERCATOR", "ticker": "MRC.WA", "name": "Mercator Medical"},
    {"symbol": "MILLENNIUM", "ticker": "MIL.WA", "name": "Bank Millennium"},
    {"symbol": "MIRBUD", "ticker": "MRB.WA", "name": "Mirbud"},
    {"symbol": "MLPGROUP", "ticker": "MLG.WA", "name": "MLP Group"},
    {"symbol": "MOBRUK", "ticker": "MBR.WA", "name": "Mo-BRUK"},
    {"symbol": "MODIVO", "ticker": "MDV.WA", "name": "Modivo"},
    {"symbol": "MOSTALZAB", "ticker": "MSZ.WA", "name": "Mostostal Zabrze"},
    {"symbol": "MURAPOL", "ticker": "MUR.WA", "name": "Murapol"},
    {"symbol": "NEUCA", "ticker": "NEU.WA", "name": "Neuca"},
    {"symbol": "NEWAG", "ticker": "NWG.WA", "name": "Newag"},
    {"symbol": "NIEWIADOW", "ticker": "GNS.WA", "name": "Niewiadów"},
    {"symbol": "ONDE", "ticker": "OND.WA", "name": "Onde"},
    {"symbol": "OPONEO.PL", "ticker": "OPN.WA", "name": "Oponeo.pl"},
    {"symbol": "ORANGEPL", "ticker": "OPL.WA", "name": "Orange Polska"},
    {"symbol": "PCCROKITA", "ticker": "PCR.WA", "name": "PCC Rokita"},
    {"symbol": "PEKAO", "ticker": "PEO.WA", "name": "Bank Pekao"},
    {"symbol": "PEP", "ticker": "PEP.WA", "name": "Polenergia"},
    {"symbol": "PEPCO", "ticker": "PCO.WA", "name": "Pepco Group"},
    {"symbol": "PGE", "ticker": "PGE.WA", "name": "PGE Polska Grupa Energetyczna"},
    {"symbol": "PKNORLEN", "ticker": "PKN.WA", "name": "Orlen"},
    {"symbol": "PKOBP", "ticker": "PKO.WA", "name": "PKO Bank Polski"},
    {"symbol": "PLAYWAY", "ticker": "PLW.WA", "name": "PlayWay"},
    {"symbol": "POLIMEXMS", "ticker": "PXM.WA", "name": "Polimex-Mostostal"},
    {"symbol": "PZU", "ticker": "PZU.WA", "name": "PZU"},
    {"symbol": "QUERCUS", "ticker": "QRS.WA", "name": "Quercus TFI"},
    {"symbol": "RAINBOW", "ticker": "RBW.WA", "name": "Rainbow Tours"},
    {"symbol": "REX", "ticker": "REX.WA", "name": "Rex Concepts"},
    {"symbol": "ROBYG", "ticker": "ROB.WA", "name": "Robyg"},
    {"symbol": "RYVU", "ticker": "RVU.WA", "name": "Ryvu Therapeutics"},
    {"symbol": "SANOK", "ticker": "SNK.WA", "name": "Sanok Rubber Company"},
    {"symbol": "SCANWAY", "ticker": "SCW.WA", "name": "Scanway"},
    {"symbol": "SCPFL", "ticker": "SCP.WA", "name": "Scope Fluidics"},
    {"symbol": "SELENAFM", "ticker": "SEL.WA", "name": "Selena FM"},
    {"symbol": "SELVITA", "ticker": "SLV.WA", "name": "Selvita"},
    {"symbol": "SNIEZKA", "ticker": "SKA.WA", "name": "FFiL Śnieżka"},
    {"symbol": "SNTVERSE", "ticker": "SVE.WA", "name": "Synthaverse"},
    {"symbol": "STALEXP", "ticker": "STX.WA", "name": "Stalexport Autostrady"},
    {"symbol": "STALPROD", "ticker": "STP.WA", "name": "Stalprodukt"},
    {"symbol": "SYGNITY", "ticker": "SGN.WA", "name": "Sygnity"},
    {"symbol": "SYN2BIO", "ticker": "S2B.WA", "name": "SYN2BIO"},
    {"symbol": "SYNEKTIK", "ticker": "SNT.WA", "name": "Synektik"},
    {"symbol": "TARCZYNSKI", "ticker": "TAR.WA", "name": "Tarczyński"},
    {"symbol": "TAURONPE", "ticker": "TPE.WA", "name": "Tauron Polska Energia"},
    {"symbol": "TEXT", "ticker": "TXT.WA", "name": "Text (LiveChat)"},
    {"symbol": "TORPOL", "ticker": "TOR.WA", "name": "Torpol"},
    {"symbol": "TOYA", "ticker": "TOA.WA", "name": "Toya"},
    {"symbol": "TSGAMES", "ticker": "TEN.WA", "name": "Ten Square Games"},
    {"symbol": "UNIBEP", "ticker": "UNI.WA", "name": "Unibep"},
    {"symbol": "UNIMOT", "ticker": "UNT.WA", "name": "Unimot"},
    {"symbol": "VERCOM", "ticker": "VRC.WA", "name": "Vercom"},
    {"symbol": "VIGOPHOTN", "ticker": "VGO.WA", "name": "VIGO Photonics"},
    {"symbol": "VOTUM", "ticker": "VOT.WA", "name": "Votum"},
    {"symbol": "VOXEL", "ticker": "VOX.WA", "name": "Voxel"},
    {"symbol": "VRG", "ticker": "VRG.WA", "name": "VRG"},
    {"symbol": "WAWEL", "ticker": "WWL.WA", "name": "Wawel"},
    {"symbol": "WIELTON", "ticker": "WLT.WA", "name": "Wielton"},
    {"symbol": "WIRTUALNA", "ticker": "WPL.WA", "name": "Wirtualna Polska"},
    {"symbol": "XTB", "ticker": "XTB.WA", "name": "XTB"},
    {"symbol": "ZABKA", "ticker": "ZAB.WA", "name": "Żabka Group"},
    {"symbol": "ZEPAK", "ticker": "ZEP.WA", "name": "ZE PAK"},
    {"symbol": "ZREMB", "ticker": "ZRE.WA", "name": "Zremb-Chojnice"},

    # --- GPW ETFS (32 FUNDUSZE: BETA ETF, HANETF, INPZU) ---
    {"symbol": "ETFBW20TR", "ticker": "ETFBW20TR.WA", "name": "Beta ETF WIG20 TR"},
    {"symbol": "ETFBW20ST", "ticker": "ETFBW20ST.WA", "name": "Beta ETF WIG20 Short"},
    {"symbol": "ETFBW20LV", "ticker": "ETFBW20LV.WA", "name": "Beta ETF WIG20 Lev"},
    {"symbol": "ETFBM40TR", "ticker": "ETFBM40TR.WA", "name": "Beta ETF mWIG40 TR"},
    {"symbol": "ETFBM40ST", "ticker": "ETFBM40ST.WA", "name": "Beta ETF mWIG40 Short"},
    {"symbol": "ETFBM40LV", "ticker": "ETFBM40LV.WA", "name": "Beta ETF mWIG40 Lev"},
    {"symbol": "ETFBS80TR", "ticker": "ETFBS80TR.WA", "name": "Beta ETF sWIG80 TR"},
    {"symbol": "ETFBCASH", "ticker": "ETFBCASH.WA", "name": "Beta ETF Obligacji 6M"},
    {"symbol": "ETFBDIVPL", "ticker": "ETFBDIVPL.WA", "name": "Beta ETF Dywidenda Plus"},
    {"symbol": "ETFBNDXPL", "ticker": "ETFBNDXPL.WA", "name": "Beta ETF Nasdaq-100 PLN"},
    {"symbol": "ETFBNQ2ST", "ticker": "ETFBNQ2ST.WA", "name": "Beta ETF Nasdaq-100 2x Short"},
    {"symbol": "ETFBNQ3LV", "ticker": "ETFBNQ3LV.WA", "name": "Beta ETF Nasdaq-100 3x Lev"},
    {"symbol": "ETFBSPXPL", "ticker": "ETFBSPXPL.WA", "name": "Beta ETF S&P 500 PLN"},
    {"symbol": "ETFBTBSP", "ticker": "ETFBTBSP.WA", "name": "Beta ETF TBSP"},
    {"symbol": "ETFBTCPL", "ticker": "ETFBTCPL.WA", "name": "Beta ETF Bitcoin"},
    {"symbol": "ETFDAX", "ticker": "ETFDAX.WA", "name": "Beta ETF DAX"},
    {"symbol": "ETFHANARMY", "ticker": "ETFHANARMY.WA", "name": "HAN Future of European Defence"},
    {"symbol": "ETFHANCPPR", "ticker": "ETFHANCPPR.WA", "name": "HAN Copper Miners"},
    {"symbol": "ETFHANDRON", "ticker": "ETFHANDRON.WA", "name": "HAN Defiance Drone"},
    {"symbol": "ETFHANESGO", "ticker": "ETFHANESGO.WA", "name": "HAN Gold Miners Screened"},
    {"symbol": "ETFHANGR8", "ticker": "ETFHANGR8.WA", "name": "HAN Making Europe Great Again"},
    {"symbol": "ETFHANMMLP", "ticker": "ETFHANMMLP.WA", "name": "HAN Alerian Midstream Energy"},
    {"symbol": "ETFHANUKRN", "ticker": "ETFHANUKRN.WA", "name": "HAN Ukraine Reconstruction"},
    {"symbol": "ETFHANURNM", "ticker": "ETFHANURNM.WA", "name": "HAN Uranium Miners"},
    {"symbol": "ETFHANYMAG", "ticker": "ETFHANYMAG.WA", "name": "HAN YieldMax Big Tech Option"},
    {"symbol": "ETFNATO", "ticker": "ETFNATO.WA", "name": "HAN Future of Defence"},
    {"symbol": "ETFPZUCASH", "ticker": "ETFPZUCASH.WA", "name": "inPZU Obligacji Rynku Pieniężnego"},
    {"symbol": "ETFPZUGOLD", "ticker": "ETFPZUGOLD.WA", "name": "inPZU Gold"},
    {"symbol": "ETFPZULONGDUR", "ticker": "ETFPZULONGDUR.WA", "name": "inPZU Obligacji Długoterminowych"},
    {"symbol": "ETFPZUW20M40", "ticker": "ETFPZUW20M40.WA", "name": "inPZU WIG20 & mWIG40"},
    {"symbol": "ETFPZUWORLD", "ticker": "ETFPZUWORLD.WA", "name": "inPZU Akcji Globalnych"},
    {"symbol": "ETFSP500", "ticker": "ETFSP500.WA", "name": "inPZU S&P 500"},
]

# Quick lookup indexes
TICKER_TO_SIGG = {item["ticker"]: item["symbol"] for item in SIGG_UNIVERSE}
SIGG_TO_TICKER = {item["symbol"]: item["ticker"] for item in SIGG_UNIVERSE}
TICKER_TO_NAME = {item["ticker"]: item["name"] for item in SIGG_UNIVERSE}
SIGG_TO_NAME = {item["symbol"]: item["name"] for item in SIGG_UNIVERSE}

def get_tv_symbol(ticker_or_symbol: str) -> str:
    cleaned = ticker_or_symbol.upper().strip()
    if cleaned in SIGG_TO_TICKER:
        return SIGG_TO_TICKER[cleaned].replace('.WA', '')
    if cleaned in TICKER_TO_SIGG:
        return cleaned.replace('.WA', '')
    return cleaned.replace('.WA', '')

def get_tradingview_link(ticker_or_symbol: str) -> str:
    tv_sym = get_tv_symbol(ticker_or_symbol)
    return f"https://pl.tradingview.com/symbols/GPW-{tv_sym}/"

def get_sigg_symbol(ticker_or_symbol: str) -> str:
    cleaned = ticker_or_symbol.upper().strip()
    if cleaned in TICKER_TO_SIGG:
        return TICKER_TO_SIGG[cleaned]
    # Check if ends with .WA
    if not cleaned.endswith('.WA') and f"{cleaned}.WA" in TICKER_TO_SIGG:
        return TICKER_TO_SIGG[f"{cleaned}.WA"]
    return cleaned.replace('.WA', '')

def get_sigg_name(ticker_or_symbol: str) -> str:
    cleaned = ticker_or_symbol.upper().strip()
    if cleaned in TICKER_TO_NAME:
        return TICKER_TO_NAME[cleaned]
    if cleaned in SIGG_TO_NAME:
        return SIGG_TO_NAME[cleaned]
    sigg_sym = get_sigg_symbol(cleaned)
    return SIGG_TO_NAME.get(sigg_sym, cleaned)

def get_contest_tickers() -> list:
    return [item["ticker"] for item in SIGG_UNIVERSE]
