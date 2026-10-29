# Frontend pubblico Rome Mobility Intelligence

React 19 / Vite 6 / TypeScript. Italiano predefinito, inglese secondario.
Design AI Studio preservato: nessun redesign o deploy in questa PR.

## Comandi

Node 22/24 + npm, dalla directory `frontend/`:

```sh
npm ci
npm run dev
npm run lint
npm run typecheck
npm test
npm run build
npm run preview
```

`lint` è il controllo statico TypeScript dell’export, non ESLint. Lockfile npm
versionato; Bun non richiesto. Nessuna dipendenza Python o credenziale richiesta
per build. `node_modules/`, `dist/` e build cache non sono versionati.

## Connessione e sicurezza

Production usa solo GET anonimi `/public/summary`, `/public/predictions/current`
e `/public/predictions/history`. Origin approvato:
`https://rome-mobility-intelligence-matteocavo.onrender.com`.
Unica variabile frontend: VITE_PUBLIC_API_URL, origin pubblico senza path/query/segreti.
Never place RMI_SERVICE_API_KEY or any backend secret in browser code.

Dev server solo localhost:3000; proxy `/public` verso localhost:8000. Avviare il
backend con la sua configurazione privata già approvata; non copiarla in Vite.
Il proxy non esiste in build production. Il contratto aggiunto da questa PR non è
ancora deployato su Render; produzione nuova origin/CORS è uno step separato.

## Popolazione e tabelle

KPI e top route risk: summary dell’intera popolazione scoring corrente. Il backend
calcola il modello operativo sull’intero snapshot con budget fisso e cache bounded;
nessuna inferenza arbitraria, training o persistenza da richieste anonime.

Situazione attuale: ricerca, filtri e ordinamento globali prima della pagina.
Storico: COUNT + filtri/sort SQL server-side su tutti i persistiti Neon.
Default 20 righe, alternative 10/50, previous/next e totali reali. Nessun download
dell’intero dataset nel browser; il limite della tabella non è il denominatore KPI.
Ricerca debounced 350 ms, reset pagina e gestione delle risposte obsolete.

Loading/wake, empty ed errore sono espliciti. Massimo 4 tentativi GET, timeout 15 s,
attese 10/20/30 s: budget nominale 120 s per chiamata. Niente keep-alive, polling
periodico o fallback automatici a mock. Fixture sintetiche solo in tests/fixtures,
fuori dal graph production. Le metriche TEST in Tecnologia sono documentazione,
non KPI live o una chiamata al model-info privato.

Il modello è binario: rischio di ritardo >=300 s. Mediana/P90 in secondi sono
ritardi osservati, mai previsioni di secondi o ETA. Disclaimer completo solo in Progetto.

## Mappa e sorgenti

Leaflet CSS, marker divIcon senza asset path fragili, altezza esplicita, cleanup
resize/map. Tile HTTPS © OpenStreetMap contributors, attribuzione visibile,
nessun prefetch offline. Fermate da GTFS statico del core con checksum documentato;
non è un GTFS aggiornato in tempo reale e non viene inventata la data di acquisizione.

Il backend restituisce coordinate reali delle fermate e route_type dal catalogo
verificato, dove abbinato. Nessuna deduzione da numeri di linea. Nessuna posizione
veicolo. Il dettaglio linea mostra una shape statica solo per il join esatto
route_id/trip_id/shape_id; se non abbinata, solo fermate reali. Nessun jitter o
percorso interpolato. I nomi sono quelli presenti nel catalogo, senza inventare
nomi mancanti. [Contratto e prove](../docs/FRONTEND_API_CONTRACT.md).

## Deploy e capacità

Nessun provider creato e nessun cambio Render/Docker. Possibile futuro host statico
Free separato. Prima del deploy: review/merge, deploy backend esplicito, verifica API,
configurazione dell’esatto origin HTTPS in CORS_ALLOWED_ORIGINS, poi deploy statico.
Nessuna wildcard o service key nel browser. Costo infrastrutturale obiettivo €0/mese.

Prova locale: 23.084 righe, 296 linee, 8.910 rischi major; tabelle default 20 righe.
Backend cap 50.000 righe / 48 MB export, cache 5 minuti, un refresh/processo; nessun
risultato troncato presentato come completo. Peak locale circa 404 MiB: verificare
il margine e la CPU del singolo worker Render Free prima del deploy. La sorgente
provata aveva watermark 2026-10-28T17:47:52Z: freshness vecchia mostrata esplicitamente,
non corretta attivando/modificando scheduler in questa task.

Codice Apache License 2.0; modello privato non distribuito.
[Attribuzioni](THIRD_PARTY_NOTICES.md).


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


Ultima riconferma runtime del 29 ottobre 2026, query_generated_at 12:03:15 UTC:
23.678 osservazioni correnti, 314 route, watermark 09:46:31 UTC, 5.176 rischi
major (21,85995%), mediana osservata -42 s e P90 osservato 692 s.
Il precedente dato 26.744 / 309 rimane solo evidenza del precedente snapshot.
Lo storico rimane 400 righe / 17 route. Nessun run avviato per questi controlli.
I filtri temporali dello storico sono disponibili anche in UI, con conversione
in timestamp ISO timezone-aware prima della richiesta.


[Hardening finale PR24](../docs/PR24_HARDENING.md): memoria misurata, quota pubblica
120/client + ceiling globale 1.200/minuto, budget richieste UI e gate CORS/proxy Render.
Nessun proxy viene fidato automaticamente; gli esatti CIDR devono essere verificati
prima del deploy. In locale CORS resta chiuso e si usa il proxy Vite same-origin.
