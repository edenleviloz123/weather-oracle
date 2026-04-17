import requests
import math
import time
import os
import json
from datetime import datetime
import pytz

# הגדרות מיתוג (Idol Studios Style)
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"
BG_DARK = "#0a0a0a"

def get_detailed_weather():
    """מושך נתוני אמת + מודלים ברמת דיוק עשרונית גבוהה"""
    # שימוש בפרמטרים מפורטים כדי למנוע עיגול של ה-API
    url = "https://api.open-meteo.com/v1/forecast?latitude=51.47&longitude=-0.45&hourly=temperature_2m,ecmwf_ifs025_temperature_2m,gfs_seamless_temperature_2m,icon_seamless_temperature_2m,meteofrance_seamless_temperature_2m&forecast_days=1&current=temperature_2m"
    
    models_data = {
        "ECMWF": {"val": 18.0, "weight": 0.30, "desc": "המודל האירופי - דיוק גבוה לטווח בינוני.", "api_key": "ecmwf_ifs025_temperature_2m"},
        "UKMO": {"val": 18.0, "weight": 0.25, "desc": "מודל השירות הבריטי - רמת דיוק מקסימלית ללונדון.", "api_key": "temperature_2m"}, # ברירת מחדל ללונדון
        "GFS": {"val": 18.0, "weight": 0.20, "desc": "המודל האמריקאי - גלובלי, מצוין לזיהוי מגמות.", "api_key": "gfs_seamless_temperature_2m"},
        "ICON": {"val": 18.0, "weight": 0.15, "desc": "מודל גרמני ברזולוציה גבוהה.", "api_key": "icon_seamless_temperature_2m"},
        "MeteoFrance": {"val": 18.0, "weight": 0.10, "desc": "מודל צרפתי המתמחה במערכות לחץ.", "api_key": "meteofrance_seamless_temperature_2m"}
    }
    
    try:
        resp = requests.get(url, timeout=15).json()
        hourly = resp.get("hourly", {})
        times = hourly.get("time", [])
        current_hour_idx = datetime.now(pytz.timezone('Europe/London')).hour
        
        # 1. זיכרון נתוני אמת - שיא שנמדד בפועל (טיפול בערך ה-0 שהופיע אצלך)
        past_temps = hourly.get("temperature_2m", [])[:current_hour_idx + 1]
        max_so_far = round(max(past_temps), 1) if past_temps else resp.get("current", {}).get("temperature_2m", 0.0)
        
        # 2. עדכון מודלים עם דיוק עשרוני
        for name, m in models_data.items():
            key = m["api_key"]
            if key in hourly and hourly[key]:
                m["val"] = round(max(hourly[key]), 1)
                m["updated"] = "LIVE"
            else:
                m["updated"] = "N/A"
        
        # 3. חישוב ממוצע משוקלל מדויק
        avg_max = sum(m["val"] * m["weight"] for m in models_data.values())
        
        # 4. מציאת שעת השיא
        peak_hour = hourly["temperature_2m"].index(max(hourly["temperature_2m"])) if "temperature_2m" in hourly else 14
        
        lhr_now = resp.get("current", {}).get("temperature_2m", 0.0)
        return models_data, lhr_now, max_so_far, peak_hour, round(avg_max, 2)
    except Exception as e:
        print(f"API Error: {e}")
        return models_data, 0.0, 0.0, 14, 18.0

def calculate_smart_prob(avg_max, target_str, max_so_far, peak_hour):
    """חישוב הסתברות חכם עם הגנה מפני איפוס שגוי"""
    tz_uk = pytz.timezone('Europe/London')
    now_uk = datetime.now(tz_uk)
    current_time_float = now_uk.hour + (now_uk.minute / 60.0)
    
    try:
        # חילוץ מספר מהכותרת (תומך בפורמט "19°C" או "22°C or higher")
        target_val = int(''.join(filter(str.isdigit, target_str.split('°')[0])))
    except: return 0.0

    # חישוב הסתברות סטטיסטית (Normal Distribution)
    std = 0.55 # רמת ביטחון גבוהה יותר
    def cdf(x): return (1.0 + math.erf((x - avg_max) / (std * math.sqrt(2.0)))) / 2.0
    
    is_above = any(x in target_str.lower() for x in ["above", "higher", "more"])
    
    if is_above:
        prob = (1.0 - cdf(target_val - 0.4)) * 100
    else:
        # טווח ספציפי (למשל בדיוק 18 מעלות)
        prob = (cdf(target_val + 0.4) - cdf(target_val - 0.4)) * 100

    # לוגיקת שעת השיא (Peak Hour Defense)
    # המערכת הופכת לפסימית רק אם עברנו את שעת השיא והטמפרטורה הנוכחית נמוכה משמעותית
    if current_time_float > (peak_hour + 0.5):
        gap = target_val - max_so_far
        if gap > 0.2:
            time_penalty = max(0.1, 1 - (gap * (current_time_float - peak_hour) * 0.5))
            prob *= time_penalty

    # אם השיא כבר הושג
    if max_so_far >= target_val and is_above:
        prob = 100.0
        
    return round(max(0.0, min(100.0, prob)), 1)

def run_bot():
    tz_il, tz_uk = pytz.timezone('Asia/Jerusalem'), pytz.timezone('Europe/London')
    now_dt = datetime.now(tz_uk)
    now_il, now_uk = datetime.now(tz_il).strftime('%H:%M'), now_dt.strftime('%H:%M')
    
    models, lhr_now, max_so_far, peak_hour, avg_max = get_detailed_weather()
    
    # משיכת נתוני פולימרקט
    date_slug = now_dt.strftime("%B-%d-%Y").lower()
    event_slug = f"highest-temperature-in-london-on-{date_slug}"
    api_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
    
    processed = []
    try:
        resp = requests.get(api_url, timeout=15).json()
        markets = resp[0]['markets'] if resp else []
        for m in markets:
            title = m.get('groupItemTitle', m.get('question', ''))
            price_raw = json.loads(m.get('outcomePrices', '["0"]'))[0]
            price = float(price_raw)
            if price <= 0 and "or higher" not in title.lower(): continue
            
            our_prob = calculate_smart_prob(avg_max, title, max_so_far, peak_hour)
            edge = round(our_prob - (price * 100), 1)
            processed.append({"label": title, "poly": f"${price:.2f}", "ours": our_prob, "edge": edge})
    except: pass

    valid = [p for p in processed if p['ours'] >= 15.0 and p['edge'] > 2.0]
    best = max(valid, key=lambda x: x['edge']) if valid else None
    recommendation = f"לרכוש: {best['label']}" if best else "להמתין - אין ארביטראז' בטוח"

    # HTML בנייה
    table_rows = "".join([f"<tr><td>{p['label']}</td><td style='font-weight:bold;'>{p['poly']}</td><td>{p['ours']}%</td><td style='color:{BRAND_GREEN if p['edge']>0 else ERROR_RED}; font-weight:bold;'>{p['edge']:+.1f}%</td></tr>" for p in processed])
    model_rows = "".join([f"<tr><td style='color:{BRAND_GREEN}'>{n}</td><td>{m['val']}°</td><td>{int(m['weight']*100)}%</td><td style='font-size:11px; color:#666;'>{m['desc']}</td><td style='font-size:11px; color:{BRAND_GREEN if m.get('updated')=='LIVE' else ERROR_RED};'>{m.get('updated', 'N/A')}</td></tr>" for n, m in models.items()])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>POLYMARKET weather v7.2</title>
        <style>
            body {{ background:#000; color:#fff; font-family:system-ui; padding:15px; margin:0; }}
            .card {{ background:{BG_DARK}; border:1px solid #1a1a1a; border-radius:20px; padding:20px; margin-bottom:15px; }}
            .status-dot {{ width:12px; height:12px; background:{BRAND_GREEN}; border-radius:50%; display:inline-block; margin-left:10px; box-shadow:0 0 8px {BRAND_GREEN}; }}
            .signal-box {{ text-align:center; padding:25px; border:2px solid {BRAND_GREEN if best else '#222'}; border-radius:20px; margin:15px 0; }}
            .recommendation {{ font-size:38px; font-weight:900; color:{BRAND_GREEN if best else '#fff'}; }}
            table {{ width:100%; border-collapse:collapse; text-align:center; }}
            td, th {{ padding:12px 5px; border-bottom:1px solid #111; }}
            .live-stats {{ display:flex; justify-content:space-around; background:#111; padding:15px; border-radius:15px; margin-bottom:15px; text-align:center; }}
            .rationale {{ background:#111; padding:15px; border-radius:15px; border-right:4px solid {BRAND_GREEN}; font-size:14px; margin-bottom:15px; }}
        </style>
    </head>
    <body>
        <div style="text-align:center; padding:20px 0;">
            <h1 style="margin:0; letter-spacing:1px;"><span class="status-dot"></span> POLYMARKET weather</h1>
            <div style="color:#555; font-size:14px;">לונדון (LHR) • {now_dt.strftime("%d/%m/%Y")}</div>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:10px;">⚖️ החלטת מערכת וארביטראז'</div>
            <div class="signal-box">
                <div style="font-size:14px; color:#555; text-transform:uppercase;">Recommended Action</div>
                <div class="recommendation">{recommendation}</div>
            </div>
            <table><tr><th>חוזה</th><th>מחיר פולי</th><th>סיכוי AI</th><th>Edge</th></tr>{table_rows}</table>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:10px;">📝 ניתוח החלטה (Rationale)</div>
            <div class="rationale">
                <b>סטטוס זמן:</b> {f"אחרי שעת השיא ({peak_hour}:00). המערכת מחמירה עם סיכויי התחממות מעבר לשיא הקיים." if now_dt.hour > peak_hour else f"לפני שעת השיא ({peak_hour}:00). יש פוטנציאל לעלייה נוספת."}
                <br><b>ממוצע מודלים:</b> {avg_max}°C. המערכת מחשבת סטיית תקן של 0.55 מעלות.
            </div>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:10px;">📊 נתוני אמת וזיכרון מודלים</div>
            <div class="live-stats">
                <div><small style="color:#555;">שיא נמדד (Max)</small><div style="font-size:24px; font-weight:bold; color:{GOLD_COLOR};">{max_so_far}°</div></div>
                <div><small style="color:#555;">טמפ' עכשיו</small><div style="font-size:24px; font-weight:bold;">{lhr_now}°</div></div>
                <div><small style="color:#555;">ממוצע משוקלל</small><div style="font-size:24px; font-weight:bold; color:{BRAND_GREEN};">{avg_max}°</div></div>
            </div>
            <table style="text-align:right;">
                <thead><tr><th style="text-align:right;">מודל</th><th>תחזית</th><th>משקל</th><th style="text-align:right;">תיאור</th><th>סטטוס</th></tr></thead>
                <tbody>{model_rows}</tbody>
            </table>
        </div>

        <div style="display:flex; justify-content:center; gap:30px; font-size:12px; color:#444; padding:20px;">
            <div>🇬🇧 London: {now_uk}</div>
            <div>🇮🇱 Israel: {now_il}</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__":
    run_bot()
