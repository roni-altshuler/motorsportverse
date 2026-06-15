"""
weather_api.py — Real-Time Weather Integration
===============================================
Fetches real-time weather forecasts for F1 circuits using the
Open-Meteo free API (no API key required).

Provides:
  - Current weather for race day
  - Rain probability and temperature for model features
  - Historical weather comparison

The module gracefully falls back to static estimates from
export_website_data.GP_WEATHER when the API is unavailable.

Usage:
    from weather_api import WeatherService
    ws = WeatherService()
    forecast = ws.get_race_forecast("Australia", "YYYY-MM-DD")
    # => {"rain_probability": 0.12, "temperature_c": 26, "humidity": 55, ...}
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Optional

# Circuit GPS coordinates for weather API lookups
CIRCUIT_COORDINATES: dict[str, dict] = {
    "Australia":      {"lat": -37.8497, "lon": 144.9680, "timezone": "Australia/Melbourne"},
    "China":          {"lat": 31.3389,  "lon": 121.2198, "timezone": "Asia/Shanghai"},
    "Japan":          {"lat": 34.8431,  "lon": 136.5407, "timezone": "Asia/Tokyo"},
    "Bahrain":        {"lat": 26.0325,  "lon": 50.5106,  "timezone": "Asia/Bahrain"},
    "Saudi Arabia":   {"lat": 21.6319,  "lon": 39.1044,  "timezone": "Asia/Riyadh"},
    "Miami":          {"lat": 25.9581,  "lon": -80.2389, "timezone": "America/New_York"},
    "Emilia Romagna": {"lat": 44.3439,  "lon": 11.7167,  "timezone": "Europe/Rome"},
    "Monaco":         {"lat": 43.7347,  "lon": 7.4206,   "timezone": "Europe/Monaco"},
    "Spain":          {"lat": 41.5700,  "lon": 2.2611,   "timezone": "Europe/Madrid"},
    "Canada":         {"lat": 45.5000,  "lon": -73.5228, "timezone": "America/Toronto"},
    "Austria":        {"lat": 47.2197,  "lon": 14.7647,  "timezone": "Europe/Vienna"},
    "Great Britain":  {"lat": 52.0786,  "lon": -1.0169,  "timezone": "Europe/London"},
    "Belgium":        {"lat": 50.4372,  "lon": 5.9714,   "timezone": "Europe/Brussels"},
    "Hungary":        {"lat": 47.5789,  "lon": 19.2486,  "timezone": "Europe/Budapest"},
    "Netherlands":    {"lat": 52.3888,  "lon": 4.5409,   "timezone": "Europe/Amsterdam"},
    "Italy":          {"lat": 45.6156,  "lon": 9.2811,   "timezone": "Europe/Rome"},
    "Azerbaijan":     {"lat": 40.3725,  "lon": 49.8533,  "timezone": "Asia/Baku"},
    "Singapore":      {"lat": 1.2914,   "lon": 103.8644, "timezone": "Asia/Singapore"},
    "United States":  {"lat": 30.1328,  "lon": -97.6411, "timezone": "America/Chicago"},
    "Mexico":         {"lat": 19.4042,  "lon": -99.0907, "timezone": "America/Mexico_City"},
    "Brazil":         {"lat": -23.7014, "lon": -46.6969, "timezone": "America/Sao_Paulo"},
    "Las Vegas":      {"lat": 36.1147,  "lon": -115.1728,"timezone": "America/Los_Angeles"},
    "Qatar":          {"lat": 25.4890,  "lon": 51.4542,  "timezone": "Asia/Qatar"},
    "Abu Dhabi":      {"lat": 24.4672,  "lon": 54.6031,  "timezone": "Asia/Dubai"},
}

# Static fallbacks (matching GP_WEATHER in export_website_data.py)
STATIC_WEATHER: dict[str, dict] = {
    "Australia":      {"rain": 0.10, "temp": 24},
    "China":          {"rain": 0.15, "temp": 18},
    "Japan":          {"rain": 0.20, "temp": 16},
    "Bahrain":        {"rain": 0.02, "temp": 32},
    "Saudi Arabia":   {"rain": 0.02, "temp": 28},
    "Miami":          {"rain": 0.15, "temp": 30},
    "Emilia Romagna": {"rain": 0.20, "temp": 22},
    "Monaco":         {"rain": 0.10, "temp": 22},
    "Spain":          {"rain": 0.05, "temp": 28},
    "Canada":         {"rain": 0.25, "temp": 20},
    "Austria":        {"rain": 0.30, "temp": 22},
    "Great Britain":  {"rain": 0.35, "temp": 18},
    "Belgium":        {"rain": 0.40, "temp": 17},
    "Hungary":        {"rain": 0.15, "temp": 30},
    "Netherlands":    {"rain": 0.30, "temp": 18},
    "Italy":          {"rain": 0.10, "temp": 26},
    "Azerbaijan":     {"rain": 0.05, "temp": 22},
    "Singapore":      {"rain": 0.20, "temp": 30},
    "United States":  {"rain": 0.10, "temp": 24},
    "Mexico":         {"rain": 0.15, "temp": 20},
    "Brazil":         {"rain": 0.30, "temp": 24},
    "Las Vegas":      {"rain": 0.02, "temp": 14},
    "Qatar":          {"rain": 0.02, "temp": 28},
    "Abu Dhabi":      {"rain": 0.02, "temp": 28},
}

WEATHER_CACHE_DIR = "weather_cache"


class WeatherService:
    """Fetch real-time weather forecasts for F1 circuits via Open-Meteo API."""

    API_BASE = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, cache_dir: str = WEATHER_CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, gp_key: str, date: str) -> str:
        return os.path.join(self.cache_dir, f"{gp_key}_{date}.json")

    def _load_cache(self, gp_key: str, date: str) -> Optional[dict]:
        path = self._cache_path(gp_key, date)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                cached = json.load(f)
            # Cache valid for 6 hours
            cached_at = datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
            if datetime.now() - cached_at > timedelta(hours=6):
                return None
            return cached
        except Exception:
            return None

    def _save_cache(self, gp_key: str, date: str, data: dict):
        data["cached_at"] = datetime.now().isoformat()
        path = self._cache_path(gp_key, date)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_race_forecast(self, gp_key: str, race_date: str) -> dict:
        """Get weather forecast for a race.

        Parameters
        ----------
        gp_key : str
            GP key (e.g. "Australia", "Monaco")
        race_date : str
            ISO date string (e.g. "YYYY-MM-DD")

        Returns
        -------
        dict with keys:
            rain_probability : float (0.0 - 1.0)
            temperature_c : float
            humidity : float (%)
            wind_speed_kmh : float
            wind_direction : int (degrees)
            cloud_cover : int (%)
            weather_code : int (WMO code)
            weather_description : str
            source : str ("api" | "cache" | "static")
            forecast_detail : list[dict] (hourly breakdown for race window)
        """
        # Check cache first
        cached = self._load_cache(gp_key, race_date)
        if cached and cached.get("source") in ("api", "cache"):
            cached["source"] = "cache"
            return cached

        # Try API
        coords = CIRCUIT_COORDINATES.get(gp_key)
        if not coords:
            return self._static_fallback(gp_key)

        try:
            result = self._fetch_from_api(coords, race_date, gp_key)
            self._save_cache(gp_key, race_date, result)
            return result
        except Exception as e:
            print(f"  ⚠️  Weather API failed for {gp_key}: {e}")
            return self._static_fallback(gp_key)

    def _fetch_from_api(self, coords: dict, race_date: str, gp_key: str) -> dict:
        """Fetch weather data from Open-Meteo API."""
        lat = coords["lat"]
        lon = coords["lon"]
        tz  = coords["timezone"]

        # Request hourly data for the race date (14:00-17:00 local = typical race window)
        url = (
            f"{self.API_BASE}?"
            f"latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,"
            f"precipitation,wind_speed_10m,wind_direction_10m,cloud_cover,weather_code"
            f"&daily=precipitation_probability_max,temperature_2m_max,temperature_2m_min"
            f"&timezone={tz}"
            f"&start_date={race_date}&end_date={race_date}"
        )

        req = urllib.request.Request(url, headers={"User-Agent": "F1Predictions/3.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Extract race-window hours (14:00-17:00 local time = typical F1 race start)
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        humidity = hourly.get("relative_humidity_2m", [])
        rain_probs = hourly.get("precipitation_probability", [])
        precip = hourly.get("precipitation", [])
        wind_speed = hourly.get("wind_speed_10m", [])
        wind_dir = hourly.get("wind_direction_10m", [])
        cloud = hourly.get("cloud_cover", [])
        weather_codes = hourly.get("weather_code", [])

        # Find race window (14:00-17:00)
        race_indices = []
        for i, t in enumerate(times):
            hour = int(t.split("T")[1].split(":")[0])
            if 14 <= hour <= 17:
                race_indices.append(i)

        # Fall back to afternoon hours if race window not found
        if not race_indices:
            race_indices = list(range(min(12, len(times)), min(18, len(times))))

        if not race_indices:
            race_indices = list(range(len(times)))

        # Aggregate race window
        def _safe_avg(lst, indices):
            vals = [lst[i] for i in indices if i < len(lst) and lst[i] is not None]
            return sum(vals) / len(vals) if vals else 0

        def _safe_max(lst, indices):
            vals = [lst[i] for i in indices if i < len(lst) and lst[i] is not None]
            return max(vals) if vals else 0

        avg_temp = _safe_avg(temps, race_indices)
        avg_humidity = _safe_avg(humidity, race_indices)
        max_rain_prob = _safe_max(rain_probs, race_indices)
        total_precip = sum(precip[i] for i in race_indices
                          if i < len(precip) and precip[i] is not None)
        avg_wind = _safe_avg(wind_speed, race_indices)
        avg_wind_dir = _safe_avg(wind_dir, race_indices)
        avg_cloud = _safe_avg(cloud, race_indices)
        mode_wcode = max(set(weather_codes[i] for i in race_indices
                            if i < len(weather_codes)),
                        key=lambda x: sum(1 for i in race_indices
                                         if i < len(weather_codes)
                                         and weather_codes[i] == x)) \
            if race_indices and weather_codes else 0

        # Build hourly detail for race window
        forecast_detail = []
        for i in race_indices:
            if i < len(times):
                forecast_detail.append({
                    "time": times[i] if i < len(times) else "",
                    "temperature_c": temps[i] if i < len(temps) else None,
                    "rain_probability": (rain_probs[i] / 100.0
                                        if i < len(rain_probs) and rain_probs[i] is not None
                                        else 0),
                    "precipitation_mm": precip[i] if i < len(precip) else 0,
                    "wind_speed_kmh": wind_speed[i] if i < len(wind_speed) else 0,
                    "cloud_cover": cloud[i] if i < len(cloud) else 0,
                })

        return {
            "rain_probability": round(max_rain_prob / 100.0, 2),
            "temperature_c": round(avg_temp, 1),
            "humidity": round(avg_humidity, 1),
            "wind_speed_kmh": round(avg_wind, 1),
            "wind_direction": int(avg_wind_dir),
            "cloud_cover": int(avg_cloud),
            "precipitation_mm": round(total_precip, 1),
            "weather_code": mode_wcode,
            "weather_description": _wmo_description(mode_wcode),
            "source": "api",
            "gp_key": gp_key,
            "race_date": race_date,
            "forecast_detail": forecast_detail,
        }

    def _static_fallback(self, gp_key: str) -> dict:
        """Return static weather estimates when API unavailable."""
        static = STATIC_WEATHER.get(gp_key, {"rain": 0.10, "temp": 22})
        return {
            "rain_probability": static["rain"],
            "temperature_c": static["temp"],
            "humidity": 60.0,
            "wind_speed_kmh": 15.0,
            "wind_direction": 0,
            "cloud_cover": 30,
            "precipitation_mm": 0.0,
            "weather_code": 0,
            "weather_description": "Estimated (API unavailable)",
            "source": "static",
            "gp_key": gp_key,
            "forecast_detail": [],
        }

    def get_all_race_forecasts(self, calendar: dict) -> dict:
        """Fetch forecasts for all races in the calendar.

        Parameters
        ----------
        calendar : dict
            CALENDAR format: {round_num: {"gp_key": ..., "date": ...}}

        Returns
        -------
        dict mapping gp_key → forecast dict
        """
        forecasts = {}
        for rnd, info in sorted(calendar.items()):
            gp_key = info["gp_key"]
            date = info["date"]
            print(f"  🌤️  Fetching weather for R{rnd} {gp_key} ({date})...")
            forecasts[gp_key] = self.get_race_forecast(gp_key, date)
        return forecasts


def _wmo_description(code: int) -> str:
    """Convert WMO weather code to human-readable description."""
    WMO_CODES = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        66: "Light freezing rain", 67: "Heavy freezing rain",
        71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
        77: "Snow grains",
        80: "Slight rain showers", 81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return WMO_CODES.get(code, f"Unknown (code {code})")


def export_weather_for_website(calendar: dict, out_path: str = None) -> dict:
    """Generate weather data JSON for the website.

    Parameters
    ----------
    calendar : dict
        CALENDAR format
    out_path : str, optional
        Path to write weather.json. Defaults to website/public/data/weather.json

    Returns
    -------
    dict of all forecasts
    """
    if out_path is None:
        out_path = os.path.join("website", "public", "data", "weather.json")

    ws = WeatherService()
    forecasts = ws.get_all_race_forecasts(calendar)

    # Build website-compatible format
    weather_data = []
    for rnd, info in sorted(calendar.items()):
        gp_key = info["gp_key"]
        forecast = forecasts.get(gp_key, ws._static_fallback(gp_key))
        weather_data.append({
            "round": rnd,
            "gpKey": gp_key,
            "name": info["name"],
            "date": info["date"],
            "rainProbability": forecast["rain_probability"],
            "temperatureC": forecast["temperature_c"],
            "humidity": forecast.get("humidity", 60),
            "windSpeedKmh": forecast.get("wind_speed_kmh", 15),
            "windDirection": forecast.get("wind_direction", 0),
            "cloudCover": forecast.get("cloud_cover", 30),
            "precipitationMm": forecast.get("precipitation_mm", 0),
            "weatherDescription": forecast.get("weather_description", ""),
            "source": forecast.get("source", "static"),
            "forecastDetail": forecast.get("forecast_detail", []),
        })

    output = {"lastUpdated": datetime.now().isoformat(), "races": weather_data}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"✅ Weather data → {out_path}")

    api_count = sum(1 for w in weather_data if w["source"] == "api")
    cache_count = sum(1 for w in weather_data if w["source"] == "cache")
    static_count = sum(1 for w in weather_data if w["source"] == "static")
    print(f"   Sources: {api_count} API, {cache_count} cached, {static_count} static")

    return output


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from f1_prediction_utils import CALENDAR, SEASON_YEAR

    parser = argparse.ArgumentParser(description="Fetch F1 race weather data")
    parser.add_argument("--gp", type=str, help="GP key (e.g. Australia)")
    parser.add_argument("--date", type=str, help="Race date (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help=f"Fetch all {SEASON_YEAR} races")
    parser.add_argument("--export", action="store_true",
                        help="Export weather.json for website")
    args = parser.parse_args()

    if args.export or args.all:
        export_weather_for_website(CALENDAR)
    elif args.gp:
        ws = WeatherService()
        default_date = next(iter(CALENDAR.values()))["date"] if CALENDAR else datetime.now().date().isoformat()
        date = args.date or default_date
        forecast = ws.get_race_forecast(args.gp, date)
        print(json.dumps(forecast, indent=2))
    else:
        # Default: show weather for next race
        ws = WeatherService()
        for rnd, info in sorted(CALENDAR.items()):
            forecast = ws.get_race_forecast(info["gp_key"], info["date"])
            status = "🌧️" if forecast["rain_probability"] > 0.5 else "☀️"
            print(f"  R{rnd:02d} {info['gp_key']:16s} {status} "
                  f"Rain: {forecast['rain_probability']:.0%}  "
                  f"Temp: {forecast['temperature_c']:.0f}°C  "
                  f"({forecast.get('source', 'unknown')})")
            break
