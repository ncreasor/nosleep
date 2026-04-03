"""
script.py — Crawl adilet.zan.kz (labor / finance / civilian_rights, rus + kaz)
            → chunk → ZeroEntropy zembed-1 → Qdrant (zan_legal_docs, 1280d)

Features:
  - Checkpoints each config's upserted docs to .qdrant_checkpoint_{config}.json
  - Resumes safely: skips docs already in Qdrant by checking first chunk ID
  - Fast: 12 concurrent workers, 0.15s delay, reusable thread-local sessions
  - Restarts mid-pipeline without losing progress

Usage:
    python script.py                  # scrape all 6 configs, full depth
    python script.py --max-pages 2    # quick test (2 listing pages per config)
"""

import os
import re
import sys
import json
import uuid
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from dotenv import load_dotenv

import urllib3
import requests
from bs4 import BeautifulSoup
from zeroentropy import ZeroEntropy
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    PayloadSchemaType,
)

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ───────────────────────────────────────────────────────────────────
ZE_API_KEY    = os.getenv("ZEROENTROPY_API_KEY", "")
QDRANT_URL    = os.getenv("QDRANT_URL", "http://localhost:6333")
MODEL         = "zembed-1"
COLLECTION    = "zan_legal_docs"
VECTOR_DIM    = 1280

CHUNK_WORDS      = 350
OVERLAP_WORDS    = 50
MIN_CHUNK_WORDS  = 50
ALPHA_RATIO_MIN  = 0.40
EMBED_BATCH      = 16
RETRY_ATTEMPTS   = 5
RETRY_BASE_DELAY = 2.0

MAX_CONCURRENCY = 12
DELAY           = 0.15
MAX_RETRIES     = 3
TIMEOUT         = 30
MAX_PAGE_NUM    = 25000

UUID_NS = uuid.UUID("b4e3c1a2-9f8d-4e7a-a1b2-3c4d5e6f7a8b")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 6 search configs: (sphere, lang, url)
SEARCH_CONFIGS = [
    ("labor",           "rus", "https://adilet.zan.kz/rus/search/docs/ir=1_002&va=%D0%9A%D0%9E%D0%94%7C%D0%97%D0%90%D0%9A"),
    ("labor",           "kaz", "https://adilet.zan.kz/kaz/search/docs/ir=1_002&va=%D0%9A%D0%9E%D0%94%7C%D0%97%D0%90%D0%9A"),
    ("finance",         "rus", "https://adilet.zan.kz/rus/search/docs/ir=1_006&va=%D0%9A%D0%9E%D0%94%7C%D0%97%D0%90%D0%9A"),
    ("finance",         "kaz", "https://adilet.zan.kz/kaz/search/docs/ir=1_006&va=%D0%9A%D0%9E%D0%94%7C%D0%97%D0%90%D0%9A"),
    ("civilian_rights", "rus", "https://adilet.zan.kz/rus/search/docs/ir=1_026&va=%D0%97%D0%90%D0%9A%7C%D0%9A%D0%9E%D0%94"),
    ("civilian_rights", "kaz", "https://adilet.zan.kz/kaz/search/docs/ir=1_026&va=%D0%97%D0%90%D0%9A%7C%D0%9A%D0%9E%D0%94"),
]

REPEALED_KW = ["утратил силу", "признан утратившим", "недействующий"]

ARTICLE_RE = re.compile(
    r'(?:^|\n)\s*(?:Статья|СТАТЬЯ|статья)\s+\d+[\.\s]'
    r'|(?:^|\n)\s*\d+\s*[-–]\s*(?:бап|бабы)\b'
    r'|(?:^|\n)\s*(?:Глава|ГЛАВА)\s+\d+'
    r'|(?:^|\n)\s*(?:Тарау)\s+\d+',
    re.MULTILINE,
)
CITATION_RE = re.compile(r'\([^)]{0,20}\d{4}\s*г\.,?\s*N\s*[\d\-]+[^)]{0,200}\)')


# ── HTTP helpers (with thread-local session reuse) ───────────────────────────

_thread_local = threading.local()

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.verify = False
    return s

def get_session() -> requests.Session:
    """Return a per-thread reusable session (avoids creating new TCP connections per doc)."""
    if not hasattr(_thread_local, "session"):
        _thread_local.session = make_session()
    return _thread_local.session

def fetch(session: requests.Session, url: str, retries: int = MAX_RETRIES):
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}/{retries}] {url} — {e} (wait {wait}s)")
            time.sleep(wait)
    print(f"  [FAIL] {url}")
    return None


# ── Scraper ───────────────────────────────────────────────────────────────────

def clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def get_doc_links(session: requests.Session, start_url: str, max_pages=None) -> list[str]:
    """Paginate from start_url (sphere search URL) and return all document URLs."""
    base = "https://adilet.zan.kz"
    # Append pagesize
    sep = "&" if ("?" in start_url or "=" in start_url) else "?"
    current = start_url + sep + "pagesize=100"
    if "pagesize" in start_url:
        current = start_url

    links: list[str] = []
    pages_done = 0

    while current:
        print(f"  [listing] {current}")
        soup = fetch(session, current)
        if soup is None:
            break

        for a in soup.select("h4.post_header a[href]"):
            href = a["href"]
            full = urljoin(base, href) if not href.startswith("http") else href
            links.append(full)

        count = len(soup.select("h4.post_header a"))
        print(f"    -> {count} docs (running total: {len(links)})")

        pages_done += 1
        if max_pages and pages_done >= max_pages:
            break

        next_url = None
        for a in soup.select("a.nextpostslink[href]"):
            href = a["href"]
            m = re.search(r"page=(\d+)", href)
            if not m or int(m.group(1)) > MAX_PAGE_NUM:
                continue
            candidate = urljoin(base, href) if not href.startswith("http") else href
            if next_url is None:
                next_url = candidate
            else:
                cur_n = int(re.search(r"page=(\d+)", next_url).group(1))
                if int(m.group(1)) < cur_n:
                    next_url = candidate

        current = next_url
        if current:
            time.sleep(DELAY)

    seen, out = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_status(soup, info_rows: list) -> str:
    for key, val in info_rows:
        if "статус" in key.lower():
            return "Repealed" if any(kw in val.lower() for kw in REPEALED_KW) else "Active"
    if soup and any(kw in soup.get_text().lower() for kw in REPEALED_KW):
        return "Repealed"
    return "Active"


def get_doc_kind(url: str) -> str:
    m = re.search(r'/docs/([A-Za-z])', url)
    if not m:
        return "other"
    return {"Z": "law", "K": "codex"}.get(m.group(1).upper(), "other")


def scrape_document(url: str, sphere: str, language: str) -> dict | None:
    session = get_session()  # Reuse per-thread session

    soup = fetch(session, url)
    if soup is None:
        return None

    h1 = soup.find("h1")
    title = clean_ws(h1.get_text()) if h1 else ""

    content = ""
    article_el = soup.find("article")
    if article_el:
        content = clean_ws(article_el.get_text())
    else:
        for sel in ["div.document-text", "div#document-text", "div.post-content", "div.content"]:
            el = soup.select_one(sel)
            if el:
                content = clean_ws(el.get_text())
                break

    if len(content) < 100:
        return None

    doc_type = date = number = authority = ""
    info_rows: list[tuple[str, str]] = []
    info_soup = fetch(session, url.rstrip("/") + "/info")
    if info_soup:
        table = info_soup.find("table", id="ethernatable") or info_soup.find("table")
        if table:
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                key = clean_ws(cells[0].get_text())
                val = clean_ws(cells[1].get_text())
                info_rows.append((key, val))
                k = key.lower()
                if ("дата принятия" in k or "дата" in k) and not date:
                    date = val
                elif ("форма акта" in k or "форма" in k) and not doc_type:
                    doc_type = val
                elif ("регистрационный номер" in k or "номер" in k) and not number:
                    number = val
                elif "орган" in k and not authority:
                    authority = val

    status = parse_status(soup, info_rows)
    doc_kind = get_doc_kind(url)
    tag = "R" if status == "Repealed" else "A"
    print(f"  [{tag}][{sphere}/{language}][{doc_kind}] {doc_type or '?'}: {title[:50]} ({date})")

    return {
        "url":       url,
        "title":     title,
        "doc_type":  doc_type,
        "date":      date,
        "number":    number,
        "authority": authority,
        "status":    status,
        "is_active": status == "Active",
        "sphere":    sphere,
        "language":  language,
        "doc_kind":  doc_kind,
        "content":   content,
    }


# ── Chunking ──────────────────────────────────────────────────────────────────

def _clean_content(text: str) -> str:
    text = CITATION_RE.sub(" ", text)
    text = re.sub(r'\s{3,}', "\n\n", text)
    text = re.sub(r'[ \t]+', " ", text)
    return text.strip()


def _is_useful(text: str) -> bool:
    words = text.split()
    if len(words) < MIN_CHUNK_WORDS:
        return False
    alpha_chars = sum(c.isalpha() for c in text)
    return alpha_chars / max(len(text), 1) >= ALPHA_RATIO_MIN


def _word_chunks(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start += size - overlap
    return chunks


def chunk_document(doc: dict) -> list[dict]:
    raw    = _clean_content(doc["content"])
    title  = doc.get("title", "").strip()
    sphere = doc.get("sphere", "")

    boundaries = [m.start() for m in ARTICLE_RE.finditer(raw)]
    if len(boundaries) >= 2:
        boundaries.append(len(raw))
        segments = [raw[boundaries[i]:boundaries[i + 1]].strip()
                    for i in range(len(boundaries) - 1)]
    else:
        segments = [raw]

    split_segments: list[str] = []
    for seg in segments:
        if len(seg.split()) > CHUNK_WORDS * 2:
            paras = re.split(r'\n{2,}', seg)
            split_segments.extend(p.strip() for p in paras if p.strip())
        else:
            split_segments.append(seg)

    final_texts: list[str] = []
    for seg in split_segments:
        if len(seg.split()) > CHUNK_WORDS:
            final_texts.extend(_word_chunks(seg, CHUNK_WORDS, OVERLAP_WORDS))
        else:
            final_texts.append(seg)

    context_prefix = f"{title}\n[{sphere}]\n\n"
    chunks = []
    for raw_chunk in final_texts:
        if not _is_useful(raw_chunk):
            continue
        chunks.append({
            "text":     context_prefix + raw_chunk,
            "raw_text": raw_chunk,
        })
    return chunks


# ── ZeroEntropy embeddings ────────────────────────────────────────────────────

def embed_batch(texts: list[str], ze: ZeroEntropy) -> list[list[float]]:
    delay = RETRY_BASE_DELAY
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = ze.models.embed(
                model=MODEL,
                input=texts,
                input_type="document",
                dimensions=VECTOR_DIM,
                encoding_format="float",
            )
            return [item.embedding[:VECTOR_DIM] for item in resp.results]
        except Exception as exc:
            if attempt == RETRY_ATTEMPTS:
                raise
            print(f"  [embed retry {attempt}/{RETRY_ATTEMPTS}] {exc} — sleeping {delay}s")
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("embed_batch: exhausted retries")


def embed_all(texts: list[str], ze: ZeroEntropy) -> list[list[float]]:
    vectors = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        vecs  = embed_batch(batch, ze)
        vectors.extend(vecs)
        print(f"    embedded {min(i + EMBED_BATCH, len(texts))}/{len(texts)}", end="\r")
    print()
    return vectors


# ── Qdrant setup ──────────────────────────────────────────────────────────────

def setup_collection(qd: QdrantClient) -> None:
    existing = {c.name for c in qd.get_collections().collections}
    if COLLECTION not in existing:
        qd.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"Created collection '{COLLECTION}' ({VECTOR_DIM}d Cosine)")
    else:
        print(f"Collection '{COLLECTION}' already exists — upserting into it")

    for field, schema in [
        ("status",    PayloadSchemaType.KEYWORD),
        ("sphere",    PayloadSchemaType.KEYWORD),
        ("language",  PayloadSchemaType.KEYWORD),
        ("doc_kind",  PayloadSchemaType.KEYWORD),
        ("is_active", PayloadSchemaType.BOOL),
    ]:
        try:
            qd.create_payload_index(
                collection_name=COLLECTION,
                field_name=field,
                field_schema=schema,
            )
        except Exception:
            pass  # Index may already exist


# ── Checkpoint management ──────────────────────────────────────────────────────

def load_checkpoint(config_key: str) -> set[str]:
    """Load set of already-upserted URLs for this config."""
    checkpoint_file = f".qdrant_checkpoint_{config_key}.json"
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("upserted_urls", []))
        except Exception:
            return set()
    return set()


def save_checkpoint(config_key: str, upserted_urls: set[str]) -> None:
    """Save checkpoint of upserted URLs."""
    checkpoint_file = f".qdrant_checkpoint_{config_key}.json"
    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump({"upserted_urls": sorted(upserted_urls)}, f, indent=2)


# ── Per-config pipeline with checkpointing ────────────────────────────────────

def process_config(
    sphere: str,
    language: str,
    start_url: str,
    qd: QdrantClient,
    ze: ZeroEntropy,
    max_pages=None,
) -> None:
    config_key = f"{sphere}_{language}"
    label = f"{sphere}/{language}"
    print(f"\n{'='*60}")
    print(f"[*] Config: {label}  ({start_url})")
    print(f"{'='*60}")

    # Load checkpoint: which URLs already upserted?
    upserted_urls = load_checkpoint(config_key)
    if upserted_urls:
        print(f"  [resume] {len(upserted_urls)} URLs already upserted in previous run")

    session = make_session()
    doc_links = get_doc_links(session, start_url, max_pages=max_pages)
    print(f"  -> {len(doc_links)} unique links collected")

    # Filter out already-processed
    todo_links = [u for u in doc_links if u not in upserted_urls]
    print(f"  -> {len(todo_links)} to process, {len(upserted_urls)} already done\n")

    # Scrape concurrently
    docs: list[dict] = []
    completed = 0

    def worker(url):
        time.sleep(DELAY)
        return scrape_document(url, sphere, language)

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {pool.submit(worker, url): url for url in todo_links}
        for future in as_completed(futures):
            doc = future.result()
            if doc:
                docs.append(doc)
            completed += 1

    print(f"  -> {len(docs)} docs scraped out of {len(todo_links)} links\n")

    total_chunks  = 0
    total_skipped = 0

    for doc_idx, doc in enumerate(docs, 1):
        url    = doc["url"]
        chunks = chunk_document(doc)

        if not chunks:
            total_skipped += 1
            upserted_urls.add(url)  # Still mark as processed
            continue

        # Double-check: skip if first chunk already in Qdrant (safety)
        first_id = str(uuid.uuid5(UUID_NS, f"{url}:0"))
        existing = qd.retrieve(collection_name=COLLECTION, ids=[first_id], with_vectors=False)
        if existing:
            print(f"  [{label}] {doc_idx}/{len(docs)} — SKIP (already in Qdrant) — {doc['title'][:60]}")
            upserted_urls.add(url)
            total_chunks += len(chunks)
            continue

        texts = [c["text"] for c in chunks]
        print(f"  [{label}] {doc_idx}/{len(docs)} — {len(chunks)} chunks — {doc['title'][:60]}")
        vectors = embed_all(texts, ze)

        points = []
        for chunk_idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            point_id = str(uuid.uuid5(UUID_NS, f"{url}:{chunk_idx}"))
            points.append(PointStruct(
                id=point_id,
                vector=vec,
                payload={
                    "text":        chunk["raw_text"],
                    "title":       doc.get("title", ""),
                    "url":         url,
                    "doc_type":    doc.get("doc_type", ""),
                    "date":        doc.get("date", ""),
                    "number":      doc.get("number", ""),
                    "authority":   doc.get("authority", ""),
                    "status":      doc.get("status", ""),
                    "is_active":   doc.get("is_active", True),
                    "sphere":      doc.get("sphere", ""),
                    "language":    doc.get("language", ""),
                    "doc_kind":    doc.get("doc_kind", "other"),
                    "chunk_index": chunk_idx,
                    "chunk_total": len(chunks),
                },
            ))

        for i in range(0, len(points), 50):
            qd.upsert(collection_name=COLLECTION, points=points[i:i + 50])
        total_chunks += len(points)

        # Mark as upserted and save checkpoint every 10 docs
        upserted_urls.add(url)
        if doc_idx % 10 == 0:
            save_checkpoint(config_key, upserted_urls)

    # Final checkpoint
    save_checkpoint(config_key, upserted_urls)
    print(f"\n  [{label}] done — {total_chunks} chunks upserted, {total_skipped} docs skipped")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Crawl adilet.zan.kz → zembed → Qdrant")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Limit listing pages per config (omit = all)")
    args = parser.parse_args()

    if not ZE_API_KEY:
        sys.exit("Error: ZEROENTROPY_API_KEY not set in .env or environment")

    qd = QdrantClient(url=QDRANT_URL)
    ze = ZeroEntropy(api_key=ZE_API_KEY)

    print(f"Qdrant: {QDRANT_URL}")
    print(f"Collection: {COLLECTION} ({VECTOR_DIM}d Cosine)\n")
    setup_collection(qd)

    for sphere, language, url in SEARCH_CONFIGS:
        process_config(sphere, language, url, qd, ze, max_pages=args.max_pages)

    info = qd.get_collection(COLLECTION)
    print(f"\n{'='*60}")
    print(f"Final collection stats:")
    print(f"  vectors indexed : {info.vectors_count}")
    print(f"  points total    : {info.points_count}")
    print(f"  collection      : {COLLECTION}")
    print(f"  dashboard       : http://localhost:6333/dashboard#/collections")


if __name__ == "__main__":
    main()
