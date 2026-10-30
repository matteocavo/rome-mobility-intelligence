# Rome Mobility Intelligence v1.0.1

**Orchestrazione OCI opzionale — Deployment preparato; provisioning non ancora eseguito.**
A1 Flex su OCI Always Free resta il target preferito, attualmente bloccato dalla host capacity.
Il test con container reali su GitHub Actions classifica E2 Micro come **MARGINAL**:
le verifiche funzionali passano senza OOM o swap, ma avvio e riavvio sotto CPU limitata
richiedono circa 213 e 194 secondi. Questo risultato non autorizza il provisioning.
[Test E2 Micro e limiti della simulazione](ops/n8n/oci/E2_FIT.md) ·
[Runbook di deployment e backup OCI](ops/n8n/oci/README.md).
**Un solo scheduler attivo alla volta**; GitHub Actions resta il fallback, solo con opt-in.

**Progetto collegato:** [Rome Public Transport Reliability & Delay Prediction](https://github.com/matteocavo/rome-public-transport-reliability),
il repository Data/ML che alimenta questo runtime applicativo.

Applicazione pubblica **FastAPI + scikit-learn** per il ML operativo del trasporto pubblico di Roma.
Stato: **v1.0.1 — frontend GitHub Pages e backend Render Free live, prediction history Neon attiva**.
HistGradientBoosting con pesi di inclusione, soglia validation 0.35; TEST valutato una volta.
Nessuno SLA real-time garantito. Applicazione: <https://matteocavo.github.io/rome-mobility-intelligence/>.
Backend: <https://rome-mobility-intelligence-matteocavo.onrender.com>. [Risultati e limiti](docs/REAL_MODEL_EVALUATION.md).

**P0: infrastruttura ricorrente a 0 EUR.**
**Orchestrator low-code principale previsto: n8n Community Edition su OCI Always Free**. Il progetto mantiene un layer
low-code/no-code reale e significativo, principale se tecnicamente sostenibile a costo zero.
**GitHub Actions: zero-cost fallback scheduler**, temporaneo e best-effort, solo con opt-in.
Il cron richiede due esecuzioni/ora, ma la delivery osservata è irregolare: non garantisce
una cadenza di 30 minuti. [Limiti e diagnostica](docs/ZERO_COST_DEPLOYMENT.md#schedule-and-failure-semantics).
n8n: integrazione low-code scelta e preparata, non ancora installata su OCI.
Una subscription n8n Cloud a pagamento non può essere un requisito obbligatorio.
La delivery privata del modello su Render e i controlli production della v1.0.1 sono
completati nel carico osservato; [misure e limiti memoria](docs/RENDER_MEMORY_VERIFICATION.md).
Il test E2 Micro non verifica l'overhead OS/Docker della VM né il burst OCI.
[Architettura, quote e blocker](docs/ZERO_COST_DEPLOYMENT.md).

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
Prediction history PostgreSQL è opzionale e disabilitata di default.

## Frontend pubblico — v1.0.1

URL production: <https://matteocavo.github.io/rome-mobility-intelligence/>.
Il frontend React/Vite usa GitHub Pages e chiama soltanto le API anonime read-only del
backend Render; le credenziali del servizio, Databricks, Neon e l'artifact del modello
restano lato server. Il backend legge i dati operativi da Databricks e lo storico da Neon.
Il bundle di produzione non contiene mock o fallback sintetici: se l'API non è disponibile,
l'interfaccia mostra lo stato di caricamento/errore e consente un nuovo tentativo.

La pubblicazione usa GitHub Actions da `main`; frontend e backend sono live e gli
endpoint pubblici sono stati verificati su dati reali. Il servizio Render Free può andare in sleep e avere un cold start; non è
garantito un aggiornamento real-time. Geografia e forme derivano dal catalogo GTFS statico;
non vengono mostrate posizioni live o simulate dei veicoli.

L'infrastruttura mantiene il target ricorrente di 0 EUR entro i limiti dei piani gratuiti. Render
rimane sul piano Free esistente. Il codice sorgente è Apache-2.0; il modello reale resta
privato e non viene incluso nel repository né nel sito statico.
Dettagli, stato e blocker: [deployment production](docs/PRODUCTION_DEPLOYMENT.md).

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
secret privato e payload minimo. Nessuna n8n Admin API/key; Compose OCI preparato,
test con container reali eseguito su GitHub Actions, nessuna VM OCI ancora provisionata.
[Import, autenticazione e confini](docs/N8N_CLOUD_ORCHESTRATION.md).
Il backend production è disponibile via HTTPS; lo smoke dei workflow n8n resta una verifica opzionale separata.
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
5. Release pubblica v1.0.0: frontend Pages, backend Render e smoke test reali completati.

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

## License and Data Attribution

Original source code is Open Source under the [Apache License 2.0](LICENSE).
Copyright 2026 Matteo Cavo.

Third-party components and public transport data remain under their applicable
upstream licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for Roma
data attribution, licensing exceptions and the scope of the original work.

## Frontend pubblico

Il dashboard React/Vite è isolato in [`frontend/`](frontend/README.md), con interfaccia
IT/EN e mappa Leaflet. Usa le API pubbliche read-only per la popolazione scoring corrente e le predizioni
persistite, senza endpoint autenticati né fallback automatici ai mock. Build e deploy
del backend FastAPI restano indipendenti. I limiti attuali di geografia e modalità
sono documentati nel contratto frontend.

## Static last-known-good snapshot (v1.0.1)

The public dashboard uses a static last-known-good snapshot generated exclusively from previously acquired production data to provide an immediate first render on GitHub Pages. The frontend then hydrates automatically from the live API when the Render backend becomes available. Snapshot values retain their original observation timestamp and are never presented as newly acquired live data. The snapshot is validated before replacement; a failed refresh leaves the previous valid snapshot untouched. This remains compatible with the zero-cost GitHub Pages + Render Free deployment model.

Snapshot refresh PRs use a stable branch and require the normal frontend/backend checks before human merge; GITHUB_TOKEN cannot bypass branch protection.

Il workflow manuale `refresh-snapshot.yml` parte solo da `main`, conserva il candidato
validato durante il cambio di branch e aggiorna `snapshot-refresh` senza force push.
Riutilizza la PR aperta; un cambiamento del solo `capturedAt` non genera un commit.
Un conflitto durante il merge di `main` interrompe il processo senza pubblicazione.
I workflow `quality.yml` e `frontend.yml` vengono avviati esplicitamente tramite
`workflow_dispatch` sul branch della PR, prima del merge umano. Il token del job
richiede `contents: write`, `pull-requests: write` e `actions: write`; non serve un PAT.
Nelle impostazioni Actions deve essere consentita la creazione di PR tramite Actions.
Prima di considerare verificata l'automazione, eseguire una prova su GitHub:
controllare il numero della PR su due esecuzioni, lo SHA dei check, il rispetto
della protezione di `main` e il deploy Pages dopo un eventuale merge autorizzato.
I test locali simulano Git/GitHub CLI e non sostituiscono questa verifica remota.
