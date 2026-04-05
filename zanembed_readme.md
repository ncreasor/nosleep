# zanembed-v01

A bilingual (Russian / Kazakh) text embedding model fine-tuned for Kazakhstani legal documents.

Built on top of [zembed-1](https://huggingface.co/zeroentropy/zembed-1) and adapted via LoRA fine-tuning on triplet loss using 2 000 legal documents from [adilet.zan.kz](https://adilet.zan.kz).

## Why?

General-purpose embedding models perform poorly on Kazakhstani legal texts — the vocabulary is domain-specific, bilingual (Russian + Kazakh), and full of legislative structure (articles, clauses, amendments). zanembed-v01 closes this gap by training directly on the legal corpus.

## Pipeline

```
adilet.zan.kz ──scrape──> law_dataset_rus.json
                          laws_dataset_training.json (1000 docs, balanced)
                          laws_dataset_kaz.json      (1000 docs, balanced)
                              │
                              ▼
                    Triplet Generation (~3000 pairs)
                    - cross-lingual RU↔KAZ (same doc ID)
                    - same-sphere positives
                    - cross-sphere hard negatives
                              │
                              ▼
                    Content Cleaning (drop stubs, amendments)
                              │
                              ▼
                    LLM Labeling (Kimi K2.5 via Groq)
                    - filter low-confidence / unrelated
                              │
                              ▼
                    LoRA Fine-tuning (triplet loss on zembed-1)
                              │
                              ▼
                    zanembed-v01-lora/
                              │
                              ▼
                    Qdrant Seeding (kazakh_laws collection)
```

## Files

| File | Description |
|------|-------------|
| `zanembed_v01.ipynb` | Complete pipeline notebook (scraping → training → seeding) |
| `scraper.py` | Standalone CLI scraper for adilet.zan.kz |
| `seeding.py` | Standalone CLI for indexing documents into Qdrant |
| `law_dataset_rus_checkpoint.json` | Full Russian scrape (~all spheres, all pages) |
| `laws_dataset_training.json` | Balanced 1000-doc Russian training set (250/sphere) |
| `laws_dataset_kaz.json` | Balanced 1000-doc Kazakh training set (250/sphere) |
| `triplets_raw.json` | Raw semantic triplets before cleaning |
| `triplets_labeled.json` | LLM-labeled triplets (filtered, high-confidence) |

## Data source

All documents are scraped from Kazakhstan's official legal database [adilet.zan.kz](https://adilet.zan.kz). Four legal spheres are covered:

| Sphere | Filter | Docs |
|--------|--------|------|
| Farming | `ir=1_005` | 250 |
| Labor | `ir=1_002` | 250 |
| Finance | `ir=1_006` | 250 |
| Sales and others | `ir=1_019` | 250 |

Each document includes: URL, title, document type, date, number, authority, status (Active/Repealed), sphere, and full text content.

## Model architecture

- **Base model:** zeroentropy/zembed-1 (multilingual sentence embedding)
- **Adaptation:** LoRA (r=16, alpha=32)
- **Target modules:** q_proj, v_proj, k_proj, o_proj, gate_proj, up_proj, down_proj
- **Trainable params:** ~0.5% of total
- **Loss:** Triplet loss with cosine distance (margin=0.3)
- **Training:** 3 epochs, batch_size=1, lr=2e-4, linear warmup (100 steps)
- **Embeddings:** 1280-dimensional vectors

## Triplet types

| Type | Description | Count |
|------|-------------|-------|
| `cross_lingual_ru_kaz` | Same law, RU anchor → KAZ positive | ~1000 |
| `cross_lingual_kaz_ru` | Same law, KAZ anchor → RU positive | ~1000 |
| `same_sphere_ru` | Different docs, same sphere (RU) | ~1000 |
| `same_sphere_kaz` | Different docs, same sphere (KAZ) | ~1000 |
| Hard negatives | Always from a different sphere | — |

## LLM labeling

Each triplet is scored by **Kimi K2.5** (via Groq) for:
- Relationship type: amends / supplements / parallel / contradicts / unrelated
- Anchor-positive similarity score
- Hard negative distinctness
- Deprecation status
- Confidence score

Triplets are filtered out if confidence < 0.65, relationship is "unrelated", hard negative is not distinct, or the document is deprecated.

## Qdrant collection

The `kazakh_laws` collection stores chunked and embedded legal documents:

- **Vectors:** 1280-dim, cosine distance
- **Payload indexes:** `status`, `sphere`, `language`
- **Chunking:** Article-boundary splitting → paragraph splitting → sliding window (350 words, 50 overlap)
- **Quality filter:** Minimum 50 words, minimum 40% alphabetic characters

## Quick start

### Scrape documents

```bash
python scraper.py                     # scrape /rus section
python scraper.py --lang kaz          # scrape /kaz section
python scraper.py --max-pages 5       # limit pages (testing)
```

### Seed Qdrant

```bash
ZEROENTROPY_API_KEY=<key> python seeding.py
```

### Run the full pipeline

Open `zanembed_v01.ipynb` in Google Colab (TPU runtime recommended for training) and run cells sequentially.

## Environment variables

| Variable | Required for | Description |
|----------|-------------|-------------|
| `GROQ_API_KEY` | LLM labeling | Groq API key for Kimi K2.5 |
| `ZEROENTROPY_API_KEY` | Embedding + seeding | ZeroEntropy API key for zembed-1 |
| `QDRANT_URL` | Seeding | Qdrant instance URL (default: `http://localhost:6333`) |

## HuggingFace

Pre-labeled triplets are available on HuggingFace:

```python
from huggingface_hub import hf_hub_download

path = hf_hub_download(
    repo_id="selffounder/zanembed_v01",
    filename="triplets_labeled.json",
    repo_type="dataset",
)
```
