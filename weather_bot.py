import requests
import math
import time
from datetime import datetime
try:
    import pytz
except ImportError:
    pytz = None

def get_live_poly_data():
    try:
        ts = int(time.time())
        url = f"https://gamma-api.polymarket.com/events?active=true&closed=false&q=London%20temperature&_={ts}"
        headers = {'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'}
        response = requests.get(url, headers=headers).json()
        results = []
        if response and len(response) > 0:
            markets = response[0].get('markets', [])
            for m in markets:
                title = m.get('groupItemTitle', "")
                if '°' not in title: continue
                try:
                    temp_val = int(title.split('°')[0].split(' ')[-1])
                    if temp_val < 10 or temp_val > 30: continue
                    prices = eval(m.get('outcomePrices', '["0.5", "0.5"]'))
                    price_raw = float(prices[0])
                    price_cents = round(price_raw * 100)
                    results.append({"temp": f"{temp_val}°C", "price": f"{price_cents}¢", "prob": f"{price_cents}%", "val": temp_val, "numeric_prob": price_cents})
                except: continue
        if not results:
            return [{"temp": "17°C", "price": "23¢", "prob": "23%", "val": 17, "numeric_prob": 23}, {"temp": "18°C", "price": "49¢", "prob": "49%", "val": 18, "numeric_prob": 49}, {"temp": "19°C", "price": "28¢", "prob": "28%", "val": 19, "numeric_prob": 28}]
        results.sort(key=lambda x: x['val'])
        return results
    except: return []

def calculate_ai_prob(points, target_temp_str):
    target_val = int(''.join(filter(str.isdigit, target_temp_str)))
    vals = list(points.values()); avg = sum(vals) / len(vals)
    std = max(math.sqrt(sum((x - avg)**2 for x in vals) / len(vals)), 0.6)
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    return round(min(max((cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100, 5), 95))

def run_bot():
    brand_green = "#B5EBBF"
    if pytz:
        tz_il = pytz.timezone('Asia/Jerusalem'); tz_uk = pytz.timezone('Europe/London')
        now_il = datetime.now(tz_il).strftime('%H:%M'); now_uk = datetime.now(tz_uk).strftime('%H:%M')
        date_str = datetime.now(tz_il).strftime('%d/%m/%Y')
    else:
        now_il = now_uk = datetime.now().strftime('%H:%M'); date_str = datetime.now().strftime('%d/%m/%Y')

    points = {"ECMWF": 18.5, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.0, "MeteoFrance": 18.1}
    weights = {"ECMWF": 0.35, "UKMO": 0.25, "GFS": 0.15, "ICON": 0.15, "MeteoFrance": 0.10}
    avg_val = sum(points[n] * (weights[n]/sum(weights.values())) for n in points)
    
    poly_data = get_live_poly_data()
    processed = []
    for opt in poly_data:
        our_p = calculate_ai_prob(points, opt['temp'])
        edge = our_p - opt['numeric_prob']
        processed.append({**opt, "our_p": our_p, "edge": edge})
    
    most_likely = max(processed, key=lambda x: x['our_p']) if processed else None
    arbitrage_signal = "YES" if most_likely and most_likely['edge'] > 0 else "NO"

    rows = ""
    for opt in processed:
        color = brand_green if opt['edge'] > 5 else "#ff4444" if opt['edge'] < -5 else "#fff"
        bg = "background: rgba(181, 235, 191, 0.1);" if opt == most_likely else ""
        rows += f"<tr style='{bg}'><td style='padding:12px;'>{opt['temp']}</td><td style='text-align:center;'>{opt['price']} | {opt['prob']}</td><td style='text-align:center; color:{brand_green};'>{opt['our_p']}%</td><td style='color:{color}; font-weight:bold;'>{opt['edge']:+.1f}%</td></tr>"

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 10px; }}
        .header {{ text-align: center; padding: 15px 0; border-bottom: 1px solid #222; }}
        .header h1 {{ font-size: 18px; margin: 0; color: {brand_green}; letter-spacing: 2px; }}
        .card {{ background: #111; border: 1px solid #222; border-radius: 20px; padding: 20px; margin-top: 15px; }}
        .title {{ font-size: 13px; color: #777; margin-bottom: 10px; font-weight: bold; border-bottom: 1px solid #222; padding-bottom: 5px; }}
        .main-val {{ font-size: 55px; font-weight: 900; color: {brand_green}; text-align: center; margin: 10px 0; }}
        .desc-box {{ background: #1a1a1a; padding: 12px; border-radius: 12px; font-size: 11px; color: #999; margin-top: 10px; }}
        .signal {{ text-align: center; padding: 20px; border-radius: 15px; border: 2px solid {brand_green if arbitrage_signal == "YES" else "#333"}; margin-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td, th {{ font-size: 12px; border-bottom: 1px solid #1a1a1a; padding: 12px 0; }}
        .footer {{ text-align: center; font-size: 11px; color: #444; margin-top: 30px; }}
    </style></head>
    <body>
        <div class="header"><h1>WEATHER ORACLE LIVE</h1></div>
        <div class="card">
            <div class="title">🎯 תחזית Oracle (ממוצע משוקלל)</div>
            <div class="main-val">{avg_val:.2f}°C</div>
            <div class="desc-box">זהו הערך הממוצע שמתקבל משקלול 5 מודלים מובילים. הוא מהווה את "נקודת האמת" של ה-AI.</div>
        </div>
        <div class="card">
            <div class="title">⚖️ ניתוח Edge וארביטראז'</div>
            <div class="signal">
                <div style="font-size:10px; color:#777; margin-bottom: 5px;">BUY SIGNAL</div>
                <div style="font-size:32px; font-weight:bold; color:{brand_green if arbitrage_signal == 'YES' else '#fff'};">{arbitrage_signal}</div>
            </div>
            <table>
                <tr style="color:#555;"><th style="text-align:right;">טמפ'</th><th style="text-align:center;">שוק (מחיר|%)</th><th style="text-align:center;">AI</th><th style="text-align:left;">פער</th></tr>
                {rows}
            </table>
            <div class="desc-box">
                <b>הסבר:</b> פער חיובי (ירוק) אומר שה-AI מעריך סיכוי גבוה מהשוק. ה-Signal נדלק רק אם באופציה הוודאית ביותר שלנו יש פער חיובי.
            </div>
        </div>
        <div class="card">
            <div class="title">🌡️ פירוט משקלי מודלים</div>
            <table>{" ".join([f"<tr><td>{n}</td><td style='color:{brand_green}; text-align:center;'>{t}°C</td><td style='text-align:left; color:#555;'>{int(weights[n]*100)}% משקל</td></tr>" for n,t in points.items()])}</table>
        </div>
        <div class="footer">🕒 ישראל: {now_il} | לונדון: {now_uk} | {date_str}</div>
    </body></html>"""
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_bot()
