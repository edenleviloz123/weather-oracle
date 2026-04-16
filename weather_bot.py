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
        # רשימת המודלים המלאה כולל ה-ECMWF
        self.weights = {"ECMWF": 0.35, "UKMO": 0.25, "ICON": 0.15, "MeteoFrance": 0.10, "GFS": 0.10, "OpenWeather": 0.05}

    def fetch_data(self):
        # הוספתי את המודל החסר (ecmwf_ifs04) בצורה מפורשת יותר
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}"
               f"&daily=temperature_2m_max,temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,temperature_2m_max_gfs_seamless"
               f"&timezone=Europe%2FLondon&start_date=2026-04-17&end_date=2026-04-17")
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
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        prices = {}
        try:
            driver.get(self.market_url)
            time.sleep(20) # זמן המתנה ארוך יותר לטעינת מחירים
            page_text = driver.find_element(By.TAG_NAME, "body").text
            # חיפוש מחיר בצורה גמישה יותר (תומך בפורמט של פולימרקט)
            for label in ["16", "17", "18", "19"]:
                match = re.search(rf"{label}°C.*?(\d+)¢", page_text)
                if match: 
                    prices[f"{label}°C"] = int(match.group(1)) / 100
            return prices
        except Exception as e:
            print(f"Market Fetch Error: {e}")
            return prices
        finally: driver.quit()

    def generate_dashboard(self, data):
        brand_green = "#B5EBBF"
        price_display = data['price'] if data['price'] > 0 else 0.01 # מונע חילוק ב-0
        roi = ((1 / price_display) - 1) * 100 if data['price'] > 0 else 0
        
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
            <title>IDOL ORACLE v7.1</title>
            <style>
                body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 20px; }}
                .container {{ max-width: 800px; margin: auto; }}
                .card {{ background: #111; border-radius: 20px; padding: 25px; margin-bottom: 20px; border: 1px solid #222; }}
                .main-temp {{ font-size: 80px; color: {brand_green}; font-weight: 900; text-align: center; }}
                .prob-bar {{ height: 10px; background: #222; border-radius: 5px; margin: 10px 0; overflow: hidden; }}
                .prob-fill {{ height: 100%; background: {brand_green}; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td, th {{ padding: 12px; border-bottom: 1px solid #222; text-align: right; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 style="text-align:center; color:{brand_green}">IDOL ORACLE</h1>
                <p style="text-align:center; color:#888;">לונדון (LHR) | 17 באפריל, 2026</p>

                <div class="card">
                    <div class="main-temp">{data['avg']:.2f}°C</div>
                    <p style="text-align:center; color:#aaa;">ממוצע משוקלל (כולל ECMWF)</p>
                </div>

                <div class="card">
                    <h3>🎯 הסתברות סטטיסטית</h3>
                    { "".join([f'<div>{t}°C ({p:.0f}%)<div class="prob-bar"><div class="prob-fill" style="width:{p}%"></div></div></div>' for t,p in range_probs.items()]) }
                </div>

                <div class="card">
                    <h3>📊 פירוט מודלים</h3>
                    <table>
                        <thead><tr><th>מודל</th><th>תחזית</th><th>משקל</th></tr></thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>

                <div class="card" style="background:{brand_green}; color:#000;">
                    <h3 style="margin:0;">💰 ניתוח פולימרקט</h3>
                    <p>מחיר ל-{data['target']}: <strong>{data['price']:.2f}¢</strong></p>
                    <p style="font-size:24px; font-weight:bold;">ROI פוטנציאלי: {roi:.1f}%</p>
                </div>
            </div>
        </body>
        </html>
        """
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)

    def run_cycle(self):
        meteo = self.fetch_data()
        if not meteo: return
        market = self.fetch_market()
        
        # מיפוי מפורש כדי לוודא ששום מודל לא נשמט
        points = {}
        d = meteo['daily']
        if 'temperature_2m_max_ecmwf_ifs04' in d: points['ECMWF'] = d['temperature_2m_max_ecmwf_ifs04'][0]
        if 'temperature_2m_max_ukmo_seamless' in d: points['UKMO'] = d['temperature_2m_max_ukmo_seamless'][0]
        if 'temperature_2m_max_icon_seamless' in d: points['ICON'] = d['temperature_2m_max_icon_seamless'][0]
        if 'temperature_2m_max_meteofrance_seamless' in d: points['MeteoFrance'] = d['temperature_2m_max_meteofrance_seamless'][0]
        if 'temperature_2m_max_gfs_seamless' in d: points['GFS'] = d['temperature_2m_max_gfs_seamless'][0]

        points = {k: v for k, v in points.items() if v is not None}
        if not points: return

        total_weight = sum(self.weights.get(n, 0.05) for n in points.keys())
        avg = sum(t * self.weights.get(n, 0.05) for n, t in points.items()) / total_weight
        target = f"{int(round(avg))}°C"
        
        self.generate_dashboard({
            'avg': avg, 'target': target, 'price': market.get(target, 0),
            'time': datetime.now().strftime('%H:%M'), 'models': points
        })

if __name__ == "__main__":
    URL = "https://polymarket.com/event/highest-temperature-in-london-on-april-17-2026"
    IdolUltraOracle(URL).run_cycle()
