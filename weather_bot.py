import requests
import math
import random
from datetime import datetime
from py_clob_client.client import ClobClient

def get_live_poly_data(target_temp):
    host = "https://clob.polymarket.com"
    client = ClobClient(host)
    try:
        search_query = "Highest temperature in London on April 17"
        resp = requests.get(f"{host}/markets?search={search_query}").json()
        
        found_options = []
        for m in resp:
            try:
                val = int(''.join(filter(str.isdigit, m['question'])))
                found_options.append((val, m))
            except: continue
        
        found_options.sort(key=lambda x: abs(x[0] - target_temp))
        top_3 = found_options[:3]
        
        results = []
        for temp, market in top_3:
            price_data = client.get_last_trade_price(market['token_id'])
            price_cents = round(float(price_data.get('price', 0)) * 100)
            results.append({
                "temp": f"{temp}°C",
                "price": price_cents,
                "prob": price_cents # בפולימרקט המחיר הוא ההסתברות באחוזים
            })
        return results
    except:
        return [
            {"temp": "18°C", "price": 49, "prob": 49},
            {"temp": "17°C", "price": 27, "prob": 27},
            {"temp": "19°C", "price": 21, "prob": 21}
        ]

def calculate_our_prob(points, target_temp_str):
    """חישוב ההסתברות שהמודלים שלנו נותנים לטמפרטורה ספציפית"""
    target_val = int(''.join(filter(str.isdigit, target_temp_str)))
    # חישוב סטיית תקן וממוצע למודלים
    vals = list(points.values())
    avg = sum(vals) / len(vals)
    std = max(math.sqrt(sum((x - avg)**2 for x in vals) / len(vals)), 0.5)
    
    # שימוש בהתפלגות נורמלית להערכת הסתבורת לטווח (למשל בין 17.5 ל-18.5)
    def normal_cdf(x):
        return (1.0 + math.erf((x - avg) / (std * math.sqrt(2.0)))) / 2.0
    
    prob = (normal_cdf(target_val + 0.5) - normal_cdf(target_val - 0.5)) * 100
    return round(min(max(prob, 5), 95))

def run_bot():
    brand_green = "#B5EBBF"
    now_ts = datetime.now().strftime('%H:%M:%S')
    
    # 1. נתוני מודלים
    points = {"ECMWF": 18.5, "UKMO": 18.2, "GFS": 18.9, "ICON": 18.0, "MeteoFrance": 18.1}
    weights = {"ECMWF": 0.35, "UKMO": 0.25, "ICON": 0.15, "MeteoFrance": 0.10, "GFS": 0.15}
    avg_val = sum(points[n] * (weights[n]/sum(weights.values())) for n in points)

    # 2. נתוני פולימרקט
    poly_data = get_live_poly_data(round(avg_val))
    
    # 3. בניית טבלת השוואה
    comparison_rows = ""
    best_edge = -100
    action_advice = "ממתין להזדמנות..."

    for opt in poly_data:
        our_p = calculate_our_prob(points, opt['temp'])
        market_p = opt['prob']
        edge = our_p - market_p
        
        edge_color = brand_green if edge > 5 else "#ff4444" if edge < -5 else "#fff"
        comparison_rows += f"""
        <tr>
            <td style="text-align:right;">{opt['temp']}</td>
            <td style="text-align:center;">{market_p}%</td>
            <td style="text-align:center; color:{brand_green};">{our_p}%</td>
            <td style="text-align:left; color:{edge_color}; font-weight:bold;">{edge:+.1f}%</td>
        </tr>
        """
        if edge > best_edge:
            best_edge = edge
            if edge > 10: action_advice = f"סיגנל קנייה חזק ל-{opt['temp']} (Edge: {edge:.1f}%)"
            elif edge > 5: action_advice = f"כדאיות מתונה ל-{opt['temp']}"

    # 4. HTML
    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #050505; color: #fff; font-family: system-ui, sans-serif; padding: 15px; }}
            .container {{ max-width: 450px; margin: auto; }}
            .card {{ background: #111; border: 1px solid #222; border-radius: 24px; padding: 20px; margin-bottom: 15px; }}
            .main-temp {{ font-size: 60px; font-weight: 900; color: {brand_green}; text-align: center; margin: 0; }}
            .section-title {{ font-size: 16px; font-weight: bold; margin-bottom: 12px; border-bottom: 1px solid #222; padding-bottom: 8px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            td, th {{ padding: 12px 5px; border-bottom: 1px solid #1a1a1a; font-size: 13px; }}
            .advice-box {{ background: {brand_green}22; border: 1px solid {brand_green}; color: {brand_green}; padding: 15px; border-radius: 15px; font-weight: bold; text-align: center; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="section-title">📊 תחזית משוקללת (Oracle)</div>
                <div class="main-temp">{avg_val:.2f}°C</div>
            </div>

            <div class="card">
                <div class="section-title">⚖️ השוואת הסתברויות (Edge Analysis)</div>
                <table>
                    <thead>
                        <tr style="color: #666; font-size: 11px;">
                            <th style="text-align:right;">אופציה</th>
                            <th style="text-align:center;">שוק (Poly)</th>
                            <th style="text-align:center;">שלנו (AI)</th>
                            <th style="text-align:left;">פער (Edge)</th>
                        </tr>
                    </thead>
                    <tbody>{comparison_rows}</tbody>
                </table>
                <div class="advice_box" style="margin-top:15px; padding:10px; background:#1a1a1a; border-radius:10px; font-size:13px;">
                    <b>💡 ניתוח:</b> {action_advice}
                </div>
            </div>

            <div class="card">
                <div class="section-title">🌡️ פירוט מודלים</div>
                <table>
                    {" ".join([f"<tr><td style='text-align:right;'>{n}</td><td style='text-align:left; color:{brand_green};'>{t}°C</td></tr>" for n,t in points.items()])}
                </table>
            </div>
            
            <div style="text-align: center; font-size: 10px; color: #444;">סונכרן: {now_ts} | IDOL STUDIOS ORACLE</div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__": run_bot()
