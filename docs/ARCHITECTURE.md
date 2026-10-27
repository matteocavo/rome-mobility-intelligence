# Architettura

## Decisione P0: costo ricorrente zero

Produzione candidata: **GitHub Actions -> HTTPS FastAPI -> Databricks / PostgreSQL**.
Trigger iniziale ogni 30 minuti, disabilitato fino a opt-in esplicito, senza ping keep-alive.
n8n Cloud e i suoi workflow rimangono **OPTIONAL / DEMO / USER-PROVIDED EXTERNAL ORCHESTRATOR**.
Non occorre n8n per il percorso production e non va attivato contemporaneamente allo schedule
Actions. [Delivery modello privata, quote, cold start e gate](ZERO_COST_DEPLOYMENT.md).

## Preparazione deployment

Tutti gli endpoint dati/inference sono ora service-to-service con X-RMI-Service-Key;
il frontend futuro richiede un'autenticazione utenti separata e non riceve questa chiave.
HttpSecurity applica auth prima del body, budget globali bounded per classe, limiti byte,
Host allowlist, header e log minimizzati. CORS è vuoto di default; forwarded headers non
sono trusted. /health è liveness e /ready anonima è ridotta; i dettagli sono protetti.
Container non-root provider-neutral, modello read-only (mount o immagine privata root-owned)
con digest esterno, un solo
worker. Nessun provider o deployment effettivo. [Audit e requisiti](SECURE_DEPLOYMENT.md).

## Confini

| Sistema | Responsabilità |
| --- | --- |
| Databricks / repository core | Ingestion, Bronze/Silver/enrichment, feature causali, etichette, Gold, serving datasets, qualità e dashboard |
| Questo repository | Configurazione, accesso SELECT, training/evaluation sklearn, persistenza, caricamento, inference interna e API FastAPI |
| n8n Cloud | Template HTTP inattivi e boundary webhook autenticato; nessun duplicato dei Job Databricks |
| React + Google AI Studio, futuro | App e progettazione UX/UI che consumano API validate |

Spark ML rimane ricerca/riferimento storico. Non si converte la Random Forest Spark;
il modello sklearn richiede selezione e valutazione proprie. Il core mantiene la preparazione
causale sull'intero storico: non viene ricalcolata sul campione locale.

## Struttura

```text
app/api/routes/       health, readiness e metadata modello
app/core/             environment e logging
app/contracts/        contratto upstream fissato e metadata Pydantic v2
app/data/             SELECT bounded, repository training e scoring input
app/ml/               preprocessing, candidati, metriche, soglia e bundle
app/services/         ModelService, caricamento unico e inference interna
scripts/              CLI training/validation e controlli repository
tests/                fixture sintetiche e test offline
artifacts/            bundle locali ignorati da Git
.github/workflows/    CI senza credenziali
```

La creazione dell'app non apre connessioni e non esegue training. L'avvio tenta un solo
caricamento dell'artifact, se configurato. Un errore mantiene il processo disponibile per
`/health` ma rende `/ready` 503; i dettagli sensibili non entrano nelle risposte pubbliche.
Nessun caricamento implicito di un modello storico o precedente in caso di errore.

## Provenienza

Source of truth: core HEAD remoto `7d263629b533f57af46ffaadcb56e4fcc0f296a7`, PR #7-#11 mergiate.
Il checkout core locale era ancora `a2dcae8f5a858a6ac4e7d08a5be8d67ff51e0a1e`;
è rimasto intatto. I sette file richiesti sono stati letti dalla revisione remota fissata.
JSON e generatore SQL del contratto risultano uguali al checkout locale, al netto dei fine riga.

Fonti upstream fissate:

- [Contratto JSON](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/contracts/operational_ml.json)
- [Proiezioni SQL](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/contracts/operational_ml.py)
- [Handoff](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/OPERATIONAL_ML_HANDOFF.md)
- [Model serving](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/MODEL_SERVING.md)
- [Current scoring](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/CURRENT_SCORING.md)
- [Decisioni](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/ARCHITECTURE_DECISIONS.md)
- [Roadmap](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/ROADMAP.md)

Stati storici nelle sezioni Spark non diventano impostazioni operative sklearn. Nessuna
autenticazione, scheduler attivo, frontend o deploy cloud in questa fase. I template n8n Cloud
restano inattivi. La prediction history
PostgreSQL è ora un componente opzionale, disabilitato di default.

## Stato dopo il primo training reale

È disponibile localmente il primo bundle sklearn reale validato; [evidenze](REAL_MODEL_EVALUATION.md).
ModelService e gli endpoint metadata/readiness sono stati verificati con questo artifact
in un’app ASGI locale. Nessun serving pubblico o scheduler inference abilitato.
Il modello e la cache rimangono fuori Git; Databricks e il repository core sono rimasti invariati.

## Confine identità

Databricks SQL è autenticato con identità workload dedicata e permessi read-only sui
due dataset necessari. [Configurazione e prove](WORKLOAD_IDENTITY.md). Il precedente training
reale resta un evento storico eseguito prima di questa separazione; non viene ripetuto.
Prima di un deploy pubblico separare anche account OS/runtime, in modo che un processo
compromesso non possa leggere il profilo o il credential store personale dell’operatore.

## Artifact e query

Il serving usa soltanto artifact approvati con digest esterno, root fidata e byte verificati
prima della deserializzazione. Query ammesse entro deadline, cap righe e concorrenza per processo.
[Disegno e prove](RUNTIME_SECURITY.md). La protezione non sostituisce isolamento OS, auth API
o rate limiting di un futuro deployment pubblico.

## Inference stateless locale

Le route /predict e /predict/batch validano le 47 feature con schema Pydantic chiuso e usano
il ModelService trusted già caricato; il lock serializza predict_proba e la threshold proviene
dai metadata. /predictions/current usa CurrentScoringRepository con tabella fissa, ultimo
feed_timestamp, lineage verificata e ordinamento deterministico. Identificativi operativi
restano separati dall'input modello e il ritardo osservato è distinto dalla prediction next stop.
Questi endpoint preview non scrivono history; [contratto API e confini](INFERENCE_API.md).

## Persistence applicativa opzionale

Databricks rimane sorgente read-only; CurrentScoringService riusa il contract e ModelService
per preview e BatchScoringService. Solo il trigger manuale abilitato esplicitamente scrive in
PostgreSQL tramite PredictionHistoryRepository. Database gestisce engine/pool/sessioni,
models definisce lo schema e Alembic applica le migrazioni fuori dal runtime HTTP.
La history API legge soltanto PostgreSQL, con filtri e range bounded. Nessun SQL business nelle
route, salvataggio implicito, scheduler attivo o frontend. n8n è soltanto un client opzionale
di questi endpoint. [Disegno e limiti](PREDICTION_HISTORY.md).

## Orchestratore n8n Cloud

Lo schedule n8n chiama readiness → persistence → history → summary, con due retry bounded.
FastAPI resta responsabile di contract, modello, SQL, transazioni e idempotenza.
Il client server-side N8nClient può notificare esclusivamente il webhook HTTPS configurato,
con host Cloud allowlisted e Header Auth. Il workflow webhook distinto valida l'evento e
risponde soltanto con ACK: non richiama FastAPI né esegue persistence. Non esiste un endpoint
pubblico di trigger e nessun endpoint esistente viene modificato per chiamare n8n.
Questo evita loop tra trigger e operazione. Nessuna Admin API o credenziale DB/Databricks
in n8n. Google AI Studio/frontend futuro passa sempre da FastAPI autenticata/rate-limited.
[Configurazione/import e smoke Cloud pending](N8N_CLOUD_ORCHESTRATION.md).
