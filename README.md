# inLaw — AI-платформа для юридических документов

> **Decentrathon 2025** — решение команды nosleep

---

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                           inLaw  ·  nosleep                                 │
│                                                                             │
│   ┌──────────────────────────────┐   ┌──────────────────────────────────┐  │
│   │         ZanEmbed             │   │         inLaw Platform           │  │
│   │                              │   │                                  │  │
│   │  adilet.zan.kz               │   │  Next.js 14  ←──→  FastAPI       │  │
│   │       │                      │   │  Tailwind CSS       SQLite       │  │
│   │       ▼                      │   │  shadcn/ui          Qdrant       │  │
│   │  scraper.py                  │   │                     OpenAI       │  │
│   │  (RU + KZ docs)              │   │                                  │  │
│   │       │                      │   │  Upload PDF/DOCX                 │  │
│   │       ▼                      │   │       │                          │  │
│   │  Synthetic Data              │   │       ▼                          │  │
│   │  Generation                  │   │  Extract Text                    │  │
│   │       │                      │   │       │                          │  │
│   │       ▼                      │   │       ├── Classify               │  │
│   │  Triplet Training            │   │       │   genuine / outdated /   │  │
│   │  + LoRA (Zembed-1)           │   │       │   invalid                │  │
│   │       │                      │   │       │                          │  │
│   │       ▼                      │   │       ├── Embed → Qdrant         │  │
│   │   ZanEmbed v1                │   │       │   (chunked, cosine)      │  │
│   │   (legal-aware)              │   │       │                          │  │
│   └──────────────────────────────┘   │       └── RAG Chat ◄─────────── │  │
│                                      │           (streaming SSE)        │  │
│                                      └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Проблема

Юристы, консультанты и аналитики проверяют документы на соответствие законодательству вручную. Законы Казахстана выходят, меняются, устаревают и дополняются быстро — это повышает риск ошибки и стоит дорогого времени специалистов.

---

## Решение

Два взаимосвязанных компонента:

### 1. ZanEmbed

Эмбеддинговая модель с юридической экспертизой на казахстанском праве.

- **База:** state-of-the-art модель Zembed-1
- **Fine-tuning:** Low Rank Adaptation (LoRA) — обновляются только адаптерные слои, основные веса заморожены → минимальные требования к GPU
- **Данные:** правовые акты с [adilet.zan.kz](https://adilet.zan.kz) (RU + KZ), домены: финансы, торговля, сельское хозяйство, труд
- **Обучение:** triplet loss на синтетически сгенерированных парах (anchor / positive / negative)

### 2. inLaw

Агентная платформа для работы с юридическими документами.

- Загружаешь документ (PDF, DOCX, TXT)
- Система автоматически извлекает текст, классифицирует его (`genuine` / `outdated` / `invalid`) и объясняет почему
- Документ разбивается на чанки, встраивается в Qdrant через ZanEmbed
- RAG-чат позволяет задавать вопросы по документу — ответы grounded на релевантных фрагментах

---

## Стек

| Слой | Технологии |
|---|---|
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui, Redux Toolkit, Recharts |
| Backend | FastAPI, SQLAlchemy (async), SQLite (aiosqlite) |
| Векторная БД | Qdrant (cosine similarity, 1536-dim) |
| LLM / Embeddings | OpenAI API (GPT-4o + text-embedding-3-small) |
| ZanEmbed scraper | Python, requests, BeautifulSoup, concurrent.futures |
| ZanEmbed training | LoRA (PEFT), Zembed-1, triplet loss |
| Auth | JWT (python-jose), Argon2 password hashing |
| Document parsing | pypdf, python-docx |

---

## Архитектура бэкенда

```
backend/
├── main.py               # FastAPI app, CORS, lifespan
├── auth.py               # JWT middleware
├── database.py           # AsyncSession, SQLite init
├── models.py             # ORM: User, Document, Chat, ChatMessage
├── schemas.py            # Pydantic schemas
├── processing.py         # Document pipeline (см. ниже)
└── routers/
    ├── auth.py           # register / login / me
    ├── documents.py      # CRUD + upload + background processing
    ├── ai.py             # /chat, /chat/stream (SSE), /embed,
    │                     # /document-chat (RAG)
    ├── chats.py          # chat history CRUD
    ├── qdrant.py         # health check
    └── admin.py          # admin endpoints
```

**Document processing pipeline** (background task):

```
Upload
  └── Extract text (PDF / DOCX / TXT)
        └── extract_metadata()    GPT: category, law_date, law_number, jurisdiction
              └── classify_document()   GPT: genuine | outdated | invalid + reason
                    └── generate_embedding()   OpenAI text-embedding-3-small
                          └── Qdrant upsert
                                ├── whole doc vector
                                └── up to 10 chunks (500w window, 100w overlap)
                                      └── SQLite update → status: ready
```

---

## Фронтенд — роуты

| Путь | Описание |
|---|---|
| `/` | Лендинг / главная |
| `/login` | Авторизация и регистрация |
| `/documents` | Список документов пользователя |
| `/documents/[id]` | Просмотр документа + AI-чат |

---

## ZanEmbed — пайплайн

```
adilet.zan.kz/rus/search/docs  ──►  scraper.py
adilet.zan.kz/kaz/search/docs       │
                                     │  - 4 воркера (concurrent.futures)
                                     │  - checkpoint каждые 50 docs
                                     │  - поля: title, content,
                                     │    doc_type, date, number, authority
                                     ▼
                           laws_dataset_rus.json
                           laws_dataset_kaz.json
                                     │
                                     ▼
                        Synthetic data generation
                        (anchor / positive / negative triplets)
                                     │
                                     ▼
                        LoRA fine-tuning на Zembed-1
                        (rank r, target_modules: q_proj, v_proj)
                                     │
                                     ▼
                              ZanEmbed v1
```

---

## Быстрый старт

### Backend

```bash
cd nosleep/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Заполни: OPENAI_API_KEY, QDRANT_URL, SECRET_KEY

uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd nosleep/frontend
pnpm install

# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000

pnpm dev
```

### ZanEmbed scraper

```bash
cd zanembed-v01
pip install requests beautifulsoup4

python scraper.py --lang rus --workers 4
python scraper.py --lang kaz --workers 4
# Прервать и продолжить: checkpoint сохраняется автоматически
```

---

## Статус реализации

### ZanEmbed
- [x] Определены домены: финансы, торговля, сельское хозяйство, труд
- [x] Pipeline создания и корректировки модели спроектирован
- [x] Скрапер adilet.zan.kz (RU + KZ, с чекпоинтингом)
- [ ] Синтетические данные сгенерированы
- [ ] Triplet training + LoRA конфигурация
- [ ] Релиз ZanEmbed + бенчмарки

### inLaw Platform
- [x] Лендинг и страница документов
- [x] Auth: регистрация, вход, Terms of Service
- [x] CRUDL документов + AI-редактирование
- [x] Qdrant векторная база данных, клиент, коллекция
- [ ] RAG генерация (подключение ZanEmbed)
- [ ] AI-чат и агентная система

---

## UI прототип

[Figma — Decentrathon Website Prototype](https://www.figma.com/site/wu4iuBPGgyBIFLfW1r0xJY/Decentrathon-Website-Prototype?node-id=0-1&p=f&t=txFfuqhcibhbDmKu-0)

---

**nosleep** @ Decentrathon 2025
