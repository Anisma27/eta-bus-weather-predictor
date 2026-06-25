from flask import Flask, render_template, request, jsonify
import pandas as pd
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# =====================
# Weather API
# =====================
WEATHER_API_KEY = "75df83fc0431d18c148aab74e2781b6b"
print("API KEY =", WEATHER_API_KEY, flush=True)
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

# Simple in-memory cache so we don't hammer the API for the same city
# {city: (weather_string, timestamp)}
_weather_cache = {}
CACHE_TTL_SECONDS = 600  # 10 minutes

# =====================
# Load Dataset
# =====================
df = pd.read_csv("Pan-India_Bus_Routes.csv")

# Create route column
df["route"] = df["From"].astype(str) + " -> " + df["To"].astype(str)

# Clean distance column
df["distance_km"] = (
    df["Distance"]
    .astype(str)
    .str.extract(r"(\d+\.?\d*)")[0]
    .astype(float)
)

# Convert duration to minutes
def duration_to_minutes(x):
    try:
        x = str(x).strip()

        if ":" in x:
            parts = x.split(":")

            if len(parts) == 3:
                # Dataset format is D:H:M (days:hours:minutes)
                d, h, m = parts
                return int(d) * 1440 + int(h) * 60 + int(m)

            if len(parts) == 2:
                # Fallback for plain H:M format, just in case
                h, m = parts
                return int(h) * 60 + int(m)

        nums = [int(i) for i in x.split() if i.isdigit()]

        if len(nums) == 2:
            return nums[0] * 60 + nums[1]

        if len(nums) == 1:
            return nums[0]

    except:
        pass

    return 120

df["travel_time_min"] = df["Duration"].apply(duration_to_minutes)

routes = sorted(df["route"].unique())

# Separate From/To pairs for the two-box search UI on the frontend.
# Backend logic (predict_eta, get_weather) still uses the combined
# "route" string exactly as before — this is purely for filtering.
route_pairs = (
    df[["From", "To", "route"]]
    .drop_duplicates()
    .sort_values(["From", "To"])
    .rename(columns={"From": "from_city", "To": "to_city"})
    .to_dict(orient="records")
)

# =====================
# Weather
# =====================
def get_weather(city):
    city = city.strip()

    # Check cache first
    cached = _weather_cache.get(city)
    if cached:
        weather_str, ts = cached
        if (datetime.now() - ts).total_seconds() < CACHE_TTL_SECONDS:
            print(f"Weather cache hit for {city}: {weather_str}", flush=True)
            return weather_str

    try:
        print("City:", city, flush=True)
        print("API KEY:", WEATHER_API_KEY, flush=True)

        params = {
            "q": city,  # Try without ,IN first
            "appid": WEATHER_API_KEY,
            "units": "metric"
        }

        r = requests.get(
            WEATHER_URL,
            params=params,
            timeout=10
        )

        print("Status:", r.status_code, flush=True)
        print("Response:", r.text, flush=True)

        if r.status_code == 401:
            # Bad/inactive API key
            result = "Weather Unavailable (invalid API key)"
            print("ERROR: API key rejected. New keys can take up to 2 hours to activate.", flush=True)
            return result

        if r.status_code == 404:
            # City not found - try appending ",IN" as a fallback
            print(f"City '{city}' not found, retrying with ',IN' suffix", flush=True)
            params["q"] = f"{city},IN"
            r = requests.get(WEATHER_URL, params=params, timeout=10)
            print("Retry Status:", r.status_code, flush=True)
            print("Retry Response:", r.text, flush=True)

            if r.status_code != 200:
                result = "Weather Unavailable (city not found)"
                return result

        if r.status_code != 200:
            return "Weather Unavailable"

        data = r.json()

        weather = data["weather"][0]["main"]
        temp = data["main"]["temp"]

        result = f"{weather} ({temp}°C)"

        # Cache successful result
        _weather_cache[city] = (result, datetime.now())

        return result

    except requests.exceptions.Timeout:
        print("Weather Error: Request timed out", flush=True)
        return "Weather Unavailable (timeout)"

    except requests.exceptions.ConnectionError:
        print("Weather Error: Connection failed - check internet connection", flush=True)
        return "Weather Unavailable (no connection)"

    except Exception as e:
        print("Weather Error:", e, flush=True)
        return "Weather Error"

# =====================
# Helper: format minutes as "Xh Ym"
# =====================
def format_hours_minutes(total_minutes):
    total_minutes = round(total_minutes)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"

# =====================
# ETA Calculation
# =====================
def predict_eta(route, traffic):

    route_df = df[df["route"] == route]

    if route_df.empty:
        return None, None, None

    avg_time = route_df["travel_time_min"].mean()

    traffic_factor = {
        "Low": 1.0,
        "Medium": 1.2,
        "High": 1.5
    }

    eta = avg_time * traffic_factor.get(traffic, 1.0)

    arrival = (
        datetime.now()
        + timedelta(minutes=eta)
    )

    eta_formatted = format_hours_minutes(eta)

    return round(eta, 2), eta_formatted, arrival.strftime("%d-%m-%Y %H:%M")

# =====================
# Weather Route (called by frontend JS, e.g. on dropdown change)
# =====================
@app.route("/get_weather")
def weather_route():
    route = request.args.get("route", "")

    if not route or "->" not in route:
        print("Invalid route param for /get_weather:", route, flush=True)
        return jsonify({"weather": "Weather Unavailable"})

    # Extract destination city
    city = route.split("->")[-1].strip()

    print("Route:", route, flush=True)
    print("Destination City:", city, flush=True)

    weather = get_weather(city)

    return jsonify({"weather": weather})

# =====================
# Home
# =====================
@app.route("/", methods=["GET", "POST"])
def home():

    result = None

    if request.method == "POST":

        route = request.form.get("route")
        traffic = request.form.get("traffic")

        if not route or not traffic:
            print("Missing route or traffic in form submission", flush=True)
        else:
            eta, eta_formatted, arrival = predict_eta(route, traffic)

            if eta is None:
                print(f"No data found for route: {route}", flush=True)
            else:
                weather = get_weather(
                    route.split("->")[-1].strip()
                )

                result = {
                    "route": route,
                    "traffic": traffic,
                    "eta": eta,
                    "eta_formatted": eta_formatted,
                    "arrival": arrival,
                    "weather": weather
                }

    return render_template(
        "index.html",
        routes=routes,
        route_pairs=route_pairs,
        result=result
    )

if __name__ == "__main__":
    app.run(debug=True)