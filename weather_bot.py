import requests
import math
import time
import os
import json
from datetime import datetime
import pytz

# הגדרות מיתוג
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"

def get_market_data():
    api_key = os.getenv("POLY_API_KEY")
    ts = int(time.time())
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=1000&_={ts}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    if api_key: headers['Authorization'] = f'Bearer {api_key}'
    
    results, weather_list = [], []
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            markets = resp.json()
            for m in markets:
                q = m.get('question', "").lower()
                if any(x in q for x in ["temp", "weather", "degree"]):
                    weather_list.append(q)
                    if any(x in q for x in ["london", "heathrow", "uk"]):
                        token_id = m.get('clobTokenIds', [""])[0]
                        if not token_id: continue
                        try:
                            price = round(float(json.loads(m.get('outcomePrices', '[0]'))[0]) * 100, 1)
                            title = m.get('groupItemTitle', q)
                            temp_val = int(''.join(filter(str.isdigit, title.split('°')[0])))
                            results.append({"temp": temp_val, "poly_price": price})
                        except: continue
        return sorted(results, key=lambda x: x['temp']), "", weather_list
    except Exception as e:
        return [], str(e), []

def calculate_ai_prob(avg, target_val):
    std = 0.7
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    return round((cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100, 1)

def run_bot():
    # חישוב שעונים
    tz_il, tz_uk = pytz.timezone('Asia/Jerusalem'), pytz.timezone('Europe/London')
    now_il, now_uk = datetime.now(tz_il).strftime('%H:%M'), datetime.now(tz_uk).strftime('%H:%M')

    # נתוני מודלים ו-Oracle
    models = {"MeteoFrance": 18.4, "ICON": 18.1, "GFS": 18.9, "UKMO": 18.2, "ECMWF": 18.6}
    avg_oracle = round(sum(models.values()) / len(models), 2)
    lhr_live = 18.2 # נתון אמת LHR

    poly_data, err, weather_list = get_market_data()
    processed = []
    for opt in poly_data:
        our_prob = calculate_ai_prob(avg_oracle, opt['temp'])
        edge = round(our_prob - opt['poly_price'], 1)
        processed.append({"label": f"{opt['temp']}°C", "poly": opt['poly_price'], "ours": our_prob, "edge": edge})

    best = max(processed, key=lambda x: x['edge']) if processed else None
    signal = "YES" if best and best['edge'] > 3.0 else "NO"
    
    model_html = "".join([f"<div style='text-align:center;'><div style='color:#555; font-size:10px;'>{k}</div><div>{v}°</div></div>" for k,v in models.items()])
    rows = "".join([f"<tr style='border-bottom:1px solid #1a1a1a;'><td style='padding:15px;'>{p['label']}</td><td style='text-align:center;'>{p['poly']}¢</td><td style='text-align:center;'>{p['ours']}%</td><td style='color:{GOLD_COLOR if p['edge']>10 else (BRAND_GREEN if p['edge']>0 else ERROR_RED)}; font-weight:bold; text-align:left;'>{p['edge']:+.1f}%</td></tr>" for p in processed])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ background:#000; color:#fff; font-family:system-ui; padding:15px; margin:0; }}
        .card {{ background:#0a0a0a; border:1px solid #1a1a1a; border-radius:24px; padding:20px; margin-bottom:15px; }}
        .title {{ font-size:11px; color:#555; font-weight:bold; margin-bottom:15px; text-transform:uppercase; }}
        table {{ width:100%; border-collapse:collapse; }}
    </style></head>
    <body>
        <div style="text-align:center; color:{BRAND_GREEN}; padding:15px; font-weight:900;">ORACLE MONSTER v6.3</div>
        <div class="card">
            <div class="title">📊 דאטה מודלים</div>
            <div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:10px; border-bottom:1px solid #1a1a1a; padding-bottom:15px; margin-bottom:15px;">{model_html}</div>
            <div style="display:flex; justify-content:space-around;">
                <div style="text-align:center;"><small style="color:#444;">ממוצע AI</small><br><b style="font-size:28px; color:{BRAND_GREEN};">{avg_oracle}°</b></div>
                <div style="text-align:center;"><small style="color:#444;">LHR LIVE</small><br><b style="font-size:28px;">{lhr_live}°</b></div>
            </div>
        </div>
        <div class="card">
            <div class="title">⚖️ ארביטראז' פולימרקט</div>
            <div style="text-align:center; padding:25px; border:2px solid {BRAND_GREEN if signal=='YES' else '#222'}; border-radius:20px; margin-bottom:20px;">
                <div style="font-size:55px; font-weight:900; color:{BRAND_GREEN if signal=='YES' else '#fff'};">{signal if processed else 'SCANNING'}</div>
            </div>
            {f"<table><tr><th style='text-align:right;'>מעלות</th><th>פולי</th><th>AI %</th><th style='text-align:left;'>EDGE</th></tr>{rows}</table>" if processed else f"<div style='font-size:10px; color:#ffaa00; padding:15px; direction:ltr; text-align:left;'><b>SCANNING:</b> Found {len(weather_list)} potential markets.</div>"}
        </div>
        <div class="card">
            <div class="title">🧠 נימוק (Rationale)</div>
            <div style="font-size:14px; color:#888;">{f"סיגנל {signal} מבוסס על פער של {best['edge']}% בטווח {best['label']}." if processed else "מחפש הזדמנויות ארביטראז'..."}</div>
        </div>
        <div style="display:flex; justify-content:center; gap:30px; font-size:12px; color:#444; padding:20px; border-top:1px solid #111;">
            <div>🇬🇧 <b>London:</b> {now_uk}</div>
            <div>🇮🇱 <b>Israel:</b> {now_il}</div>
        </div>
    </body></html>"""
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_bot()
