# Backend API (FastAPI)

## Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip3 install -r requirements.txt
```

## Run

```bash
python main.py
```

The API will be available at `http://localhost:8000`

### Health Check
- GET `/health` - Returns `{"status": "ok"}`

### Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
