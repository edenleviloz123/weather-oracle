import requests
import math
import time
import os
import json
from datetime import datetime, timedelta
try:
    import pytz
except ImportError:
    pytz = None

# --- הגדרות עיצוב ---
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"

def get_accurate_poly_data():
    """סריקה ישירה של שווקים (Markets) למניעת פספוסים"""
    api_key = os.getenv("POLY_API_KEY")
    ts = int(time.time())
    
    # שימוש ב-Endpoint של שווקים ישירים (יותר אמין מחיפוש אירועים)
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100&_={ts}"
    headers = {'Authorization': f'Bearer {api_key}', 'Cache-Control': 'no-cache'}
    
    results = []
    debug_info = ""

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return [], f"API Error: {response.status_code}", response.text[:200]
            
        markets = response.json()
        for m in markets:
            # בדיקת התאמה לפי שם השוק או התיאור
            question = m.get('question', "").lower()
            group_title = m.get('groupItemTitle', "").lower()
            
            if "london" in question and ("temp" in question or "temp" in group_title):
                try:
                    # חילוץ טמפרטורה
                    raw_title = m.get('groupItemTitle', "")
                    temp_val = int(''.join(filter(str.isdigit, raw_title.split('°')[0])))
                    
                    # חילוץ מחיר YES
                    outcome_prices = json.loads(m.get('outcomePrices', '["0", "0"]'))
                    price_raw = float(outcome_prices[0])
                    
                    if price_raw > 0:
                        price_cents = round(price_raw * 100)
                        results.append({
                            "temp": f"{temp_val}°C",
                            "price": f"{price_cents}¢",
                            "val": temp_val,
                            "numeric_prob": price_cents
                        })
                except: continue
        
        results.sort(key=lambda x: x['val'])
        return results, None, "Success"
    except Exception as e:
        return [], str(e), "Connection Failed"

def get_ground_truth():
    """נתוני אמת (METAR) - כרגע בסימולציה עד חיבור API ייעודי"""
    return {"current": 18.3, "previous": 17.9, "station": "Heathrow (LHR)"}

def calculate_ai_prob(models, target_val):
    vals = list(models.values()); avg = sum(vals) / len(vals)
    std = max(math.sqrt(sum((x - avg)**2 for x in vals) / len(vals)), 0.6)
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    prob = round((cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100)
    return min(max(prob, 2), 98)

def run_bot():
    if pytz:
        tz_il = pytz.timezone('Asia/Jerusalem'); tz_uk = pytz.timezone('Europe/London')
        now_il = datetime.now(tz_il).strftime('%H:%M'); now_uk = datetime.now(tz_uk).strftime('%H:%M')
        time_left = (datetime.now(tz_uk).replace(hour=23, minute=59) - datetime.now(tz_uk))
        expiry_str = f"{time_left.seconds // 3600} שעות"
    else:
        now_il = now_uk = datetime.now().strftime('%H:%M'); expiry_str = "לא זמין"

    models = {"ECMWF": 18.5, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.0, "MeteoFrance": 18.1}
    avg_oracle = sum(models.values()) / len(models)
    truth = get_ground_truth()
    momentum = "↑" if truth['current'] > truth['previous'] else "↓"
    
    poly_data, error_msg, debug_raw = get_accurate_poly_data()
    processed = []
    for opt in poly_data:
        ai_p = calculate_ai_prob(models, opt['val'])
        edge = ai_p - opt['numeric_prob']
        processed.append({**opt, "ai_p": ai_p, "edge": edge})
    
    most_likely = max(processed, key=lambda x: x['ai_p']) if processed else None
    signal = "YES" if most_likely and most_likely['edge'] > 3 else "NO"

    rows = ""
    for opt in processed:
        is_panic = opt['edge'] > 15
        color = GOLD_COLOR if is_panic else (BRAND_GREEN if opt['edge'] > 0 else ERROR_RED)
        bg = "background: rgba(255, 215, 0, 0.05);" if is_panic else ""
        rows += f"<tr style='{bg} border-bottom: 1px solid #1a1a1a;'><td style='padding:15px;'>{opt['temp']}</td><td style='text-align:center;'>{opt['price']}</td><td style='text-align:center;'>{opt['ai_p']}%</td><td style='color:{color}; font-weight:bold; text-align:left;'>{opt['edge']:+.1f}%</td></tr>"

    # לוגיקת נימוק החלטה
    rationale = f"ה-Oracle חוזה {avg_oracle:.1f}°C. בשטח נמדדים {truth['current']}°C במגמת {('עלייה' if momentum == '↑' else 'ירידה')}."
    if not processed: rationale = "ממתין לעדכון נתוני שוק מפולימרקט. המערכת מסרבת לייצר ניתוח על בסיס נתונים חסרים."

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 10px; margin: 0; }}
        .card {{ background: #111; border: 1px solid #222; border-radius: 24px; padding: 20px; margin-bottom: 15px; }}
        .title {{ font-size: 11px; color: #666; font-weight: bold; margin-bottom: 10px; }}
        .main-val {{ font-size: 45px; font-weight: 900; color: {BRAND_GREEN}; text-align: center; }}
        .signal-box {{ text-align: center; padding: 20px; border-radius: 20px; border: 2px solid {BRAND_GREEN if signal == "YES" else "#333"}; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ font-size: 10px; color: #444; padding-bottom: 10px; }}
        .error {{ color: {ERROR_RED}; font-size: 12px; padding: 10px; border: 1px solid {ERROR_RED}; border-radius: 10px; margin-bottom: 15px; text-align: center; }}
    </style></head>
    <body>
        <div style="text-align:center; padding:10px;"><h2 style="font-size:14px; color:{BRAND_GREEN}; letter-spacing:3px;">ORACLE MONSTER v3.4</h2></div>

        {f'<div class="error">⚠️ {error_msg}<br><small style="font-size:8px;">{debug_raw}</small></div>' if error_msg or not processed else ''}

        <div class="card">
            <div class="title">🎯 ORACLE VS GROUND TRUTH</div>
            <div style="display:flex; justify-content: space-around;">
                <div style="text-align:center;"><div style="font-size:9px; color:#444;">AI</div><div style="font-size:24px; color:{BRAND_GREEN};">{avg_oracle:.2f}°</div></div>
                <div style="text-align:center;"><div style="font-size:9px; color:#444;">LHR</div><div style="font-size:24px;">{truth['current']}° <span style="color:{BRAND_GREEN if momentum == '↑' else ERROR_RED};">{momentum}</span></div></div>
            </div>
        </div>

        <div class="card">
            <div class="title">⚖️ נתוני שוק (EDGE)</div>
            <div class="signal-box">
                <div style="font-size:10px; color:#666;">SIGNAL</div>
                <div style="font-size:40px; font-weight:bold; color:{BRAND_GREEN if signal == 'YES' else '#fff'};">{signal if processed else 'WAIT'}</div>
                <div style="font-size:10px; color:#555; margin-top:5px;">סגירה: {expiry_str}</div>
            </div>
            <table>
                <tr><th style="text-align:right;">טווח</th><th>מחיר</th><th>AI</th><th style="text-align:left;">EDGE</th></tr>
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
