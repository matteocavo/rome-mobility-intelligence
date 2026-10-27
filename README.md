# Rome Mobility Intelligence

**SELECTED / DEPLOYMENT PREPARED / NOT YET PROVISIONED**.
[OCI deployment and backup runbooks](ops/n8n/oci/README.md). **ONLY ONE scheduler active at a time**; Actions remains fallback only.

API locale **FastAPI + scikit-learn** per il ML operativo del trasporto pubblico di Roma.
Stato: **inference sul modello reale e prediction history PostgreSQL opzionale**, per review.
HistGradientBoosting con pesi di inclusione, soglia validation 0.35; TEST valutato una volta.
Nessuno SLA live o deploy pubblico. [Risultati e limiti](docs/REAL_MODEL_EVALUATION.md).

**P0: infrastruttura ricorrente a 0 EUR.**
**PRIMARY LOW-CODE ORCHESTRATOR: n8n Community Edition on OCI Always Free**. Il progetto mantiene un layer
low-code/no-code reale e significativo, principale se tecnicamente sostenibile a costo zero.
**GitHub Actions: zero-cost fallback scheduler**, ogni 30 minuti e solo con opt-in.
n8n: primary low-code integration; selected and prepared, not yet provisioned.
Una subscription n8n Cloud a pagamento non può essere un requisito obbligatorio.
Delivery modello privata in build, gate Linux/RAM e opt-in schedule ancora da verificare
prima di un deployment reale. [Architettura, quote e blocker](docs/ZERO_COST_DEPLOYMENT.md).

Il [repository Data/ML](https://github.com/matteocavo/rome-public-transport-reliability)
rimane la sorgente di ingestion GTFS/GTFS-RT, Bronze/Silver, enrichment, feature engineering,
Gold, qualità dati e dashboard. Spark ML è un riferimento storico. Questo repository
contiene il runtime applicativo target sklearn/FastAPI, senza notebook o trasformazioni Spark.

## Architettura e contratto

```text
Databricks -> dataset etichettato v12 / input scoring versionato
           -> export SELECT limitato e riproducibile
           -> sklearn: preprocessing + modello + soglia rivalidata
           -> bundle trusted immutabile -> FastAPI inference e metadata
```

47 feature grezze: 42 numeriche e 5 categoriche (`route_id`, `route_type`, `direction_id`,
`agency_id`, `current_status`). `trip_progress_ratio` esclusa. Evento `next_stop_delay_ge_300s`:
ritardo realizzato alla prossima fermata **>=300 secondi**. L'hash canonico degli input resta
`11682b3cc1ab5c1d8440af4f6294e932e815126c3dd86ab609f4d5f8f35c41a5`.
La soglia probabilistica Spark storica non viene ereditata: si sceglie sul validation set.

Il solo JSON del contratto è incorporato senza modificarlo dalla revisione core
`7d263629b533f57af46ffaadcb56e4fcc0f296a7`; non è una copia del repository Databricks.
L'hash upstream include preprocessing Spark storico ed è provenienza degli input,
non prova di equivalenza con sklearn. Il bundle ha anche un digest del contratto completo.

## Setup locale

Python **3.11+**; ambiente isolato, nessuna credenziale necessaria per i test:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
Copy-Item .env.example .env
```

`.env.example` contiene solo placeholder; `.env`, export e artifact runtime sono ignorati.
Configurare le variabili `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`,
`DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET` oppure `DATABRICKS_CREDENTIAL_TARGET`,
`DATABRICKS_CATALOG`, `DATABRICKS_SCHEMA`, `TRAINING_TABLE`,
`INFERENCE_TABLE`, `MODEL_ARTIFACT_PATH`, `ENVIRONMENT`. Nessun segreto nei log o in Git.
Lasciare `MODEL_ARTIFACT_PATH` vuoto per la modalità skeleton.

## Training fixture e artifact

Eseguire dalla root, con le dipendenze installate:

```powershell
python -m scripts.train_model --source fixture --output artifacts/fixture-v1
# Fixture appena prodotta da codice locale fidato: conservare la pin fuori dal bundle.
$env:MODEL_ARTIFACT_PATH=(Resolve-Path artifacts/fixture-v1).Path
$env:MODEL_ARTIFACT_ROOT=(Resolve-Path artifacts).Path
$env:MODEL_ARTIFACT_MANIFEST_SHA256=(Get-FileHash "$env:MODEL_ARTIFACT_PATH/checksums.json" -Algorithm SHA256).Hash.ToLowerInvariant()
python -m scripts.validate_model_artifact $env:MODEL_ARTIFACT_PATH --trusted-root $env:MODEL_ARTIFACT_ROOT --expected-manifest-sha256 $env:MODEL_ARTIFACT_MANIFEST_SHA256
python -m uvicorn app.main:app --reload
```

La fixture è **solo sintetica**, marcata nei metadata e in `/model/info`. Il bundle contiene
pipeline joblib, metadata JSON, contratto completo e checksum. Non sovrascrive bundle esistenti.
Caricare soltanto artifact locali fidati: joblib può eseguire codice; la pin del manifest deve essere fornita dalla configurazione fidata esterna al bundle.
Non ricavare la pin da un bundle scaricato e non revisionato: firmerebbe la sostituzione dell’attaccante.
Il loader rifiuta symlink/reparse e deserializza gli stessi byte verificati, senza riaprire il file. Il loader richiede la stessa versione sklearn.

## Training Databricks

```powershell
python -m scripts.train_model --source databricks --plan data_exports/private-plan.json --output artifacts/model-v1
```

Richiede configurazione privata, versione training **12** esplicita, confini temporali
congelati, budget e misure pilota di capacità. Nessun fallback a latest o allo storico v8.
Il primo export e training reale sono stati completati su v12; artifact e dati restano locali,
fuori Git. [Valutazione reale](docs/REAL_MODEL_EVALUATION.md). Vedere
[accesso dati](docs/DATA_ACCESS.md) e [training/valutazione](docs/MODEL_TRAINING.md).

## API

| Endpoint | Comportamento |
| --- | --- |
| `GET /health` | Stato processo, servizio e versione |
| `GET /ready` | Modello trusted caricato, integrity e configurazione identità; 503 senza modello |
| `GET /model/info` | Tipo modello, timestamp, hash/versione contratto, soglia, metriche validation/TEST e flag synthetic; 503 senza modello |
| `POST /predict` | Una osservazione con esattamente le 47 feature |
| `POST /predict/batch` | Lista di osservazioni; max 100, configurabile verso il basso |
| `GET /predictions/current?limit=50` | Latest available current scoring snapshot, inference read-only e freshness |

Il modello si carica una volta all'avvio tramite il loader trusted. La soglia viene dai metadata
(0.35 per il modello reale corrente), mai dalla richiesta. Le fixture sintetiche sono rifiutate
dagli endpoint inference fuori da `ENVIRONMENT=test`. `/ready` non esegue query SQL.
[Contratti, errori, esempi sintetici e limiti](docs/INFERENCE_API.md).
Prediction history PostgreSQL è opzionale e disabilitata di default; nessun frontend.
Autenticazione API e hosting sono fasi successive.
Public deployment is NOT yet approved: serve un account OS di servizio separato, senza ownership
dello storage modello e senza accesso al credential store personale dell'operatore.

## Prediction history PostgreSQL

`POST /predictions/current/persist?limit=50` abilita il trigger manuale soltanto con
`ENABLE_PREDICTION_PERSISTENCE=true` e `DATABASE_URL` privata. Il batch corrente viene salvato
atomicamente con unique constraint e ON CONFLICT; un secondo batch identico non duplica righe.
`GET /predictions/history` consulta lo storico con filtri allowlist, max 200 righe e intervalli
max 7 giorni. Preview e POST /predict restano stateless. Nessuna scrittura Databricks.
Schema gestito da `alembic upgrade head`, mai creato automaticamente all'avvio.
[Setup, idempotenza, sicurezza e validazione PostgreSQL nativa](docs/PREDICTION_HISTORY.md).

## Orchestrazione n8n Community

Primary: n8n Community su OCI Always Free, con workflow importabili e inattivi in [ops/n8n](ops/n8n/README.md).
Schedule ogni 30 minuti, cold-start wait/retry finiti e summary compatti; webhook separato con Header Auth.
Il client server-side FastAPI usa soltanto URL HTTPS configurata, host esplicitamente fidato,
secret privato e payload minimo. Nessuna n8n Admin API/key; Compose OCI preparato ma nessun container reale avviato.
[Import, autenticazione e confini](docs/N8N_CLOUD_ORCHESTRATION.md).
Lo smoke end-to-end resta pending: n8n Cloud non può raggiungere in sicurezza il FastAPI locale.
Nessun deploy pubblico o tunnel è approvato o creato.

## Verifiche

Le API operative richiedono `X-RMI-Service-Key`, configurata privatamente come
`N8N_SERVICE_API_KEY` e distinta dal secret webhook. `/health` resta pubblica, `/ready` anonima
è ridotta; i dettagli richiedono la chiave. Questa credenziale non va al frontend.
[Deployment sicuro](docs/SECURE_DEPLOYMENT.md): auth, rate/body limits, CORS/host, immagine
non-root senza modello incluso, un worker e requisiti HTTPS/secret manager.
Nessun deployment pubblico è stato eseguito; la configurazione production è fail-closed.

```powershell
python -m compileall -q app scripts tests
pytest -q
ruff check .
python -m scripts.check_repository
git diff --check
```

CI GitHub Actions su push/PR per Python 3.11 e 3.12, senza credenziali Databricks.
I test coprono contratto, SQL read-only e budget, preprocessing, purging, soglia,
isolamento del TEST, endpoint e persistenza/ricaricamento in un nuovo processo.
Mypy rinviato: le verifiche attuali usano ruff e test funzionali per evitare override rumorosi
delle API pandas/sklearn; non viene dichiarata copertura statica completa.

## Roadmap

1. Revisionare il primo artifact reale e il protocollo di valutazione.
2. Acquisire nuove date TEST indipendenti e rivalidare prima del serving operativo.
3. Accettare freshness, autenticazione e serving inference.
4. Preparare il deployment sicuro prima dello smoke n8n Cloud; mantenere i workflow inattivi.
5. React e UX/UI con Google AI Studio, in una fase successiva.

Nessuna modifica al core, ai Job o a Databricks è richiesta da questa foundation.
[Architettura e responsabilità](docs/ARCHITECTURE.md).

## Artifact reale locale

Per avviare soltanto metadata/readiness con il bundle validato, presente solo sulla macchina di training:

```powershell
# La configurazione .env locale punta alla copia protetta e include root/pin esterne.
python -m uvicorn app.main:app
```

Il clone Git non include il modello. Con artifact non configurato resta la modalità skeleton.
Non rilanciare il training sullo stesso TEST per ottimizzarlo. Il training effettivo usa il commit
`f9dbf187185a2c9426970b42f2dfa9748615f45d`; le modifiche documentali successive non riaddestrano il modello.

## Identità Databricks separata

Il canale applicativo usa OAuth M2M di un service principal con scope `sql`, senza fallback
al profilo CLI personale o a `DATABRICKS_TOKEN`. Il secret locale è nel Credential Manager
Windows; `.env` contiene soltanto client ID, endpoint e nome della voce protetta.
Ogni connessione verifica `current_user()` contro il client ID configurato prima della query.
Permessi runtime e verifiche: [workload identity](docs/WORKLOAD_IDENTITY.md).

## Confini di sicurezza runtime

Artifact path assoluto sotto MODEL_ARTIFACT_ROOT e MODEL_ARTIFACT_MANIFEST_SHA256 esterna sono
obbligatori se si configura un modello. La copia in artifacts/ resta staging storico; la copia
servita locale è fuori da OneDrive, in storage con ACL restrittive. Un clone non include la pin
né il modello. Query: deadline 120s, coda massima 1s, un solo worker SQL per warehouse/processo,
STATEMENT_TIMEOUT di sessione e LIMIT server-side. [Dettagli e limiti](docs/RUNTIME_SECURITY.md).
