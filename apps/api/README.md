# Mentora API

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python manage.py migrate
```

## Run

```powershell
python manage.py runserver 127.0.0.1:8000
```

Start workers in separate terminals:

```powershell
celery -A config worker -Q heavy -n heavy@%h --loglevel=info
celery -A config worker -Q agent -n agent@%h --loglevel=info
celery -A config worker -Q learning -n learning@%h --loglevel=info
```

## Test

```powershell
pytest
```
