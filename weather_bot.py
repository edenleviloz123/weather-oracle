import requests
from datetime import datetime
import random

def run_bot():
    print("--- Starting IDOL ORACLE ---")
    brand_green = "#B5EBBF"
    lat, lon = 51.5048, 0.0495
    now = datetime.now().strftime('%H:%M:%S')
    
    # מספר רנדומלי שמוודא שגיטהאב מזהה שינוי בקובץ בכל ריצה
    run_id = random.randint(10000, 99999) 
    
    # 1. לוגיקת משקלים ומודלים
    weights = {"ECMWF": 0.35, "UKMO": 0.25, "ICON": 0.15, "MeteoFrance": 0.10, "GFS": 0.15}
    url_weather = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,temperature_2m_max_gfs_seamless&timezone=Europe%2FLondon&start_date=2026-04-17&end_date=2026-04-17&nocache={run_id}"
    
    try:
        w_data = requests.get(url_weather, timeout=15).json()['daily']
        mapping = {
            'ECMWF': 'temperature_2m_max_ecmwf_ifs04',
            'UKMO': 'temperature_2m_max_ukmo_seamless',
            'ICON': 'temperature_2m_max_icon_seamless',
            'MeteoFrance': 'temperature_2m_max_meteofrance_seamless',
            'GFS': 'temperature_2m_max_gfs_seamless'
        }
        
        # סינון מודלים שלא החזירו תשובה
        points = {n: w_data[k][0] for n, k in mapping.items() if w_data.get(k) and w_data[k][0] is not None}
        if not points:
            raise ValueError("No data from models")
            
        # חישוב ממוצע משוקלל חכם (מסתגל למודלים חסרים)
        active_weights = {n: weights[n] for n in points}
        total_w = sum(active_weights.values())
        avg = sum(points[n] * (active_weights[n]/total_w) for n in points)
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # 2. לוגיקת פולימרקט וזיהוי ארביטראז' (סימולציה)
    market_prediction = round(avg)
    market_price = random.randint(60, 85) # מחיר השוק בסנטים
    
    # זיהוי פער: אם השוק מתמחר נמוך מ-70 סנט אבל המודלים בטוחים
    if market_price < 70:
        arb_status = "הזדמנות (Arbitrage)"
        arb_color = brand_green
    else:
        arb_status = "שוק יציב"
        arb_color = "#fff"

    # 3. בניית הממשק (HTML + CSS)
    rows = "".join([f"<tr><td>{n}</td><td style='color:{brand_green}; font-weight:bold;'>{t:.1f}°C</td><td style='color:#666;'>{int((active_weights[n]/total_w)*100)}%</td></tr>" for n, t in points.items()])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IDOL ORACLE</title>
        <style>
            body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 20px; margin: 0; }}
            .container {{ max-width: 500px; margin: 20px auto; }}
            .card {{ background: #111; border-radius: 24px; padding: 30px; margin-bottom: 20px; border: 1px solid #222; text-align: center; }}
            .main-temp {{ font-size: 80px; color: {brand_green}; font-weight: 900; margin: 10px 0; }}
            .market-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 20px; }}
            .market-item {{ background: #1a1a1a; padding: 15px; border-radius: 15px; border: 1px solid #333; }}
            .price {{ font-size: 24px; color: {brand_green}; font-weight: bold; margin-top: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            td {{ padding: 12px 0; border-bottom: 1px solid #222; text-align: center; font-size: 15px; }}
            .angel-footer {{ margin-top: 40px; opacity: 0.4; font-size: 12px; letter-spacing: 2px; text-align: center; line-height: 1.8; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div style="letter-spacing: 4px; font-size: 13px; color: {brand_green}; font-weight: bold;">IDOL STUDIOS ORACLE</div>
                <div class="main-temp">{avg:.2f}°C</div>
                <div style="color: #888; font-size: 14px;">לונדון | 17 באפריל 2026</div>
                <div style="color: #555; font-size: 12px; margin-top: 5px;">ממוצע משוקלל (חי)</div>
            </div>

            <div class="card">
                <h3 style="margin-top:0; font-size: 18px; text-align: right;">📊 ניתוח שוק (Polymarket)</h3>
                <div class="market-grid">
                    <div class="market-item">
                        <div style="font-size: 12px; color: #888;">הימור על {market_prediction}°C</div>
                        <div class="price">{market_price}¢</div>
                    </div>
                    <div class="market-item">
                        <div style="font-size: 12px; color: #888;">סטטוס שוק</div>
                        <div class="price" style="color: {arb_color}; font-size: 16px;">{arb_status}</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h3 style="margin-top:0; font-size: 18px; text-align: right;">🌡️ התפלגות מודלים</h3>
                <table>
                    <tr style="color:#666; font-size:12px;"><td>מודל</td><td>תחזית</td><td>משקל יחסי</td></tr>
                    {rows}
                </table>
            </div>

            <div class="angel-footer">
                THOUSANDS OF LOYAL ANGELS <br>
                SYNC: {now} | ID: {run_id}
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Successfully wrote index.html (Run ID: {run_id})")

if __name__ == "__main__":
    run_bot()
