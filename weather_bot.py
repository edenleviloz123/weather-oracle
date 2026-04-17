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

def get_live_weather_models():
    """מושך נתוני מודלים מטאורולוגיים בזמן אמת עבור לונדון הית'רו"""
    # קואורדינטות LHR: 51.47, -0.45
    url = "https://api.open-meteo.com/v1/forecast?latitude=51.47&longitude=-0.45&hourly=temperature_2m&models=ecmwf_ifs025,gfs_seamless,icon_seamless,meteofrance_seamless&forecast_days=1"
    
    models_data = {
        "ECMWF": {"val": 18.6, "weight": 0.30, "desc": "המודל האירופי - נחשב למדויק ביותר בעולם."},
        "UKMO": {"val": 18.2, "weight": 0.25, "desc": "מודל השירות הבריטי - דיוק מקסימלי לאזור לונדון."},
        "GFS": {"val": 18.9, "weight": 0.20, "desc": "המודל האמריקאי - מצוין לזיהוי מגמות."},
        "ICON": {"val": 18.1, "weight": 0.15, "desc": "מודל גרמני ברזולוציה גבוהה."},
        "MeteoFrance": {"val": 18.4, "weight": 0.10, "desc": "מודל צרפתי המתמחה במערכות אירופאיות."}
    }
    
    try:
        resp = requests.get(url, timeout=15).json()
        # שליפת הטמפרטורה המקסימלית החזויה להיום מכל מודל זמין
        if "hourly" in resp:
            # עדכון ערכים מה-API (אם המודל קיים בתוצאות)
            models_map = {
                "ecmwf_ifs025": "ECMWF",
                "gfs_seamless": "GFS",
                "icon_seamless": "ICON",
                "meteofrance_seamless": "MeteoFrance"
            }
            for api_key, model_name in models_map.items():
                if api_key in resp.get("hourly", {}):
                    temps = resp["hourly"][api_key]
                    models_data[model_name]["val"] = round(max(temps), 1)
        
        # LHR LIVE - הטמפרטורה הנוכחית שנמדדה
        current_url = "https://api.open-meteo.com/v1/forecast?latitude=51.47&longitude=-0.45&current=temperature_2m"
        curr_resp = requests.get(current_url, timeout=10).json()
        lhr_live = curr_resp.get("current", {}).get("temperature_2m", 18.2)
        
    except Exception as e:
        print(f"Weather API Error: {e}")
        lhr_live = 18.2 # Fallback
        
    return models_data, lhr_live

def get_market_data_by_date():
    """בונה את הסלאג לפי התאריך הנוכחי בלונדון ושואב נתונים"""
    tz_uk = pytz.timezone('Europe/London')
    now_uk = datetime.now(tz_uk)
    date_slug = now_uk.strftime("%B-%d-%Y").lower()
    event_slug = f"highest-temperature-in-london-on-{date_slug}"
    
    api_url = f"https://gamma-api.polymarket.com/events?slug={event_slug}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    results = []
    try:
        resp = requests.get(api_url, headers=headers, timeout=20)
        if resp.status_code == 200:
            events = resp.json()
            if events:
                markets = events[0].get('markets', [])
                for m in markets:
                    title = m.get('groupItemTitle', '')
                    if not title: continue
                    try:
                        prices = json.loads(m.get('outcomePrices', '["0", "0"]'))
                        # שמירה על מחיר דצימלי (למשל 0.06)
                        price_val = float(prices[0])
                    except: price_val = 0.0
                    
                    if price_val > 0:
                        results.append({"title": title, "poly_price": price_val})
            
            def extract_num(t):
                nums = ''.join(filter(str.isdigit, t.split('°')[0]))
                return int(nums) if nums else 0
            results.sort(key=lambda x: extract_num(x['title']))
            return results
    except: pass
    return []

def calculate_ai_prob(avg, target_str):
    std = 0.7
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    try:
        val = int(''.join(filter(str.isdigit, target_str.split('°')[0])))
    except: return 0.0
    t_lower = target_str.lower()
    if any(x in t_lower for x in ["higher", "above", "more", "or above"]):
        prob = 1.0 - cdf(val - 0.5)
    elif any(x in t_lower for x in ["below", "under", "less", "or below"]):
        prob = cdf(val + 0.5)
    else:
        prob = cdf(val + 0.5) - cdf(val - 0.5)
    return round(prob * 100, 1)

def run_bot():
    tz_il, tz_uk = pytz.timezone('Asia/Jerusalem'), pytz.timezone('Europe/London')
    dt_uk = datetime.now(tz_uk)
    now_il, now_uk = datetime.now(tz_il).strftime('%H:%M'), dt_uk.strftime('%H:%M')
    
    # 1. LIVE DATA FETCHING
    model_details, lhr_live = get_live_weather_models()
    avg_oracle = round(sum(m['val'] * m['weight'] for m in model_details.values()), 2)

    # 2. PROCESSING
    poly_data = get_market_data_by_date()
    processed = []
    for opt in poly_data:
        our_prob = calculate_ai_prob(avg_oracle, opt['title'])
        # המרת מחיר פולי לאחוזים לצורך חישוב ה-Edge
        poly_percentage = opt['poly_price'] * 100
        edge = round(our_prob - poly_percentage, 1)
        processed.append({
            "label": opt['title'], 
            "poly_display": f"${opt['poly_price']:.2f}", # תצוגה כמו בפולימרקט
            "poly_raw": poly_percentage,
            "ours": our_prob, 
            "edge": edge
        })

    safety_threshold = 25.0
    valid_opportunities = [p for p in processed if p['ours'] >= safety_threshold and p['edge'] > 3.0]
    best_contract = max(valid_opportunities, key=lambda x: x['edge']) if valid_opportunities else None
    
    signal_action = "BUY" if best_contract else "WAIT"
    recommendation = f"לרכוש: {best_contract['label']}" if best_contract else "אין הזדמנות מובהקת כרגע"

    # 3. HTML GENERATION
    table_rows = "".join([f"<tr><td>{p['label']}</td><td style='font-weight:bold; color:#fff;'>{p['poly_display']}</td><td>{p['ours']}%</td><td style='color:{GOLD_COLOR if p['edge']>10 else (BRAND_GREEN if p['edge']>0 else ERROR_RED)}; font-weight:bold;'>{p['edge']:+.1f}%</td></tr>" for p in processed])
    model_rows = "".join([f"<tr><td style='color:{BRAND_GREEN}'>{name}</td><td>{m['val']}°</td><td>{int(m['weight']*100)}%</td><td style='font-size:11px; color:#888; text-align:right;'>{m['desc']}</td></tr>" for name, m in model_details.items()])
    
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
            .main-title {{ font-size:28px; font-weight:900; letter-spacing:1px; margin:0; display:flex; align-items:center; justify-content:center; gap:10px; }}
            .status-dot {{ width:12px; height:12px; background:{BRAND_GREEN if processed else 'orange'}; border-radius:50%; box-shadow: 0 0 10px {BRAND_GREEN if processed else 'orange'}; }}
            .subtitle {{ color:#666; font-size:14px; margin-top:5px; }}
            .signal-box {{ text-align:center; padding:25px; border:2px solid {BRAND_GREEN if signal_action=="BUY" else "#222"}; border-radius:20px; margin:15px 0; }}
            .recommendation {{ font-size:38px; font-weight:900; color:{BRAND_GREEN if signal_action=="BUY" else "#fff"}; margin:5px 0; }}
            table {{ width:100%; border-collapse:collapse; text-align:center; margin-top:10px; }}
            th {{ font-size:11px; color:#444; padding-bottom:10px; border-bottom:1px solid #1a1a1a; }}
            td {{ padding:12px 5px; border-bottom:1px solid #111; }}
            .rationale-section {{ background:#111; padding:15px; border-radius:15px; border-right:4px solid {BRAND_GREEN}; }}
            .rationale-title {{ font-weight:bold; color:{BRAND_GREEN}; margin-bottom:8px; }}
            .section-label {{ font-size:11px; color:#555; margin-bottom:10px; display:flex; align-items:center; gap:5px; }}
        </style>
    </head>
    <body>
        <div class="header-area">
            <h1 class="main-title"><span class="status-dot"></span> POLYMARKET weather</h1>
            <div class="subtitle">לונדון (LHR) • אירוע: {dt_uk.strftime("%d/%m/%Y")}</div>
        </div>

        <div class="card">
            <div class="section-label">⚖️ החלטת מערכת וארביטראז'</div>
            <div class="signal-box">
                <div style="font-size:14px; color:#555;">RECOMMENDED ACTION</div>
                <div class="recommendation">{recommendation if processed else "מערכת סורקת..."}</div>
            </div>
            {f"<table><tr><th>חוזה (טמפ')</th><th>מחיר פולי</th><th>סיכוי AI</th><th>Edge</th></tr>{table_rows}</table>" if processed else ""}
        </div>

        <div class="card">
            <div class="section-label">📝 ניתוח החלטה (Decision Rationale)</div>
            <div class="rationale-section">
                <div class="rationale-title">מסקנה מבוססת נתוני זמן אמת:</div>
                <div style="font-size:14px; color:#ccc;">
                    {f"זוהה ארביטראז' בחוזה <b>{best_contract['label']}</b>. המחיר {best_contract['poly_display']} משקף הסתברות שוק נמוכה מדי ביחס לתחזית ה-AI המעודכנת." if best_contract else "מחירי השוק כרגע מאוזנים יחסית לתחזיות המודלים, או שהחוזים המשתלמים נושאים סיכון גבוה מדי (מתחת ל-25%)."}
                </div>
            </div>
        </div>

        <div class="card">
            <div class="section-label">📊 מודלים בשידור חי (Live Models)</div>
            <div style="display:flex; justify-content:space-around; background:#111; padding:15px; border-radius:15px; margin-bottom:15px;">
                <div style="text-align:center;"><small style="color:#555;">ממוצע מודלים</small><div style="font-size:24px; font-weight:bold; color:{BRAND_GREEN};">{avg_oracle}°</div></div>
                <div style="text-align:center;"><small style="color:#555;">LHR LIVE</small><div style="font-size:24px; font-weight:bold;">{lhr_live}°</div></div>
            </div>
            <table style="text-align:right;">
                <thead><tr><th style="text-align:right;">מודל</th><th>תחזית</th><th>משקל</th><th style="text-align:right;">סטטוס</th></tr></thead>
                <tbody>{model_rows}</tbody>
            </table>
        </div>

        <div style="display:flex; justify-content:center; gap:30px; font-size:12px; color:#444; padding:10px;">
            <div>🇬🇧 <b>London:</b> {now_uk}</div>
            <div>🇮🇱 <b>Israel:</b> {now_il}</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__":
    run_bot()
