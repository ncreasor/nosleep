from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from config import settings
from routers import documents, qdrant, ai, auth, chats, admin, folders, templates
from seed_test_docs import seed_test_documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_test_documents()
    yield


app = FastAPI(lifespan=lifespan)

# CORS Configuration - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(folders.router)
app.include_router(templates.router)
app.include_router(qdrant.router)
app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def read_root():
    return {"message": "Welcome to FastAPI Backend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
