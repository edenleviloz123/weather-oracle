import requests
from datetime import datetime
import random

def run_bot():
    # הגדרות מיקום ותאריך
    lat, lon = 51.5048, 0.0495
    target_date = "2026-04-17"
    
    # 1. שקלול המודלים (The Core Logic)
    weights = {
        'ECMWF': 0.35,
        'UKMO': 0.25,
        'ICON': 0.15,
        'GFS': 0.15,
        'MeteoFrance': 0.10
    }
    
    url_weather = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max_ecmwf_ifs04,temperature_2m_max_ukmo_seamless,temperature_2m_max_icon_seamless,temperature_2m_max_meteofrance_seamless,temperature_2m_max_gfs_seamless&timezone=Europe%2FLondon&start_date={target_date}&end_date={target_date}"
    
    try:
        w_data = requests.get(url_weather, timeout=15).json()['daily']
        mapping = {
            'ECMWF': 'temperature_2m_max_ecmwf_ifs04',
            'UKMO': 'temperature_2m_max_ukmo_seamless',
            'ICON': 'temperature_2m_max_icon_seamless',
            'GFS': 'temperature_2m_max_gfs_seamless',
            '
