import requests
from datetime import datetime
import random

def run_bot():
    print("Starting bot execution...")
    lat, lon = 51.5048, 0.0495
    brand_green = "#B5EBBF"
    now = datetime.now().strftime('%H:%M:%S')
    
    # הוספת מספר רנדומלי כדי להכריח שינוי בקובץ
    run_id = random.randint(1000, 9999)

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,temperature_2m_max_gfs_seamless&timezone=Europe%2FLondon&start_date=2026-04-17&end_date=2026-04-17"
    
    try:
        res = requests.get(url, timeout=15)
        data = res.json()['daily']
        mapping = {
            'ECMWF': 'temperature_2m_max_ecmwf_ifs04',
            'UKMO': 'temperature_2m_max_ukmo_seamless',
            'ICON': 'temperature_2m_max_icon_seamless',
            'MeteoFrance': 'temperature_2m_max_meteofrance_seamless',
            'GFS': 'temperature_2m_max_gfs_seamless'
        }
        
        points = {n: data[k][0] for n, k in mapping.items() if data.get(k) and data[k][0] is not None}
        if not points:
            print("No data found, using fallback.")
            avg = 18.4  # Fallback
        else:
            avg = sum(points.values()) / len(points)
            
    except Exception as e:
        print(f"Error: {e}")
        avg = 18.4

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <title>IDOL ORACLE</title>
        <style>
            body {{ background: #050505; color: #fff; font-family: sans-serif; text-align: center; padding-top: 50px; }}
            .card {{ border: 1px solid #222; background: #111; padding: 40px; border-radius: 30px; display: inline-block; min-width: 300px; }}
            .temp {{ font-size: 80px; color: {brand_green}; font-weight: 900; }}
            .footer {{ color: #444; margin-top: 20px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1 style="color:{brand_green}">IDOL ORACLE</h1>
            <div class="temp">{avg:.2f}°C</div>
            <p>לונדון | 17 באפריל 2026</p>
            <div class="footer">עודכן ב: {now} (מזהה הרצה: {run_id})</div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Successfully wrote index.html with Run ID: {run_id}")

if __name__ == "__main__":
    run_bot()
