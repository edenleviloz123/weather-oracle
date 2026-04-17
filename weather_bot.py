import requests
import math
import json
from datetime import datetime
import pytz

# הגדרות מיתוג Idol Studios
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"
BG_DARK = "#0a0a0a"

def get_robust_weather():
    """משיכת נתונים עם סנכרון כפוי בין המציאות למודלים"""
    url = (
        "https://api.open-meteo.com/v1/forecast?latitude=51.47&longitude=-0.45"
        "&hourly=temperature_2m,ecmwf_ifs025_temperature_2m,gfs_seamless_temperature_2m,"
        "icon_seamless_temperature_2m,meteofrance_seamless_temperature_2m"
        "&current=temperature_2m&forecast_days=1&timezone=Europe%2FLondon"
    )
    
    try:
        resp = requests.get(url, timeout=15).json()
        current_temp = resp.get("current", {}).get("temperature_2m", 0)
        hourly = resp.get("hourly", {})
        
        now_london = datetime.now(pytz.timezone('Europe/London'))
        current_hour = now_london.hour
        
        # 1. חישוב שיא נמדד אבסולוטי (הגנה מפני איבוד נתונים)
        past_temps = hourly.get("temperature_2m", [])[:current_hour + 1]
        max_so_far = round(max(past_temps), 1) if (past_temps and max(past_temps) > 0) else current_temp
        # וידוא שהשיא שנמדד לא נמוך מהטמפרטורה הנוכחית
        max_so_far = max(max_so_far, current_temp)
        
        # 2. פונקציית עוגן: אם השיא שנמדד עקף את המודל, המודל מתיישר לשיא
        def get_anchored_model(key, default_offset):
            temps = hourly.get(key, [])
            api_max = max(temps) if temps else (max_so_far + default_offset)
            # לוגיקת העוגן: המודל לא יכול לחזות פחות ממה שכבר קרה
            return round(max(api_max, max_so_far), 1)

        models = {
            "ECMWF": {"val": get_anchored_model("ecmwf_ifs025_temperature_2m", 0.2), "weight": 0.30, "desc": "המודל האירופי - סונכרן לשיא."},
            "UKMO": {"val": get_anchored_model("temperature_2m", -0.1), "weight": 0.25, "desc": "מודל בריטי - רגישות מקומית."},
            "GFS": {"val": get_anchored_model("gfs_seamless_temperature_2m", 0.4), "weight": 0.20, "desc": "מודל אמריקאי - טווח רחב."},
            "ICON": {"val": get_anchored_model("icon_seamless_temperature_2m", -0.2), "weight": 0.15, "desc": "מודל גרמני - רזולוציה גבוהה."},
            "MeteoFrance": {"val": get_anchored_model("meteofrance_seamless_temperature_2m", 0.0), "weight": 0.10, "desc": "מודל צרפתי משלים."}
        }
        
        weighted_avg = sum(m['val'] * m['weight'] for m in models.values())
        peak_hour = hourly.get("temperature_2m", []).index(max(hourly.get("temperature_2m", [0]))) if "temperature_2m" in hourly else 14
        
        return models, round(current_temp, 1), round(max_so_far, 1), peak_hour, round(weighted_avg, 2)
    except Exception as e:
        return {}, 18.0, 18.0, 14, 18.5

def calculate_logical_probs(avg_max, max_so_far, peak_hour, markets):
    """חישוב הסתברות AI עם 'רצפת זכוכית' של השיא שנמדד"""
    tz_uk = pytz.timezone('Europe/London')
    now_uk = datetime.now(tz_uk)
    current_time = now_uk.hour + (now_uk.minute / 60.0)
    
    # הגדרת סטייה (Sigma) - ככל שמתקרבים לערב, הודאות עולה
    if current_time > (peak_hour + 0.5):
        expected_peak = max_so_far
        sigma = 0.2
        status_text = f"המערכת בזמן אמת: השיא שנמדד ({max_so_far}°) הוא העוגן הסופי לחישוב."
    else:
        expected_peak = max(avg_max, max_so_far)
        sigma = 0.6
        status_text = f"לפני שעת השיא: המערכת משלבת בין ממוצע מודלים ({avg_max}°) לשיא הנוכחי."

    processed = []
    total_raw = 0
    
    for m in markets:
        try:
            target = float(''.join(c for c in m['label'] if c.isdigit() or c == '.'))
        except: target = 18.0
        
        # חוק הברזל: אם השיא הנוכחי כבר עקף את החוזה, הסיכוי לחוזה הזה הוא אפס מוחלט
        if target < math.floor(max_so_far):
            raw_p = 0
        else:
            diff = target - expected_peak
            raw_p = math.exp(-(diff**2) / (2 * sigma**2))
            
        processed.append({"label": m['label'], "price": m['price'], "raw_p": raw_p})
        total_raw += raw_p

    if total_raw == 0: total_raw = 1
    for p in processed:
        p['ours'] = round((p['raw_p'] / total_raw) * 100, 1)
        p['edge'] = round(p['ours'] - (p['price'] * 100), 1)
        
    return processed, status_text

def run_bot():
    tz_uk = pytz.timezone('Europe/London')
    now_dt = datetime.now(tz_uk)
    
    models, current_temp, max_so_far, peak_hour, avg_max = get_robust_weather()
    
    # פולימרקט
    date_slug = now_dt.strftime('%B-%d-%Y').lower()
    api_url = f"https://gamma-api.polymarket.com/events?slug=highest-temperature-in-london-on-{date_slug}"
    markets_data = []
    try:
        resp = requests.get(api_url, timeout=10).json()
        for m in resp[0]['markets']:
            title = m.get('groupItemTitle', m.get('question', 'N/A'))
            price = float(json.loads(m.get('outcomePrices', '["0"]'))[0])
            markets_data.append({"label": title, "price": price})
    except:
        markets_data = [{"label": f"{t}°C", "price": 0.1} for t in range(18, 23)]

    processed, status_text = calculate_logical_probs(avg_max, max_so_far, peak_hour, markets_data)
    best = max(processed, key=lambda x: x['edge']) if any(p['ours'] > 5 for p in processed) else None
    recommendation = f"לרכוש: {best['label']}" if (best and best['edge'] > 4) else "אין ארביטראז' בטוח"

    # HTML
    table_rows = "".join([f"<tr><td>{p['label']}</td><td>${p['price']:.2f}</td><td style='color:{BRAND_GREEN}; font-weight:bold;'>{p['ours']}%</td><td style='color:{BRAND_GREEN if p['edge']>0 else ERROR_RED};'>{p['edge']:+.1f}%</td></tr>" for p in processed])
    model_rows = "".join([f"<tr><td style='color:{BRAND_GREEN}'>{n}</td><td style='font-weight:bold;'>{m['val']}°</td><td>{int(m['weight']*100)}%</td><td style='font-size:11px; color:#666;'>{m['desc']}</td><td style='font-size:11px; color:{BRAND_GREEN};'>SYNCED</td></tr>" for n, m in models.items()])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ background:#000; color:#fff; font-family:system-ui; padding:15px; margin:0; }}
            .card {{ background:{BG_DARK}; border:1px solid #1a1a1a; border-radius:24px; padding:24px; margin-bottom:16px; }}
            .signal-box {{ text-align:center; padding:30px; border:2px solid {BRAND_GREEN if best else '#222'}; border-radius:20px; margin:20px 0; background: rgba(181, 235, 191, 0.03); }}
            .recommendation {{ font-size:42px; font-weight:900; color:{BRAND_GREEN if best else '#fff'}; }}
            table {{ width:100%; border-collapse:collapse; text-align:center; }}
            td, th {{ padding:14px 8px; border-bottom:1px solid #111; }}
            .live-stats {{ display:flex; justify-content:space-around; background:#111; padding:20px; border-radius:18px; margin-bottom:20px; text-align:center; }}
            .rationale {{ background:#111; padding:18px; border-radius:18px; border-right:4px solid {BRAND_GREEN}; font-size:14px; color:#ddd; }}
        </style>
    </head>
    <body>
        <div style="text-align:center; padding:30px 0;">
            <h1 style="margin:0;">POLYMARKET <span style="color:{BRAND_GREEN}">weather</span></h1>
            <div style="color:#555;">לונדון (LHR) • {now_dt.strftime("%d/%m/%Y")}</div>
        </div>

        <div class="card">
            <div class="signal-box">
                <div style="font-size:12px; color:#666;">RECOMMENDED ACTION</div>
                <div class="recommendation">{recommendation}</div>
            </div>
            <table>
                <thead><tr><th>חוזה</th><th>מחיר פולי</th><th>סיכוי AI</th><th>Edge</th></tr></thead>
                <tbody>{table_rows}</tbody>
            </table>
        </div>

        <div class="card">
            <div class="rationale"><b>ניתוח סנכרון:</b> {status_text}</div>
        </div>

        <div class="card">
            <div class="live-stats">
                <div><small style="color:#666;">שיא נמדד (Max)</small><div style="font-size:26px; font-weight:bold; color:{GOLD_COLOR};">{max_so_far}°</div></div>
                <div><small style="color:#666;">טמפ' עכשיו</small><div style="font-size:26px; font-weight:bold;">{current_temp}°</div></div>
                <div><small style="color:#666;">ממוצע מסונכרן</small><div style="font-size:26px; font-weight:bold; color:{BRAND_GREEN};">{avg_max}°</div></div>
            </div>
            <table style="text-align:right; font-size:13px;">
                <thead><tr><th>מודל</th><th>תחזית</th><th>משקל</th><th>תיאור</th><th>סטטוס</th></tr></thead>
                <tbody>{model_rows}</tbody>
            </table>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__":
    run_bot()
