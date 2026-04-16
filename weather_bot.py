import requests
from datetime import datetime

def run_bot():
    # נתוני מיקום ומשקלים
    lat, lon = 51.5048, 0.0495
    weights = {"ECMWF": 0.35, "UKMO": 0.25, "ICON": 0.15, "MeteoFrance": 0.10, "GFS": 0.15}
    brand_green = "#B5EBBF"

    # משיכת נתונים מה-API
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,temperature_2m_max_gfs_seamless&timezone=Europe%2FLondon&start_date=2026-04-17&end_date=2026-04-17"
    
    try:
        data = requests.get(url).json()['daily']
        mapping = {
            'ECMWF': 'temperature_2m_max_ecmwf_ifs04',
            'UKMO': 'temperature_2m_max_ukmo_seamless',
            'ICON': 'temperature_2m_max_icon_seamless',
            'MeteoFrance': 'temperature_2m_max_meteofrance_seamless',
            'GFS': 'temperature_2m_max_gfs_seamless'
        }
        
        points = {name: data[key][0] for name, key in mapping.items() if data.get(key) and data[key][0] is not None}
        
        # חישוב ממוצע משוקלל
        active_weights = {n: weights[n] for n in points}
        total_w = sum(active_weights.values())
        avg = sum(points[n] * active_weights[n] for n in points) / total_w
        
    except: return

    # יצירת שורות הטבלה
    rows = "".join([f"<tr><td>{n}</td><td>{t:.1f}°C</td><td>{weights[n]*100:.0f}%</td></tr>" for n, t in points.items()])

    # יצירת ה-HTML (מבוסס על העיצוב שאהבת בתמונה)
    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IDOL ORACLE</title>
        <style>
            body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 20px; }}
            .container {{ max-width: 600px; margin: auto; }}
            .card {{ background: #111; border-radius: 24px; padding: 30px; margin-bottom: 20px; border: 1px solid #222; text-align: center; }}
            .main-temp {{ font-size: 80px; color: {brand_green}; font-weight: 900; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            td, th {{ padding: 12px; border-bottom: 1px solid #222; text-align: right; }}
            .footer {{ color: #444; font-size: 12px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 style="text-align:center; color:{brand_green}">IDOL ORACLE</h1>
            <div class="card">
                <div class="main-temp">{avg:.2f}°C</div>
                <p>ממוצע משוקלל כולל ECMWF</p>
            </div>
            <div class="card">
                <table>
                    <thead><tr><th>מודל</th><th>תחזית</th><th>משקל</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
            <div class="footer">עודכן אוטומטית ב: {datetime.now().strftime('%H:%M')}</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    run_bot()
