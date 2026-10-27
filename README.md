# Rome Mobility Intelligence

Foundation **FastAPI + scikit-learn** per il futuro ML operativo del trasporto pubblico di Roma.
Stato: **primo artifact sklearn reale addestrato e validato localmente**, pronto per review.
HistGradientBoosting con pesi di inclusione, soglia validation 0.35; TEST valutato una volta.
**Nessuna inference live o deployment**. [Risultati e limiti](docs/REAL_MODEL_EVALUATION.md).

Il [repository Data/ML](https://github.com/matteocavo/rome-public-transport-reliability)
rimane la sorgente di ingestion GTFS/GTFS-RT, Bronze/Silver, enrichment, feature engineering,
Gold, qualità dati e dashboard. Spark ML è un riferimento storico. Questo repository
contiene il runtime applicativo target sklearn/FastAPI, senza notebook o trasformazioni Spark.

## Architettura e contratto

```text
Databricks -> dataset etichettato v12 / input scoring versionato
           -> export SELECT limitato e riproducibile
           -> sklearn: preprocessing + modello + soglia rivalidata
           -> bundle locale immutabile -> FastAPI /health /ready /model/info
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
| `GET /ready` | App inizializzata; se artifact configurato deve essere caricabile, altrimenti 503 |
| `GET /model/info` | Tipo modello, timestamp, hash/versione contratto, soglia, metriche validation/TEST e flag synthetic; 503 senza modello |

La readiness skeleton non certifica un modello disponibile né la connessione Databricks.
Il modello si carica all'avvio e non viene ricaricato per ogni richiesta. Non esiste `/predict`
pubblico; `ModelService` espone inference interna guidata dal contratto e dalla soglia salvata.
Autenticazione e hosting di produzione sono fasi successive.

## Verifiche

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
4. Aggiungere prediction history, poi orchestrazione n8n.
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
