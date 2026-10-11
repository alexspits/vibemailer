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

# По этой метке `make docker_build` находит и удаляет прежние образы проекта — и только их.
LABEL app=vibe-mail

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app

WORKDIR /app

# uid 1000 — тот же, что у обычного пользователя на хосте: контейнеру пробрасывают
# ~/.ssh с ключами (права 600), и читать их он должен без root.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app

# openssh-client — ansible шлёт команды через бинарник ssh, в slim-образе его нет.
# sshpass — вход по паролю на свежий сервер, где ключа ещё нет: ssh читает пароль
# только с терминала, и без sshpass первый прогон плейбука невозможен.
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client sshpass \
 && rm -rf /var/lib/apt/lists/*

COPY Pipfile Pipfile.lock ./
RUN pip install --no-cache-dir pipenv \
 && pipenv install --system --deploy \
 && pip uninstall -y --no-input pipenv \
 && rm -rf /root/.cache

# Сценарии поднятия сервера едут в образ: одним образом на новой машине поднимается
# и панель, и новые VPN-серверы. Коллекции ставятся системно — процесс работает не от
# root и в свой HOME их уже не положит.
COPY ansible/ ./ansible/

# HOME на время установки подменяем: иначе galaxy сложит свой кеш в /home/app от root,
# и процесс (uid 1000) не создаст там ~/.ansible/tmp при первом же прогоне плейбука.
# Повторы не перестраховка: galaxy отдаёт архивы через CDN, который рвёт TLS-рукопожатие
# примерно на каждой второй сборке. Проверка в конце — чтобы молча не собрался образ
# без коллекций: плейбук упал бы на первой же задаче «не найден модуль».
RUN for attempt in 1 2 3 4 5; do \
      HOME=/tmp/galaxy ansible-galaxy collection install \
        -r ansible/requirements.yml \
        -p /usr/share/ansible/collections \
        --timeout 30 && break; \
      echo "galaxy: попытка $attempt не удалась, повтор через 5 с"; \
      sleep 5; \
    done; \
    rm -rf /tmp/galaxy; \
    test -d /usr/share/ansible/collections/ansible_collections/community/docker

COPY app/ ./app/
COPY check_servers.py check_smtp.py reset_configs.py ./
COPY --from=front /front/dist ./admin-front/dist

USER app

EXPOSE 8000

# Слушаем все интерфейсы контейнера, наружу порт публикует compose — и только
# на 127.0.0.1: у API нет аутентификации.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
