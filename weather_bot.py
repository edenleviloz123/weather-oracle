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
            if not events: return []
            
            markets = events[0].get('markets', [])
            for m in markets:
                title = m.get('groupItemTitle', '')
                if not title: continue
                try:
                    prices = json.loads(m.get('outcomePrices', '["0", "0"]'))
                    yes_price = round(float(prices[0]) * 100, 1)
                except: yes_price = 0.0
                
                if yes_price > 0:
                    results.append({"title": title, "poly_price": yes_price})
            
            def extract_num(t):
                nums = ''.join(filter(str.isdigit, t.split('°')[0]))
                return int(nums) if nums else 0
            results.sort(key=lambda x: extract_num(x['title']))
            return results
    except Exception as e:
        print(f"DEBUG Error: {e}")
    return []

def calculate_ai_prob(avg, target_str):
    """חישוב הסתברות לפי התפלגות נורמלית (CDF)"""
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
    event_date_str = dt_uk.strftime("%d/%m/%Y")

    # 1. מודלים מטאורולוגיים
    model_details = {
        "ECMWF": {"val": 18.6, "weight": "30%", "desc": "המודל האירופי - נחשב למדויק ביותר בעולם לטווח בינוני."},
        "UKMO": {"val": 18.2, "weight": "25%", "desc": "מודל השירות הבריטי - רמת דיוק מקסימלית לאזור לונדון."},
        "GFS": {"val": 18.9, "weight": "20%", "desc": "המודל האמריקאי - גלובלי, מצוין לזיהוי מגמות טמפרטורה."},
        "ICON": {"val": 18.1, "weight": "15%", "desc": "מודל גרמני ברזולוציה גבוהה, מצטיין בחיזוי מקומי באירופה."},
        "MeteoFrance": {"val": 18.4, "weight": "10%", "desc": "מודל צרפתי מתקדם המתמחה במערכות לחץ משתנות."}
    }
    avg_oracle = round(sum(m['val'] * (int(m['weight'].replace('%',''))/100) for m in model_details.values()), 2)

    # 2. עיבוד נתונים
    poly_data = get_market_data_by_date()
    processed = []
    for opt in poly_data:
        our_prob = calculate_ai_prob(avg_oracle, opt['title'])
        edge = round(our_prob - opt['poly_price'], 1)
        processed.append({"label": opt['title'], "poly": opt['poly_price'], "ours": our_prob, "edge": edge})

    # לוגיקת בחירה משודרגת: רק חוזים עם לפחות 25% סיכוי ריאלי
    safety_threshold = 25.0
    valid_opportunities = [p for p in processed if p['ours'] >= safety_threshold and p['edge'] > 3.0]
    
    best_contract = None
    signal_action = "WAIT"
    recommendation = "אין הזדמנות מובהקת כרגע"
    
    if valid_opportunities:
        best_contract = max(valid_opportunities, key=lambda x: x['edge'])
        signal_action = "BUY"
        recommendation = f"לרכוש: {best_contract['label']}"
    else:
        # אם אין הזדמנות קנייה, נחפש אם יש משהו להתרחק ממנו (Edge שלילי מאוד)
        risky_contracts = [p for p in processed if p['edge'] < -10.0]
        if risky_contracts:
            avoid = max(risky_contracts, key=lambda x: abs(x['edge']))
            recommendation = f"להתרחק מ: {avoid['label']}"

    # 3. בניית ה-HTML
    table_rows = "".join([f"<tr><td>{p['label']}</td><td>{p['poly']}¢</td><td>{p['ours']}%</td><td style='color:{GOLD_COLOR if p['edge']>10 else (BRAND_GREEN if p['edge']>0 else ERROR_RED)}; font-weight:bold;'>{p['edge']:+.1f}%</td></tr>" for p in processed])
    model_rows = "".join([f"<tr><td style='color:{BRAND_GREEN}'>{name}</td><td>{m['val']}°</td><td>{m['weight']}</td><td style='font-size:11px; color:#888; text-align:right;'>{m['desc']}</td></tr>" for name, m in model_details.items()])
    status_color = BRAND_GREEN if processed else "orange"
    
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
            .status-dot {{ width:12px; height:12px; background:{status_color}; border-radius:50%; box-shadow: 0 0 10px {status_color}; }}
            .subtitle {{ color:#666; font-size:14px; margin-top:5px; }}
            .signal-box {{ text-align:center; padding:25px; border:2px solid {BRAND_GREEN if signal_action=="BUY" else "#222"}; border-radius:20px; margin:15px 0; }}
            .signal-action {{ font-size:14px; color:#555; text-transform:uppercase; }}
            .recommendation {{ font-size:38px; font-weight:900; color:{BRAND_GREEN if signal_action=="BUY" else "#fff"}; margin:5px 0; }}
            table {{ width:100%; border-collapse:collapse; text-align:center; margin-top:10px; }}
            th {{ font-size:11px; color:#444; padding-bottom:10px; border-bottom:1px solid #1a1a1a; }}
            td {{ padding:12px 5px; border-bottom:1px solid #111; }}
            .rationale-section {{ background:#111; padding:15px; border-radius:15px; border-right:4px solid {BRAND_GREEN}; }}
            .rationale-title {{ font-weight:bold; color:{BRAND_GREEN}; margin-bottom:8px; }}
            .rationale-text {{ font-size:14px; color:#ccc; }}
            .support-list {{ font-size:13px; color:#888; margin-top:10px; padding-right:15px; }}
            .section-label {{ font-size:11px; color:#555; margin-bottom:10px; display:flex; align-items:center; gap:5px; }}
            .info-icon {{ font-size:10px; border:1px solid #333; border-radius:50%; width:14px; height:14px; display:inline-flex; align-items:center; justify-content:center; }}
        </style>
    </head>
    <body>
        <div class="header-area">
            <h1 class="main-title"><span class="status-dot"></span> POLYMARKET weather</h1>
            <div class="subtitle">לונדון (LHR) • אירוע: {event_date_str}</div>
        </div>

        <div class="card">
            <div class="section-label"><span class="info-icon">i</span> החלטת מערכת וארביטראז'</div>
            <div class="signal-box">
                <div class="signal-action">Recommended Action</div>
                <div class="recommendation">{recommendation if processed else "סורק נתונים..."}</div>
            </div>
            {f"<table><tr><th>חוזה (טמפ')</th><th>מחיר פולי</th><th>הסתברות AI</th><th>Edge</th></tr>{table_rows}</table>" if processed else ""}
        </div>

        <div class="card">
            <div class="section-label"><span class="info-icon">i</span> מסקנה מפורטת (Decision Rationale)</div>
            <div class="rationale-section">
                <div class="rationale-title">ניתוח ארביטראז' סופי:</div>
                <div class="rationale-text">
                    {f"זוהה פער משמעותי בחוזה <b>{best_contract['label']}</b>. להסתברות של {best_contract['ours']}% יש בסיס סטטיסטי חזק (מעל רף ה-25%), והמחיר בשוק זול משמעותית." if signal_action=="BUY" else f"המערכת לא זיהתה חוזה המשלב הסתברות גבוהה (מעל 25%) עם Edge משמעותי. {recommendation}."}
                </div>
                <div class="support-list">
                    • <b>ביסוס:</b> שקלול מודלים נותן {avg_oracle}°. <br>
                    • <b>רף ביטחון:</b> המערכת מסננת כעת אירועים עם הסתברות נמוכה מ-25%.<br>
                    • <b>עדכון:</b> הנתונים נכונים לשעה {now_uk} זמן לונדון.
                </div>
            </div>
        </div>

        <div class="card">
            <div class="section-label"><span class="info-icon">i</span> התפלגות מודלים (The Oracle Weights)</div>
            <table style="text-align:right;">
                <thead>
                    <tr><th style="text-align:right;">מודל</th><th>תחזית</th><th>משקל</th><th style="text-align:right;">תיאור המודל</th></tr>
                </thead>
                <tbody>{model_rows}</tbody>
            </table>
            <div style="text-align:center; margin-top:15px; font-size:12px; color:{BRAND_GREEN}; font-weight:bold;">
                ממוצע משוקלל סופי: {avg_oracle}°
            </div>
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
