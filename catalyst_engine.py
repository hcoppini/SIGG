#!/usr/bin/env python3
"""
Agentic AI News & Catalyst Intelligence Engine (GPW / SIGG)
Fetches live regulatory & market news, maps headlines to SIGG universe instruments,
classifies sentiment & catalysts, and calculates an AI Catalyst Impact Score.
"""

import os
import re
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from sigg_universe import SIGG_UNIVERSE, get_sigg_symbol, get_sigg_name

NEWS_CACHE_FILE = os.path.join("cache", "news_cache.json")
CACHE_TTL_SECONDS = 1800  # 30 minutes

# Polish financial catalyst keyword lexicons with weightings
CATALYST_PATTERNS = [
    # Earnings & Financial Performance
    {
        "category": "EARNINGS_BEAT",
        "tag": "📈 EARNINGS BEAT",
        "weight": 3.8,
        "keywords": [
            r"wzrost zysku", r"wyższy zysk", r"wyniki powyżej oczekiwań", r"zysk netto wzrósł",
            r"rekordow(e|ych) przychod(y|ów)", r"mocne wyniki", r"poprawa rentowności",
            r"zysk operacyjny w górę", r"ebitda wzrosła", r"zwiększył przychody",
            r"rekordow(e|ych|y) zysk(i|ów)?", r"przebi(ł|ły) konsensus"
        ]
    },
    {
        "category": "EARNINGS_MISS",
        "tag": "📉 EARNINGS MISS",
        "weight": -3.5,
        "keywords": [
            r"spadek zysku", r"strata netto", r"gorsze wyniki", r"rozczarowanie wynikami",
            r"poniżej prognoz", r"zysk stopniał", r"zmniejszył przychody", r"\bodpis(y|ów|u)?\b"
        ]
    },
    # Contracts, Acquisitions & Orders
    {
        "category": "CONTRACT_WIN",
        "tag": "🔥 CONTRACT WIN",
        "weight": 3.2,
        "keywords": [
            r"now(a|ą) umow(a|ę)", r"kontrakt na", r"wygran(y|a) przetarg", r"znacząc(a|ej) umow(y|a)",
            r"zwiększenie zamówień", r"porozumienie z", r"partnerstwo", r"przejęcie", r"akwizycj(a|i)",
            r"nowe zleceni(e|a)", r"list intencyjny"
        ]
    },
    # Analyst Ratings & Target Prices
    {
        "category": "ANALYST_UPGRADE",
        "tag": "🎯 ANALYST BUY",
        "weight": 2.8,
        "keywords": [
            r"rekomendacja kupuj", r"podnosi cenę docelową", r"faworyt analityków",
            r"wyższa wycena", r"podwyższa rekomendację", r"potencjał wzrostu"
        ]
    },
    {
        "category": "ANALYST_DOWNGRADE",
        "tag": "⚠️ DOWNGRADE",
        "weight": -2.8,
        "keywords": [
            r"obniża cenę docelową", r"rekomendacja sprzedaj", r"redukuj",
            r"obniża rekomendację", r"zaleca ostrożność"
        ]
    },
    # Dividends & Buybacks
    {
        "category": "DIVIDEND_BUYBACK",
        "tag": "💰 BUYBACK / DIVIDEND",
        "weight": 2.5,
        "keywords": [
            r"dywidend(a|y|ę)", r"skup akcji własnych", r"buyback", r"wypłata zaliczki na poczet",
            r"rekordowa dywidenda"
        ]
    },
    # Capital Dilution & Insolvency
    {
        "category": "DILUTION_RISK",
        "tag": "🚨 DILUTION RISK",
        "weight": -4.0,
        "keywords": [
            r"emisja akcji", r"rozwodnienie", r"upadłość", r"niewypłacalność",
            r"postępowanie restrukturyzacyjne", r"rezygnacja prezesa", r"afera", r"kara knf"
        ]
    },
    # Biotech / Medtech Clinical Success
    {
        "category": "BIOTECH_BREAKTHROUGH",
        "tag": "🧬 CLINICAL SUCCESS",
        "weight": 4.0,
        "keywords": [
            r"badania kliniczne", r"fda", r"patent", r"sukces badań", r"zgoda na rozpoczęcie badań",
            r"faza 1", r"faza 2", r"faza 3", r"europejska agencja leków"
        ]
    },
    # Gaming / Digital Releases
    {
        "category": "GAMING_HIT",
        "tag": "🎮 GAMING CATALYST",
        "weight": 3.5,
        "keywords": [
            r"premiera gry", r"wishlist(a|y)", r"bestseller", r"sukces gry",
            r"sprzedaż gry", r"debiut na steam", r"bardzo pozytywne recenzje"
        ]
    },
    # Broad Momentum & Market Attention
    {
        "category": "MOMENTUM_BUZZ",
        "tag": "⚡ MARKET BUZZ",
        "weight": 2.0,
        "keywords": [
            r"w centrum uwagi", r"liderem wzrostów", r"rekord notowań", r"nowe szczyty",
            r"drożeje o", r"rajd na akcjach", r"silny popyt"
        ]
    },
    {
        "category": "SELLOFF_PRESSURE",
        "tag": "⚠️ SELLOFF PRESSURE",
        "weight": -2.2,
        "keywords": [
            r"pod presją", r"wyprzedaż", r"spada o", r"traci na giełdzie",
            r"nowe minima", r"krwawy piątek", r"załamanie notowań"
        ]
    }
]

def load_news_cache() -> Dict:
    if os.path.exists(NEWS_CACHE_FILE):
        try:
            with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"timestamp": 0, "articles": [], "ticker_analysis": {}}

def save_news_cache(cache_data: Dict):
    os.makedirs(os.path.dirname(NEWS_CACHE_FILE), exist_ok=True)
    try:
        with open(NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: could not save news cache: {e}")

def fetch_rss_feed(url: str, timeout: int = 6) -> List[Dict[str, str]]:
    articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            root = ET.fromstring(content)
            for item in root.findall(".//item"):
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                desc = item.find("description").text if item.find("description") is not None else ""
                
                # Clean html tags from description
                desc_clean = re.sub(r"<[^>]+>", "", desc or "")
                
                if title:
                    articles.append({
                        "title": title.strip(),
                        "link": link.strip(),
                        "pub_date": pub_date.strip(),
                        "description": desc_clean.strip(),
                        "source_url": url
                    })
    except Exception as e:
        # Graceful fallback on network timeout
        pass
    return articles

def fetch_all_gpw_market_news() -> List[Dict[str, str]]:
    """Fetches combined market news from top financial RSS feeds."""
    feed_urls = [
        "https://www.bankier.pl/rss/wiadomosci.xml",
        "https://www.bankier.pl/rss/gielda.xml",
        "https://news.google.com/rss/search?q=GPW+gielda+akcje&hl=pl&gl=PL&ceid=PL:pl"
    ]
    all_articles = []
    seen_titles = set()
    for u in feed_urls:
        items = fetch_rss_feed(u)
        for item in items:
            t = item["title"].lower()
            if t not in seen_titles:
                seen_titles.add(t)
                all_articles.append(item)
    return all_articles

def build_ticker_search_patterns() -> Dict[str, Dict]:
    """Builds regex patterns for all 172 SIGG universe symbols to detect mentions in headlines."""
    patterns = {}
    for entry in SIGG_UNIVERSE:
        sym = entry["symbol"]
        ticker = entry["ticker"]
        name = entry["name"]
        
        # Build search keywords
        clean_name = re.sub(r"\b(s\.a\.|sa|spółka|holding|inc\.|group|polska|poland)\b", "", name, flags=re.IGNORECASE).strip()
        kw_list = [re.escape(sym)]
        if clean_name and len(clean_name) >= 3:
            kw_list.append(re.escape(clean_name))
        
        # Special ticker custom nicknames
        if "DINOPL" in sym: kw_list.extend(["dino", "dino polska"])
        elif "ALLEGRO" in sym: kw_list.extend(["allegro", "allegro.eu"])
        elif "CDPROJEKT" in sym: kw_list.extend(["cd projekt", "cdprojekt", "cyberpunk", "wiedźmin"])
        elif "11BIT" in sym: kw_list.extend(["11 bit", "frostpunk"])
        elif "KGHM" in sym: kw_list.extend(["kghm", "kghm polska miedź"])
        elif "ORLEN" in sym: kw_list.extend(["orlen", "pkn orlen"])
        elif "LPP" in sym: kw_list.extend(["lpp", "reserved", "sinsay"])
        elif "XTB" in sym: kw_list.extend(["xtb"])
        elif "DEVELIA" in sym: kw_list.extend(["develia"])
        elif "SELENAFM" in sym: kw_list.extend(["selena", "selena fm"])
        elif "ETFBNQ2ST" in sym: kw_list.extend(["nasdaq short", "nasdaq 2x short", "etfbnq2st"])
        elif "ETFBNQ3LV" in sym: kw_list.extend(["nasdaq 3x", "etfbnq3lv", "nasdaq lev"])
        elif "ETFBW20ST" in sym: kw_list.extend(["wig20 short", "etfbw20st"])
        elif "ETFBW20LV" in sym: kw_list.extend(["wig20 lev", "etfbw20lv"])
        elif "ETFBTCPL" in sym: kw_list.extend(["bitcoin", "btc", "etfbtcpl"])
        
        regex = re.compile(r"\b(" + "|".join(kw_list) + r")\b", re.IGNORECASE)
        patterns[sym] = {
            "symbol": sym,
            "ticker": ticker,
            "name": name,
            "regex": regex
        }
    return patterns

_TICKER_PATTERNS = None

def get_ticker_patterns() -> Dict[str, Dict]:
    global _TICKER_PATTERNS
    if _TICKER_PATTERNS is None:
        _TICKER_PATTERNS = build_ticker_search_patterns()
    return _TICKER_PATTERNS

def analyze_headline_catalyst(text: str) -> Tuple[float, Optional[str], Optional[str]]:
    """Evaluates text against financial catalyst dictionaries returning (score, category, tag)."""
    text_lower = text.lower()
    total_score = 0.0
    detected_tag = None
    detected_cat = None
    
    for pat in CATALYST_PATTERNS:
        for kw in pat["keywords"]:
            if re.search(kw, text_lower):
                total_score += pat["weight"]
                if detected_tag is None:
                    detected_tag = pat["tag"]
                    detected_cat = pat["category"]
                break
                
    # Normalize score between -5.0 and +5.0
    final_score = max(-5.0, min(5.0, round(total_score, 1)))
    return final_score, detected_cat, detected_tag

def fetch_ticker_specific_news(company_name: str, symbol: str) -> List[Dict]:
    """Fetches high-signal Google News RSS specifically for a target company."""
    clean_query = re.sub(r"\b(s\.a\.|sa|spółka|holding|inc\.|group)\b", "", company_name, flags=re.IGNORECASE).strip()
    query = f"{clean_query} GPW akcje"
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=pl&gl=PL&ceid=PL:pl"
    items = fetch_rss_feed(url, timeout=5)
    return items[:5]

def get_ai_catalyst_intelligence(target_symbols: Optional[List[str]] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Main entrypoint: analyzes recent news for universe or target symbols.
    Returns per-ticker sentiment score, catalyst tag, and top headlines.
    """
    cache = load_news_cache()
    now_ts = time.time()
    
    ticker_patterns = get_ticker_patterns()
    
    # 1. Check if cache is still fresh
    if not force_refresh and (now_ts - cache.get("timestamp", 0) < CACHE_TTL_SECONDS) and cache.get("ticker_analysis"):
        analysis = cache["ticker_analysis"]
        if target_symbols:
            return {s: analysis.get(s, default_neutral_catalyst(s)) for s in target_symbols}
        return analysis

    # 2. Ingest broad GPW market news
    articles = fetch_all_gpw_market_news()
    
    # Map articles to symbols
    symbol_mentions = {s: [] for s in ticker_patterns}
    
    for art in articles:
        combined_text = f"{art['title']} {art.get('description', '')}"
        for sym, pat_info in ticker_patterns.items():
            if pat_info["regex"].search(combined_text):
                symbol_mentions[sym].append(art)
                
    # If specific target symbols requested, fetch targeted news for candidates with 0 broad mentions
    if target_symbols:
        for sym in target_symbols:
            if not symbol_mentions.get(sym):
                pat = ticker_patterns.get(sym)
                if pat:
                    specific_articles = fetch_ticker_specific_news(pat["name"], sym)
                    symbol_mentions[sym] = specific_articles
                    articles.extend(specific_articles)

    ticker_analysis = {}
    
    for sym, art_list in symbol_mentions.items():
        if not art_list:
            ticker_analysis[sym] = default_neutral_catalyst(sym)
            continue
            
        scores = []
        best_tag = None
        headline_summaries = []
        
        for art in art_list[:4]:
            t = art["title"]
            sc, cat, tag = analyze_headline_catalyst(t)
            scores.append(sc)
            if tag and best_tag is None:
                best_tag = tag
            headline_summaries.append({
                "title": t,
                "link": art.get("link", ""),
                "pub_date": art.get("pub_date", ""),
                "headline_score": sc
            })
            
        avg_score = round(float(sum(scores) / len(scores)), 2) if scores else 0.0
        
        # Determine aggregate classification
        if best_tag is None:
            if avg_score > 1.0:
                best_tag = "📈 POSITIVE SENTIMENT"
            elif avg_score < -1.0:
                best_tag = "📉 NEGATIVE SENTIMENT"
            else:
                best_tag = "⚡ TECHNICAL MOMENTUM"
                
        ticker_analysis[sym] = {
            "symbol": sym,
            "ai_score": avg_score,
            "catalyst_tag": best_tag,
            "mention_count": len(art_list),
            "top_headline": headline_summaries[0]["title"] if headline_summaries else "No recent articles",
            "top_link": headline_summaries[0]["link"] if headline_summaries else "",
            "headlines": headline_summaries,
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
    cache["timestamp"] = now_ts
    cache["articles"] = articles[:60]
    cache["ticker_analysis"] = ticker_analysis
    save_news_cache(cache)
    
    if target_symbols:
        return {s: ticker_analysis.get(s, default_neutral_catalyst(s)) for s in target_symbols}
    return ticker_analysis

def default_neutral_catalyst(symbol: str) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "ai_score": 0.0,
        "catalyst_tag": "⚡ TECHNICAL MOMENTUM",
        "mention_count": 0,
        "top_headline": "Pure price/volume momentum setup",
        "top_link": "",
        "headlines": [],
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Agentic AI News & Catalyst Engine...")
    print("=" * 60)
    res = get_ai_catalyst_intelligence(["DEVELIA", "ETFBNQ2ST", "KGHM", "ALLEGRO", "DINOPL"])
    for sym, data in res.items():
        print(f"\n[{sym}] Score: {data['ai_score']:+.2f} | Tag: {data['catalyst_tag']}")
        print(f"Top Headline: {data['top_headline']}")
