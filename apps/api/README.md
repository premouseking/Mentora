# Mentora API

## 环境准备

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python manage.py migrate
```

## 运行

```powershell
python manage.py runserver 127.0.0.1:8000
```

在独立终端中启动 worker：

```powershell
celery -A config worker -Q heavy -n heavy@%h --loglevel=info
celery -A config worker -Q agent -n agent@%h --loglevel=info
celery -A config worker -Q learning -n learning@%h --loglevel=info
```

## 测试

```powershell
pytest
```
