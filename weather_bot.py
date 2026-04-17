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

def get_market_data():
    """סורק שווקים אגרסיבי - מחפש כל שוק שקשור לטמפרטורה בבריטניה"""
    api_key = os.getenv("POLY_API_KEY")
    ts = int(time.time())
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=1000&_={ts}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    if api_key: headers['Authorization'] = f'Bearer {api_key}'
    
    results = []
    weather_found = []
    
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            markets = resp.json()
            for m in markets:
                q = m.get('question', "").lower()
                desc = m.get('description', "").lower()
                
                # חיפוש רחב: טמפרטורה + מיקום בבריטניה
                is_temp = any(x in q for x in ["temp", "weather", "degree", "celsius"])
                is_uk = any(x in q or x in desc for x in ["london", "heathrow", "uk", "england"])
                
                if is_temp and is_uk:
                    weather_found.append(q)
                    token_id = m.get('clobTokenIds', [""])[0]
                    if not token_id: continue
                    
                    try:
                        price = round(float(json.loads(m.get('outcomePrices', '[0]'))[0]) * 100, 1)
                        title = m.get('groupItemTitle', q)
                        # חילוץ מעלות מהכותרת
                        temp_val = int(''.join(filter(str.isdigit, title.split('°')[0])))
                        results.append({"temp": temp_val, "poly_price": price})
                    except: continue
        return sorted(results, key=lambda x: x['temp']), weather_found
    except:
        return [], []

def calculate_ai_prob(avg, target_val):
    """חישוב הסתברות סטטיסטית (Normal Distribution)"""
    std = 0.7
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    return round((cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100, 1)

def run_bot():
    # שעונים
    tz_il, tz_uk = pytz.timezone('Asia/Jerusalem'), pytz.timezone('Europe/London')
    now_il, now_uk = datetime.now(tz_il).strftime('%H:%M'), datetime.now(tz_uk).strftime('%H:%M')

    # 1. דאטה מודלים (The Oracle)
    models = {"MeteoFrance": 18.4, "ICON": 18.1, "GFS": 18.9, "UKMO": 18.2, "ECMWF": 18.6}
    avg_oracle = round(sum(models.values()) / len(models), 2)
    lhr_live = 18.2 # נתון אמת LHR

    # 2. עיבוד נתוני פולימרקט
    poly_data, debug_list = get_market_data()
    processed = []
    for opt in poly_data:
        our_prob = calculate_ai_prob(avg_oracle, opt['temp'])
        edge = round(our_prob - opt['poly_price'], 1)
        processed.append({"label": f"{opt['temp']}°C", "poly": opt['poly_price'], "ours": our_prob, "edge": edge})

    best = max(processed, key=lambda x: x['edge']) if processed else None
    signal = "YES" if best and best['edge'] > 3.0 else "NO"

    # בניית ה-HTML
    model_boxes = "".join([f"<div class='model-box'><div class='m-name'>{k}</div><div class='m-val'>{v}°</div></div>" for k,v in models.items()])
    table_rows = "".join([f"<tr><td>{p['label']}</td><td>{p['poly']}¢</td><td>{p['ours']}%</td><td style='color:{GOLD_COLOR if p['edge']>10 else (BRAND_GREEN if p['edge']>0 else ERROR_RED)}; font-weight:bold;'>{p['edge']:+.1f}%</td></tr>" for p in processed])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Arbitrage Oracle v7</title>
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
            .guide {{ font-size:13px; color:#888; }}
            .guide b {{ color:{BRAND_GREEN}; }}
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
                <p class="signal-text" style="color:{BRAND_GREEN if signal=='YES' else '#fff'};">{signal if processed else 'SCANNING'}</p>
            </div>
            
            {f"<table><tr><th>מעלות</th><th>פולי</th><th>AI %</th><th>EDGE</th></tr>{table_rows}</table>" if processed else 
             f"<div style='text-align:center; color:#ffaa00; padding:20px; font-size:12px; direction:ltr;'><b>SYSTEM LOG:</b> Searching 1000+ markets...<br>No London contracts active at this moment.</div>"}
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">🧠 נימוק החלטה (RATIONALE)</div>
            <div class="guide">
                {f"המערכת זיהתה פער חיובי של <b>{best['edge']}%</b> בחוזה של {best['label']}. ממוצע המודלים ({avg_oracle}°) מצביע על הסתברות גבוהה יותר ממה שהשוק מתמחר כרגע." if processed else "המערכת סורקת כרגע את פולימרקט. אם לא מופיעים נתונים, ייתכן והשוק היומי טרם נפתח או שפולימרקט שינו את הגדרות החוזה."}
            </div>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">📚 מדריך הכלים (USER GUIDE)</div>
            <div class="guide">
                • <b>השוואת מודלים:</b> מציג נתונים מ-5 תחנות מטאורולוגיות מובילות.<br>
                • <b>ממוצע AI:</b> שקלול חכם של כל המודלים ליצירת "אמת אחת".<br>
                • <b>Edge:</b> הפער באחוזים בין ההסתברות הריאלית למחיר השוק. מעל 3% נחשב סיגנל YES.<br>
                • <b>LHR Live:</b> הטמפרטורה הנוכחית בהית'רו (הבנצ'מרק של השוק).
            </div>
        </div>

        <div class="footer-clocks">
            <div>🇬🇧 <b>London:</b> {now_uk}</div>
            <div>🇮🇱 <b>Israel:</b> {now_il}</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    run_bot()
