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

# --- הגדרות מותג ---
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"

def get_clob_price(token_id):
    """משיכת מחיר מדויק מתוך ספר הפקודות (CLOB)"""
    url = f"https://clob.polymarket.com/book?token_id={token_id}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            # לוקחים את הממוצע בין הקונה הכי גבוה למוכר הכי נמוך (Midpoint)
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            if bids and asks:
                mid = (float(bids[0]['price']) + float(asks[0]['price'])) / 2
                return round(mid * 100, 1)
        return None
    except:
        return None

def get_market_data():
    """סריקת שווקים ושימוש ב-CLOB לדיוק מקסימלי"""
    api_key = os.getenv("POLY_API_KEY")
    ts = int(time.time())
    # שלב 1: מציאת השווקים הרלוונטיים ב-Gamma
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100&_={ts}"
    headers = {'Authorization': f'Bearer {api_key}', 'Cache-Control': 'no-cache'}
    
    results = []
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        markets = resp.json()
        for m in markets:
            title = m.get('question', "").lower()
            group = m.get('groupItemTitle', "").lower()
            
            if "london" in title and "temp" in title:
                # שלב 2: אם מצאנו שוק, ננסה להביא מחיר CLOB מדויק לפי ה-Token ID
                token_id = m.get('clobTokenIds', [""])[0]
                if not token_id: continue
                
                clob_p = get_clob_price(token_id)
                # אם ה-CLOB נכשל, נשתמש במחיר הכללי של Gamma (כגיבוי אמת בלבד)
                final_p = clob_p if clob_p else round(float(json.loads(m.get('outcomePrices', '[0]'))[0]) * 100, 1)
                
                if final_p > 0:
                    temp_val = int(''.join(filter(str.isdigit, m.get('groupItemTitle', "").split('°')[0])))
                    results.append({
                        "temp": f"{temp_val}°C",
                        "price": f"{final_p}¢",
                        "val": temp_val,
                        "numeric_prob": final_p,
                        "is_clob": clob_p is not None
                    })
        results.sort(key=lambda x: x['val'])
        return results, None
    except Exception as e:
        return [], str(e)

def calculate_ai_prob(models, target_val):
    vals = list(models.values()); avg = sum(vals) / len(vals)
    std = max(math.sqrt(sum((x - avg)**2 for x in vals) / len(vals)), 0.6)
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    return round((cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100)

def run_bot():
    # זמנים
    if pytz:
        tz_il = pytz.timezone('Asia/Jerusalem'); tz_uk = pytz.timezone('Europe/London')
        now_il = datetime.now(tz_il).strftime('%H:%M'); now_uk = datetime.now(tz_uk).strftime('%H:%M')
    else:
        now_il = now_uk = datetime.now().strftime('%H:%M')

    # המודלים (The Oracle)
    models = {"ECMWF": 18.5, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.0, "MeteoFrance": 18.1}
    avg_oracle = sum(models.values()) / len(models)
    
    # נתונים חיים בלבד - No Fake Data
    poly_data, err = get_market_data()
    processed = []
    for opt in poly_data:
        ai_p = calculate_ai_prob(models, opt['val'])
        edge = ai_p - opt['numeric_prob']
        processed.append({**opt, "ai_p": ai_p, "edge": edge})

    # סיגנל ונימוק
    most_likely = max(processed, key=lambda x: x['ai_p']) if processed else None
    signal = "YES" if most_likely and most_likely['edge'] > 3 else "NO"
    
    rationale = f"ה-Oracle חוזה {avg_oracle:.2f}°C. "
    if processed:
        rationale += f"ניתוח ה-CLOB זיהה {len(processed)} טווחי מסחר פעילים. "
        if signal == "YES": rationale += f"סיגנל YES הופעל עקב פער חיובי בטווח {most_likely['temp']}."
    else:
        rationale = "המערכת במצב המתנה. לא זוהו נתוני מסחר אמיתיים בפולימרקט."

    # בניית הטבלה
    rows = ""
    for opt in processed:
        is_panic = opt['edge'] > 15
        color = GOLD_COLOR if is_panic else (BRAND_GREEN if opt['edge'] > 0 else ERROR_RED)
        clob_tag = "<small style='font-size:8px; color:#555;'>[CLOB]</small>" if opt['is_clob'] else ""
        rows += f"<tr style='border-bottom:1px solid #1a1a1a;'><td style='padding:15px;'>{opt['temp']} {clob_tag}</td><td style='text-align:center;'>{opt['price']}</td><td style='text-align:center;'>{opt['ai_p']}%</td><td style='color:{color}; font-weight:bold; text-align:left;'>{opt['edge']:+.1f}%</td></tr>"

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 10px; }}
        .card {{ background: #111; border: 1px solid #222; border-radius: 20px; padding: 20px; margin-bottom: 15px; }}
        .title {{ font-size: 11px; color: #666; font-weight: bold; margin-bottom: 10px; }}
        .main-val {{ font-size: 45px; font-weight: 900; color: {BRAND_GREEN}; text-align: center; }}
        .signal-box {{ text-align: center; padding: 20px; border-radius: 20px; border: 2px solid {BRAND_GREEN if signal == "YES" else "#333"}; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ font-size: 10px; color: #444; padding-bottom: 10px; }}
        .error {{ color: {ERROR_RED}; font-size: 12px; padding: 15px; border: 1px solid {ERROR_RED}; border-radius: 12px; margin-bottom: 15px; text-align: center; }}
    </style></head>
    <body>
        <div style="text-align:center; padding:10px; color:{BRAND_GREEN}; letter-spacing:3px; font-size:14px;">ORACLE MONSTER v3.5</div>

        {f'<div class="error">⚠️ {err if err else "לא נמצאו נתוני שוק פעילים"}</div>' if not processed else ''}

        <div class="card">
            <div class="title">🎯 חיזוי ORACLE משוקלל</div>
            <div class="main-val">{avg_oracle:.2f}°C</div>
        </div>

        <div class="card">
            <div class="title">⚖️ ספר פקודות (CLOB PRECISION)</div>
            <div class="signal-box">
                <div style="font-size:10px; color:#555;">SIGNAL</div>
                <div style="font-size:40px; font-weight:bold; color:{BRAND_GREEN if signal == 'YES' else '#fff'};">{signal if processed else 'WAIT'}</div>
            </div>
            <table>
                <tr><th style="text-align:right;">טווח</th><th>מחיר</th><th>AI %</th><th style="text-align:left;">EDGE</th></tr>
                {rows}
            </table>
        </div>

        <div class="card">
            <div class="title">🧠 נימוקי החלטה</div>
            <div style="font-size:13px; line-height:1.6; color:#ccc;">{rationale}</div>
        </div>

        <div style="text-align:center; font-size:10px; color:#333; margin-top:20px;">לונדון: {now_uk} | ישראל: {now_il}</div>
    </body></html>"""
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_bot()
