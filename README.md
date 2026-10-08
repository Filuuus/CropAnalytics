# CropAnalytics

Welcome to the CropAnalytics project. This document provides the necessary instructions to get the application up and running on your local machine.

## Prerequisites
- Docker and Docker Compose (for the local PostgreSQL database)
- Python 3.10+
- Node.js (v20+)
- Angular CLI

## Local Environment Setup

### 1. Environment variables
Copy the template and fill in the values (at least `POSTGRES_PASSWORD` and `SADMIN_PASSWORD`):
```bash
cp backend/.env.example backend/.env
```

### 2. Start the Database Layer
The project relies on a PostgreSQL database. Ensure your Docker daemon is running, then spin up the database and pgAdmin containers (Compose reads the variables from `backend/.env`):
```bash
docker compose --env-file backend/.env up -d
```

### 3. Backend Setup (Django)
The backend requires setting up a virtual environment and installing dependencies:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the database migrations (they are versioned; do not run `makemigrations` unless you changed `models.py`):
```bash
python manage.py migrate
```

If `SADMIN_PASSWORD` was empty when migrating, the super admin has no usable password. Set one with:
```bash
python manage.py changepassword sadmin@cropanalytics.local
```

Run the tests (no database needed):
```bash
python manage.py test api
```

**Important:** Populate the initial datasets to guarantee the analytics page displays values:
```bash
python manage.py cargar_datos
```

Finally, start the backend server:
```bash
python manage.py runserver
```
The Django API will be accessible at `http://localhost:8000`.

#### Soil analysis data (SMAP)
The `/soil-analysis` page estimates soil moisture with a frozen LSTM model (`backend/api/ml/`). It needs the NASA AppEEARS exports for the 11 Jalisco reference plots, which are not versioned. Place them in `backend/data/`:
- `CropAnalytics-BOB-SMAP-2024-SPL3SMP-E-006-results.csv`
- `CropAnalytics-BOB-Weather-2024-DAYMET-004-results.csv`

Without them, `/api/recomendacion-humedad/` responds with `503`.

### 4. Frontend Setup (Angular)
In a new terminal window, navigate to the frontend folder and install the dependencies:
```bash
cd frontend
npm install
npm start
```
The Angular application will be running on your designated localhost port.
