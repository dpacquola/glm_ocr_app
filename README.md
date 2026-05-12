# GLM OCR App

Webapp per convertire PDF sporchi, scansioni e immagini in **Markdown pulito** usando il modello GLM-OCR via Ollama.

Carica un documento, e l'app mostra le pagine originali a sinistra e il risultato OCR a destra, con supporto per tabelle, figure, elenchi e codice.

## Screenshot

```
┌─────────────────────┬─────────────────────────┐
│    Originale        │     Risultato OCR        │
│                     │                         │
│  ┌─────────────┐    │  ┌───────────────────┐  │
│  │             │    │  │ Markdown grezzo    │  │
│  │  PDF/Image  │    │  ├───────────────────┤  │
│  │  preview    │    │  │ Anteprima HTML     │  │
│  │             │    │  │ (tabelle, code...)  │  │
│  └─────────────┘    │  └───────────────────┘  │
└─────────────────────┴─────────────────────────┘
```

## Caratteristiche

- Caricamento PDF, PNG, JPG, BMP, TIFF, WebP
- Conversione pagine PDF in immagini (150 DPI)
- OCR via GLM-OCR su Ollama (locale o cloud)
- Pannello diviso ridimensionabile: originale a sinistra, OCR a destra
- Vista doppia del risultato: **Markdown grezzo** + **Anteprima renderizzata**
- Copia markdown con un click
- Download del risultato come file `.md`
- OCR singola pagina o OCR completo del documento
- Navigazione tra pagine con pulsanti o frecce tastiera

## Stack

| Componente | Tecnologia |
|------------|-----------|
| Backend | Python + FastAPI + Uvicorn |
| OCR Engine | GLM-OCR (1.1B) via Ollama |
| PDF processing | PyMuPDF (fitz) |
| Frontend | Vanilla JS + Marked.js |
| Stili | CSS custom |
| Database | Filesystem (JSON + PNG + MD) |

## Requisiti

- Python 3.10+
- Ollama con modello `glm-ocr:latest`
- GPU consigliata per velocità (CPU-only funziona ma è lento)

## Installazione locale (Linux / WSL)

```bash
# Clona il repository
git clone https://github.com/dpacquola/glm_ocr_app.git
cd glm_ocr_app

# Crea ambiente virtuale (opzionale)
python3 -m venv venv
source venv/bin/activate

# Installa dipendenze Python
pip install -r backend/requirements.txt

# Avvia Ollama (se non già in esecuzione)
ollama serve

# Scarica il modello GLM-OCR
ollama pull glm-ocr:latest

# Avvia l'app
cd backend
python serve.py
```

Apri `http://localhost:8000` nel browser.

## Deploy su RunPod (GPU cloud)

1. Crea un pod su [runpod.io](https://runpod.io) con GPU (es. RTX 4090)
2. Template: PyTorch. Porte esposte: `8000`, `11434`, `8889`
3. Connettiti via SSH e configura:

```bash
# Installa dipendenze
apt update && apt install -y zstd git
curl -fsSL https://ollama.com/install.sh | sh
ollama serve > /tmp/ollama.log 2>&1 &
ollama pull glm-ocr:latest

# Clona il progetto
git clone https://github.com/dpacquola/glm_ocr_app.git app

# Avvia l'app
cd /root/app/backend
unset OLLAMA_HOST
pip3 install -r requirements.txt
sed -i 's/host="localhost"/host="0.0.0.0"/' serve.py
nohup python3 serve.py > /tmp/server.log 2>&1 &
```

4. Apri la porta HTTP 8000 dalla dashboard RunPod

## API

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/upload` | POST | Carica PDF/immagine |
| `/api/meta/{file_id}` | GET | Ottieni metadati file |
| `/api/pages/{file_id}/{page}` | GET | Ottieni immagine pagina |
| `/api/ocr/{file_id}/{page}` | POST | Esegui OCR su una pagina |
| `/api/ocr/{file_id}/{page}` | GET | Ottieni risultato OCR salvato |
| `/api/ocr-all/{file_id}` | POST | OCR su tutte le pagine |
| `/api/health` | GET | Health check |

## Configurazione

Variabili d'ambiente:

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `OLLAMA_HOST` | `localhost:11434` | Host Ollama |
| `OLLAMA_MODEL` | `glm-ocr:latest` | Modello Ollama |

## Struttura del progetto

```
glm_ocr_app/
├── backend/
│   ├── main.py           # API FastAPI
│   └── serve.py          # Avvio server
├── frontend/
│   ├── index.html        # Interfaccia web
│   ├── app.js            # Logica frontend
│   └── styles.css        # Stili
├── temp_uploads/         # File temporanei (gitignorato)
└── requirements.txt      # Dipendenze Python
```
