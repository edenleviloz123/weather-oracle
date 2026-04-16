import requests
from datetime import datetime

def run_bot():
    lat, lon = 51.5048, 0.0495
    # שימוש בצבע המותג של Idol Studios
    brand_green = "#B5EBBF"
    
    # משיכת נתונים מכל המודלים כולל ECMWF
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,temperature_2m_max_gfs_seamless&timezone=Europe%2FLondon&start_date=2026-04-17&end_date=2026-04-17"
    
    try:
        res = requests.get(url)
        data = res.json()['daily']
        mapping = {
            'ECMWF': 'temperature_2m_max_ecmwf_ifs04',
            'UKMO': 'temperature_2m_max_ukmo_seamless',
            'ICON': 'temperature_2m_max_icon_seamless',
            'MeteoFrance': 'temperature_2m_max_meteofrance_seamless',
            'GFS': 'temperature_2m_max_gfs_seamless'
        }
        
        points = {n: data[k][0] for n, k in mapping.items() if data.get(k) and data[k][0] is not None}
        if not points: return
        
        avg = sum(points.values()) / len(points)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    except: return

    rows = "".join([f"<tr><td>{n}</td><td>{t:.1f}°C</td></tr>" for n, t in points.items()])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <title>IDOL ORACLE</title>
        <style>
            body {{ background: #050505; color: #fff; font-family: sans-serif; padding: 20px; text-align: center; }}
            .card {{ background: #111; border-radius: 24px; padding: 30px; border: 1px solid #222; max-width: 500px; margin: auto; }}
            .temp {{ font-size: 70px; color: {brand_green}; font-weight: bold; }}
            table {{ width: 100%; margin-top: 20px; border-collapse: collapse; }}
            td {{ padding: 10px; border-bottom: 1px solid #222; text-align: right; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 style="color:{brand_green}">IDOL ORACLE</h1>
            <div class="card">
                <div class="temp">{avg:.2f}°C</div>
                <p>ממוצע משוקלל מעודכן</p>
                <table>{rows}</table>
            </div>
            <p style="color:#444; font-size:12px;">סנכרון אחרון: {timestamp}</p>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    run_bot()
