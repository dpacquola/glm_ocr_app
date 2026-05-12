# GLM OCR App — Storia completa della conversazione

*Data sessione: 12/05/2026*

---

## 1. Primo contatto — Esplorazione del progetto

L'utente ha copiato i file del progetto in WSL Linux (`/home/dpac/GLM_OCR_APP/`).

### Struttura del progetto

```
GLM_OCR_APP/
├── backend/
│   ├── main.py          # API FastAPI (upload, OCR, health)
│   ├── serve.py         # Avvio uvicorn
│   └── requirements.txt # Dipendenze Python
├── frontend/
│   ├── index.html        # SPA — pannello diviso (originale | OCR)
│   ├── app.js            # Logica frontend
│   └── styles.css        # Stili
├── temp_uploads/         # Immagini pagine PDF + risultati OCR
├── Istruzioni_per_codebase.txt
└── venv/
```

### Come funziona

1. Caricamento PDF → convertito in PNG per ogni pagina (200 DPI)
2. OCR via Ollama → glm-ocr:latest via `/api/generate`
3. Frontend: sinistra = pagina originale, destra = markdown renderizzato

---

## 2. Test iniziale — Errore "Impossibile connettersi a Ollama"

- Ollama presente in WSL con glm-ocr:latest (1.1B, F16)
- CPU-only (nessuna GPU NVIDIA in WSL)
- Errore 502: `Impossibile connettersi a Ollama. Host provati: ['http://localhost:11434', 'http://172.30.192.1:11434']`
- **Causa reale**: timeout del modello su CPU (richieste >5 minuti per pagina)
- `httpx.RequestError` catturava il timeout → tentativo secondo host (Windows) → falliva → messaggio fuorviante

### Fix applicati a `backend/main.py`

| Modifica | Valore vecchio | Nuovo |
|----------|---------------|-------|
| DPI rendering PDF | 200 | 150 |
| Timeout richiesta Ollama | 300s | 600s |
| Messaggio errore | generico | distingue timeout da connessione |

---

## 3. Analisi hardware portatile

- **CPU**: Intel Core i7-4700HQ (4ª gen, Haswell, 2013)
- **GPU integrata**: Intel HD Graphics 4600 (1 GB)
- **GPU discreta**: NVIDIA GeForce GTX 760M (2 GB) — compute 3.0
- La GTX 760M è troppo vecchia per:
  - WSL2 GPU passthrough (richiede compute 5.0+)
  - Modelli ML moderni (solo 2 GB VRAM, glm-ocr serve ~2.2 GB)

---

## 4. Valutazione eGPU

Domanda: esistono GPU esterne via USB per portatile vecchio?

### Risultato
- **USB 3.x non supporta PCIe tunneling** → niente eGPU via USB normale
- **Thunderbolt 3/4 o USB4** necessari (40 Gbps)
- **OCuLink**: alternativa via slot NVMe (hacky, richiede apertura portatile)
- Portatile del 2014: probabilmente solo USB 3.0 → **nessuna eGPU possibile**

---

## 5. Soluzione cloud GPU — RunPod

### Provider confrontati

| Servizio | GPU | Costo/h | Facilità |
|----------|-----|---------|----------|
| **RunPod** | RTX 4090 24GB | ~$0.39 | Alta (template Ollama) |
| Vast.ai | RTX 4090 24GB | ~$0.20 | Media |
| Lambda Labs | A6000 48GB | ~$1.10 | Media |

### Setup RunPod completato

1. **Pod creato**: RTX 4090, template PyTorch
2. **Porte esposte**: 8000 (app), 11434 (Ollama), 8889 (VS Code)
3. **Ollama installato**: glm-ocr:latest scaricato
4. **App trasferita** via tmpfiles.org
5. **code-server installato**: VS Code via browser

### Dettagli accesso

- **URL app**: `https://3x9wfu5horvbfb-8000.proxy.runpod.net`
- **SSH**: `ssh 3x9wfu5horvbfb-64411a7e@ssh.runpod.io -i ~/.ssh/id_ed25519`
- **Download app**: `https://tmpfiles.org/dl/37640595/app.bin`

### Comandi setup pod

```bash
# Installare zstd + Ollama
apt update && apt install -y zstd
curl -fsSL https://ollama.com/install.sh | sh
ollama serve > /tmp/ollama.log 2>&1 &
ollama pull glm-ocr:latest

# Avviare app
cd /root/backend
unset OLLAMA_HOST  # fondamentale!
nohup python3 serve.py > /tmp/server.log 2>&1 &

# Installare VS Code Web
curl -fsSL https://code-server.dev/install.sh | sh
nohup code-server --port 8889 --auth none --bind-addr 0.0.0.0 > /tmp/codeserver.log 2>&1 &
```

### Problema riscontrato
- `OLLAMA_HOST=0.0.0.0` veniva letto dall'app come host Ollama invece che da Ollama come bind address
- **Fix**: `unset OLLAMA_HOST` prima di avviare l'app + `sed -i 's/host="localhost"/host="0.0.0.0"/' serve.py`

---

## 6. Miglioramenti frontend

### Modifiche richieste dall'utente

1. **Pannello destro diviso**: mostrare markdown grezzo (sopra) + anteprima renderizzata (sotto)
2. **Pulsante download**: scarica risultato OCR come file `.md`

### Dettaglio modifiche

**`index.html`** — Riorganizzato pannello destro:
- Sezione "Markdown grezzo" con `<pre id="ocr-raw">`
- Divider orizzontale
- Sezione "Anteprima" con `<div id="ocr-content">`
- Pulsante "Scarica" accanto a "Copia"

**`app.js`** — Aggiunte:
- `btnDownload`, `ocrRaw`, `ocrRawSection`, `ocrRenderedSection`
- Handler download: crea Blob → download con nome `[pdf]_pagina_N.md`
- `showOcrResult()`: popola sia raw che rendered
- `clearOcrResult()`: pulisce entrambi

**`styles.css`** — Nuove classi:
- `#ocr-panel`: flex column, padding 0
- `.ocr-sub-panel`: flex 1, flex column
- `.sub-panel-header`: stile intestazione sezione
- `.ocr-raw-content`: monospace, pre-wrap
- `.ocr-sub-divider`: linea 3px
- `.panel-header-actions`: flex row per bottoni

---

## 7. Persistenza dati (Network Volume)

### Problema
RunPod senza Network Volume perde tutti i dati quando il pod viene fermato.

### Soluzione
1. RunPod → Storage → Network Volumes → Add Volume
2. Regione: stessa del pod, Nome: es. `glm-ocr-data`, Dimensione: 10 GB (~2€/mese)
3. In pod → Edit → Network Volume: seleziona volume, Mount Path: `/workspace`
4. Lavorare sempre dentro `/workspace` — i dati sopravvivono a stop/start

---

## 8. Gestione con GitHub

Per evitare di ricaricare i file su tmpfiles ogni volta che modifichi qualcosa, abbiamo configurato Git + GitHub.

### Setup iniziale

**In WSL:**
```bash
cd /home/dpac/GLM_OCR_APP
git init
git config user.email "davide@email.com"
git config user.name "Davide"
git add -A
git commit -m "primo commit"
git branch -M main
git remote add origin https://github.com/dpacquola/glm_ocr_app.git
git push -u origin main
```

**Sul pod RunPod (prima volta):**
```bash
cd /root
git clone https://github.com/dpacquola/glm_ocr_app.git app
cd /root/app/backend
pip3 install -r requirements.txt
sed -i 's/host="localhost"/host="0.0.0.0"/' serve.py
nohup python3 serve.py > /tmp/server.log 2>&1 &
```

### Aggiornamento dopo modifiche locali

**In WSL (dopo aver modificato i file):**
```bash
cd /home/dpac/GLM_OCR_APP
git add -A
git commit -m "descrizione delle modifiche"
git push
```

**Sul pod (per ricevere gli aggiornamenti):**
```bash
cd /root/app && git pull && pkill -f serve.py && cd /root/app/backend && unset OLLAMA_HOST && nohup python3 serve.py > /tmp/server.log 2>&1 &
```

### Vantaggi
- Versionamento delle modifiche
- Backup su cloud
- Aggiornamento rapido del pod con `git pull`
- Possibilità di collaborare

---

## 9. Raccomandazioni finali

| Cosa | Consiglio |
|------|-----------|
| **Uso occasionale** | RunPod Stop quando non usi (non paghi GPU, solo disco) |
| **Uso frequente** | PC fisso con RTX 4060 Ti 16GB (~€450 GPU) |
| **Portatile nuovo** | Cercare con RTX 4060 laptop + almeno 16GB RAM |
| **Persistenza** | Network Volume su RunPod (2€/mese) |
| **Backup** | Salvare comandi e URL in file .txt |

---

## Riferimenti rapidi

### URL
- App: `https://3x9wfu5horvbfb-8000.proxy.runpod.net`
- RunPod: `https://runpod.io`
- GitHub: `https://github.com/dpacquola/glm_ocr_app`

### SSH
```
ssh 3x9wfu5horvbfb-64411a7e@ssh.runpod.io -i ~/.ssh/id_ed25519
```

### Avvio rapido dopo riavvio pod
```bash
unset OLLAMA_HOST
cd /root/app/backend && nohup python3 serve.py > /tmp/server.log 2>&1 &
```
Oppure con Network Volume:
```bash
unset OLLAMA_HOST
cd /workspace/app/backend && nohup python3 serve.py > /tmp/server.log 2>&1 &
```

### Aggiornamento dopo modifiche in locale
```bash
cd /root/app && git pull && pkill -f serve.py && cd /root/app/backend && unset OLLAMA_HOST && nohup python3 serve.py > /tmp/server.log 2>&1 &
```

---

*Fine documento — Generato il 12/05/2026*
