# Trip Optimizer — Multi-Agent AI Travel Planner

A Flask web application that coordinates the existing Weather, Location, Hotel, Transport, Budget and Itinerary agents through `AgentCoordinator`, with a responsive HTML/CSS/JavaScript frontend.

## What was improved

- Added a complete responsive browser frontend in `static/`.
- Added SQLite persistence (`trip_optimizer.db`) instead of losing all trips whenever Flask restarts.
- Added persistent trip history, reopen and delete actions.
- Removed hardcoded OpenWeather, NVIDIA and Pexels keys from source code.
- Added `.env.example` and environment-variable configuration.
- Added timeouts to previously unbounded external weather/location requests.
- Restricted CORS by default; cross-origin access is enabled only when `CORS_ALLOWED_ORIGINS` is configured.
- Added input validation for budget, rooms, people, dates, trip length and dropdown values.
- Added security response headers and request-size limits.
- Avoids exposing internal exception details unless `FLASK_DEBUG=1`.
- Fixed refinement dependency order so final itinerary is generated before local transport and budget are recalculated.
- Date changes now refresh weather information during refinement.

## Project structure

```text
trip-optimizer/
├── app.py
├── coordinator.py
├── weather.py
├── location.py
├── hotel.py
├── transport.py
├── budget_agent.py
├── itinerary.py
├── india_eta.py
├── language.py
├── chat.py
├── requirements.txt
├── .env.example
└── static/
    ├── index.html
    ├── styles.css
    └── app.js
```

## 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure API keys

Copy `.env.example` to `.env` and enter your own keys:

```env
OPENWEATHER_API_KEY=...
NVIDIA_API_KEY=...
PEXELS_API_KEY=...
FLASK_DEBUG=0
PORT=5000
```

**Important:** the previously committed keys should be considered exposed. Revoke/rotate them in the corresponding provider dashboards and use newly generated keys in `.env`.

## 3. Run

```bash
python app.py
```

Open:

```text
http://localhost:5000
```

No npm, React, Vite or second frontend server is required.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | API/database health |
| GET | `/api/options` | Form dropdown values |
| POST | `/api/plan` | Generate a complete trip |
| GET | `/api/plan/<trip_id>` | Load a saved trip |
| POST | `/api/plan/<trip_id>/refine` | Re-run affected planning agents |
| GET | `/api/history` | Persistent trip history |
| DELETE | `/api/history/<trip_id>` | Delete a saved trip |

## Frontend features

The frontend includes trip inputs, weather-risk confirmation, trip score, hotel details, budget visualization, transport information, day-wise itinerary, packing/weather information, refinement controls and persistent trip history.

## Deployment notes

- Use `FLASK_DEBUG=0` outside local development.
- Keep `.env` private and never commit it.
- For a separate frontend domain, set `CORS_ALLOWED_ORIGINS` to an explicit comma-separated allowlist.
- SQLite is appropriate for this student project/single-instance deployment. For multiple production workers/servers, migrate the persistence helpers in `app.py` to PostgreSQL or another shared database.
- External agents still depend on provider availability and outbound internet access. Their returned hotel/place/weather data should be treated as recommendations rather than guaranteed booking inventory.
