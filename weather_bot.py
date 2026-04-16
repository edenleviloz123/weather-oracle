import requests
import math
from datetime import datetime
import pytz # חבילה לניהול אזורי זמן

def get_live_poly_data():
    try:
        url = "https://gamma-api.polymarket.com/events?active=true&closed=false&q=London%20temperature%20April%2017"
        response = requests.get(url).json()
        if not response: return None
        
        markets = response[0].get('markets', [])
        results = []
        for m in markets:
            title = m.get('groupItemTitle', "")
            temp_str = title.split('°')[0].split(' ')[-1]
            try:
                temp_val = int(temp_str)
                if temp_val > 50 or temp_val < 10: continue
                prices = eval(m['outcomePrices'])
                price_cents = round(float(prices[0]) * 100)
                results.append({
                    "temp": f"{temp_val}°C",
                    "price": f"{price_cents}¢",
                    "prob": f"{price_cents}%",
                    "val": temp_val,
                    "numeric_prob": price_cents
                })
            except: continue
        results.sort(key=lambda x: x['val'])
        return results if results else None
    except: return None

def calculate_ai_prob(points, target_temp_str):
    target_val = int(''.join(filter(str.isdigit, target_temp_str)))
    vals = list(points.values())
    avg = sum(vals) / len(vals)
    std = max(math.sqrt(sum((x - avg)**2 for x in vals) / len(vals)), 0.6)
    def cdf(x): return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    prob = (cdf(target_val + 0.5) - cdf(target_val - 0.5)) * 100
    return round(min(max(prob, 5), 95))

def run_bot():
    brand_green = "#B5EBBF"
    
    # ניהול זמנים (ישראל ולונדון)
    tz_il = pytz.timezone('Asia/Jerusalem')
    tz_uk = pytz.timezone('Europe/London')
    now_il = datetime.now(tz_il).strftime('%H:%M')
    now_uk = datetime.now(tz_uk).strftime('%H:%M')
    date_str = datetime.now(tz_il).strftime('%d/%m/%Y')

    points = {"ECMWF": 18.5, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.0, "MeteoFrance": 18.1}
    weights = {"ECMWF": 0.35, "UKMO": 0.25, "GFS": 0.15, "ICON": 0.15, "MeteoFrance": 0.10}
    avg_val = sum(points[n] * (weights[n]/sum(weights.values())) for n in points)

    poly_data = get_live_poly_data()
    status_label = "LIVE SYNC" if poly_data else "OFFLINE"
    if not poly_data:
        poly_data = [{"temp": "17°C", "price": "27¢", "prob": "27%", "numeric_prob": 27},
                     {"temp": "18°C", "price": "49¢", "prob": "49%", "numeric_prob": 49},
                     {"temp": "19°C", "price": "21¢", "prob": "21%", "numeric_prob": 21}]
    
    comparison_rows = ""
    arbitrage_signal = "NO"
    for opt in poly_data:
        our_p = calculate_ai_prob(points, opt['temp'])
        edge = our_p - opt['numeric_prob']
        color = brand_green if edge > 5 else "#ff4444" if edge < -5 else "#fff"
        if edge > 10: arbitrage_signal = "YES"
        comparison_rows += f"""
        <tr>
            <td style="text-align:right; padding:12px;">{opt['temp']}</td>
            <td style="text-align:center;">{opt['price']} | {opt['prob']}</td>
            <td style="text-align:center; color:{brand_green};">{our_p}%</td>
            <td style="text-align:left; color:{color}; font-weight:bold;">{edge:+.1f}%</td>
        </tr>"""

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 10px; }}
            .container {{ max-width: 480px; margin: auto; }}
            .card {{ background: #111; border: 1px solid #222; border-radius: 20px; padding: 20px; margin-bottom: 15px; }}
            .title {{ font-size: 14px; color: #777; margin-bottom: 10px; border-bottom: 1px solid #222; padding-bottom: 5px; font-weight: bold; }}
            .main-val {{ font-size: 50px; font-weight: 900; color: {brand_green}; text-align: center; }}
            .desc {{ font-size: 12px; color: #999; margin-top: 10px; background: #1a1a1a; padding: 10px; border-radius: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            td, th {{ font-size: 12px; border-bottom: 1px solid #1a1a1a; padding: 8px 0; }}
            .signal-box {{ text-align: center; padding: 15px; border-radius: 15px; border: 2px solid {brand_green if arbitrage_signal == "YES" else "#333"}; margin-top: 10px; }}
            .time-footer {{ text-align: center; font-size: 11px; color: #555; margin-top: 20px; line-height: 1.6; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div style="font-size:10px; color:{brand_green}; float:left;">{status_label}</div>
                <div class="title">🎯 תחזית משוקללת (Oracle)</div>
                <div class="main-val">{avg_val:.2f}°C</div>
                <div class="desc">ממוצע המודלים המשוקלל. דיוק גבוה מבוסס ECMWF ו-UKMO.</div>
            </div>

            <div class="card">
                <div class="title">⚖️ ניתוח ארביטראז' (Edge)</div>
                <div class="signal-box">
                    <div style="font-size: 10px; color: #777;">הזדמנות קנייה (Arbitrage)</div>
                    <div style="font-size: 24px; font-weight: bold; color: {brand_green if arbitrage_signal == "YES" else "#fff"};">{arbitrage_signal}</div>
                </div>
                <table>
                    <tr style="color:#555; font-size:10px;">
                        <th style="text-align:right;">טמפ'</th>
                        <th style="text-align:center;">מחיר | סיכוי שוק</th>
                        <th style="text-align:center;">סיכוי AI</th>
                        <th style="text-align:left;">פער (Edge)</th>
                    </tr>
                    {comparison_rows}
                </table>
                <div class="desc">מספר ירוק חיובי מציין שהשוק זול יותר מהסיכוי שהמודלים חוזים.</div>
            </div>

            <div class="card">
                <div class="title">🌡️ פירוט מודלים</div>
                <table>
                    {" ".join([f"<tr><td>{n}</td><td style='color:{brand_green}; text-align:center;'>{t}°C</td><td style='text-align:left; color:#555;'>משקל: {int(weights[n]*100)}%</td></tr>" for n,t in points.items()])}
                </table>
            </div>

            <div class="time-footer">
                IDOL STUDIOS | {date_str} <br>
                🕒 ישראל: {now_il} | 🕒 לונדון: {now_uk} <br>
                <span style="font-size: 9px; opacity: 0.5;">THOUSANDS OF LOYAL ANGELS</span>
            </div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_bot()
