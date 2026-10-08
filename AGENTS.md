# Instrucciones para agentes (Codex, Claude Code y similares)

Aplican a todo el repositorio. Las instrucciones explícitas de la persona que te usa tienen
prioridad, **excepto las reglas de la base de datos compartida**, que no se omiten.
Para el frontend lee también `frontend/AGENTS.md` (reglas de Angular).

## Proyecto

Sentineli (antes CropAnalytics): plataforma para comparar híbridos de maíz para ensilaje en
Los Altos de Jalisco. Proyecto modular de Ingeniería en Computación, CUAltos (UdeG).
El repositorio de trabajo es este; el del hackathon IBM (`IBM-summer-experience-26`) está
deprecado y no se usa para desarrollo.

- `backend/`: Django 6 + Django REST Framework, Python 3.12+.
  - `api/utils/milk_calculator.py`: MILK2024, réplica de la hoja oficial de Wisconsin.
  - `api/ml/`: modelo LSTM congelado de humedad del suelo (SMAP + Daymet), celdas SMAP de
    9 km (`celdas.py`) y panorama por celda (`panorama.py`).
  - `api/management/commands/`: carga de datos, generación de celdas, solicitud a NASA
    AppEEARS, cálculo del panorama.
- `frontend/`: Angular 21, Tailwind, Leaflet, Plotly, Chart.js.
- Base de datos: **PostgreSQL 17 compartido en DigitalOcean** (sin PostGIS en el código).

## Base de datos compartida: reglas obligatorias

`backend/.env` apunta a la base de datos real del equipo, con los 1,023 ciclos de ensayo y
las cuentas de usuario. No hay una base "de desarrollo" separada.

- **No ejecutes migraciones** (`migrate`, `makemigrations` seguido de `migrate`) contra ella.
  Las migraciones las aplica solo Juan Pablo, después de fusionar a `main`.
- **No modifiques datos** (INSERT, UPDATE, DELETE, DROP, `loaddata`, `flush`, el shell de
  Django con escrituras, el admin de Django) ni crees o cambies usuarios o roles.
- **No corras las pruebas contra ella.** `python manage.py test` crea y borra una base
  `test_` en el servidor configurado. Usa siempre SQLite:
  ```bash
  cd backend && DATABASE_URL=sqlite:///test.sqlite3 python manage.py test api
  ```
- Para probar la aplicación localmente con datos, pide a Juan Pablo un respaldo o usa una
  base local; no apuntes `DATABASE_URL` a DigitalOcean para experimentar.
- Si un cambio requiere modelos nuevos, crea la migración en tu rama y **avisa**; no la
  apliques. Antes de crearla, revisa que no exista otra con el mismo número en `main`.

## Secretos y datos

- El repositorio es **público**. Nunca agregues a commits, bitácoras o respuestas valores de
  `.env`, tokens, contraseñas, cadenas de conexión ni credenciales de NASA Earthdata.
- No se versionan (ya están en `.gitignore`): `backend/.env`, `*.csv`, `backend/data/*.json`,
  `docs/` (documentación del proyecto modular, con nombres del equipo) y `references/`
  (datos TxSON para reentrenar, reportes del hackathon, respaldos).
- Los datos de TxSON pertenecen al laboratorio de UT Austin: no los copies al repositorio.

## Reglas del dominio

- **MILK2024** (`milk_calculator.py`) es una réplica validada de la hoja oficial. No cambies
  sus ecuaciones ni constantes sin la hoja de referencia; la prueba
  `test_igual_a_la_hoja_oficial` debe seguir pasando con los valores de la hoja.
- Toda entrada a MILK2024 se arma con `datos_milk2024()`; no dupliques el cálculo en vistas
  ni en el frontend (el frontend lee `leche_ha` del backend).
- **Modelo de humedad:** los pesos de `api/ml/weights/` están congelados; no los reentrenes
  ni los reemplaces sin acordarlo. El modelo acierta el momento de humectación y secado, no
  el nivel absoluto: usa indicadores relativos (`panorama.py`), no umbrales absolutos en
  m³/m³ nuevos.
- La inferencia pasa por `ml_engine.estimar_humedad()`; no crees caminos paralelos.
- Alcance geográfico: hasta 25 km de un ensayo de campo (ranking completo), de 25 a 40 km
  ranking extrapolado; más lejos no hay datos de ensayos.

## Flujo de trabajo con Git

- Revisa `git status` y la rama antes de editar. No reviertas ni incluyas cambios ajenos.
- Trabaja en una rama propia (`feature/...`, `fix/...`); no hagas commit directo a `main`.
- Commits en español con formato convencional: `feat(api): ...`, `fix(frontend): ...`,
  `docs: ...`. Agrega archivos por ruta (`git add <ruta>`), no `git add .`.
- No hagas `push --force`, `reset --hard` ni reescribas historial sin autorización.
- No hagas commit, push ni abras PR si no te lo pidieron.

## Validación antes de entregar

- Backend: `cd backend && DATABASE_URL=sqlite:///test.sqlite3 python manage.py test api`
  y `python manage.py makemigrations --check --dry-run` (con la misma variable).
- Frontend: `cd frontend && npx ng build`.
- Si no pudiste ejecutar una validación, dilo y explica por qué; no la declares aprobada.

## Entrega

Resume qué cambió, qué validaste y qué queda pendiente, con los archivos relevantes.
Si tocaste algo relacionado con la base de datos compartida, dilo explícitamente.
