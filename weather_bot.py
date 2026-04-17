import requests
import math
import time
import os
import json
from datetime import datetime
import pytz

# הגדרות מיתוג וצבעים (Idol Studios Style)
BRAND_GREEN = "#B5EBBF"
ERROR_RED = "#FF4444"
GOLD_COLOR = "#FFD700"

def get_live_clob_price(token_id):
    """שולף את המחיר העדכני ביותר מספר הפקודות החי (CLOB)"""
    try:
        # ניקוי ה-ID מתווים מיותרים
        clean_id = str(token_id).strip('[]" ')
        url = f"https://clob.polymarket.com/price?token_id={clean_id}&side=buy"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            price_data = resp.json()
            p = float(price_data.get('price', 0))
            return round(p * 100, 1)
    except Exception as e:
        print(f"DEBUG: Error fetching CLOB price for {token_id}: {e}")
    return 0.0

def get_market_data():
    """סורק שווקים רחב - מוצא כל חוזה טמפרטורה בלונדון/הית'רו"""
    ts = int(time.time())
    # שליפת 500 השווקים הפעילים ביותר
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=500&_={ts}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    results = []
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            markets = resp.json()
            print(f"DEBUG: Scanned {len(markets)} markets.")
            
            for m in markets:
                q = m.get('question', "").lower()
                desc = m.get('description', "").lower()
                slug = m.get('slug', "").lower()
                
                # לוגיקת זיהוי: האם השוק קשור לטמפרטורה בלונדון?
                is_london = any(x in q or x in desc or x in slug for x in ["london", "heathrow"])
                is_temp = any(x in q or x in desc or x in slug for x in ["temp", "weather", "degree", "celsius"])
                
                if is_london and is_temp:
                    # חילוץ כותרת האופציה (למשל 18°C)
                    title = m.get('groupItemTitle', '') or m.get('question', 'Unknown Temp')
                    
                    token_ids = m.get('clobTokenIds', [])
                    if not token_ids:
                        continue
                    
                    token_id = token_ids[0]
                    live_price = get_live_clob_price(token_id)
                    
                    # אנחנו מציגים רק שווקים עם מחיר פעיל (מעל 0)
                    if live_price > 0:
                        results.append({
                            "title": title,
                            "token_id": token_id,
                            "poly_price": live_price
                        })
            
            # מיון התוצאות לפי המעלות (חילוץ מספרים מהטקסט)
            def extract_num(t):
                nums = ''.join(filter(str.isdigit, t.split('°')[0]))
                return int(nums) if nums else 0
                
            results.sort(key=lambda x: extract_num(x['title']))
            print(f"DEBUG: Found {len(results)} relevant London temperature markets.")
            return results
    except Exception as e:
        print(f"DEBUG: Critical error in get_market_data: {e}")
    return []

def calculate_ai_prob(avg, target_str):
    """המרת טמפרטורה להסתברות (CDF) כולל תמיכה בטווחים"""
    std = 0.7 # סטיית תקן קבועה לפי אפיון
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    
    try:
        # חילוץ הערך המספרי מהכותרת
        val = int(''.join(filter(str.isdigit, target_str.split('°')[0])))
    except:
        return 0.0
        
    t_lower = target_str.lower()
    if "higher" in t_lower or "more" in t_lower or "above" in t_lower:
        prob = 1.0 - cdf(val - 0.5)
    elif "below" in t_lower or "less" in t_lower or "under" in t_lower:
        prob = cdf(val + 0.5)
    else:
        # טמפרטורה ספציפית (למשל בדיוק 18)
        prob = cdf(val + 0.5) - cdf(val - 0.5)
        
    return round(prob * 100, 1)

def run_bot():
    # הגדרת אזורי זמן
    tz_il = pytz.timezone('Asia/Jerusalem')
    tz_uk = pytz.timezone('Europe/London')
    now_il = datetime.now(tz_il).strftime('%H:%M')
    now_uk = datetime.now(tz_uk).strftime('%H:%M')

    # 1. מנוע ה-Oracle (נתוני מודלים לפי אפיון)
    # הערה: כאן ניתן בעתיד לחבר API מזג אוויר חי למשיכת הנתונים הללו
    models = {
        "MeteoFrance": 18.4, 
        "ICON": 18.1, 
        "GFS": 18.9, 
        "UKMO": 18.2, 
        "ECMWF": 18.6
    }
    avg_oracle = round(sum(models.values()) / len(models), 2)
    lhr_live = 18.2 # טמפרטורה נוכחית בהית'רו

    # 2. סריקת פולימרקט ועיבוד נתונים
    poly_data = get_market_data()
    processed = []
    
    for opt in poly_data:
        our_prob = calculate_ai_prob(avg_oracle, opt['title'])
        edge = round(our_prob - opt['poly_price'], 1)
        processed.append({
            "label": opt['title'],
            "poly": opt['poly_price'],
            "ours": our_prob,
            "edge": edge
        })

    # זיהוי הסיגנל הטוב ביותר
    best = max(processed, key=lambda x: x['edge']) if processed else None
    signal = "YES" if best and best['edge'] > 3.0 else "NO"

    # 3. בניית ה-HTML (עיצוב Idol Studios)
    model_boxes = "".join([f"<div class='model-box'><div class='m-name'>{k}</div><div class='m-val'>{v}°</div></div>" for k,v in models.items()])
    
    table_rows = ""
    for p in processed:
        edge_color = GOLD_COLOR if p['edge'] > 10 else (BRAND_GREEN if p['edge'] > 0 else ERROR_RED)
        table_rows += f"""
        <tr>
            <td>{p['label']}</td>
            <td>{p['poly']}¢</td>
            <td>{p['ours']}%</td>
            <td style='color:{edge_color}; font-weight:bold;'>{p['edge']:+.1f}%</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Arbitrage Oracle v7.0</title>
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
                <p class="signal-text" style="color:{BRAND_GREEN if signal=='YES' else '#fff'};">{signal if processed else 'SCANNING'}</p>
            </div>
            
            {f"<table><tr><th>מעלות</th><th>פולי</th><th>AI %</th><th>EDGE</th></tr>{table_rows}</table>" if processed else 
             f"<div style='text-align:center; color:#ffaa00; padding:20px; font-size:12px; direction:ltr;'><b>SYSTEM LOG:</b> Searching for London contracts...<br>No matching markets found at this moment.</div>"}
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">🧠 נימוק החלטה (RATIONALE)</div>
            <div class="guide">
                {f"המערכת זיהתה פער חיובי של <b>{best['edge']}%</b> בחוזה של {best['label']}. ממוצע המודלים ({avg_oracle}°) מצביע על הסתברות גבוהה יותר ממה שהשוק מתמחר." if processed and best and best['edge'] > 0 else "המערכת סורקת כרגע את פולימרקט. אם לא מופיעים נתונים, ייתכן והשוק טרם נפתח או שהמערכת לא זיהתה התאמה מדויקת."}
            </div>
        </div>

        <div class="card">
            <div style="font-size:11px; color:#555; margin-bottom:12px;">📚 מדריך הכלים (USER GUIDE)</div>
            <div class="guide">
                • <b>השוואת מודלים:</b> שקלול נתונים מ-5 מודלים מובילים.<br>
                • <b>Edge:</b> הפער באחוזים בין ה-AI למחיר השוק. מעל 3% נחשב סיגנל YES.<br>
                • <b>LHR Live:</b> הטמפרטורה הנוכחית בהית'רו לניטור תנודות.
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
        f.write(html_content)
    print("DEBUG: index.html generated successfully.")

if __name__ == "__main__":
    run_bot()
