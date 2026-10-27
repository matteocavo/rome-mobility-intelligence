# Operational inference API

Estensione opzionale: [prediction history PostgreSQL](PREDICTION_HISTORY.md).
POST /predictions/current/persist è un trigger manuale esplicitamente abilitato, disabilitato
di default; GET /predictions/history è read-only con range/limit bounded. Gli endpoint preview
descritti sotto restano stateless e non salvano automaticamente righe. Le affermazioni sotto
sull'assenza di persistenza si riferiscono a questi endpoint e allo smoke iniziale della PR #14.

Inference sklearn stateless locale. Public deployment is NOT yet approved.
Il modello reale corrente è Weighted HistGradientBoostingClassifier, già addestrato:
nessun training o aggiornamento del bundle in questa fase. La versione pubblica è il digest
SHA-256 del manifest approvato, stabile e indipendente dal nome della directory:
`fb68e01e6893c841236687ed4297d940fda0322824e025c7d3fe6bc00403332e`.
La threshold 0.35 viene letta esclusivamente dai metadata trusted; decisione `p >= threshold`.

## Avvio e contratto

Configurare root, path assoluto e digest esterno del modello approvato, più OAuth M2M SQL
read-only. Non ricavare il digest da un download non fidato. Avvio locale, senza access log
degli input HTTP: `python -m uvicorn app.main:app --host 127.0.0.1 --no-access-log`.
Non viene aperto alcun listener durante i test ASGI. Nessun deploy pubblico.

Input raw: 47 campi obbligatori (42 numerici, 5 categorici) dal contratto incorporato.
Hash `11682b3cc1ab5c1d8440af4f6294e932e815126c3dd86ab609f4d5f8f35c41a5`.
I nomi sono esposti nello schema Pydantic `/openapi.json`, senza dati reali.
Numerici: float coercibili e finiti oppure null; route_type/direction_id: interi coercibili
oppure null; altre categorie: stringhe oppure null. Null espliciti sono gestiti dalla pipeline;
un campo assente resta errore 422. Le categorie sconosciute sono gestite dall'encoder esistente.
Ordine ricostruito dal contract prima di predict_proba. Nessun target o campo extra ammesso.

## Endpoint

`POST /predict`: body JSON con esattamente le 47 feature, nessun wrapper e nessun parametro
query. Restituisce model_version, feature_contract_hash, threshold, major_delay_probability,
predicted_major_delay. Non accetta SQL, path, threshold o metadata arbitrari.

`POST /predict/batch`: body JSON lista delle stesse osservazioni. Ordine preservato.
`INFERENCE_MAX_BATCH_ROWS=100`, validato tra 1 e 100: nessun batch illimitato.
Lista vuota: 400; oltre il limite configurato: 413; singola riga invalida: 422.
Output: metadata comuni, rows e predictions con probability/boolean per riga.

Esempio esclusivamente sintetico, generato dal contract (non eseguire training):

```python
from app.contracts.operational_ml import NUMERIC, CATEGORICAL
row = {name: None for name in NUMERIC + CATEGORICAL}
row.update(route_id="synthetic-route", route_type=3, direction_id=0)
# requests.post("http://127.0.0.1:8000/predict", json=row)
# requests.post("http://127.0.0.1:8000/predict/batch", json=[row, row])
```

`GET /predictions/current?limit=50`: solo parametro limit intero positivo; massimo uguale
al max batch configurato. Il default effettivo è min(50, max batch). Query param extra o duplicati,
limit invalido/sopra il massimo: 422 prima di qualsiasi SELECT. Nessun filtro arbitrario.
La tabella è fissata nel codice: `rome_transport.features.next_stop_delay_scoring`.
I setting legacy catalog/schema/table del training non possono cambiarla.

Il repository seleziona `MAX(feed_timestamp)` dalla tabella corrente nella stessa SELECT,
proietta solo le colonne del contract, verifica hash, lineage di preparazione e grain nel batch,
poi ordina per feed_timestamp, entity_id, trip_id, stop_sequence, stop_id e applica un LIMIT
parametrizzato. Le window di lineage precedono il LIMIT e coprono tutto l'ultimo feed.
Nessun fallback a un feed vecchio quando l'ultimo è invalido. Schema reale ispezionato read-only.
Non si rivendica un nuovo audit globale di tutte le righe o una certificazione downstream Gold.

Output: metadata modello, source_watermark UTC, prediction_generated_at UTC,
source_age_seconds e rows. Ogni riga include route_id, trip_id, vehicle_id, stop_id,
feed_timestamp, current_arrival_delay_seconds, probability, decisione e threshold.
`current_arrival_delay_seconds` è il ritardo osservato attuale; la probabilità riguarda
major delay (ritardo >=300s) alla fermata successiva. Non sono la stessa misura.

## Freshness ed errori

Semantica: **latest available current scoring snapshot**. Source age è l'intervallo tra feed
e generazione della risposta; non certifica ingestion continua. Snapshot vecchi possono essere
restituiti con età esplicita: nessuno SLA live, realtime o 10 minuti. Timestamp futuri rifiutati.

400: input semanticamente invalido (batch vuoto); 413: batch troppo grande; 422: schema/contract
invalido; 503: modello assente/non operativo oppure sorgente indisponibile/capacità esaurita;
504: application query deadline. Non si restituiscono traceback, valori rifiutati, path o segreti.
I log API contengono nomi evento fissi, senza righe, SQL o exception raw.

`/ready`: model_ready, artifact_integrity, workload_identity_configured e
databricks_readiness=not_checked. Configurazione identità non significa verifica di connessione:
nessun OAuth o SQL a ogni health check. `/model/info`: tipo, versione, threshold, trained_at,
hash, metriche validation/TEST, serving_status e artifact_integrity_verified, senza path/secret.

## Sicurezza e limiti

Il loader F02 rimane unico: root fidata, pin esterna, rifiuto symlink/reparse e caricamento
dei byte verificati. Il ModelService carica una volta e serializza predict_proba con un lock.
Fuori da ENVIRONMENT=test gli artifact sintetici non possono servire prediction operative.
Databricks usa solo workload M2M read-only, con identity check per connessione e nessun PAT/CLI.
Il client F06 conserva deadline 120s, coda 1s, concorrenza 1 per processo/warehouse,
cancel esplicito e slot trattenuto fino a cleanup, STATEMENT_TIMEOUT di sessione,
retry limitati e cap righe server-side. `INFERENCE_MAX_BYTES=8000000` limita il fetch client-side.
Cancellation request non garantisce terminazione remota immediata. LIMIT non limita i byte
scansionati dal server. Un deployment con più processi richiede un gate distribuito.

Questi endpoint preview non persistono righe o prediction. Il trigger history è separato e
opt-in. Nessun cron, training, frontend, n8n o scrittura Databricks. Nessuna autenticazione API
o difesa per esposizione Internet viene dichiarata.
Prima del deploy pubblico serve un account OS separato, senza ownership di storage/config
modello e senza accesso al credential store personale. Tale isolamento non è implementato qui.

## Smoke test reale read-only — 2026-10-27

Dopo la suite locale (149 PASS, 2 SKIP Windows), richiesta ASGI senza listener pubblico:
workload M2M → client SQL hardened → tabella scoring fissa → contract → preprocessing
sklearn reale → probability → threshold → risposta API HTTP 200. Nessuna riga persistita.

| Aggregato | Risultato |
| --- | --- |
| Source watermark UTC | 2026-10-27T07:47:53Z |
| Prediction generated at UTC | 2026-10-27T10:28:24.247924Z |
| Source age seconds | 9631.247924 |
| Rows | 100 |
| Probability min | 0.0026423961320532438 |
| Probability median | 0.16635709863030274 |
| Probability max | 0.980115234301818 |
| Predicted positives | 42 |
| Positive rate | 0.42 |
| Inference seconds | 0.0510612 |
| Total request seconds | 3.6461283 |
| NaN / inf | 0 / 0 |
| Threshold mapping | 100% `p >= saved_threshold` |

Soglia letta dai metadata: 0.35. Modello reale e versione manifest indicati sopra.
Il checksum originale della pipeline è invariato. L'età è circa 2h40m: questo test prova
il percorso inference read-only, non continuità di ingestion o uno SLA della sorgente.
Il batch è deterministico e limitato; il tasso positivo non è una stima dell'intera rete.
