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
    """מושך נתוני אמת + מודלים + שעת שיא עבור הית'רו"""
    url = "https://api.open-meteo.com/v1/forecast?latitude=51.47&longitude=-0.45&hourly=temperature_2m&models=ecmwf_ifs025,gfs_seamless,icon_seamless,meteofrance_seamless&forecast_days=1&current=temperature_2m"
    
    models_data = {
        "ECMWF": {"val": 18.0, "weight": 0.30, "desc": "המודל האירופי - נחשב למדויק ביותר בעולם.", "updated": "N/A"},
        "UKMO": {"val": 18.0, "weight": 0.25, "desc": "מודל השירות הבריטי - דיוק מקסימלי לאזור.", "updated": "N/A"},
        "GFS": {"val": 18.0, "weight": 0.20, "desc": "המודל האמריקאי - מצוין לזיהוי מגמות.", "updated": "N/A"},
        "ICON": {"val": 18.0, "weight": 0.15, "desc": "מודל גרמני ברזולוציה גבוהה.", "updated": "N/A"},
        "MeteoFrance": {"val": 18.0, "weight": 0.10, "desc": "מודל צרפתי המתמחה במערכות אירופאיות.", "updated": "N/A"}
    }
    
    try:
        resp = requests.get(url, timeout=15).json()
        hourly = resp.get("hourly", {})
        current_hour_idx = datetime.now(pytz.timezone('Europe/London')).hour
        
        # 1. זיכרון של נתוני אמת: מה היה השיא עד עכשיו?
        past_temps = hourly.get("temperature_2m", [])[:current_hour_idx + 1]
        max_so_far = max(past_temps) if past_temps else 0.0
        
        # 2. מציאת שעת השיא הצפויה (לפי ממוצע מודלים)
        model_keys = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "meteofrance_seamless"]
        hourly_averages = []
        for i in range(len(hourly.get("time", []))):
            h_temps = [hourly[m][i] for m in model_keys if m in hourly]
            hourly_averages.append(sum(h_temps)/len(h_temps) if h_temps else 0)
        
        peak_val = max(hourly_averages)
        peak_hour = hourly_averages.index(peak_val)
        
        # 3. עדכון ערכי מודלים (T-Max לכל היום)
        models_map = {"ecmwf_ifs025": "ECMWF", "gfs_seamless": "GFS", "icon_seamless": "ICON", "meteofrance_seamless": "MeteoFrance"}
        for api_key, model_name in models_map.items():
            if api_key in hourly:
                models_data[model_name]["val"] = round(max(hourly[api_key]), 1)
                models_data[model_name]["updated"] = "LIVE"
        
        lhr_now = resp.get("current", {}).get("temperature_2m", 0.0)
        return models_data, lhr_now, max_so_far, peak_hour, round(peak_val, 2)
    except:
        return models_data, 0.0, 0.0, 14, 18.0

def calculate_smart_prob(avg_max, target_str, max_so_far, peak_hour):
    """חישוב הסתברות עם שקיעת זמן (Time Decay) ורף חצי שעה משעת השיא"""
    tz_uk = pytz.timezone('Europe/London')
    now_uk = datetime.now(tz_uk)
    current_time_float = now_uk.hour + (now_uk.minute / 60.0)
    
    try:
        target_val = int(''.join(filter(str.isdigit, target_str.split('°')[0])))
    except: return 0.0

    # חישוב CDF בסיסי
    std = 0.6
    def cdf(x): return (1.0 + math.erf((x - avg_max) / (std * math.sqrt(2.0)))) / 2.0
    
    prob = 0.0
    if "above" in target_str.lower() or "higher" in target_str.lower():
        prob = (1.0 - cdf(target_val - 0.5)) * 100
    else:
        prob = (cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100

    # לוגיקת שעת השיא: אם עברנו את השיא ב-30 דק' והטמפ' נמוכה מהיעד
    if current_time_float > (peak_hour + 0.5):
        if target_val > max_so_far:
            gap = target_val - max_so_far
            penalty = max(0.05, 1 - (gap * (current_time_float - peak_hour) * 0.6))
            prob *= penalty

    if max_so_far >= target_val and "above" in target_str.lower():
        prob = 100.0
    return round(prob, 1)

def run_bot():
    tz_il, tz_uk = pytz.timezone('Asia/Jerusalem'), pytz.timezone('Europe/London')
    now_dt = datetime.now(tz_uk)
    now_il, now_uk = datetime.now(tz_il).strftime('%H:%M'), now_dt.strftime('%H:%M')
    
    models, lhr_now, max_so_far, peak_hour, avg_max = get_detailed_weather()
    
    # פולימרקט
    date_slug = now_dt.strftime("%B-%d-%Y").lower()
    event_slug = f"highest-temperature-in-london-on-{date_slug}"
    api_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
    
    processed = []
    try:
        resp = requests.get(api_url, timeout=15).json()
        markets = resp[0]['markets'] if resp else []
        for m in markets:
            title = m.get('groupItemTitle', '')
            price = float(json.loads(m.get('outcomePrices', '["0"]'))[0])
            if price <= 0: continue
            
            our_prob = calculate_smart_prob(avg_max, title, max_so_far, peak_hour)
            edge = round(our_prob - (price * 100), 1)
            processed.append({"label": title, "poly": f"${price:.2f}", "ours": our_prob, "edge": edge})
    except: pass

    valid = [p for p in processed if p['ours'] >= 25.0 and p['edge'] > 3.0]
    best = max(valid, key=lambda x: x['edge']) if valid else None
    recommendation = f"לרכוש: {best['label']}" if best else "להמתין - אין ארביטראז' בטוח"

    # HTML בנייה מלאה
    table_rows = "".join([f"<tr><td>{p['label']}</td><td style='font-weight:bold;'>{p['poly']}</td><td>{p['ours']}%</td><td style='color:{BRAND_GREEN if p['edge']>0 else ERROR_RED}; font-weight:bold;'>{p['edge']:+.1f}%</td></tr>" for p in processed])
    model_rows = "".join([f"<tr><td style='color:{BRAND_GREEN}'>{n}</td><td>{m['val']}°</td><td>{int(m['weight']*100)}%</td><td style='font-size:11px; color:#888;'>{m['desc']}</td><td style='font-size:11px; color:{BRAND_GREEN};'>{m['updated']}</td></tr>" for n, m in models.items()])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>POLYMARKET weather</title>
        <style>
            body {{ background:#000; color:#fff; font-family:system-ui; padding:15px; margin:0; line-height:1.4; }}
            .card {{ background:{BG_DARK}; border:1px solid #1a1a1a; border-radius:20px; padding:20px; margin-bottom:15px; }}
            .header-area {{ text-align:center; padding:20px 0; }}
            .status-dot {{ width:12px; height:12px; background:{BRAND_GREEN}; border-radius:50%; box-shadow: 0 0 10px {BRAND_GREEN}; display:inline-block; margin-left:10px; }}
            .signal-box {{ text-align:center; padding:25px; border:2px solid {BRAND_GREEN if best else '#222'}; border-radius:20px; margin:15px 0; }}
            .recommendation {{ font-size:38px; font-weight:900; color:{BRAND_GREEN if best else '#fff'}; margin:5px 0; }}
            table {{ width:100%; border-collapse:collapse; text-align:center; margin-top:10px; }}
            th {{ font-size:11px; color:#444; padding-bottom:10px; border-bottom:1px solid #1a1a1a; }}
            td {{ padding:12px 5px; border-bottom:1px solid #111; }}
            .rationale {{ background:#111; padding:15px; border-radius:15px; border-right:4px solid {BRAND_GREEN}; font-size:14px; color:#ccc; }}
            .live-stats {{ display:flex; justify-content:space-around; background:#111; padding:15px; border-radius:15px; margin-bottom:15px; text-align:center; }}
        </style>
    </head>
    <body>
        <div class="header-area">
            <h1 style="margin:0;"><span class="status-dot"></span> POLYMARKET weather</h1>
            <div style="color:#666; font-size:14px; margin-top:5px;">לונדון (LHR) • {now_dt.strftime("%d/%m/%Y")}</div>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:10px;">⚖️ החלטת מערכת וארביטראז'</div>
            <div class="signal-box">
                <div style="font-size:14px; color:#555;">RECOMMENDED ACTION</div>
                <div class="recommendation">{recommendation}</div>
            </div>
            <table><tr><th>חוזה</th><th>מחיר פולי</th><th>סיכוי AI</th><th>Edge</th></tr>{table_rows}</table>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:10px;">📝 ניתוח החלטה (Rationale)</div>
            <div class="rationale">
                {f"זוהה ארביטראז' בחוזה <b>{best['label']}</b>. המערכת מחשבת סיכוי של {best['ours']}%." if best else "המערכת לא זיהתה הזדמנות קנייה מעל רף ה-25% וה-Edge הנדרש."}
                <br><br>
                <b>סטטוס זמן:</b> {f"עברנו את שעת השיא ({peak_hour}:00). המערכת מחמירה עם סיכויי התחממות." if now_dt.hour > peak_hour else f"לפני שעת השיא ({peak_hour}:00). פוטנציאל התחממות קיים."}
            </div>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:10px;">📊 נתוני אמת וזיכרון מודלים</div>
            <div class="live-stats">
                <div><small style="color:#555;">שיא נמדד (Max)</small><div style="font-size:22px; font-weight:bold; color:{GOLD_COLOR};">{max_so_far}°</div></div>
                <div><small style="color:#555;">טמפ' עכשיו</small><div style="font-size:22px; font-weight:bold;">{lhr_now}°</div></div>
                <div><small style="color:#555;">תחזית ממוצעת</small><div style="font-size:22px; font-weight:bold; color:{BRAND_GREEN};">{avg_max}°</div></div>
            </div>
            <table style="text-align:right;">
                <thead><tr><th style="text-align:right;">מודל</th><th>שיא</th><th>משקל</th><th style="text-align:right;">תיאור</th><th>סטטוס</th></tr></thead>
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
