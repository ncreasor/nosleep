# 🚀 Быстрый старт (для друга)

## Шаг 1: Клонируй репозиторий

```bash
git clone https://github.com/ncreasor/nosleep.git
cd nosleep
```

## Шаг 2: Настрой OpenAI API ключ

```bash
cp .env.example .env
```

Отредактируй `.env` и добавь свой OpenAI API ключ:

```
OPENAI_API_KEY=sk-your-actual-key-here
```

## Шаг 3: Запусти Docker

```bash
docker-compose up --build
```

Это запустит:
- **Frontend**: http://localhost:3000 ← открой в браузере
- **Backend**: http://localhost:8000 (автоматически)
- **Qdrant**: http://localhost:6333 (автоматически)

## Шаг 4: Готово! 🎉

Перейди на http://localhost:3000 и начни использовать inLaw!

## Функции

✅ **Загрузка документов** — PDF, DOCX, TXT
✅ **Анализ норм** — ИИ находит все ссылки на казахские законы
✅ **Проверка статуса** — видит какие нормы актуальны, какие устарели
✅ **Генерация шаблонов** — создаёт шаблон-конструктор из любого документа

## Проблемы?

### Порт 3000 уже занят

Измени в `docker-compose.yml`:
```yaml
ports:
  - "3001:3000"  # вместо 3000:3000
```

### Backend не запускается

Проверь логи:
```bash
docker-compose logs backend
```

Проверь что OPENAI_API_KEY в `.env` правильный!

### Frontend пустой

Подожди 10-15 секунд пока бэкенд загрузится (видишь "healthy" статус).

## Документация

- 📖 [Docker документация](./DOCKER.md) — подробная информация о контейнерах
- 📁 [Backend README](./backend/README.md) — API документация
- 🎨 [Frontend README](./frontend/README.md) — интерфейс

## Остановка

```bash
docker-compose down
```

Удаление всех данных (БД, uploads):

```bash
docker-compose down -v
```

---

Вопросы? Создай issue в репозитории!
