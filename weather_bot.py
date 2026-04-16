import requests
from datetime import datetime
import random

def run_bot():
    print("--- IDOL ORACLE: OPERATIONAL ---")
    brand_green = "#B5EBBF"
    lat, lon = 51.5048, 0.0495
    now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    run_id = random.randint(100000, 999999)
    target_date = "2026-04-17"

    # 1. הגדרת משקלים (הלוגיקה המקורית שלנו)
    weights = {
        "ECMWF": 0.35,
        "UKMO": 0.25,
        "ICON": 0.15,
        "MeteoFrance": 0.10,
        "GFS": 0.15
    }

    # 2. שליפת נתונים מכל המודלים (עם הגנה מפני שינויי API של הרגע האחרון)
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,"
           f"temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,"
           f"temperature_2m_max_gfs_seamless&timezone=Europe%2FLondon"
           f"&start_date={target_date}&end_date={target_date}")

    points = {}
    try:
        response = requests.get(url, timeout=15)
        res_json = response.json()
        
        if 'daily' in res_json:
            data = res_json['daily']
            mapping = {
                'ECMWF': 'temperature_2m_max_ecmwf_ifs04',
                'UKMO': 'temperature_2m_max_ukmo_seamless',
                'ICON': 'temperature_2m_max_icon_seamless',
                'MeteoFrance': 'temperature_2m_max_meteofrance_seamless',
                'GFS': 'temperature_2m_max_gfs_seamless'
            }
            for name, key in mapping.items():
                if key in data and data[key][0] is not None:
                    points[name] = data[key][0]
        
        # אם ה-API ביום האירוע לא מחזיר 'daily', ננסה למשוך נתון נוכחי כגיבוי
        elif 'current' in res_json:
            points["CURRENT_OBS"] = res_json['current']['temperature_2m']
            
    except Exception as e:
        print(f"Fetch Error: {e}")

    # 3. חישוב ממוצע משוקלל חכם
    if points:
        active_weights = {n: weights.get(n, 0.1) for n in points}
        total_w = sum(active_weights.values())
        avg = sum(points[n] * (active_weights[n]/total_w) for n in points)
        status_msg = "LIVE DATA"
    else:
        avg = 18.40  # ערך בטוח למקרה של קריסה טוטאלית של ה-API
        status_msg = "FALLBACK MODE"

    # 4. לוגיקת פולימרקט (ארביטראז')
    market_price = random.randint(65, 82) # כאן יכנס ה-API של פולימרקט בהמשך
    arb_opportunity = "YES" if market_price < 72 else "NO"

    # 5. בניית ה-HTML (העיצוב המלא שסיכמנו)
    rows_html = ""
    for name, temp in points.items():
        rows_html += f"""
        <tr>
            <td style="text-align:right; padding:12px;">{name}</td>
            <td style="text-align:left; color:{brand_green}; font-weight:bold;">{temp:.1f}°C</td>
        </tr>"""

    full_html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IDOL ORACLE</title>
        <style>
            body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 450px; margin: auto; }}
            .card {{ background: #111; border: 1px solid #222; border-radius: 28px; padding: 25px; margin-bottom: 20px; }}
            .brand-header {{ color: {brand_green}; letter-spacing: 4px; font-size: 12px; font-weight: bold; margin-bottom: 20px; text-align: center; }}
            .temp-display {{ font-size: 72px; font-weight: 900; color: {brand_green}; text-align: center; margin: 10px 0; }}
            .market-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
            .market-box {{ background: #1a1a1a; border: 1px solid #333; padding: 15px; border-radius: 18px; text-align: center; }}
            .price {{ font-size: 24px; font-weight: bold; color: {brand_green}; }}
            table {{ width: 100%; border-collapse: collapse; }}
            tr {{ border-bottom: 1px solid #222; }}
            .footer {{ text-align: center; font-size: 10px; color: #444; margin-top: 40px; letter-spacing: 2px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="brand-header">IDOL STUDIOS ORACLE</div>
                <div style="text-align:center; color:#666; font-size:14px;">LONDON | {target_date}</div>
                <div class="temp-display">{avg:.2f}°C</div>
                <div style="text-align:center; font-size:12px; color:#444;">STATUS: {status_msg}</div>
            </div>

            <div class="card">
                <div style="font-weight:bold; margin-bottom:15px;">📊 POLYMARKET ANALYSIS</div>
                <div class="market-grid">
                    <div class="market-box">
                        <div style="font-size:11px; color:#888;">MARKET PRICE</div>
                        <div class="price">{market_price}¢</div>
                    </div>
                    <div class="market-box">
                        <div style="font-size:11px; color:#888;">ARBITRAGE</div>
                        <div class="price" style="color:#fff;">{arb_opportunity}</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div style="font-weight:bold; margin-bottom:15px;">🌡️ MODEL BREAKDOWN</div>
                <table>{rows_html}</table>
            </div>

            <div class="footer">
                THOUSANDS OF LOYAL ANGELS<br>
                SYNCED: {now_ts} | ID: {run_id}
            </div>
        </div>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"Success! Oracle Updated with ID {run_id}")

if __name__ == "__main__":
    run_bot()
