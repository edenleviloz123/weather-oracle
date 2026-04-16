import requests
from datetime import datetime
import random

def run_bot():
    print("--- Starting IDOL ORACLE ---")
    brand_green = "#B5EBBF"
    lat, lon = 51.5048, 0.0495
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    run_id = random.randint(10000, 99999) 
    
    # תאריך היעד שלנו
    target_date = "2026-04-17"
    
    # כתובת ה-API עם פרמטרים ברורים
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_gfs_seamless&timezone=Europe%2FLondon&start_date={target_date}&end_date={target_date}"
    
    try:
        response = requests.get(url, timeout=15)
        res_data = response.json()
        
        # בדיקה אם יש שגיאה בתשובה מה-API
        if 'daily' not in res_data:
            print(f"API Error: {res_data.get('reason', 'Unknown reason')}")
            avg = 18.40 # נתון ברירת מחדל כדי שהאתר לא יקרוס
            status_msg = "זמני (ממתין ל-API)"
            points = {}
        else:
            data = res_data['daily']
            # ננסה למשוך מה שיש (גם אם רק מודל אחד חזר)
            vals = []
            if 'temperature_2m_max_ecmwf_ifs04' in data and data['temperature_2m_max_ecmwf_ifs04'][0]:
                vals.append(data['temperature_2m_max_ecmwf_ifs04'][0])
            if 'temperature_2m_max_gfs_seamless' in data and data['temperature_2m_max_gfs_seamless'][0]:
                vals.append(data['temperature_2m_max_gfs_seamless'][0])
            
            avg = sum(vals) / len(vals) if vals else 18.40
            status_msg = "מעודכן"
            points = {"ECMWF": vals[0] if len(vals) > 0 else "N/A", "GFS": vals[1] if len(vals) > 1 else "N/A"}

    except Exception as e:
        print(f"Critical System Error: {e}")
        avg = 18.40
        status_msg = "שגיאת מערכת"
        points = {}

    # בניית ה-HTML
    rows = "".join([f"<tr><td>{n}</td><td style='color:{brand_green}'>{t}°C</td></tr>" for n, t in points.items()])

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <title>IDOL ORACLE</title>
        <style>
            body {{ background: #050505; color: #fff; font-family: sans-serif; text-align: center; padding: 20px; }}
            .card {{ background: #111; border: 1px solid #222; padding: 30px; border-radius: 20px; max-width: 400px; margin: auto; }}
            .temp {{ font-size: 60px; color: {brand_green}; font-weight: bold; }}
            .footer {{ color: #333; font-size: 10px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2 style="color:{brand_green}; letter-spacing: 2px;">IDOL ORACLE</h2>
            <div class="temp">{avg:.2f}°C</div>
            <p>לונדון | {target_date}</p>
            <p style="font-size:12px; color:#666;">סטטוס: {status_msg}</p>
            <table style="width:100%; margin-top:10px;">{rows}</table>
        </div>
        <div class="footer">SYNC: {now} | ID: {run_id}</div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"File updated successfully. Run ID: {run_id}")

if __name__ == "__main__":
    run_bot()
