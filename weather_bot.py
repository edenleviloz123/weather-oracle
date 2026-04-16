import requests
from datetime import datetime
import os

def run_bot():
    # נתונים בסיסיים
    lat, lon = 51.5048, 0.0495
    brand_green = "#B5EBBF"
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # שליפת נתונים - הוספת פרמטר אקראי ל-URL כדי למנוע Cache מה-API
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,temperature_2m_max_gfs_seamless&timezone=Europe%2FLondon&start_date=2026-04-17&end_date=2026-04-17&nocache={datetime.now().timestamp()}"
    
    try:
        response = requests.get(url, timeout=15)
        data = response.json()['daily']
        
        mapping = {
            'ECMWF': 'temperature_2m_max_ecmwf_ifs04',
            'UKMO': 'temperature_2m_max_ukmo_seamless',
            'ICON': 'temperature_2m_max_icon_seamless',
            'MeteoFrance': 'temperature_2m_max_meteofrance_seamless',
            'GFS': 'temperature_2m_max_gfs_seamless'
        }
        
        points = {n: data[k][0] for n, k in mapping.items() if k in data and data[k][0] is not None}
        if not points:
            print("No data points found!")
            return
            
        avg = sum(points.values()) / len(points)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # בניית הטבלה
    rows = "".join([f"<tr><td>{n}</td><td>{t:.1f}°C</td></tr>" for n, t in points.items()])

    # יצירת ה-HTML עם חותמת זמן נסתרת (Timestamp) להכרחת עדכון
    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <title>IDOL ORACLE v7.7</title>
        <style>
            body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 20px; text-align: center; }}
            .card {{ background: #111; border-radius: 24px; padding: 30px; border: 1px solid #222; max-width: 500px; margin: auto; }}
            .main-temp {{ font-size: 80px; color: {brand_green}; font-weight: 900; }}
            table {{ width: 100%; margin-top: 20px; border-collapse: collapse; }}
            td {{ padding: 12px; border-bottom: 1px solid #222; text-align: right; }}
            .update-time {{ color: #444; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 style="color:{brand_green}">IDOL ORACLE</h1>
            <div class="card">
                <div class="main-temp">{avg:.2f}°C</div>
                <p>ממוצע משוקלל (לונדון | 17.04)</p>
                <table>{rows}</table>
            </div>
            <div class="update-time">סנכרון אחרון: {now_str}</div>
        </div>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Update completed at {now_str}")

if __name__ == "__main__":
    run_bot()
