# Docker Setup для inLaw

Быстрый запуск приложения через Docker.

## Требования

- Docker 20.10+
- Docker Compose 2.0+
- OpenAI API Key

## Быстрый старт

### 1. Создайте `.env` файл

```bash
cp .env.example .env
```

Отредактируйте `.env` и добавьте ваш OpenAI API ключ:

```
OPENAI_API_KEY=sk-your-actual-api-key-here
```

### 2. Запустите Docker Compose

```bash
docker-compose up --build
```

Это запустит три сервиса:
- **Frontend** (Next.js): http://localhost:3000
- **Backend** (FastAPI): http://localhost:8000
- **Qdrant** (Vector DB): http://localhost:6333

### 3. Проверьте здоровье

```bash
# Frontend
curl http://localhost:3000

# Backend
curl http://localhost:8000/health
```

## Остановка

```bash
docker-compose down
```

## Очистка

```bash
# Остановить и удалить контейнеры, но сохранить данные
docker-compose down

# Остановить и удалить всё (включая объемы БД)
docker-compose down -v
```

## Логи

```bash
# Все контейнеры
docker-compose logs -f

# Только бэкенд
docker-compose logs -f backend

# Только фронтенд
docker-compose logs -f frontend
```

## Переменные окружения

### Backend

- `OPENAI_API_KEY` — OpenAI API ключ (обязательно)
- `OPENAI_MODEL` — модель GPT (по умолчанию: gpt-4o-mini)
- `DATABASE_URL` — SQLite база данных (по умолчанию: sqlite:///./app.db)
- `QDRANT_URL` — URL Qdrant сервиса (по умолчанию: http://qdrant:6333)

### Frontend

- `NEXT_PUBLIC_BACKEND_URL` — URL бэкенда (по умолчанию: http://backend:8000)
- `NODE_ENV` — production / development (по умолчанию: production)

## Troubleshooting

### Порт уже в использовании

Если порты 3000, 8000, или 6333 занят:

```bash
# Измените порты в docker-compose.yml
# Например, 3001 вместо 3000
```

### Backend не стартует

Проверьте что OpenAI API ключ правильный:

```bash
docker-compose logs backend
```

### Frontend не видит Backend

Проверьте что бэкенд healthy:

```bash
docker-compose ps
# Backend должен показать status "healthy"
```

## Продакшн деплой

Для деплоя на сервер:

1. Установите Docker и Docker Compose
2. Скопируйте все файлы проекта
3. Создайте `.env` файл с переменными
4. Запустите `docker-compose up -d`
5. (Опционально) Настройте reverse proxy (nginx) на фронт

## Развитие

Для локальной разработки (без Docker):

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend (в другом терминале)
cd frontend
npm install
npm run dev
```
