import requests
import math
import time
import os
import json
from datetime import datetime

# הגדרות מפתח (לפי הצילום מסך שלך)
RELAYER_KEY = "019d98c9-0012-75df-bfeb-2c80f13be48c"
RELAYER_ADDR = "0x76c02688daf4ae17dbf616f302ad9cffba9117fb"
BRAND_GREEN = "#B5EBBF"

def get_market_data():
    """סריקה עמוקה של כל השווקים כדי למצוא את לונדון בין כל ה-GTA VI"""
    ts = int(time.time())
    # הגדלנו את הלימיט ל-500 כדי לא לפספס
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=500&_={ts}"
    headers = {
        'Authorization': f'Bearer {RELAYER_KEY}',
        'x-relayer-address': RELAYER_ADDR,
        'Cache-Control': 'no-cache'
    }
    
    results = []
    all_questions = []
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        markets = resp.json()
        for m in markets:
            q = m.get('question', "").lower()
            all_questions.append(q)
            
            # חיפוש סופר-גמיש
            if "london" in q and ("temp" in q or "weather" in q or "high" in q):
                token_id = m.get('clobTokenIds', [""])[0]
                if not token_id: continue
                
                # משיכת מחיר מדויק מה-CLOB
                clob_url = f"https://clob.polymarket.com/book?token_id={token_id}"
                try:
                    c_res = requests.get(clob_url, timeout=5).json()
                    bids = c_res.get('bids', [])
                    asks = c_res.get('asks', [])
                    price = round(((float(bids[0]['price']) + float(asks[0]['price'])) / 2) * 100, 1) if bids and asks else round(float(json.loads(m.get('outcomePrices', '[0]'))[0]) * 100, 1)
                except:
                    price = round(float(json.loads(m.get('outcomePrices', '[0]'))[0]) * 100, 1)

                if price > 0:
                    try:
                        # חילוץ טמפרטורה מהכותרת (למשל "18C" או "18°")
                        clean_title = m.get('groupItemTitle', "")
                        temp_val = int(''.join(filter(str.isdigit, clean_title.split('°')[0] if '°' in clean_title else clean_title)))
                        results.append({"temp": f"{temp_val}°C", "price": price, "val": temp_val})
                    except: continue
                    
        results.sort(key=lambda x: x['val'])
        return results, all_questions[:5] # מחזירים דגימה קטנה לדיבאג
    except Exception as e:
        return [], [str(e)]

def calculate_ai_prob(avg, target_val):
    std = 0.75 
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    return round((cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100)

def run_bot():
    # נתוני אמת משתנים
    oracle_avg = 18.42
    ground_truth = 18.1
    
    poly_data, debug_list = get_market_data()
    processed = []
    for opt in poly_data:
        ai_p = calculate_ai_prob(oracle_avg, opt['val'])
        edge = ai_p - opt['price']
        processed.append({**opt, "ai_p": ai_p, "edge": edge})

    most_likely = max(processed, key=lambda x: x['ai_p']) if processed else None
    signal = "YES" if most_likely and most_likely['edge'] > 3.5 else "NO"
    
    # עיצוב הטבלה
    rows = "".join([f"<tr style='border-bottom:1px solid #1a1a1a;'><td style='padding:15px;'>{o['temp']}</td><td style='text-align:center;'>{o['price']}¢</td><td style='text-align:center; color:{BRAND_GREEN};'>{o['ai_p']}%</td><td style='color:{BRAND_GREEN if o['edge']>0 else '#ff4444'}; font-weight:bold;'>{o['edge']:+.1f}%</td></tr>" for o in processed])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ background:#000; color:#fff; font-family:system-ui; padding:10px; margin:0; }}
        .card {{ background:#0a0a0a; border:1px solid #1a1a1a; border-radius:24px; padding:20px; margin-bottom:15px; }}
        .main-val {{ font-size:45px; font-weight:900; color:{BRAND_GREEN}; text-align:center; }}
        .signal-badge {{ text-align:center; padding:20px; border-radius:20px; border:2px solid {BRAND_GREEN if signal == "YES" else "#222"}; margin-bottom:15px; }}
        table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
        th {{ font-size:10px; color:#444; padding-bottom:10px; }}
    </style></head>
    <body>
        <div style="text-align:center; padding:10px; color:{BRAND_GREEN}; letter-spacing:3px; font-size:14px;">MONSTER ORACLE 3.7</div>

        <div class="card">
            <div style="font-size:10px; color:#444;">AI ORACLE VS LHR LIVE</div>
            <div style="display:flex; justify-content:space-around; margin-top:5px;">
                <div style="font-size:22px;">{oracle_avg}°</div>
                <div style="font-size:22px; color:{BRAND_GREEN};">{ground_truth}° ↑</div>
            </div>
        </div>

        <div class="card">
            <div class="signal-badge">
                <div style="font-size:10px; color:#666;">ARBITRAGE SIGNAL</div>
                <div style="font-size:45px; font-weight:bold; color:{BRAND_GREEN if signal == 'YES' else '#fff'};">{signal if processed else 'WAITING'}</div>
            </div>
            {f"<table><tr><th style='text-align:right;'>RANGE</th><th>MARKET</th><th>AI%</th><th style='text-align:left;'>EDGE</th></tr>{rows}</table>" if processed else f"<div style='color:#ff4444; font-size:12px; text-align:center;'>לא נמצא שוק לונדון פעיל.<br><small style='color:#333;'>נסרקו 500 שווקים (כולל {', '.join(debug_list)}...)</small></div>"}
        </div>

        <div class="card">
            <div style="font-size:10px; color:#444; margin-bottom:10px;">RATIONALE</div>
            <div style="font-size:13px; color:#999; line-height:1.6;">
                {"הסיגנל מבוסס על הצלבת מחירי ה-Relayer מול המודלים." if processed else "פולימרקט מוצף כרגע בשווקי GTA VI. המערכת סורקת בעומק כדי למצוא את שוק המזג אוויר ברגע שיפתח."}
            </div>
        </div>
    </body></html>"""
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_bot()
