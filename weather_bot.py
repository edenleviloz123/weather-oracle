import requests
import time
import re
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

class IdolUltraOracle:
    def __init__(self, ow_api_key, market_url):
        self.ow_api_key = ow_api_key
        self.market_url = market_url
        self.lat, self.lon = 51.5048, 0.0495
        self.weights = {"ECMWF": 0.35, "UKMO": 0.25, "ICON": 0.15, "MeteoFrance": 0.10, "GFS": 0.10, "OpenWeather": 0.05}
        self.history_avg = 15.5 

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
        conf_score = (data['agreement'] * 0.7) + (30 if data['clouds'] > 50 else 10)
        
        reasons = []
        if data['avg'] > self.history_avg:
            reasons.append(f"התחזית גבוהה ב-{data['avg']-self.history_avg:.1f}°C מהממוצע ההיסטורי.")
        if data.get('agreement', 0) >= 70:
            reasons.append("קונצנזוס רחב בין המודלים.")

        rows = "".join([f"<tr><td>{n}</td><td>{t:.1f}°C</td><td>{self.weights.get(n,0)*100:.0f}%</td></tr>" for n, t in data['models'].items()])

        html = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="he">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>IDOL ULTRA DASHBOARD</title>
            <style>
                body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 20px; }}
                .container {{ max-width: 700px; margin: auto; }}
                .card {{ background: #111; border-radius: 20px; padding: 25px; margin-bottom: 20px; border: 1px solid #222; }}
                .main-temp {{ font-size: 72px; color: {brand_green}; font-weight: 900; line-height: 1; }}
                .badge {{ background: {brand_green}; color: #000; padding: 6px 15px; border-radius: 30px; font-weight: bold; font-size: 14px; }}
                .reason-tag {{ border-right: 4px solid {brand_green}; padding-right: 15px; margin-bottom: 15px; font-size: 14px; color: #ccc; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ padding: 12px 5px; border-bottom: 1px solid #1a1a1a; font-size: 14px; }}
                th {{ color: #555; text-align: right; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card" style="text-align: center;">
                    <span class="badge">{data['signal']} | CONFIDENCE: {conf_score:.0f}%</span>
                    <div class="main-temp">{data['avg']:.2f}°C</div>
                    <div style="font-size: 20px; margin-top: 10px;">יעד פולימרקט: <strong style="color:{brand_green}">{data['target']}</strong></div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div class="card">
                        <h3 style="margin:0; color:{brand_green}">ROI</h3>
                        <div style="font-size: 32px; font-weight: bold; margin: 10px 0;">{roi:.1f}%</div>
                    </div>
                    <div class="card">
                        <h3 style="margin:0;">תנאי שטח</h3>
                        <div style="margin-top: 10px; font-size: 14px;">
                            <p>💧 {data['humidity']}% | ☁️ {data['clouds']}% | 🌧️ {data['rain_prob']}%</p>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <h3 style="margin-top:0;">📊 השוואת מודלים</h3>
                    <table>
                        <thead><tr><th>מודל</th><th>תחזית</th><th>משקל</th></tr></thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>
                <p style="text-align: center; color: #333; font-size: 12px;">IDOL ORACLE | {data['time']}</p>
            </div>
        </body>
        </html>
        """
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)

    def run_cycle(self):
        meteo = self.fetch_data()
        if not meteo or 'daily' not in meteo:
            return

        market = self.fetch_market()
        model_map = {"ecmwf_ifs04": "ECMWF", "ukmo_seamless": "UKMO", "icon_seamless": "ICON", "meteofrance_seamless": "MeteoFrance", "gfs_seamless": "GFS"}
        
        # --- התיקון הקריטי ---
        points = {}
        for k, name in model_map.items():
            field = f'temperature_2m_max_{k}'
            if field in meteo['daily'] and meteo['daily'][field][0] is not None:
                points[name] = float(meteo['daily'][field][0])

        if not points:
            print("No valid data points.")
            return

        total_weight = sum(self.weights.get(n, 0.05) for n in points.keys())
        weighted_sum = sum(t * self.weights.get(n, 0.05) for n, t in points.items())
        avg = weighted_sum / total_weight
        # ---------------------

        target = f"{int(round(avg))}°C"
        price = market.get(target, 0)
        votes = [int(round(t)) for t in points.values()]
        agreement = (votes.count(int(round(avg))) / len(votes)) * 100
        
        self.generate_dashboard({
            'avg': avg, 'target': target, 
            'humidity': meteo['daily'].get('relative_humidity_2m_max', [0])[0],
            'clouds': meteo['daily'].get('cloud_cover_max', [0])[0], 
            'rain_prob': meteo['daily'].get('precipitation_probability_max', [0])[0],
            'signal': "BUY" if price < 0.50 else "HOLD",
            'price': price, 'time': datetime.now().strftime('%d/%m %H:%M'), 'models': points, 'agreement': agreement
        })

if __name__ == "__main__":
    API = "e6c511db5ea4dfdef0c71743de948251"
    URL = "https://polymarket.com/event/highest-temperature-in-london-on-april-17-2026"
    agent = IdolUltraOracle(API, URL)
    agent.run_cycle()
