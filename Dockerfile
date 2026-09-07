# Один образ на всё: FastAPI отдаёт и API, и собранный фронт. Разводить их по двум
# контейнерам смысла нет — это инструмент на одну машину, а лишний веб-сервер добавил
# бы конфиг, порт и ещё одно место, где ломается CORS.

# --- сборка фронта ---
FROM node:22-alpine AS front

WORKDIR /front

# Сначала только манифесты: слой с npm ci переживает правки исходников.
COPY admin-front/package.json admin-front/package-lock.json ./
RUN npm ci

COPY admin-front/ ./

# VITE_API_BASE_URL намеренно не задаём: без него фронт ходит в /api того же origin,
# то есть в это же приложение. Зашить сюда адрес бэкенда — значит привязать образ
# к одному хосту и порту.
RUN npm run build


# --- приложение ---
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app

WORKDIR /app

# uid 1000 — тот же, что у обычного пользователя на хосте: контейнеру пробрасывают
# ~/.ssh с ключами (права 600), и читать их он должен без root.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app

COPY Pipfile Pipfile.lock ./
RUN pip install --no-cache-dir pipenv \
 && pipenv install --system --deploy \
 && pip uninstall -y --no-input pipenv \
 && rm -rf /root/.cache

COPY app/ ./app/
COPY check_servers.py check_smtp.py reset_configs.py ./
COPY --from=front /front/dist ./admin-front/dist

USER app

EXPOSE 8000

# Слушаем все интерфейсы контейнера, наружу порт публикует compose — и только
# на 127.0.0.1: у API нет аутентификации.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
