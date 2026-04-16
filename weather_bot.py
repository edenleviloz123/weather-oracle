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
        # משקלים אסטרטגיים לחישוב ממוצע
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
        
        # חישוב הסתברויות לטווח של 3 מעלות (הממוצע וסביבתו)
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

                <div class="card" style="text-align: center
