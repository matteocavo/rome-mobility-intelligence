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

Il backend restituisce coordinate reali delle fermate e route_type reale dove
presente. Mai inferenze Bus/Tram da numeri di linea. Le coordinate veicolo e le
shapes non sono disponibili nella proiezione autorizzata: null/avviso, nessun jitter,
nessuna polyline fittizia. Route short/long name non disponibile: ID vero, non nomi
inventati. [Contratto e prove](../docs/FRONTEND_API_CONTRACT.md).

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
