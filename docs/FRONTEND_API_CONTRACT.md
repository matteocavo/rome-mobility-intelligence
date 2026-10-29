# API pubblica frontend: popolazione corrente e storico distinti

Base URL dopo deploy esplicito della PR:
`https://rome-mobility-intelligence-matteocavo.onrender.com`.
Il backend attualmente deployato restituisce ancora 404 per questo nuovo contratto.
Never place RMI_SERVICE_API_KEY or any backend secret in browser code.

## Route

| Endpoint | Metodo/auth | Fonte e responsabilità |
| --- | --- | --- |
| `/public/routes` | GET anonimo | catalogo GTFS completo e checksum, senza query runtime |
| `/public/route-map` | GET anonimo | geometria statica per join esatto route/trip, al massimo 5.000 punti |
| `/public/status` | GET anonimo | stesso snapshot completo/cached di summary |
| `/public/summary` | GET anonimo | aggregati della popolazione scoring corrente completa |
| `/public/predictions/current` | GET anonimo | pagina ordinata/filtrata della stessa popolazione corrente |
| `/public/predictions/history` | GET anonimo | pagina ordinata/filtrata di tutte le predizioni persistite Neon |

Current non legge Neon come surrogato del dataset corrente. History non definisce
il denominatore corrente. Nessun KPI principale è calcolato dalla pagina del browser.

## Current: completezza, inferenza e budget

Un SELECT fisso su `rome_transport.features.next_stop_delay_scoring` legge l’intero
MAX(feed_timestamp), con la proiezione del contratto a 47 feature e gli audit già
usati dal repository corrente. Grain, hash, lineage, next-stop identity e timestamp
sono verificati sull’intero snapshot prima di esporre risultati.

Limite server fisso: **50.000 righe / 48 MB di export**. Il COUNT window dello snapshot
viene confrontato con il numero effettivo di righe: se la popolazione supera il budget,
si rifiuta la richiesta; non viene pubblicata una popolazione troncata come completa.
Il limite non è controllabile dal browser. Il client F06 mantiene deadline SQL,
cancellazione, limiti di concorrenza e identity check OAuth M2M già esistenti.

Il modello operativo già caricato con artifact trust F02 esegue predict_proba
sull’intero input validato, con il lock già previsto. Nessun training, scelta modello,
feature override, raw inference payload o persistenza anonima. Le probabilità NaN/inf
sono rifiutate. La soglia deriva dai metadata del modello, non dal client.

Un solo refresh per processo, cache in memoria 300 secondi, cooldown fallimento 30 s,
nessun fallback a risultati scaduti. Prima del refresh la cache scaduta viene liberata.
Budget elapsed verificato a fine elaborazione: 150 s; questo non è cancellazione
preemptive della CPU sklearn. SQL ha il suo deadline F06. Nessun scheduler o keep-alive.
Una richiesta concorrente al refresh riceve 503. Model/SQL non disponibili non
vengono presentati come dataset vuoto o mock.

Lo snapshot cached contiene solo i campi pubblici necessari e un indice testuale
server per ricerca di route, stop, nome fermata, trip e vehicle. Le feature raw non
sono mantenute nel risultato pubblico, né vengono scaricate nel browser.

Summary: scored_count, route_count, observed_delay_count, conteggio/quota major-delay
risk, mediana/P90 del ritardo osservato, distribuzione osservata, top-5 route risk,
watermark/age e generazione. Percentili calcolati sui valori osservati disponibili
della popolazione intera; null esclusi e conteggiati separatamente. Il rischio ML
non è la quota di ritardi osservati >=300 s. Modello binario: nessuna ETA o previsione
di secondi/minuti di ritardo. Tutte le probabilità correnti provengono dal modello
operativo sklearn, non da uno Spark replay o dalle righe storiche.

## Paginazione comune

```text
GET /public/predictions/current?page=1&page_size=20&query=557&sort=risk_desc
GET /public/predictions/history?page=1&page_size=20&query=557&sort=time_desc
```

Response: coverage, total filtrato, page, page_size, total_pages, items,
source_watermark, source_age_seconds, query_generated_at e population_generated_at.
Quest’ultimo collega pagina current e aggregati alla medesima generazione della cache.
Current coverage=`current_scoring_population`; history=`persisted_prediction_history`.
Empty: items=[], total=0, total_pages=1. Nessun mock.

| Parametro | Valori ammessi |
| --- | --- |
| page | intero 1..100000, default 1 |
| page_size | 10 / 20 / 50, default 20 |
| route / stop | ID esatto, max 128 caratteri con allowlist alfanumerica `_.:-` |
| query | substring case-insensitive, max 100 caratteri, niente control characters |
| risk_class | all / major / moderate / regular |
| sort | risk_desc / delay_desc / route_asc / time_desc |
| mode | all / bus / tram; solo Current, tipi GTFS reali 3/0 |
| from / to | History: timestamp con timezone, estremi coerenti |

Ordine: filtro completo -> ordinamento completo -> pagina. Major usa la decisione
probability >= threshold; moderate è probabilità >=0.2 sotto soglia; regular è
probabilità <0.2 sotto soglia. Questi filtri sono rischio ML, distinti dal ritardo
osservato. Delay sort usa ritardo osservato, null in fondo. Tie-break stabile su
observation_id Current e id interno History. Gli ordinamenti SQL sono mappe fisse,
mai testo/colonne forniti dal client. History default UI più recente; Current rischio
più alto. Tutti i filtri/valori SQL sono bind. La ricerca nomi fermata usa il lookup
GTFS statico e il filtro stop_id SQL, non nomi hardcoded in React.

History legge `public.prediction_history`: COUNT e SELECT LIMIT/OFFSET nella stessa
transazione REPEATABLE READ, READ ONLY; statement_timeout=2 s, lock_timeout=1 s,
pool/connect timeout hardened e uno slot non bloccante. Default senza filtro data:
tutto lo storico disponibile, senza dump completo. Niente metadata correnti usati
per inventare modalità storiche: mode storico non disponibile -> 503. Dati DB
malformati non diventano una risposta apparentemente valida.

Il frontend debounced a 350 ms invia ricerca/filtri/sort al server e resetta page=1.
Previous/next/page-size sono comuni alle due tabelle. Le risposte superate da una
richiesta più recente vengono ignorate. L’eventuale cambio generazione current
aggiorna gli aggregati tramite summary, non calcolandoli dalla pagina.

## Campi pubblici

items: observation_id opaco, route_id/type, route_short_name nullable,
trip_id e vehicle_id GTFS pubblici (se disponibili), stop_id/name/lat/lon,
stop_sequence, target_next_stop_id, observed_current_delay_seconds,
major_delay_probability, predicted_major_delay, threshold, source_watermark,
prediction_generated_at, vehicle_lat/lon nullable. Non sono credenziali: trip e
vehicle sono identificativi del feed di trasporto. Nessun entity_id raw, vettore
47-feature, hash/lineage di training, artifact path, token o secret è pubblicato.
I dettagli tecnici restano espandibili nella UI.

## Sicurezza / CORS / errori

Solo GET. POST/PUT/PATCH/DELETE/HEAD ->405. Parametri sconosciuti, duplicati, sort
arbitrario e input malformato ->422; 429 con Retry-After; 503 indisponibilità/capacità;
504 deadline SQL/DB. Errori fissi, senza body remoto, URL privati o eccezioni grezze.
Budget pubblico per client verificato: 120 richieste/60 s; ceiling globale 1.200/60 s,
max 1.024 bucket bounded. Le route operative mantengono budget separati invariati.
Nessuna fiducia in X-Forwarded-For. [Trust proxy, benchmark e gate pre-deploy](PR24_HARDENING.md).
Il refresh completo è coalesced e bounded; nessun parametro può forzare refresh,
soglia, modello, tabella, SQL o una scrittura.

CORS production resta invariato e chiuso finché l’origin frontend HTTPS finale
non è configurato esplicitamente in CORS_ALLOWED_ORIGINS. Niente wildcard,
allow_credentials=false, nessun service-key header dal browser. In dev Vite
inoltra solo `/public` al backend localhost:8000, non route operative.

`/health` e `/ready` restano health pubblici minimali. `/model/info`,
`/predictions/current`, `/predictions/history`, `/predict`, `/predict/batch` e
`/predictions/current/persist` restano autenticati/interni: nessuna chiamata browser.
Nessuna modifica a Render, grant Databricks, Neon, n8n, OCI o scheduler Actions.

## Origine geografia

| Campo | Fonte | Limite |
| --- | --- | --- |
| stop coordinates/name | core `data/reference/gtfs_static/stops.txt`, copia normalizzata `app/data/reference/stops.json` | statico; acquisition date non provata, missing=null |
| current trip/vehicle/route/stop/sequence | `rome_transport.features.next_stop_delay_scoring` | snapshot completo MAX(feed_timestamp) |
| history IDs/risultati/tempi | Neon `public.prediction_history` | tutti i persistiti, filtrati/paginati |
| route_type | campo reale scoring | parzialmente mancante, mai inferito da ID linea |
| vehicle position | non disponibile nella proiezione autorizzata | null, nessun jitter/marker simulato |
| shape | non disponibile nella proiezione autorizzata | nessuna polyline inventata |

8.297 fermate statiche; SHA-256 originale:
`97c1b281575f6794a9c639a5527a26f95bb9bd8c2d054387a627c8f369325b62`.
Attribution Leaflet / OpenStreetMap sempre visibile. Dataset GTFS mantiene licenza
upstream; codice originale Apache-2.0, bundle modello privato non distribuito.

## Prova reale locale, 29 ottobre 2026

Full population **23.084**, **296** route_id, **22.748** ritardi osservati;
watermark **2026-10-28T17:47:52Z** (dato vecchio, non claim di live freshness).
Modello operativo threshold **0.35**: **8.910** major-delay risk, **38,598%**.
Mediana osservata **86 s**, P90 esatto **1.152 s**. Prima elaborazione locale circa
**21,33 s**, peak working set osservato circa **404 MiB**. Non è una misura di
latenza/memoria Render Free: review del margine 512 MB necessaria prima del deploy.

Current page_size=20: total=23.084, total_pages=1.155. Query `557`: total=131
(match substring anche su trip/vehicle), non solo la pagina iniziale.
History page_size=20: total=400, total_pages=20; query `557`: total=20.
Major filter current: total=8.910, coerente con summary.

Nessun KPI principale usa il limite UI. Le tabelle mostrano **20 righe di default**,
non l’intero universo. Nessun banner legale/metodologico sopra i KPI: il disclaimer
completo resta in Progetto; precisazioni in Tecnologia e nelle metriche pertinenti.


### Aggiornamento naturale della sorgente, prova finale 09:00 UTC

Senza avviare/modificare pipeline o schedule, il produttore esistente ha aggiornato
il dataset: **26.744** osservazioni / **309** linee, watermark
**2026-10-29T07:47:49Z**. Il medesimo modello operativo sull’intera popolazione dà
**5.611** major-delay risk (**20,9804%**), **26.293** ritardi osservati,
mediana **-50 s** e P90 **537 s**. Elaborazione locale circa **23,47 s**;
peak working set osservato circa **403 MiB**. Il limite server è 50.000 righe /48 MB;
la costruzione delle risposte usa iterazione per riga, senza materializzare anche
una lista di dizionari di tutte le feature. Snapshot e aggregati sono pubblicati
come una generazione coerente per evitare mix fra refresh concorrente e pagine.

Current page 2: **20 items**, total=26.744, total_pages=1.338. Ricerca substring
`557`: **257** risultati globali prima della pagina. History page 2: **20 items**,
total=400, total_pages=20. I numeri precedenti sono prove datate, non costanti del
codice: i totali si aggiornano con la sorgente e i KPI non derivano dalla pagina.


### Catalogo linee GTFS e copertura distinta

`GET /public/routes` espone il catalogo statico completo, indipendente da Databricks,
Neon e dalle pagine visualizzate. Il catalogo normalizzato contiene 435 route e solo
`route_id`, `route_short_name`, `route_long_name`, `route_type`, con provenienza e SHA256.
Source of truth: core `data/reference/gtfs_static/routes.txt`;
SHA256 `19ac1d2f24a096f47f9921809f7c645e57aa2027edce4592d458ee4d4c8319a6`.
La data di acquisizione del file non e' documentata: il catalogo e' la copia verificata
versionata nel core, non una dichiarazione di copertura di tutte le linee oggi esistenti.

Entrambi i selettori usano tutte le 435 route, senza dedurle dalle osservazioni.
La ricerca supporta ID, nome breve e nome esteso; il backend estende le ricerche
sulle osservazioni con il lookup del catalogo. Le linee senza osservazioni rimangono
selezionabili e producono uno stato vuoto, senza simulare dati.

I conteggi sono distinti: catalogo GTFS (435), linee nel current scoring (309 nel
controllo del 29 ottobre 2026, watermark 07:47:49 UTC), linee nello storico Neon
(17 nel controllo dello stesso giorno, 400 righe persistite). `source_route_count`
nelle pagine indica il COUNT DISTINCT della sorgente intera, indipendente da ricerca,
filtri e paginazione. I KPI correnti continuano a provenire dal summary completo.
Il catalogo completo non contiene osservazioni: scaricarlo non scarica la popolazione
scoring o la tabella history. Il limite di risposta e i GET allowlisted restano attivi.


### Geometria GTFS verificata

Audit relazionale: 166.161 trips, 1.248 shape_id, 5.027.858 stop_times;
zero riferimenti mancanti a trip o stop, tutte le shape dei trips presenti.
Il manifest `app/data/reference/gtfs_manifest.json` contiene i checksum di tutti
cinque i file. Gli indici statici per route sono generati da
`scripts/build_public_gtfs_maps.py`, senza credenziali o query runtime.
`GET /public/route-map?route=...&trip=...` risolve solo un abbinamento esatto
route/trip/shape e restituisce punti originali ordinati per shape_pt_sequence,
mai un percorso costruito collegando le osservazioni. File scelto con SHA256
dell'ID dal catalogo, nessun path controllabile dal client. Lookup locale bounded,
max 5.000 punti in risposta; join assente = available:false, coordinates:[].
Il dettaglio mostra la geometria della corsa selezionata o della prima osservazione
visualizzata, esplicitamente statica. Non equivale al percorso operativo attuale.
Le posizioni veicolo non sono disponibili e non vengono disegnate. L'overview
mostra le fermate reali della pagina, senza inventare geometrie di rete.


Ultima riconferma runtime del 29 ottobre 2026, query_generated_at 12:03:15 UTC:
23.678 osservazioni correnti, 314 route, watermark 09:46:31 UTC, 5.176 rischi
major (21,85995%), mediana osservata -42 s e P90 osservato 692 s.
Il precedente dato 26.744 / 309 rimane solo evidenza del precedente snapshot.
Lo storico rimane 400 righe / 17 route. Nessun run avviato per questi controlli.
I filtri temporali dello storico sono disponibili anche in UI, con conversione
in timestamp ISO timezone-aware prima della richiesta.


L'hardening finale sostituisce la misura storica ~403 MiB con confronti controllati
prima/dopo sullo stesso snapshot e processo a freddo. Vedere
[PR 24 hardening](PR24_HARDENING.md): picchi ottimizzati 299,24-309,24 MiB sui due
snapshot verificati, inferenza chunked e probabilita' esattamente equivalenti.
