import requests
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

class IdolUltraOracle:
    def __init__(self, market_url):
        self.market_url = market_url
        self.lat, self.lon = 51.5048, 0.0495
        self.weights = {"ECMWF": 0.35, "UKMO": 0.25, "ICON": 0.15, "MeteoFrance": 0.10, "GFS": 0.10, "OpenWeather": 0.05}

    def fetch_data(self):
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}"
               f"&daily=temperature_2m_max,relative_humidity_2m_max,cloud_cover_max,precipitation_probability_max"
               f"&timezone=Europe%2FLondon&models=ecmwf_ifs04,ukmo_seamless,icon_seamless,meteofrance_seamless,gfs_seamless"
               f"&start_date=2026-04-17&end_date=2026-04-17")
        try:
            res = requests.get(url, timeout=15)
            return res.json()
        except Exception as e:
            print(f"Weather API Error: {e}")
            return None

    def fetch_market(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        prices = {}
        try:
            driver.get(self.market_url)
            time.sleep(15)
            page_text = driver.find_element(By.TAG_NAME, "body").text
            for label in ["16°C", "17°C", "18°C", "19°C"]:
                match = re.search(f"{label}.*?(\d+)¢", page_text)
                if match: prices[label] = int(match.group(1)) / 100
            return prices
        except: return prices
        finally: driver.quit()

    def generate_dashboard(self, data):
        brand_green = "#B5EBBF"
        roi = ((1 / data['price']) - 1) * 100 if data['price'] > 0 else 0
        
        target_int = int(round(data['avg']))
        range_probs = {}
        for offset in range(-1, 2): 
            temp = target_int + offset
            count = sum(1 for t in data['models'].values() if int(round(t)) == temp)
            range_probs[temp] = (count / len(data['models'])) * 100 if len(data['models']) > 0 else 0

        rows = "".join([f"<tr><td>{n}</td><td>{t:.1f}°C</td><td>{self.weights.get(n,0)*100:.0f}%</td></tr>" for n, t in data['models'].items()])

        html = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="he">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>IDOL ORACLE v7.0</title>
            <style>
                body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 20px; }}
                .container {{ max-width: 800px; margin: auto; }}
                .card {{ background: #111; border-radius: 20px; padding: 25px; margin-bottom: 20px; border: 1px solid #222; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .main-temp {{ font-size: 80px; color: {brand_green}; font-weight: 900; }}
                .location-tag {{ color: #888; font-size: 18px; margin-top: -10px; }}
                .prob-bar {{ height: 10px; background: #222; border-radius: 5px; margin: 10px 0; overflow: hidden; }}
                .prob-fill {{ height: 100%; background: {brand_green}; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                td, th {{ padding: 12px; border-bottom: 1px solid #222; text-align: right; }}
                .explanation {{ font-size: 14px; color: #aaa; line-height: 1.6; border-right: 3px solid {brand_green}; padding-right: 15px; margin-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin:0; color:{brand_green}">IDOL ORACLE</h1>
                    <div class="location-tag">לונדון (LHR/City) | 17 באפריל, 2026</div>
                </div>

                <div class="card" style="text-align: center;">
                    <div style="font-size: 14px; letter-spacing: 2px; color: #888;">תחזית משוקללת סופית</div>
                    <div class="main-temp">{data['avg']:.2f}°C</div>
                    <div class="explanation">
                        <strong>הסבר טכני:</strong> הממוצע מחושב לפי משקלים קבועים: ECMWF (אירופאי) מקבל 35% בגלל דיוק גבוה בבריטניה. הנתון הוא שילוב של 5 מודלים שונים.
                    </div>
                </div>

                <div class="card">
                    <h3>🎯 הסתברות סטטיסטית (טווח 3 מעלות)</h3>
                    { "".join([f'''
                        <div style="margin-bottom:15px;">
                            <div style="display:flex; justify-content:space-between; font-size:14px;">
                                <span>טמפרטורה חזויה: {temp}°C</span>
                                <span>{prob:.0f}% תמיכת מודלים</span>
                            </div>
                            <div class="prob-bar"><div class="prob-fill" style="width: {prob}%"></div></div>
                        </div>
                    ''' for temp, prob in range_probs.items()]) }
                </div>

                <div class="card">
                    <h3>📊 פירוט נתונים גולמיים מכל המודלים</h3>
                    <table>
                        <thead><tr><th>מקור דיווח</th><th>תחזית</th><th>משקל בחישוב</th></tr></thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>

                <div class="card" style="background: {brand_green}; color: #000;">
                    <h3 style="margin:0;">💰 ניתוח שוק (Polymarket)</h3>
                    <p>מחיר שוק ליעד {data['target']}: <strong>{data['price']:.2f}¢</strong></p>
                    <p style="font-size: 24px; font-weight: bold; margin: 5px 0;">ROI פוטנציאלי: {roi:.1f}%</p>
                </div>
                
                <p style="text-align: center; color: #444; font-size: 11px;">IDOL ORACLE v7.0 | {data['time']}</p>
            </div>
        </body>
        </html>
        """
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)

    def run_cycle(self):
        meteo = self.fetch_data()
        if not meteo or 'daily' not in meteo: return

        market = self.fetch_market()
        model_map = {"ecmwf_ifs04": "ECMWF", "ukmo_seamless": "UKMO", "icon_seamless": "ICON", "meteofrance_seamless": "MeteoFrance", "gfs_seamless": "GFS"}
        
        points = {}
        for k, name in model_map.items():
            field = f'temperature_2m_max_{k}'
            if field in meteo['daily'] and meteo['daily'][field][0] is not None:
                points[name] = float(meteo['daily'][field][0])

        if not points: return

        total_weight = sum(self.weights.get(n, 0.05) for n in points.keys())
        avg = sum(t * self.weights.get(n, 0.05) for n, t in points.items()) / total_weight
        
        target = f"{int(round(avg))}°C"
        price = market.get(target, 0)
        
        self.generate_dashboard({
            'avg': avg, 'target': target, 
            'price': price, 'time': datetime.now().strftime('%d/%m %H:%M'), 'models': points
        })

if __name__ == "__main__":
    URL = "https://polymarket.com/event/highest-temperature-in-london-on-april-17-2026"
    agent = IdolUltraOracle(URL)
    agent.run_cycle()
