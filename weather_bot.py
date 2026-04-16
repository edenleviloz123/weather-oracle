import requests
import time
import re
from datetime import datetime

class IdolUltraOracle:
    def __init__(self):
        self.lat, self.lon = 51.5048, 0.0495
        self.weights = {"ECMWF": 0.35, "UKMO": 0.25, "ICON": 0.15, "MeteoFrance": 0.10, "GFS": 0.10}

    def fetch_data(self):
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}"
               f"&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,temperature_2m_max_gfs_seamless"
               f"&timezone=Europe%2FLondon&start_date=2026-04-17&end_date=2026-04-17")
        try:
            res = requests.get(url, timeout=15)
            return res.json()
        except: return None

    def generate_dashboard(self, data):
        brand_green = "#B5EBBF"
        rows = "".join([f"<tr><td>{n}</td><td>{t:.1f}°C</td><td>{self.weights.get(n,0)*100:.0f}%</td></tr>" for n, t in data['models'].items()])
        
        html = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="he">
        <head>
            <meta charset="UTF-8">
            <title>IDOL ORACLE v7.3</title>
            <style>
                body {{ background: #050505; color: #fff; font-family: sans-serif; padding: 20px; text-align: center; }}
                .card {{ background: #111; border-radius: 20px; padding: 20px; margin: 20px auto; max-width: 600px; border: 1px solid #222; }}
                .temp {{ font-size: 64px; color: {brand_green}; font-weight: bold; }}
                table {{ width: 100%; margin-top: 20px; border-collapse: collapse; }}
                td, th {{ padding: 10px; border-bottom: 1px solid #222; }}
            </style>
        </head>
        <body>
            <h1>IDOL ORACLE</h1>
            <p>לונדון | 17 באפריל, 2026</p>
            <div class="card">
                <div class="temp">{data['avg']:.2f}°C</div>
                <p>ממוצע משוקלל כולל ECMWF</p>
            </div>
            <div class="card">
                <h3>פירוט מודלים</h3>
                <table>
                    <thead><tr><th>מודל</th><th>תחזית</th><th>משקל</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
            <p style="color:#444;">עודכן ב: {data['time']}</p>
        </body>
        </html>
        """
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)

    def run(self):
        meteo = self.fetch_data()
        if not meteo or 'daily' not in meteo: return
        
        points = {}
        d = meteo['daily']
        mapping = {'ECMWF': 'temperature_2m_max_ecmwf_ifs04', 'UKMO': 'temperature_2m_max_ukmo_seamless', 
                   'ICON': 'temperature_2m_max_icon_seamless', 'MeteoFrance': 'temperature_2m_max_meteofrance_seamless', 
                   'GFS': 'temperature_2m_max_gfs_seamless'}
        
        for name, key in mapping.items():
            if key in d and d[key][0] is not None:
                points[name] = float(d[key][0])
        
        if not points: return
        avg = sum(t * self.weights.get(n, 0.1) for n, t in points.items()) / sum(self.weights.get(n, 0.1) for n in points.keys())
        
        self.generate_dashboard({
            'avg': avg, 'time': datetime.now().strftime('%H:%M'), 'models': points
        })

if __name__ == "__main__":
    IdolUltraOracle().run()
