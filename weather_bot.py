import requests
import math
import time
import os
import json
from datetime import datetime
import pytz

# הגדרות מיתוג וצבעים (Idol Studios Style)
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"

def get_market_data_scraping():
    """סורק את הנתונים ישירות מה-Internal API של האתר (בדומה ל-Scraping)"""
    # כתובת ה-API הפנימית שפולימרקט משתמשת בה כדי להציג את האירוע הספציפי
    # אנחנו מחפשים אירועים תחת הסלאג של טמפרטורה בלונדון
    url = "https://gamma-api.polymarket.com/events?slug=highest-temperature-in-london-on-april-17"
    
    # ניסיון דינמי: אם התאריך משתנה, הבוט ינסה למצוא את האירוע לפי מילת מפתח
    search_url = "https://gamma-api.polymarket.com/events?limit=10&query=highest%20temperature%20london&active=true"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    results = []
    try:
        # 1. חיפוש האירוע הפעיל
        resp = requests.get(search_url, headers=headers, timeout=20)
        if resp.status_code != 200: return []
        
        events = resp.json()
        if not events: return []
        
        # לוקחים את האירוע הראשון שמתאים (הכי רלוונטי)
        target_event = events[0]
        markets = target_event.get('markets', [])
        
        print(f"DEBUG: Found Event: {target_event.get('title')}")
        
        for m in markets:
            # כאן אנחנו לוקחים את הנתונים בדיוק כפי שהם מוצגים בטבלה באתר
            title = m.get('groupItemTitle', '')
            if not title: continue
            
            # שליפת מחיר ה-YES (outcomePrices בדרך כלל מכיל [YES, NO])
            try:
                prices = json.loads(m.get('outcomePrices', '["0", "0"]'))
                yes_price = round(float(prices[0]) * 100, 1)
            except:
                yes_price = 0.0
                
            if yes_price > 0:
                results.append({
                    "title": title,
                    "poly_price": yes_price
                })

        # מיון לפי מעלות
        def extract_num(t):
            nums = ''.join(filter(str.isdigit, t.split('°')[0]))
            return int(nums) if nums else 0
            
        results.sort(key=lambda x: extract_num(x['title']))
        return results
        
    except Exception as e:
        print(f"DEBUG: Scraping Error: {e}")
    return []

def calculate_ai_prob(avg, target_str):
    """חישוב הסתברות (CDF)"""
    std = 0.7
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    
    try:
        val = int(''.join(filter(str.isdigit, target_str.split('°')[0])))
    except: return 0.0
        
    t_lower = target_str.lower()
    if "higher" in t_lower or "above" in t_lower or "more" in t_lower:
        prob = 1.0 - cdf(val - 0.5)
    elif "below" in t_lower or "under" in t_lower or "less" in t_lower:
        prob = cdf(val + 0.5)
    else:
        prob = cdf(val + 0.5) - cdf(val - 0.5)
        
    return round(prob * 100, 1)

def run_bot():
    tz_il, tz_uk = pytz.timezone('Asia/Jerusalem'), pytz.timezone('Europe/London')
    now_il, now_uk = datetime.now(tz_il).strftime('%H:%M'), datetime.now(tz_uk).strftime('%H:%M')

    # 1. ORACLE DATA
    models = {"MeteoFrance": 18.4, "ICON": 18.1, "GFS": 18.9, "UKMO": 18.2, "ECMWF": 18.6}
    avg_oracle = round(sum(models.values()) / len(models), 2)
    lhr_live = 18.2

    # 2. GET DATA (Using Scraping Logic)
    processed = []
    poly_data = get_market_data_scraping()
    
    for opt in poly_data:
        our_prob = calculate_ai_prob(avg_oracle, opt['title'])
        edge = round(our_prob - opt['poly_price'], 1)
        processed.append({
            "label": opt['title'],
            "poly": opt['poly_price'],
            "ours": our_prob,
            "edge": edge
        })

    best = max(processed, key=lambda x: x['edge']) if processed else None
    signal = "YES" if best and best['edge'] > 3.0 else "NO"

    # 3. HTML GENERATION
    model_boxes = "".join([f"<div class='model-box'><div class='m-name'>{k}</div><div class='m-val'>{v}°</div></div>" for k,v in models.items()])
    table_rows = "".join([f"<tr><td>{p['label']}</td><td>{p['poly']}¢</td><td>{p['ours']}%</td><td style='color:{GOLD_COLOR if p['edge']>10 else (BRAND_GREEN if p['edge']>0 else ERROR_RED)}; font-weight:bold;'>{p['edge']:+.1f}%</td></tr>" for p in processed])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Oracle Monster v7.0</title>
        <style>
            body {{ background:#000; color:#fff; font-family:system-ui; padding:15px; margin:0; line-height:1.4; }}
            .card {{ background:#0a0a0a; border:1px solid #1a1a1a; border-radius:20px; padding:20px; margin-bottom:15px; }}
            .brand-header {{ text-align:center; color:{BRAND_GREEN}; font-weight:900; letter-spacing:3px; padding:10px; }}
            .model-grid {{ display:grid; grid-template-columns: repeat(5, 1fr); gap:8px; margin-bottom:20px; }}
            .model-box {{ background:#111; padding:10px; border-radius:12px; text-align:center; border:1px solid #1a1a1a; }}
            .m-name {{ font-size:9px; color:#555; text-transform:uppercase; }}
            .m-val {{ font-size:14px; font-weight:bold; }}
            .main-stats {{ display:flex; justify-content:space-around; align-items:center; padding:10px 0; }}
            .stat-item {{ text-align:center; }}
            .stat-val {{ font-size:32px; font-weight:bold; color:{BRAND_GREEN}; }}
            .signal-box {{ text-align:center; padding:30px; border:2px solid {BRAND_GREEN if signal=='YES' else '#222'}; border-radius:20px; margin:15px 0; }}
            .signal-text {{ font-size:60px; font-weight:900; margin:0; }}
            table {{ width:100%; border-collapse:collapse; text-align:center; }}
            th {{ font-size:11px; color:#444; padding-bottom:10px; border-bottom:1px solid #1a1a1a; }}
            td {{ padding:15px 5px; border-bottom:1px solid #111; }}
            .footer-clocks {{ display:flex; justify-content:center; gap:30px; font-size:12px; color:#444; padding-top:10px; }}
        </style>
    </head>
    <body>
        <div class="brand-header">ORACLE MONSTER v7.0</div>
        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">📊 השוואת מודלים (THE ORACLE)</div>
            <div class="model-grid">{model_boxes}</div>
            <div class="main-stats">
                <div class="stat-item"><small>ממוצע AI</small><div class="stat-val">{avg_oracle}°</div></div>
                <div style="width:1px; height:40px; background:#1a1a1a;"></div>
                <div class="stat-item"><small>LHR LIVE</small><div class="stat-val" style="color:#fff;">{lhr_live}°</div></div>
            </div>
        </div>
        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">⚖️ ארביטראז' פולימרקט</div>
            <div class="signal-box">
                <div style="font-size:12px; color:#555;">RECOMMENDED SIGNAL</div>
                <p class="signal-text" style="color:{BRAND_GREEN if signal=='YES' else '#fff'};">{signal if processed else 'NO DATA'}</p>
            </div>
            {f"<table><tr><th>מעלות</th><th>פולי</th><th>AI %</th><th>EDGE</th></tr>{table_rows}</table>" if processed else 
             f"<div style='text-align:center; color:#ffaa00; padding:20px; font-size:12px; direction:ltr;'><b>SCRAPING LOG:</b> No active London markets found via internal scan.</div>"}
        </div>
        <div class="footer-clocks">
            <div>🇬🇧 <b>London:</b> {now_uk}</div>
            <div>🇮🇱 <b>Israel:</b> {now_il}</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__":
    run_bot()
