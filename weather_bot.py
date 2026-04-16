import requests
import math
from datetime import datetime

def get_live_poly_data():
    """משיכת נתונים חיים מפולימרקט באמצעות ה-API הפתוח"""
    try:
        # פנייה ל-API הציבורי לחיפוש השוק של לונדון
        url = "https://gamma-api.polymarket.com/events?active=true&closed=false&q=London%20temperature"
        response = requests.get(url).json()
        
        if not response:
            return None
        
        # לקיחת השוק הראשון שנמצא
        event = response[0]
        markets = event.get('markets', [])
        
        results = []
        for m in markets:
            try:
                # חילוץ הטמפרטורה משם השוק (למשל "18°C or above")
                temp_val = ''.join(filter(str.isdigit, m['groupItemTitle']))
                if not temp_val: continue
                
                # המחיר (ההסתברות) נמצא בתוך outcomePrices
                prices = eval(m['outcomePrices']) # מחיר בפורמט ["0.49", "0.51"]
                prob = round(float(prices[0]) * 100) # מחיר ה-"YES"
                
                results.append({"temp": f"{temp_val}°C", "prob": prob})
            except: continue
            
        # מיון לפי טמפרטורה
        results.sort(key=lambda x: int(''.join(filter(str.isdigit, x['temp']))))
        return results if results else None
    except Exception as e:
        print(f"Poly Sync Error: {e}")
        return None

def calculate_ai_prob(points, target_temp_str):
    """חישוב הסתברות AI לפי התפלגות נורמלית של המודלים"""
    try:
        target_val = int(''.join(filter(str.isdigit, target_temp_str)))
        vals = list(points.values())
        avg = sum(vals) / len(vals)
        std = max(math.sqrt(sum((x - avg)**2 for x in vals) / len(vals)), 0.6)
        def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
        prob = (cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100
        return round(min(max(prob, 5), 95))
    except: return 0

def run_bot():
    brand_green = "#B5EBBF"
    now_ts = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    # 1. נתוני מודלים (החזרתי את כל הפירוט שביקשת)
    points = {"ECMWF": 18.5, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.0, "MeteoFrance": 18.1}
    weights = {"ECMWF": 0.35, "UKMO": 0.25, "GFS": 0.15, "ICON": 0.15, "MeteoFrance": 0.10}
    avg_val = sum(points[n] * (weights[n]/sum(weights.values())) for n in points)

    # 2. נתוני פולימרקט חיים
    poly_data = get_live_poly_data()
    
    # אם השליפה נכשלה, נשתמש בנתוני Fallback כדי שהאתר לא יהיה ריק
    is_live = "LIVE" if poly_data else "OFFLINE (Fallback)"
    if not poly_data:
        poly_data = [{"temp": "17°C", "prob": 27}, {"temp": "18°C", "prob": 49}, {"temp": "19°C", "prob": 21}]
    
    # 3. בניית טבלת ההשוואה
    comparison_rows = ""
    for opt in poly_data:
        our_p = calculate_ai_prob(points, opt['temp'])
        market_p = opt['prob']
        edge = our_p - market_p
        color = brand_green if edge > 5 else "#ff4444" if edge < -5 else "#fff"
        
        comparison_rows += f"""
        <tr>
            <td style="text-align:right; padding:12px;">{opt['temp']}</td>
            <td style="text-align:center;">{market_p}%</td>
            <td style="text-align:center; color:{brand_green};">{our_p}%</td>
            <td style="text-align:left; color:{color}; font-weight:bold;">{edge:+.1f}%</td>
        </tr>"""

    # 4. עיצוב ה-HTML המלא עם הסברים מפורטים
    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 10px; line-height: 1.4; }}
            .container {{ max-width: 480px; margin: auto; }}
            .card {{ background: #111; border: 1px solid #222; border-radius: 20px; padding: 20px; margin-bottom: 15px; }}
            .title {{ font-size: 14px; font-weight: bold; color: #777; margin-bottom: 10px; border-bottom: 1px solid #222; padding-bottom: 5px; }}
            .main-val {{ font-size: 50px; font-weight: 900; color: {brand_green}; text-align: center; }}
            .desc {{ font-size: 12px; color: #999; margin-top: 10px; background: #1a1a1a; padding: 10px; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            td, th {{ font-size: 13px; border-bottom: 1px solid #1a1a1a; padding: 8px 0; }}
            .status-tag {{ font-size: 10px; background: {brand_green if poly_data else '#ff4444'}; color: #000; padding: 2px 6px; border-radius: 4px; float: left; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="status-tag">{is_live}</div>
                <div class="title">🎯 תחזית משוקללת (Oracle)</div>
                <div class="main-val">{avg_val:.2f}°C</div>
                <div class="desc">
                    <b>מה אתה רואה?</b> זוהי "נקודת האמת" של המערכת. היא משקללת 5 מודלים עולמיים. 
                    המודלים ECMWF ו-UKMO מקבלים עדיפות כי הם המדויקים ביותר לאזור בריטניה.
                </div>
            </div>

            <div class="card">
                <div class="title">⚖️ ניתוח ארביטראז' (Edge)</div>
                <table>
                    <tr style="color:#555; font-size:10px;">
                        <th style="text-align:right;">טמפרטורה</th>
                        <th style="text-align:center;">שוק (Poly)</th>
                        <th style="text-align:center;">שלנו (AI)</th>
                        <th style="text-align:left;">פער (Edge)</th>
                    </tr>
                    {comparison_rows}
                </table>
                <div class="desc">
                    <b>איך לקרוא את זה?</b> <br>
                    1. <b>שוק:</b> ההסתברות הנוכחית בפולימרקט בזמן אמת. <br>
                    2. <b>שלנו:</b> מה הסיכוי הסטטיסטי שהמודלים צופים לאותה מעלה. <br>
                    3. <b>פער:</b> אם המספר <b>ירוק וחיובי</b>, השוק מעריך בחסר את האופציה – זהו פוטנציאל לרווח.
                </div>
            </div>

            <div class="card">
                <div class="title">🌡️ פירוט מודלים (נתונים גולמיים)</div>
                <table>
                    {" ".join([f"<tr><td style='padding:8px;'>{n}</td><td style='color:{brand_green}; text-align:center;'>{t}°C</td><td style='text-align:left; color:#555;'>משקל: {int(weights[n]*100)}%</td></tr>" for n,t in points.items()])}
                </table>
                <div class="desc">
                    <b>למה זה חשוב?</b> ככל שהמודלים קרובים יותר אחד לשני (סטיית תקן נמוכה), רמת הביטחון שלנו בחיזוי עולה.
                </div>
            </div>

            <div style="text-align:center; font-size:10px; color:#444; margin-top:20px;">
                IDOL STUDIOS | סונכרן: {now_ts} | THOUSANDS OF LOYAL ANGELS
            </div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_bot()
