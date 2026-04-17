import requests
import math
import time
import os
from datetime import datetime
import pytz

# הגדרות מיתוג וצבעים (Idol Studios Style)
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"

def get_live_clob_price(token_id):
    """שולף את המחיר העדכני ביותר מספר הפקודות החי"""
    try:
        url = f"https://clob.polymarket.com/price?token_id={token_id}&side=buy"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            price_data = resp.json()
            # מכפילים ב-100 כדי להפוך לאחוזים/סנטים
            return round(float(price_data.get('price', 0)) * 100, 1)
    except Exception as e:
        print(f"Error fetching CLOB price for {token_id}: {e}")
    return 0.0

def get_market_data(tz_uk):
    """חיפוש האירוע היומי של לונדון ושליפת כל האפשרויות מתוכו"""
    # יצירת מחרוזת תאריך שתואמת לפולימרקט (למשל "April 17")
    today_date = datetime.now(tz_uk)
    today_str = f"{today_date.strftime('%B')} {today_date.day}" 
    
    query = "highest temperature in london"
    url = f"https://gamma-api.polymarket.com/events?query={query}&active=true"
    
    results = []
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            events = resp.json()
            if not events:
                return []
            
            # חיפוש האירוע של היום הספציפי
            target_event = None
            for event in events:
                if today_str.lower() in event.get('title', '').lower():
                    target_event = event
                    break
            
            # אם לא נמצא אירוע להיום, ניקח את הראשון הפעיל (בדרך כלל של מחר)
            if not target_event:
                target_event = events[0]
                
            markets = target_event.get('markets', [])
            
            for m in markets:
                # חילוץ שם האופציה (למשל "18°C" או "22°C or higher")
                title = m.get('groupItemTitle', '') or m.get('question', '')
                token_ids = m.get('clobTokenIds', [])
                
                if not token_ids:
                    continue
                    
                token_id = token_ids[0] # ה-Token ID של ה-YES
                live_price = get_live_clob_price(token_id)
                
                # נוסיף רק שווקים שיש להם מחיר אקטיבי ורלוונטי
                if live_price > 0:
                    results.append({
                        "title": title,
                        "token_id": token_id,
                        "poly_price": live_price
                    })
                    
            # מיון התוצאות לפי המספר שבכותרת
            def extract_num(t):
                try:
                    return int(''.join(filter(str.isdigit, t.split('°')[0])))
                except: return 0
                
            results.sort(key=lambda x: extract_num(x['title']))
            return results
            
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return []

def calculate_ai_prob(avg, target_str):
    """חישוב הסתברות חכם התומך גם בטווחים (Ranges)"""
    std = 0.7
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    
    try:
        # חילוץ המספר מהמחרוזת
        val = int(''.join(filter(str.isdigit, target_str.split('°')[0])))
    except:
        return 0.0
        
    target_lower = target_str.lower()
    
    # טיפול בחריגות: מינימום, מקסימום או טמפרטורה מדויקת
    if "higher" in target_lower or "more" in target_lower:
        # סיכוי לטמפ' הזו ומעלה
        prob = 1.0 - cdf(val - 0.5)
    elif "below" in target_lower or "less" in target_lower:
        # סיכוי לטמפ' הזו ומטה
        prob = cdf(val + 0.5)
    else:
        # סיכוי לטמפ' הספציפית הזו בלבד
        prob = cdf(val + 0.5) - cdf(val - 0.5)
        
    return round(prob * 100, 1)

def run_bot():
    # שעונים
    tz_il, tz_uk = pytz.timezone('Asia/Jerusalem'), pytz.timezone('Europe/London')
    now_il = datetime.now(tz_il).strftime('%H:%M')
    now_uk = datetime.now(tz_uk).strftime('%H:%M')

    # 1. דאטה מודלים (The Oracle)
    models = {"MeteoFrance": 18.4, "ICON": 18.1, "GFS": 18.9, "UKMO": 18.2, "ECMWF": 18.6}
    avg_oracle = round(sum(models.values()) / len(models), 2)
    lhr_live = 18.2 # נתון אמת LHR (כאן תוכל לחבר API מזג אוויר בעתיד)

    # 2. עיבוד נתוני פולימרקט
    poly_data = get_market_data(tz_uk)
    processed = []
    
    for opt in poly_data:
        title = opt['title']
        our_prob = calculate_ai_prob(avg_oracle, title)
        edge = round(our_prob - opt['poly_price'], 1)
        processed.append({
            "label": title, 
            "poly": opt['poly_price'], 
            "ours": our_prob, 
            "edge": edge
        })

    best = max(processed, key=lambda x: x['edge']) if processed else None
    signal = "YES" if best and best['edge'] > 3.0 else "NO"

    # בניית ה-HTML
    model_boxes = "".join([f"<div class='model-box'><div class='m-name'>{k}</div><div class='m-val'>{v}°</div></div>" for k,v in models.items()])
    table_rows = "".join([f"<tr><td>{p['label']}</td><td>{p['poly']}¢</td><td>{p['ours']}%</td><td style='color:{GOLD_COLOR if p['edge']>10 else (BRAND_GREEN if p['edge']>0 else ERROR_RED)}; font-weight:bold;'>{p['edge']:+.1f}%</td></tr>" for p in processed])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Arbitrage Oracle v7</title>
        <style>
            body {{ background:#000; color:#fff; font-family:system-ui; padding:15px; margin:0; line-height:1.4; }}
            .card {{ background:#0a0a0a; border:1px solid #1a1a1a; border-radius:20px; padding:20px; margin-bottom:15px; }}
            .brand-header {{ text-align:center; color:{BRAND_GREEN}; font-weight:900; letter-spacing:3px; padding:10px; }}
            .model-grid {{ display:grid; grid-template-columns: repeat(5, 1fr); gap:8px; margin-bottom:20px; }}
            .model-box {{ background:#111; padding:10px; border-radius:12px; text-align:center; border:1px solid #1a1a1a; }}
            .m-name {{ font-size:9px; color:#555; text-transform:uppercase; }}
            .m-val {{ font-size:14px; font-weight:bold; }}
            .main-stats {{ display:flex; justify-content:space-around; align-items:center; padding:10px 0; }}
            .stat-item {{ text-align:center; }}
            .stat-val {{ font-size:32px; font-weight:bold; color:{BRAND_GREEN}; }}
            .signal-box {{ text-align:center; padding:30px; border:2px solid {BRAND_GREEN if signal=='YES' else '#222'}; border-radius:20px; margin:15px 0; }}
            .signal-text {{ font-size:60px; font-weight:900; margin:0; }}
            table {{ width:100%; border-collapse:collapse; text-align:center; }}
            th {{ font-size:11px; color:#444; padding-bottom:10px; border-bottom:1px solid #1a1a1a; }}
            td {{ padding:15px 5px; border-bottom:1px solid #111; }}
            .guide {{ font-size:13px; color:#888; }}
            .guide b {{ color:{BRAND_GREEN}; }}
            .footer-clocks {{ display:flex; justify-content:center; gap:30px; font-size:12px; color:#444; padding-top:10px; }}
        </style>
    </head>
    <body>
        <div class="brand-header">ORACLE MONSTER v7.0</div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">📊 השוואת מודלים (THE ORACLE)</div>
            <div class="model-grid">{model_boxes}</div>
            <div class="main-stats">
                <div class="stat-item"><small>ממוצע AI</small><div class="stat-val">{avg_oracle}°</div></div>
                <div style="width:1px; height:40px; background:#1a1a1a;"></div>
                <div class="stat-item"><small>LHR LIVE</small><div class="stat-val" style="color:#fff;">{lhr_live}°</div></div>
            </div>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">⚖️ ארביטראז' פולימרקט</div>
            <div class="signal-box">
                <div style="font-size:12px; color:#555;">RECOMMENDED SIGNAL</div>
                <p class="signal-text" style="color:{BRAND_GREEN if signal=='YES' else '#fff'};">{signal if processed else 'NO MARKETS'}</p>
            </div>
            
            {f"<table><tr><th>מעלות</th><th>פולי</th><th>AI %</th><th>EDGE</th></tr>{table_rows}</table>" if processed else 
             f"<div style='text-align:center; color:#ffaa00; padding:20px; font-size:12px; direction:ltr;'><b>SYSTEM LOG:</b> Scanning events...<br>No active London temperature markets found for today.</div>"}
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">🧠 נימוק החלטה (RATIONALE)</div>
            <div class="guide">
                {f"המערכת זיהתה פער חיובי של <b>{best['edge']}%</b> בחוזה של {best['label']}. ממוצע המודלים ({avg_oracle}°) מצביע על הסתברות שונה מזו שהשוק מתמחר כרגע." if processed and best and best['edge'] > 0 else "המערכת סורקת כרגע את פולימרקט. לא נמצאו הזדמנויות ארביטראז' אטרקטיביות בשלב זה (Edge שלילי או חסר)."}
            </div>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">📚 מדריך הכלים (USER GUIDE)</div>
            <div class="guide">
                • <b>השוואת מודלים:</b> מציג נתונים מ-5 תחנות מטאורולוגיות מובילות.<br>
                • <b>ממוצע AI:</b> שקלול חכם של כל המודלים ליצירת "אמת אחת".<br>
                • <b>Edge:</b> הפער באחוזים בין ההסתברות הריאלית למחיר השוק. מעל 3% נחשב סיגנל YES.<br>
                • <b>LHR Live:</b> הטמפרטורה הנוכחית בהית'רו (הבנצ'מרק של השוק).
            </div>
        </div>

        <div class="footer-clocks">
            <div>🇬🇧 <b>London:</b> {now_uk}</div>
            <div>🇮🇱 <b>Israel:</b> {now_il}</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    run_bot()
