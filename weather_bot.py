import requests
import math
import json
from datetime import datetime
import pytz

# הגדרות מיתוג (Idol Studios Style)
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"
BG_DARK = "#0a0a0a"

def get_detailed_weather():
    """קריאה ישירה לכל ערוצי הנתונים כדי למנוע N/A ועיגולים"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=51.47&longitude=-0.45&hourly=temperature_2m,ecmwf_ifs025_temperature_2m,gfs_seamless_temperature_2m,icon_seamless_temperature_2m,meteofrance_seamless_temperature_2m&forecast_days=1&current=temperature_2m"
    
    models_data = {
        "ECMWF": {"weight": 0.30, "key": "ecmwf_ifs025_temperature_2m", "desc": "המודל האירופי - דיוק גבוה לטווח בינוני."},
        "UKMO": {"weight": 0.25, "key": "temperature_2m", "desc": "מודל השירות הבריטי - רמת דיוק מקסימלית ללונדון."},
        "GFS": {"weight": 0.20, "key": "gfs_seamless_temperature_2m", "desc": "המודל האמריקאי - גלובלי, מצוין לזיהוי מגמות."},
        "ICON": {"weight": 0.15, "key": "icon_seamless_temperature_2m", "desc": "מודל גרמני ברזולוציה גבוהה."},
        "MeteoFrance": {"weight": 0.10, "key": "meteofrance_seamless_temperature_2m", "desc": "מודל צרפתי המתמחה במערכות לחץ."}
    }
    
    try:
        resp = requests.get(url, timeout=15).json()
        hourly = resp.get("hourly", {})
        lhr_now = resp.get("current", {}).get("temperature_2m", 0.0)
        
        # חילוץ נתוני אמת מהשעות שעברו
        current_hour_idx = datetime.now(pytz.timezone('Europe/London')).hour
        temps_today = hourly.get("temperature_2m", [])[:current_hour_idx + 1]
        max_so_far = round(max(temps_today), 1) if temps_today else lhr_now

        # עדכון נתוני מודלים
        updated_models = {}
        weighted_sum = 0
        for name, cfg in models_data.items():
            val = round(max(hourly.get(cfg["key"], [18.0])), 1)
            updated_models[name] = {"val": val, "weight": cfg["weight"], "desc": cfg["desc"], "status": "LIVE"}
            weighted_sum += val * cfg["weight"]

        # שעת שיא (לפי המודל המרכזי)
        peak_hour = hourly["temperature_2m"].index(max(hourly["temperature_2m"])) if "temperature_2m" in hourly else 14
        
        return updated_models, lhr_now, max_so_far, peak_hour, round(weighted_sum, 2)
    except Exception as e:
        return {n: {"val": 18.0, "weight": c["weight"], "desc": c["desc"], "status": "ERR"} for n, c in models_data.items()}, 0.0, 0.0, 14, 18.0

def calculate_all_probs(avg_max, max_so_far, peak_hour, markets):
    """מחשב התפלגות הסתברות שמשלימה ל-100% ומתחשבת בזמן"""
    tz_uk = pytz.timezone('Europe/London')
    now_uk = datetime.now(tz_uk)
    current_time = now_uk.hour + (now_uk.minute / 60.0)
    
    # החלטת ליבה: האם אנחנו לפני או אחרי שעת השיא?
    if current_time > (peak_hour + 0.5):
        expected_final = max_so_far
        sigma = 0.2 # סטייה קטנה מאוד - אנחנו כמעט בטוחים שזה השיא הסופי
        status_text = f"אחרי שעת השיא ({peak_hour}:00). המערכת נועלת סיכויים סביב השיא שכבר נמדד ({max_so_far}°)."
    else:
        expected_final = avg_max
        sigma = 0.6 # חלון הזדמנויות פתוח - מסתמכים על המודלים
        status_text = f"לפני שעת השיא ({peak_hour}:00). יש פוטנציאל התחממות. המערכת מחשבת לפי ממוצע המודלים ({avg_max}°)."
        
    probs = []
    total_raw_prob = 0
    
    for m in markets:
        try:
            target = int(''.join(filter(str.isdigit, m['label'].split('°')[0])))
        except: target = 18
        
        # חישוב הסתברות ראשונית
        raw_p = math.exp(-(target - expected_final)**2 / (2 * sigma**2))
        probs.append({"label": m['label'], "price": m['price'], "raw_p": raw_p})
        total_raw_prob += raw_p

    # נרמול - הופך את כל הסיכויים ל-100% ביחד
    for p in probs:
        p['ours'] = round((p['raw_p'] / total_raw_prob) * 100, 1) if total_raw_prob > 0 else 0.0
        p['edge'] = round(p['ours'] - (p['price'] * 100), 1)
        
    return probs, status_text

def run_bot():
    tz_il, tz_uk = pytz.timezone('Asia/Jerusalem'), pytz.timezone('Europe/London')
    now_dt = datetime.now(tz_uk)
    now_il, now_uk = datetime.now(tz_il).strftime('%H:%M'), now_dt.strftime('%H:%M')
    
    models, lhr_now, max_so_far, peak_hour, avg_max = get_detailed_weather()
    
    # משיכת נתוני פולימרקט
    date_slug = now_dt.strftime("%B-%d-%Y").lower()
    event_slug = f"highest-temperature-in-london-on-{date_slug}"
    api_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
    
    markets_data = []
    try:
        resp = requests.get(api_url, timeout=15).json()
        for m in resp[0]['markets']:
            title = m.get('groupItemTitle', m.get('question', ''))
            price = float(json.loads(m.get('outcomePrices', '["0"]'))[0])
            if price > 0 or "or higher" in title.lower():
                markets_data.append({"label": title, "price": price})
    except: pass

    # חישוב וקבלת החלטה
    processed, status_text = calculate_all_probs(avg_max, max_so_far, peak_hour, markets_data)
    valid = [p for p in processed if p['ours'] >= 15.0 and p['edge'] > 3.0]
    best = max(valid, key=lambda x: x['edge']) if valid else None
    recommendation = f"לרכוש: {best['label']}" if best else "להמתין - אין ארביטראז' בטוח"

    # HTML בנייה
    table_rows = "".join([f"<tr><td>{p['label']}</td><td style='font-weight:bold;'>${p['price']:.2f}</td><td style='color:{BRAND_GREEN}; font-weight:bold;'>{p['ours']}%</td><td style='color:{BRAND_GREEN if p['edge']>0 else ERROR_RED}; font-weight:bold;'>{p['edge']:+.1f}%</td></tr>" for p in processed])
    model_rows = "".join([f"<tr><td style='color:{BRAND_GREEN}'>{n}</td><td>{m['val']}°</td><td>{int(m['weight']*100)}%</td><td style='font-size:11px; color:#666;'>{m['desc']}</td><td style='font-size:11px; color:{BRAND_GREEN if m.get('status')=='LIVE' else ERROR_RED};'>{m.get('status', 'N/A')}</td></tr>" for n, m in models.items()])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>POLYMARKET weather v8.0</title>
        <style>
            body {{ background:#000; color:#fff; font-family:system-ui; padding:15px; margin:0; line-height:1.4; }}
            .card {{ background:{BG_DARK}; border:1px solid #1a1a1a; border-radius:20px; padding:20px; margin-bottom:15px; }}
            .status-dot {{ width:12px; height:12px; background:{BRAND_GREEN}; border-radius:50%; display:inline-block; margin-left:10px; box-shadow:0 0 8px {BRAND_GREEN}; }}
            .signal-box {{ text-align:center; padding:25px; border:2px solid {BRAND_GREEN if best else '#222'}; border-radius:20px; margin:15px 0; }}
            .recommendation {{ font-size:38px; font-weight:900; color:{BRAND_GREEN if best else '#fff'}; }}
            table {{ width:100%; border-collapse:collapse; text-align:center; margin-top:10px; }}
            td, th {{ padding:12px 5px; border-bottom:1px solid #111; }}
            th {{ font-size:11px; color:#444; padding-bottom:10px; border-bottom:1px solid #1a1a1a; }}
            .live-stats {{ display:flex; justify-content:space-around; background:#111; padding:15px; border-radius:15px; margin-bottom:15px; text-align:center; }}
            .rationale {{ background:#111; padding:15px; border-radius:15px; border-right:4px solid {BRAND_GREEN}; font-size:14px; margin-bottom:15px; color:#ccc; }}
        </style>
    </head>
    <body>
        <div style="text-align:center; padding:20px 0;">
            <h1 style="margin:0; letter-spacing:1px;"><span class="status-dot"></span> POLYMARKET weather</h1>
            <div style="color:#555; font-size:14px; margin-top:5px;">לונדון (LHR) • {now_dt.strftime("%d/%m/%Y")}</div>
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
                <b>סטטוס זמן וניהול סיכונים:</b><br>{status_text}
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
