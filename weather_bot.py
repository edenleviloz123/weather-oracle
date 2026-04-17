import requests
import math
import time
import os
import json
from datetime import datetime
import pytz

BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"

def get_market_data():
    """משיכת נתונים עם מערכת דיבאג (זיהוי חסימות)"""
    api_key = os.getenv("POLY_API_KEY")
    ts = int(time.time())
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=500&_={ts}"
    
    # ננסה לשלוח כותרות שידמו דפדפן אמיתי כדי לעקוף חסימות
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json'
    }
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    
    results = []
    debug_info = ""
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        
        # אם שרת פולימרקט חוסם אותנו
        if resp.status_code != 200:
            return [], f"API חסם את הבקשה (שגיאה {resp.status_code}). ייתכן ש-GitHub Actions נחסם ע'י Cloudflare."
            
        markets = resp.json()
        london_markets_found = []
        
        for m in markets:
            q = m.get('question', "").lower()
            if "london" in q:
                london_markets_found.append(q[:30] + "...") # שומרים את מה שהוא כן מצא לדיבאג
                
                if any(x in q for x in ["temp", "weather", "degree", "high"]):
                    token_id = m.get('clobTokenIds', [""])[0]
                    if not token_id: continue
                    
                    price = 0
                    try:
                        c_url = f"https://clob.polymarket.com/book?token_id={token_id}"
                        c_data = requests.get(c_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
                        bids, asks = c_data.get('bids', []), c_data.get('asks', [])
                        if bids and asks:
                            price = round(((float(bids[0]['price']) + float(asks[0]['price'])) / 2) * 100, 1)
                    except: pass
                    
                    if price == 0:
                        try:
                            price = round(float(json.loads(m.get('outcomePrices', '[0]'))[0]) * 100, 1)
                        except: pass

                    if price > 0:
                        try:
                            title = m.get('groupItemTitle', "")
                            temp_val = int(''.join(filter(str.isdigit, title)))
                            results.append({"temp": temp_val, "poly_price": price})
                        except: continue
        
        if not results:
            debug_info = f"לא נמצאו טווחי טמפרטורות. שווקים עם המילה לונדון שכן נמצאו: {', '.join(london_markets_found[:3])}" if london_markets_found else "לא נמצא אף שוק עם המילה London היום."
            return [], debug_info
            
        return sorted(results, key=lambda x: x['temp']), ""
        
    except Exception as e:
        return [], f"שגיאת תקשורת קריטית: {str(e)}"

def calculate_ai_prob(avg, target_val):
    std = 0.7
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    return round((cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100, 1)

def run_bot():
    # --- שעונים ---
    tz_il = pytz.timezone('Asia/Jerusalem')
    tz_uk = pytz.timezone('Europe/London')
    now_il = datetime.now(tz_il).strftime('%H:%M')
    now_uk = datetime.now(tz_uk).strftime('%H:%M')

    # --- מודלים ונתוני אמת ---
    models = {"ECMWF": 18.6, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.1, "MeteoFrance": 18.4}
    avg_oracle = round(sum(models.values()) / len(models), 2)
    lhr_live = 18.2
    momentum = "↑"
    
    # --- נתונים מפולימרקט ---
    poly_data, err_msg = get_market_data()
    
    # --- חישוב ארביטראז' ---
    processed = []
    for opt in poly_data:
        our_prob = calculate_ai_prob(avg_oracle, opt['temp'])
        edge = round(our_prob - opt['poly_price'], 1)
        processed.append({"label": f"{opt['temp']}°C", "poly": f"{opt['poly_price']}¢", "ours": f"{our_prob}%", "edge": edge})

    best = max(processed, key=lambda x: x['edge']) if processed else None
    signal = "YES" if best and best['edge'] > 3.5 else "NO"

    # --- יצירת ה-HTML (כולל את כל האלמנטים) ---
    model_cards = "".join([f"<div style='text-align:center;'><div style='color:#444; font-size:9px;'>{k}</div><div>{v}°</div></div>" for k,v in models.items()])
    rows = "".join([f"<tr style='border-bottom:1px solid #1a1a1a;'><td style='padding:12px;'>{p['label']}</td><td style='text-align:center;'>{p['poly']}¢</td><td style='text-align:center;'>{p['ours']}%</td><td style='color:{GOLD_COLOR if p['edge']>12 else (BRAND_GREEN if p['edge']>0 else ERROR_RED)}; font-weight:bold;'>{p['edge']:+.1f}%</td></tr>" for p in processed])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ background:#000; color:#fff; font-family:system-ui; padding:10px; margin:0; }}
        .card {{ background:#0a0a0a; border:1px solid #1a1a1a; border-radius:20px; padding:20px; margin-bottom:15px; }}
        .title {{ font-size:10px; color:#444; font-weight:bold; margin-bottom:10px; text-transform:uppercase; }}
        table {{ width:100%; border-collapse:collapse; }}
        th {{ font-size:9px; color:#333; padding-bottom:8px; text-align:center; }}
        .clock-box {{ display:flex; justify-content:center; gap:20px; font-size:12px; color:#aaa; margin-top:15px; padding:15px; background:#111; border-radius:15px; }}
        .debug-box {{ font-size:11px; color:{ERROR_RED}; padding:15px; border:1px solid {ERROR_RED}; border-radius:10px; margin-top:10px; background:rgba(255,0,0,0.1); text-align:center; direction:ltr; }}
    </style></head>
    <body>
        <div style="text-align:center; color:{BRAND_GREEN}; letter-spacing:3px; padding:10px; font-weight:bold; font-size:15px;">ORACLE MONSTER v5.0</div>

        <div class="card">
            <div class="title">📊 השוואת מודלים (THE ORACLE)</div>
            <div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:5px; border-bottom:1px solid #1a1a1a; padding-bottom:10px; margin-bottom:10px;">{model_cards}</div>
            <div style="display:flex; justify-content:space-around; align-items:center;">
                <div style="text-align:center;"><small style="color:#444;">ממוצע AI</small><br><b style="font-size:24px; color:{BRAND_GREEN};">{avg_oracle}°</b></div>
                <div style="text-align:center;"><small style="color:#444;">LHR LIVE</small><br><b style="font-size:24px;">{lhr_live}° <span style="color:{BRAND_GREEN};">{momentum}</span></b></div>
            </div>
        </div>

        <div class="card">
            <div class="title">⚖️ טבלת ארביטראז' פולימרקט</div>
            <div style="text-align:center; padding:15px; border:2px solid {BRAND_GREEN if signal=='YES' else '#222'}; border-radius:15px; margin-bottom:15px;">
                <div style="font-size:10px; color:#555;">SIGNAL STATUS</div>
                <div style="font-size:45px; font-weight:900; color:{BRAND_GREEN if signal=='YES' else '#fff'};">{signal if processed else 'WAITING'}</div>
            </div>
            {f"<table><tr><th style='text-align:right;'>מעלות</th><th>מחיר פולי</th><th>מחיר AI</th><th style='text-align:left;'>EDGE</th></tr>{rows}</table>" if processed else f"<div class='debug-box'><b>API DEBUG INFO:</b><br>{err_msg}</div>"}
        </div>

        <div class="card">
            <div class="title">🧠 נימוקי החלטה (RATIONALE)</div>
            <div style="font-size:13px; color:#888; line-height:1.5;">{f"הסיגנל ממליץ על {signal} לאור זיהוי פער ארביטראז' חיובי של {best['edge']}% בטווח של {best['label']}." if processed else "המערכת נמצאת במצב המתנה עד לקבלת נתוני אמת תקינים מה-API של פולימרקט."}</div>
        </div>

        <div class="clock-box">
            <div>🇬🇧 <b>לונדון:</b> <span style="color:#fff;">{now_uk}</span></div>
            <div>🇮🇱 <b>ישראל:</b> <span style="color:#fff;">{now_il}</span></div>
        </div>
    </body></html>"""
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_bot()
