# PR 24 - final hardening

## Memoria: meccanismo e misura

La lettura corrente continua a coprire tutto lo snapshot (max 50.000 righe / 48 MB
raw), con COUNT/grain/hash/lineage e feature contract invariati. Nessuna pagina o
sorgente storica viene usata come denominatore.

- Validazione delle 47 feature riga per riga, senza una lista di N dizionari.
- Inferenza in blocchi da 1.024 righe: stesso modello fitted/trusted, nessun fit.
- Cache pubblica di tuple immutabili, senza un dict e fields-set Pydantic per riga.
  Ogni riga viene comunque validata; solo le <=50 righe della risposta tornano modelli.
- Feature e lineage intermedi rilasciati dopo inferenza/audit, prima della cache.
- Solo per la popolazione pubblica: cursor.arraysize=1.000, anche se fetchmany era
  gia' 1.000. Il connector usa arraysize per il buffer interno, default 10.000.
- Dictionary encoding per stringhe a bassa cardinalita' nei batch SQL. Il budget
  viene verificato sulla dimensione raw PRIMA della compressione. Null e nuove
  categorie restano rappresentati: nessun valore viene convertito silenziosamente
  a categoria mancante. Il comportamento dei SELECT privati resta invariato.

Riferimento: [Databricks Connector - arraysize](https://docs.databricks.com/aws/en/dev-tools/python-sql-connector).
La compattazione della sola cache non era sufficiente: il picco dominante precedeva
l'inferenza, nella lettura SQL. Il buffer esplicito e' la riduzione determinante.

Benchmark opt-in `python -m scripts.benchmark_public_population`, con credenziali
workload e artifact trust gia' configurati via ambiente. Nessun HTTP server,
training, persistenza o scrittura remota. `--baseline` carica le due classi di
riferimento dal commit revisionato 9536093; eseguire in processi separati a freddo.
Non stampa credenziali, feature, righe sorgente o dettagli di eccezioni.

Misura Windows PeakWorkingSetSize, include runtime, modello e connector; quattro
pagine da 50 con tutti gli ordinamenti e serializzazione JSON. Il vecchio dato
~403 MiB era una misura precedente; il confronto controllato sullo stesso snapshot
23.678 / 314, watermark 2026-10-29 09:46:31 UTC, restituisce:

| Variante | Startup peak MiB | Picco completo MiB |
| --- | ---: | ---: |
| baseline 9536093 | 269,70 | 387,29 |
| ottimizzata | 271,04 | 309,24 |

Riduzione 78,05 MiB (20,15%). KPI identici: 5.176 major, mediana -42 s, P90 692 s.
Target <350 MiB raggiunto; preferenza <300 non raggiunta. Misura locale, non test
cgroup Linux/Render: Docker non e' disponibile su questa macchina. Il limite 512 MB
lascia nominalmente circa 179-203 MiB (a seconda dell'unita' del limite), ma non e'
una garanzia per ogni snapshot fino al cap, concurrency, o comportamento provider.
Non aumentare worker/limiti e non autorizzare il deploy basandosi sul solo benchmark.

## Rate limiting pubblico

Prima: tutte le visite condividevano 30 richieste / 60 secondi.
Ora: 120 richieste per finestra fissa di 60 secondi per client verificato, piu' tetto globale sliding
1.200 / 60 secondi per processo. I rifiuti del client non consumano il tetto globale.
I tre budget autenticati read/inference/write restano distinti e invariati.

Massimo 1.024 bucket client, ciascuno con due scalari e una chiave hash da 16 byte.
Nessuna deque per visitatore. Le IP non sono conservate in chiaro o loggate.
Le IPv6 nella stessa /64 condividono quota. I bucket scaduti sono riutilizzabili;
nessun bucket attivo viene espulso per azzerarne la quota. Se la tabella e' piena
si rifiutano nuovi client con 429/Retry-After: cardinalita' e memoria restano bounded.
Il tetto globale ha al massimo 1.200 timestamp con i default. Si tratta di limiti
per singolo processo: il production entrypoint resta a un solo worker.

### Identita' e Render

Default sicuro `PUBLIC_CLIENT_IP_HEADER=none`: usa solo il peer socket ASGI e ignora
X-Forwarded-For, Forwarded, CF-Connecting-IP. Uvicorn resta proxy_headers=False.
Questo e' corretto per connessione diretta; dietro Render, il peer e' il proxy e NON
va presentato come identita' distinta di ogni visitatore.

[La documentazione ufficiale Render](https://render.com/articles/host-pocketbase-on-render)
indica che Cloudflare sovrascrive CF-Connecting-IP per i public web service. Per quel
solo percorso pubblico, PRIMA di un futuro deploy:

1. Verificare gli effettivi CIDR del proxy immediato e che tutto l'ingresso anonimo
   passi dal public edge Render/Cloudflare, senza bypass diretto/private ingress
   accessibile a chiamanti non fidati. Non inventare CIDR dai range privati generici.
2. Configurare `PUBLIC_CLIENT_IP_HEADER=cf-connecting-ip` e
   `PUBLIC_TRUSTED_PROXY_CIDRS` come JSON array degli esatti CIDR verificati.
3. Verificare due client reali e una richiesta con X-Forwarded-For falsificato.

Il codice usa quel solo header SOLTANTO da un peer nei CIDR espliciti: un singolo
IP pubblico valido, nessuna lista, duplicato o valore mancante. Altrimenti fail
closed (429), senza fiducia nel primo elemento XFF. CIDR /0, trust implicita e
configurazioni parziali sono rifiutati. Nessuna impostazione Render e' stata cambiata;
CIDR reali e percorso di ingresso sono una verifica obbligatoria pre-deploy ancora
non eseguita. Non abilitare trust automatico basato sul nome host o header client.

## Budget richieste frontend

Conteggi production a cache calda, nessuna retry, non includono tile OSM:

| Azione | Richieste pubbliche |
| --- | ---: |
| Primo dashboard: catalogo + summary + current + history | 4 |
| Aprire Current / History gia' caricati (ancore) | 0 |
| Selezionare una linea | 1 current + al massimo 1 route-map |
| Selezionare una corsa differente nel dettaglio | 1 route-map |
| Pagina, filtro, sort o ricerca Current | 1 current; +1 map se cambia la corsa nel dettaglio |
| Pagina, filtro, sort, ricerca o date History | 1 history |
| Torna a tutte le linee | 1 current |
| Aggiorna / cambio lingua | 1 summary + 1 current + 1 history |

Se scade/cambia la generazione corrente: al massimo +1 summary per riallineare i
KPI. Ricerca debounced 350 ms. Ogni GET ha max 4 tentativi transitori; il cold start
puo' quindi aumentare i conteggi (max 16 tentativi per i quattro GET iniziali).
React StrictMode puo' duplicare gli effect solo nello sviluppo, non nel build
production. 4 iniziali + 20 selezioni (40) + 20 pagine/ricerche = 64, molto sotto
120/min. Fra due finestre consecutive un client puo' avere un burst al confine: al massimo
240 ammissioni in una finestra globale sliding (20% del ceiling 1.200), mai l'intero
budget. Utenti sullo stesso NAT condividono la quota per IP, comportamento intenzionale.

## CORS

Configurazione corrente locale e default: `CORS_ALLOWED_ORIGINS=[]`. Il dev server
127.0.0.1:3000 usa il proxy same-origin /public verso 127.0.0.1:8000; non occorre
aprire CORS. Nessuna wildcard e nessuna credenziale browser.

Dopo la scelta dell'hosting, impostare nel backend
`CORS_ALLOWED_ORIGINS=["https://HOST-FRONTEND-ESATTO"]` (JSON, senza path o slash
finale) e validare preflight/origin consentita e origin estranea. Solo URL HTTPS
production, allow_credentials=False. Questa configurazione non e' stata applicata.


### Riconferma su un secondo snapshot e parita' completa

Il produttore ha avanzato naturalmente lo snapshot durante il lavoro; nessuna
pipeline e' stata avviata da questa task. Con il benchmark versionato, in due nuovi
processi a freddo, source watermark 2026-10-29 11:44:12 UTC:

| Variante | Righe | Route | Picco MiB | Tempo s |
| --- | ---: | ---: | ---: | ---: |
| baseline 9536093 | 20.535 | 282 | 364,25 | 18,86 |
| ottimizzata | 20.535 | 282 | 299,24 | 22,03 |

Riduzione abbinata 65,01 MiB (17,85%). SHA256 di tutte le probabilita'/decisioni/
ritardi osservati, nell'ordine sorgente, identico prima/dopo:
`b77ebf1e014a00348bf89df32e07a2bd8a2ec496164b7575693bc237f865debc`.
KPI identici: 3.869 major, mediana -78 s, P90 565 s. Il valore <300 MiB riguarda
questo snapshot; la misura ottimizzata piu' alta fra i due snapshot resta 309,24 MiB.
I tempi dipendono dal warehouse/cold start/rete: non sono una promessa di SLA.
