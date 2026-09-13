FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Applies any pending Alembic migrations before the app starts — needed
# since main.py no longer calls Base.metadata.create_all() itself. Shell
# form (not exec-form CMD) so `&&` actually chains the two commands.
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000
