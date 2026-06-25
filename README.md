# 🚍 Pan-India Bus ETA & Weather Predictor

A Flask-based web application that predicts bus arrival times (ETA) using historical route data, traffic conditions, and real-time weather information.

## Features

* Predicts Estimated Time of Arrival (ETA) for bus routes
* Supports multiple Pan-India routes
* Traffic-based ETA adjustment
* Real-time weather integration using OpenWeather API
* User-friendly web interface

## Technologies Used

* Python
* Flask
* Pandas
* HTML/CSS
* OpenWeather API

## Project Structure

```text
eta-bus-weather-predictor/
│
├── app.py
├── requirements.txt
├── Pan-India_Bus_Routes.csv
├── templates/
│   └── index.html
├── README.md
└── .gitignore
```

## Installation

```bash
pip install -r requirements.txt
python app.py
```

## Usage

1. Select a bus route.
2. Choose the traffic level.
3. Click **Predict ETA**.
4. View ETA, arrival time, and weather information.

## Author

Anisma A
