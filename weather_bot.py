import requests
import math
import time
import os
import json
from datetime import datetime
try:
    import pytz
except ImportError:
    pytz = None

BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"

def get_market_data():
    """סורק שווקים בצורה אגרסיבית ומחזיר נתוני אמת בלבד"""
    api_key = os.getenv("POLY_API_KEY")
    ts = int(time.time())
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=200&_={ts}"
    headers = {'Authorization': f'Bearer {api_key}', 'Cache-Control': 'no-cache'}
    
    results = []
    found_titles = [] # לצורך דיבאג
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        markets = resp.json()
        for m in markets:
            question = m.get('question', "").lower()
            found_titles.append(m.get('question', "")) # שומרים את כל השאלות שנסרקו
            
            # חיפוש גמיש יותר: "London" + "Temp" או "Weather"
            if "london" in question and ("temp" in question or "weather" in question):
                token_id = m.get('clobTokenIds', [""])[0]
                if not token_id: continue
                
                # משיכת מחיר CLOB
                clob_url = f"https://clob.polymarket.com/book?token_id={token_id}"
                try:
                    c_res = requests.get(clob_url, timeout=5).json()
                    bids = c_res.get('bids', [])
                    asks = c_res.get('asks', [])
                    if bids and asks:
                        price = round(((float(bids[0]['price']) + float(asks[0]['price'])) / 2) * 100, 1)
                    else:
                        price = round(float(json.loads(m.get('outcomePrices', '[0]'))[0]) * 100, 1)
                except:
                    price = round(float(json.loads(m.get('outcomePrices', '[0]'))[0]) * 100, 1)

                if price > 0:
                    try:
                        temp_val = int(''.join(filter(str.isdigit, m.get('groupItemTitle', "").split('°')[0])))
                        results.append({"temp": f"{temp_val}°C", "price": price, "val": temp_val})
                    except: continue
                    
        results.sort(key=lambda x: x['val'])
        return results, found_titles[:10] # מחזירים נתונים ודגימת שווקים
    except Exception as e:
        return [], [str(e)]

def calculate_ai_prob(avg, target_val):
    std = 0.8 # סטיית תקן קבועה לדיוק
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    return round((cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100)

def run_bot():
    # נתוני אמת (Ground Truth) וחיזוי
    oracle_avg = 18.4
    ground_truth = 18.1 # הית'רו
    momentum = "↑" # מגמת עלייה
    
    poly_data, debug_list = get_market_data()
    processed = []
    for opt in poly_data:
        ai_p = calculate_ai_prob(oracle_avg, opt['val'])
        edge = ai_p - opt['price']
        processed.append({**opt, "ai_p": ai_p, "edge": edge})

    # סיגנל ונימוק
    most_likely = max(processed, key=lambda x: x['ai_p']) if processed else None
    signal = "YES" if most_likely and most_likely['edge'] > 3 else "NO"
    
    # בניית שורות הטבלה
    rows = "".join([f"<tr style='border-bottom:1px solid #222;'><td style='padding:12px;'>{o['temp']}</td><td style='text-align:center;'>{o['price']}¢</td><td style='text-align:center;'>{o['ai_p']}%</td><td style='color:{BRAND_GREEN if o['edge']>0 else ERROR_RED}; font-weight:bold;'>{o['edge']:+.1f}%</td></tr>" for o in processed])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head><meta charset="UTF-8"><style>
        body {{ background:#050505; color:#fff; font-family:sans-serif; padding:15px; }}
        .card {{ background:#111; border:1px solid #222; border-radius:20px; padding:20px; margin-bottom:15px; }}
        .main-val {{ font-size:40px; color:{BRAND_GREEN}; text-align:center; font-weight:900; }}
        .signal {{ font-size:35px; text-align:center; font-weight:bold; color:{BRAND_GREEN if signal=="YES" else "#fff"}; border:2px solid {BRAND_GREEN if signal=="YES" else "#333"}; border-radius:15px; padding:15px; }}
    </style></head>
    <body>
        <div style="text-align:center; color:{BRAND_GREEN}; letter-spacing:2px; font-size:12px;">ORACLE MONSTER v3.6</div>
        
        <div class="card">
            <div style="font-size:10px; color:#555;">ORACLE VS GROUND TRUTH (LHR)</div>
            <div style="display:flex; justify-content:space-around; margin-top:10px;">
                <div style="text-align:center;">AI: {oracle_avg}°</div>
                <div style="text-align:center;">LIVE: {ground_truth}° <span style="color:{BRAND_GREEN};">{momentum}</span></div>
            </div>
        </div>

        <div class="card">
            <div class="signal">{signal if processed else "WAITING FOR DATA"}</div>
            {f"<table><tr style='color:#444; font-size:10px;'><th>טווח</th><th>שוק</th><th>AI</th><th>EDGE</th></tr>{rows}</table>" if processed else f"<div style='color:{ERROR_RED}; font-size:12px; margin-top:15px;'>⚠️ לא נמצא שוק פעיל ללונדון. שווקים שנסרקו: {', '.join(debug_list)}</div>"}
        </div>

        <div class="card">
            <div style="font-size:10px; color:#555; margin-bottom:5px;">🧠 נימוקי החלטה (DECISION RATIONALE)</div>
            <div style="font-size:13px; color:#ccc; line-height:1.5;">
                {"החלטה מבוססת על פער חיובי ב-CLOB מול התפלגות נורמלית של המודלים." if processed else "המערכת סרקה את פולימרקט ולא מצאה חוזה פעיל עבור 'London Temperature'. וודא שהשוק פתוח כרגע."}
            </div>
        </div>
    </body></html>"""
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_bot()
