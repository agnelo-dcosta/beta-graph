# API Keys and Secrets

Place your API key files here. **Never commit the actual key files** (they are gitignored).

## Files

| File | Purpose |
|------|---------|
| `google_api_key` | Gemini API key for the LangGraph agent. Get at https://aistudio.google.com/apikey |
| `openweathermap_api_key` | OpenWeatherMap API key for weather forecasts. Get at https://openweathermap.org/api |
| `google_maps_api_key` | Google Maps API key for Places (location lookup). Enable Places API at https://console.cloud.google.com/apis/library/places-backend.googleapis.com |

## Setup

1. Copy each `.example` file to the non-example name (e.g. `cp openweathermap_api_key.example openweathermap_api_key`)
2. Paste your key into the file

Or set env vars: `GOOGLE_API_KEY`, `OPENWEATHERMAP_API_KEY`, `GOOGLE_MAPS_API_KEY`.
