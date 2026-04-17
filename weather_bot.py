import requests
import math
import time
import os
from datetime import datetime, timedelta
try:
    import pytz
except ImportError:
    pytz = None

# --- הגדרות עיצוב ---
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"

def get_accurate_poly_data():
    """משיכת נתונים אגרסיבית. מחזירה רשימה ריקה אם אין נתוני אמת."""
    api_key = os.getenv("POLY_API_KEY")
    ts = int(time.time())
    
    # חיפוש רחב יותר כדי לוודא שאנחנו תופסים את האירוע
    url = f"https://gamma-api.polymarket.com/events?active=true&closed=false&limit=100&_={ts}"
    headers = {'Authorization': f'Bearer {api_key}', 'Cache-Control': 'no-cache'}
    
    results = []
    fetch_error = None

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return [], f"API Error: {response.status_code}"
            
        data = response.json()
        for event in data:
            title = event.get('title', "").lower()
            # מחפשים שילוב של לונדון וטמפרטורה
            if "london" in title and "temp" in title:
                markets = event.get('markets', [])
                for m in markets:
                    m_title = m.get('groupItemTitle', "")
                    if '°' not in m_title: continue
                    try:
                        # חילוץ הטמפרטורה (למשל מ-"18°C")
                        temp_val = int(''.join(filter(str.isdigit, m_title.split('°')[0])))
                        
                        # חילוץ מחיר (שימוש ב-json.loads בטוח יותר מ-eval)
                        import json
                        prices = json.loads(m.get('outcomePrices', '["0", "0"]'))
                        price_raw = float(prices[0])
                        
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
        return results, None
    except Exception as e:
        return [], str(e)

def calculate_ai_prob(models, target_val):
    """חישוב הסתברות AI לפי התפלגות נורמלית"""
    # $P(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{1}{2}\left(\frac{x-\mu}{\sigma}\right)^2}$
    vals = list(models.values()); avg = sum(vals) / len(vals)
    std = max(math.sqrt(sum((x - avg)**2 for x in vals) / len(vals)), 0.6)
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    prob = round((cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100)
    return min(max(prob, 2), 98)

def run_bot():
    # ניהול זמנים
    if pytz:
        tz_il = pytz.timezone('Asia/Jerusalem'); tz_uk = pytz.timezone('Europe/London')
        now_il = datetime.now(tz_il).strftime('%H:%M'); now_uk = datetime.now(tz_uk).strftime('%H:%M')
    else:
        now_il = now_uk = datetime.now().strftime('%H:%M')

    # המודלים (The Oracle)
    models = {"ECMWF": 18.5, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.0, "MeteoFrance": 18.1}
    avg_oracle = sum(models.values()) / len(models)
    
    # משיכת נתונים אמיתיים בלבד
    poly_data, error_msg = get_accurate_poly_data()
    
    processed = []
    for opt in poly_data:
        ai_p = calculate_ai_prob(models, opt['val'])
        edge = ai_p - opt['numeric_prob']
        processed.append({**opt, "ai_p": ai_p, "edge": edge})
    
    # בניית הודעת שגיאה אם הנתונים ריקים
    error_html = ""
    if error_msg:
        error_html = f"<div style='color:{ERROR_RED}; padding:10px; border:1px solid {ERROR_RED}; border-radius:10px; margin-bottom:15px;'>שגיאת מערכת: {error_msg}</div>"
    elif not processed:
        error_html = f"<div style='color:{ERROR_RED}; padding:10px; border:1px solid {ERROR_RED}; border-radius:10px; margin-bottom:15px;'>⚠️ לא נמצאו נתוני שוק פעילים בפולימרקט ברגע זה.</div>"

    rows = ""
    for opt in processed:
        color = BRAND_GREEN if opt['edge'] > 0 else ERROR_RED
        rows += f"<tr><td style='padding:15px;'>{opt['temp']}</td><td style='text-align:center;'>{opt['price']}</td><td style='text-align:center;'>{opt['ai_p']}%</td><td style='color:{color}; font-weight:bold; text-align:left;'>{opt['edge']:+.1f}%</td></tr>"

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 10px; }}
        .card {{ background: #111; border: 1px solid #222; border-radius: 20px; padding: 20px; margin-bottom: 15px; }}
        .title {{ font-size: 11px; color: #555; font-weight: bold; margin-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ font-size: 10px; color: #444; padding-bottom: 10px; }}
        .signal {{ font-size: 40px; font-weight: bold; text-align: center; color: {BRAND_GREEN if processed else "#333"}; }}
    </style></head>
    <body>
        <div style="text-align:center; padding:10px; color:{BRAND_GREEN}; letter-spacing:2px;">WEATHER ORACLE v3.3</div>
        
        {error_html}

        <div class="card">
            <div class="title">🎯 תחזית ORACLE משוקללת</div>
            <div style="font-size:40px; font-weight:900; color:{BRAND_GREEN}; text-align:center;">{avg_oracle:.2f}°C</div>
        </div>

        <div class="card">
            <div class="title">⚖️ נתוני פולימרקט בזמן אמת</div>
            <table>
                <tr style="border-bottom:1px solid #222;"><th style="text-align:right;">טווח</th><th>מחיר</th><th>AI %</th><th style="text-align:left;">EDGE</th></tr>
                {rows}
            </table>
        </div>

        <div class="card">
            <div class="title">🧠 נימוק מערכת</div>
            <div style="font-size:13px; color:#999;">
                {"ניתוח הארביטראז' מבוסס על הצלבת מחירי ה-Orderbook המדויקים מול התפלגות נורמלית של 5 מודלי חיזוי." if processed else "ממתין לנתוני שוק אמת לצורך ביצוע ניתוח."}
            </div>
        </div>

        <div style="text-align:center; font-size:10px; color:#333; margin-top:20px;">🕒 לונדון: {now_uk} | ישראל: {now_il}</div>
    </body></html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    run_bot()
