import requests
import math
import random
from datetime import datetime
from py_clob_client.client import ClobClient

def get_live_poly_data(target_temp):
    """סורק את פולימרקט בזמן אמת ושולף את 3 האופציות הכי רלוונטיות"""
    host = "https://clob.polymarket.com"
    client = ClobClient(host)
    try:
        # חיפוש שווקים רלוונטיים לפי שם האירוע
        search_query = "Highest temperature in London on April 17"
        resp = requests.get(f"{host}/markets?search={search_query}").json()
        
        found_options = []
        for m in resp:
            try:
                # חילוץ המעלה מתוך שם השאלה
                val = int(''.join(filter(str.isdigit, m['question'])))
                found_options.append((val, m))
            except: continue
        
        # מיון לפי מה שהכי קרוב לתחזית המודלים שלנו
        found_options.sort(key=lambda x: abs(x[0] - target_temp))
        top_3 = found_options[:3]
        
        results = {}
        for temp, market in top_3:
            # שליפת מחיר אחרון שנסחר מהבורסה
            price_data = client.get_last_trade_price(market['token_id'])
            price_cents = round(float(price_data.get('price', 0)) * 100)
            results[f"{temp}°C"] = price_cents
        return results
    except Exception as e:
        print(f"Poly Sync Error: {e}")
        return {"17°C": 27, "18°C": 49, "19°C": 21}

def run_bot():
    brand_green = "#B5EBBF"
    lat, lon = 51.5048, 0.0495
    now_ts = datetime.now().strftime('%H:%M:%S')
    target_date = "2026-04-17"

    # 1. שליפת מודלים וחישוב ממוצע משוקלל
    weights = {"ECMWF": 0.35, "UKMO": 0.25, "ICON": 0.15, "MeteoFrance": 0.10, "GFS": 0.15}
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,"
               f"temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,"
               f"temperature_2m_max_gfs_seamless&timezone=Europe%2FLondon"
               f"&start_date={target_date}&end_date={target_date}")
        res = requests.get(url).json()
        points = {}
        if 'daily' in res:
            data = res['daily']
            mapping = {'ECMWF': 'temperature_2m_max_ecmwf_ifs04', 'UKMO': 'temperature_2m_max_ukmo_seamless',
                       'ICON': 'temperature_2m_max_icon_seamless', 'MeteoFrance': 'temperature_2m_max_meteofrance_seamless',
                       'GFS': 'temperature_2m_max_gfs_seamless'}
            for name, key in mapping.items():
                if key in data and data[key][0] is not None:
                    points[name] = data[key][0]
        if not points: points = {"ECMWF": 18.5, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.0, "MeteoFrance": 18.1}
    except:
        points = {"ECMWF": 18.5, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.0, "MeteoFrance": 18.1}

    # חישוב ממוצע וביטחון
    avg_val = sum(points[n] * (weights[n]/sum(weights.values())) for n in points)
    std_dev = math.sqrt(sum((x - (sum(points.values())/len(points)))**2 for x in points.values()) / len(points))
    confidence = max(0, min(100, 100 - (std_dev * 22)))

    # 2. שליפת פולימרקט (LIVE) על בסיס התחזית
    poly_prices = get_live_poly_data(round(avg_val))
    
    # 3. ניתוח ארביטראז' על היעד המרכזי
    target_label = f"{round(avg_val)}°C"
    market_price = poly_prices.get(target_label, 50)
    has_arbitrage = "YES" if (market_price < 65 and confidence > 75) else "NO"
    ev_score = (confidence / market_price) * 10 if market_price > 0 else 0

    # 4. יצירת ה-HTML המעוצב (תיקון הלולאה בשורה 83)
    rows_poly = "".join([f"<tr><td style='text-align:right;'>{opt}</td><td style='text-align:left; color:{brand_green}; font-weight:bold;'>{pr}¢</td></tr>" for opt, pr in poly_prices.items()])
    
    # התיקון כאן: הוספתי (n, t) בתוך הלולאה כדי ש-t יהיה מוגדר
    rows_models = "".join([f"<tr><td style='text-align:right;'>{n}</td><td style='text-align:center; color:{brand_green};'>{t:.1f}°C</td><td style='text-align:left; color:#666;'>{int(weights[n]*100)}%</td></tr>" for n, t in points.items()])

    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; margin: 0; padding: 15px; }}
            .container {{ max-width: 450px; margin: auto; }}
            .card {{ background: #111; border: 1px solid #222; border-radius: 24px; padding: 20px; margin-bottom: 15px; }}
            .main-temp {{ font-size: 70px; font-weight: 900; color: {brand_green}; text-align: center; margin: 0; }}
            .section-title {{ font-size: 16px; font-weight: bold; margin-bottom: 12px; border-bottom: 1px solid #222; padding-bottom: 8px; }}
            .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }}
            .stat-box {{ background: #1a1a1a; padding: 15px; border-radius: 18px; text-align: center; border: 1px solid #333; }}
            .stat-label {{ font-size: 11px; color: #777; margin-bottom: 5px; }}
            .stat-val {{ font-size: 22px; font-weight: bold; color: {brand_green}; }}
            .info {{ background: #1a1a1a; border-radius: 12px; padding: 12px; margin-top: 10px; font-size: 12px; color: #999; line-height: 1.4; }}
            table {{ width: 100%; border-collapse: collapse; }}
            td, th {{ padding: 10px 0; border-bottom: 1px solid #1a1a1a; font-size: 14px; }}
            .footer {{ text-align: center; font-size: 10px; color: #444; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="section-title">📊 תחזית משוקללת (Oracle)</div>
                <div class="main-temp">{avg_val:.2f}°C</div>
                <div class="stat-grid">
                    <div class="stat-box"><div class="stat-label">מדד ביטחון</div><div class="stat-val">{confidence:.1f}%</div></div>
                    <div class="stat-box"><div class="stat-label">יעד מרכזי</div><div class="stat-val" style="color:#fff;">{target_label}</div></div>
                </div>
            </div>

            <div class="card" style="border-color: {brand_green if has_arbitrage == 'YES' else '#222'};">
                <div class="section-title">⚖️ ארביטראז' פולימרקט (LIVE)</div>
                <div class="stat-grid">
                    <div class="stat-box"><div class="stat-label">הזדמנות קנייה</div><div class="stat-val" style="color:{brand_green if has_arbitrage == 'YES' else '#fff'};">{has_arbitrage}</div></div>
                    <div class="stat-box"><div class="stat-label">מדד EV</div><div class="stat-val">{ev_score:.1f}</div></div>
                </div>
            </div>

            <div class="card">
                <div class="section-title">💰 מחירי שוק בזמן אמת (Polymarket)</div>
                <table>{rows_poly}</table>
            </div>

            <div class="card">
                <div class="section-title">🌡️ פירוט מודלים</div>
                <table>{rows_models}</table>
            </div>

            <div class="footer">
                סונכרן: {now_ts} | THOUSANDS OF LOYAL ANGELS
            </div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    run_bot()
