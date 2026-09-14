# CropAnalytics

Welcome to the CropAnalytics project. This document provides the necessary instructions to get the application up and running on your local machine.

## Prerequisites
- Docker and Docker Compose (for the local PostGIS database)
- Python 3.10+
- Node.js (v20+)
- Angular CLI

## Local Environment Setup

### 1. Start the Database Layer
The project relies on a PostGIS database. Ensure your Docker daemon is running, then spin up the database and pgAdmin containers:
```bash
docker compose up -d
```

### 2. Backend Setup (Django)
The backend requires setting up a virtual environment and installing dependencies:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the database migrations:
```bash
python manage.py makemigrations api
python manage.py makemigrations
python manage.py migrate
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

### 3. Frontend Setup (Angular)
In a new terminal window, navigate to the frontend folder and install the dependencies:
```bash
cd frontend
npm install
npm start
```
The Angular application will be running on your designated localhost port.

## Note on Environment Variables
Ensure that you have your local `.env` files set up based on any `.env.example` templates if they exist in the root or component directories.