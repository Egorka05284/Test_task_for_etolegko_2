# Adrobot — Keitaro Campaign Manager

Учебное приложение для тестового задания Adrobot. Оно создаёт кампании в Keitaro через Admin API и позволяет управлять офферами в потоке выбранной кампании.

**Стек:** Python 3.12+, FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, HTTPX, Jinja2, Bootstrap 5 и JavaScript.

## Возможности

### 1. Создание кампании

Форма запрашивает:

- название кампании;
- двухбуквенный GEO-код страны;
- домен;
- группу кампаний;
- источник трафика;
- первоначальный оффер.

Справочники загружаются из Keitaro через `GET /domains`, `GET /groups?type=campaigns`, `GET /traffic_sources` и `GET /offers`. Для учебного стенда заранее созданы следующие сущности:

| Сущность | ID | Название |
|---|---:|---|
| Домен | `1813` | Домен стенда |
| Группа кампаний | `10332` | `FORTESTS` |
| Источник трафика | `836` | `FORTESTS` |

При создании выполняются запросы:

1. `POST /campaigns` — создаёт кампанию с названием, alias, типом `position`, группой и источником.
2. `PUT /campaigns/{id}` — устанавливает `domain_id`.
3. `POST /streams` — создаёт поток `Geo redirect` типа `regular`, схемы `redirect`, с действием `http`, URL `https://google.com` и фильтром выбранной страны.
4. `POST /streams` — создаёт поток `Офферы` типа `default`, схемы `landings`, с первоначальным оффером и долей `100%`.

GEO-поток создаётся первым. Default-поток офферов служит fallback для трафика, который не совпал с GEO-фильтром.

Если один из шагов настройки после создания кампании завершается ошибкой, приложение пытается удалить созданную кампанию через `DELETE /campaigns/{id}`, чтобы не оставлять частично настроенную сущность.

### 2. Редактор офферов

- Импортирует существующую кампанию по Keitaro campaign ID.
- Автоматически ищет поток с офферами. Если подходящий поток определить нельзя, можно передать stream ID вручную.
- Читает актуальный состав офферов из `GET /streams/{id}`.
- Добавляет и удаляет офферы.
- Перед изменением повторно получает текущий состав потока.
- Отправляет полный новый массив `offers` через `PUT /streams/{id}`: на учебном стенде это поле заменяет состав целиком.
- Равномерно распределяет доли и сохраняет сумму `100%`.
- Не позволяет удалить последний оффер.
- Сохраняет состояние уже добавленных офферов (`state`) при изменении состава; новый оффер добавляется в состоянии `active`.

Примеры распределения: `1 → 100%`, `2 → 50/50`, `3 → 34/33/33`, `4 → 25/25/25/25`.

## Структура проекта

```text
adrobot/
├── app/
│   ├── core/          # настройки и подключение к БД
│   ├── models/        # SQLAlchemy-модели
│   ├── schemas/       # Pydantic-схемы и валидация
│   ├── routers/       # HTTP API и HTML-страницы
│   ├── services/      # бизнес-логика и клиент Keitaro Admin API
│   ├── templates/     # Jinja2-шаблоны
│   └── static/        # CSS и JavaScript
├── alembic/           # миграции БД
├── tests/             # unit-тесты
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── requirements-dev.txt
```

## Требования

- Docker Engine и Docker Compose plugin — для рекомендуемого запуска;
- Python 3.12+ — для локального запуска без Docker; PostgreSQL нужен, если локально используете PostgreSQL вместо SQLite;
- API-ключ от учебного стенда Keitaro.

Адрес Admin API учебного стенда: `https://keitaro-for-tests.etolegko.com/admin_api/v1`.

## Быстрый запуск через Docker Compose

1. Склонируйте репозиторий:

   ```bash
   git clone <YOUR_GITHUB_REPOSITORY_URL>
   cd adrobot
   ```

2. Создайте файл окружения:

   ```bash
   cp .env.example .env
   ```

   В Windows PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Откройте `.env` и укажите свой API-ключ:

   ```env
   KEITARO_BASE_URL=https://keitaro-for-tests.etolegko.com
   KEITARO_API_KEY=YOUR_KEITARO_API_KEY
   ```

   Не используйте угловые скобки вокруг ключа. Не коммитьте `.env` в Git.

4. Соберите и запустите приложение:

   ```bash
   docker compose up --build -d
   ```

   Compose поднимает PostgreSQL и приложение. Перед запуском Uvicorn контейнер приложения выполняет `alembic upgrade head`. В Docker Compose `DATABASE_URL` автоматически направляется на сервис `db`.

5. Проверьте состояние:

   ```bash
   docker compose ps
   docker compose logs -f web
   ```

6. Откройте приложение:

   - интерфейс: <http://localhost:8000>
   - Swagger UI: <http://localhost:8000/docs>
   - health check: <http://localhost:8000/health>

Остановить приложение:

```bash
docker compose down
```

Остановить приложение и удалить локальный volume PostgreSQL (все локальные записи Adrobot будут удалены):

```bash
docker compose down -v
```

## Локальный запуск без Docker

1. Создайте и активируйте виртуальное окружение:

   ```bash
   python -m venv .venv
   # macOS/Linux
   source .venv/bin/activate
   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   ```

2. Установите зависимости:

   ```bash
   pip install -r requirements-dev.txt
   ```

3. Создайте `.env` из примера. Для локального запуска без PostgreSQL замените `DATABASE_URL` на SQLite:

   ```env
   DATABASE_URL=sqlite:///./adrobot.db
   KEITARO_BASE_URL=https://keitaro-for-tests.etolegko.com
   KEITARO_API_KEY=YOUR_KEITARO_API_KEY
   ```

   Для локального запуска с PostgreSQL укажите доступный с вашей машины адрес БД, например `postgresql+psycopg://user:password@localhost:5432/adrobot`.

4. Примените миграции и запустите сервер:

   ```bash
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

В локальном режиме без Docker таблицы создаются миграцией Alembic. `AUTO_CREATE_TABLES` оставьте `false` — автосоздание через SQLAlchemy предназначено только для отдельного локального сценария разработки.

## Переменные окружения

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL БД | `sqlite:///./adrobot.db` в настройках приложения; Docker Compose переопределяет его на PostgreSQL |
| `KEITARO_BASE_URL` | Базовый URL трекера без `/admin_api/v1` | `https://keitaro-for-tests.etolegko.com` |
| `KEITARO_API_KEY` | Admin API key | Пусто; необходимо задать |
| `KEITARO_DEFAULT_DOMAIN_ID` | Предвыбранный домен в форме | `1813` |
| `KEITARO_DEFAULT_GROUP_ID` | Предвыбранная группа | `10332` |
| `KEITARO_DEFAULT_TRAFFIC_SOURCE_ID` | Предвыбранный источник | `836` |
| `GOOGLE_REDIRECT_URL` | Назначение GEO-потока | `https://google.com` |
| `AUTO_CREATE_TABLES` | Создание таблиц через SQLAlchemy при старте | `false` |
| `REQUEST_TIMEOUT_SECONDS` | Таймаут HTTP-запроса к Keitaro | `20` |

API-ключ хранится только в переменной окружения и передаётся Keitaro в заголовке `Api-Key`. Не добавляйте реальные ключи, `.env` или дампы БД в публичный репозиторий.

**Важно:** в приложении нет пользовательской аутентификации. Compose публикует интерфейс только на `127.0.0.1`, поэтому по умолчанию он доступен с локальной машины. Не открывайте приложение в интернет без добавления аутентификации и настройки защищённого HTTPS-доступа.

## Внутренний API Adrobot

| Метод | Endpoint | Назначение |
|---|---|---|
| `GET` | `/api/keitaro/options` | Загрузить домены, группы, источники и офферы из Keitaro |
| `GET` | `/api/keitaro/campaigns` | Получить кампании из Keitaro |
| `GET` | `/api/campaigns` | Список кампаний, сохранённых в локальной БД |
| `POST` | `/api/campaigns` | Создать кампанию и два потока в Keitaro |
| `POST` | `/api/campaigns/import` | Импортировать существующую кампанию в локальную БД |
| `GET` | `/api/campaigns/{campaign_id}` | Получить локальную кампанию |
| `GET` | `/api/campaigns/{campaign_id}/offers` | Получить офферы потока и сумму долей |
| `POST` | `/api/campaigns/{campaign_id}/offers` | Добавить оффер и пересчитать доли |
| `DELETE` | `/api/campaigns/{campaign_id}/offers/{offer_id}` | Удалить оффер и пересчитать доли |

## Миграции базы данных

Применить все миграции:

```bash
alembic upgrade head
```

Создать новую миграцию после изменения SQLAlchemy-моделей:

```bash
alembic revision --autogenerate -m "describe_change"
```

Откатить одну миграцию:

```bash
alembic downgrade -1
```

После генерации autogenerate-миграции проверьте её содержимое перед применением.

## Тесты

Установите dev-зависимости и запустите тесты:

```bash
pip install -r requirements-dev.txt
pytest -q
```

Тесты используют SQLite in-memory и mock-объект Keitaro, поэтому для них не нужны доступ к учебному стенду, API-ключ или PostgreSQL.

GitHub Actions автоматически выполняет тесты и проверку компиляции Python при push и pull request.

## Ограничения учебного стенда

Приложение использует только endpoints, перечисленные в задании. Оно не обращается к `/stream_filters`, `/streams_actions`, `/stream_types`, `/stream_schemas` и не использует статистику, клики, лендинги, триггеры, постбэки или отчёты. Справочники офферов, доменов, групп и источников доступны только для чтения.

Реальная настройка кампаний, потоков и офферов проверяется через Admin API и интерфейс учебного стенда. Сам стенд не предоставляет клики или статистику рекламного трафика.
