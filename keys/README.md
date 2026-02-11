# API Keys and Secrets

Place your API key files here. **Never commit the actual key files** (they are gitignored).

## Files

| File | Purpose |
|------|---------|
| `google_api_key` | Gemini API key for the LangGraph agent. Get at https://aistudio.google.com/apikey |
| `openweathermap_api_key` | OpenWeatherMap API key for weather forecasts. Get at https://openweathermap.org/api |
| `alltrails_cookies` | Cookie header for AllTrails scraping (optional). Copy from browser dev tools. |

## Setup

1. Copy each `.example` file to the non-example name (e.g. `cp openweathermap_api_key.example openweathermap_api_key`)
2. Paste your key/cookies into the file

Or set env vars: `GOOGLE_API_KEY`, `OPENWEATHERMAP_API_KEY`, `ALLTRAILS_COOKIE_FILE`.
