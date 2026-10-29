# Frontend production deployment

## Architettura e stato

Frontend React/Vite statico su GitHub Pages:
<https://matteocavo.github.io/rome-mobility-intelligence/>.

```text
Browser -> GitHub Pages -> public read-only FastAPI endpoints on Render
                                      |-> Databricks current scoring
                                      `-> Neon persisted history
```

Il frontend è sotto il base path `/rome-mobility-intelligence/`. Vite applica questo
percorso al build production, inclusi gli asset Leaflet; il server di sviluppo rimane
alla root. Il workflow `.github/workflows/pages.yml` è limitato a `push` su `main` e
`workflow_dispatch` su `main`, con controlli sul ref in entrambi i job. Esegue lint,
typecheck, test e guardia dell'artifact prima di caricare/deployare `frontend/dist`.
Pages usa il source GitHub Actions. Nessun workflow di feature branch pubblica il sito.

L'origin API pubblico compilato nel bundle è
`https://rome-mobility-intelligence-matteocavo.onrender.com`. Il browser deve usare
esclusivamente `GET /public/summary`, `/public/predictions/current`,
`/public/predictions/history`, i due `/aggregate`, `/public/routes` e `/public/route-map`; nessuna chiave o
endpoint privato va inserito nel frontend. Il backend usa i dati correnti Databricks e
lo storico Neon, senza mock automatici. Il modello e i suoi artifact restano privati.

## CORS e rate limiting

Origin CORS prevista per il backend:

```text
["https://matteocavo.github.io"]
```

Un origin è solo schema + host, quindi non include il path GitHub Pages. Non usare `*`.
Il valore è attivo sul servizio Render e verificato dalle richieste del sito production.

La PR #24 configura il limite pubblico a 120 richieste per client al minuto, un tetto
globale di 1.200/minuto per processo e massimo 1.024 bucket; i forwarding header non
sono fidati per default. Non impostare `PUBLIC_CLIENT_IP_HEADER` o CIDR proxy finché
Render non documenta/verifica gli esatti CIDR del proxy immediato e non è escluso un
bypass dell'ingresso pubblico. Non inventare range e non aggirare il limite. Il backend Render espone gli endpoint pubblici anonimi read-only; le route operative
restano protette da service authentication.

## Cold start e accuratezza

Il piano Render Free può sospendere il servizio. Il primo caricamento della popolazione
completa può essere lento; il frontend mostra loading, retry ed errori senza fallback
sintetici. Le risposte successive possono usare la cache. Nessuno SLA real-time garantito.

Il catalogo e le geometrie sono derivati da GTFS statico. Non ci sono coordinate live o
simulate dei mezzi. Evitare promesse di real-time: freschezza e cadenza dipendono dai dati
e dal backend.

## Costo, licenza e affiliazione

Questo change non crea servizi, risorse o costi ricorrenti; usa GitHub Pages per il
repository pubblico e il servizio Render Free già esistente. Non modifica billing,
Databricks grants, Neon permissions, OCI o n8n. L'infrastruttura selezionata/preparata è
zero-cost, ma dipende dai limiti e dalla disponibilità dei piani gratuiti esistenti.

Il codice è Apache-2.0. L'artifact reale del modello non è pubblicato. Il progetto è
indipendente e non affiliato, approvato o gestito da Roma Capitale, ATAC S.p.A. o altri
operatori di trasporto.

## Stato di rilascio v1.0.0

Applicazione pubblica live su GitHub Pages, backend Render Free, scoring corrente in
Databricks e storico PostgreSQL/Neon. Il modello sklearn esegue inference lato server;
summary e aggregate usano la popolazione completa, le tabelle usano pagination server-side.
Il catalogo e la geografia GTFS sono statici; le posizioni veicolo non sono esposte.

La release conserva codice Apache-2.0 e artifact modello privato non distribuito.
La verifica finale copre gli endpoint pubblici e le superfici IT/EN. Il target di costo
ricorrente è 0 EUR, soggetto ai limiti dei piani Free e a cadenza best-effort.
