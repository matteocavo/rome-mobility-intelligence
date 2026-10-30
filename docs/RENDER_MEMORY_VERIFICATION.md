# Verifica memoria Render Free

## Evidenza del 30 ottobre 2026

La Console riporta `Ran out of memory (used over 512MB)` per l'istanza `pg2n6`.
Il commit deployato era `103ec73`, non la patch v1.0.1 della PR #30.
L'ultimo ciclo completo visibile nei log aveva 23.741 osservazioni e 310 linee:
lettura/validazione circa 51 s, inferenza circa 12 s, cache circa 6 s.
Il DataFrame riportava 25.980.658 byte. Questo valore non include runtime, modello,
Arrow, buffer del connettore, copie temporanee e cache e non misura il RSS.
Le serie storiche CPU/memoria non sono consultabili nel piano Free della Console.
Queste evidenze confermano l'OOM, ma non dimostrano un memory leak specifico.

## Contenimento nella patch

- Un solo worker, limiti di query e modello invariati.
- CloudFetch attivo, `max_download_threads=1` al posto del default 10.
- `cursor.buffer_size_bytes=1048576` al posto del default 104857600.
- `cursor.arraysize=1000`; budget complessivi righe/byte invariati.
- Validazione feature in blocchi da 1.024, senza copia di tutte le 47 colonne.
- `serving_memory` registra solo stage, RSS corrente e picco RSS, senza righe,
  identificativi, configurazioni o credenziali. Su piattaforme senza `/proc` viene omesso.

## Prova dopo deploy autorizzato

1. Verificare nei log il commit e il bootstrap dello stesso artifact verificato.
2. Effettuare una sola richiesta summary e attendere il completamento; non creare
   un load test concorrente sul servizio Free.
3. Leggere RSS/picco negli stage `source_start`, `source_ready`, `inference_ready`,
   `cache_ready`; confrontare totali e watermark tra summary e current.
4. Verificare pagina current, ricerca, aggregate e history senza download completo.
5. Dopo la naturale scadenza della cache (300 s), ripetere una sola costruzione e
   confrontare memoria con la prima. Osservare eventuali restart negli Events.
6. Solo successivamente eseguire un run di persistenza controllato e verificare
   l'idempotenza senza presentare il run manuale come prova dello scheduler.

Target di margine: preferire RSS sotto 400 MiB; oltre 450 MiB richiede ulteriore
analisi. Nessun successo sotto Windows equivale a una garanzia cgroup Linux.
Se il servizio supera ancora il limite, lasciare la release bloccata e analizzare
lo stage interessato; non aumentare automaticamente il piano o tagliare la popolazione.

## Budget della popolazione dopo il primo deploy

Sul commit `6a190af` health/ready sono tornati 200, ma la prima summary ha restituito
503. I log hanno misurato un picco RSS di 407.052.288 byte, senza nuovo OOM.
Una lettura locale con la stessa identita workload read-only ha riprodotto
`ExportBudgetError`: 27.449 osservazioni restano sotto il cap righe, ma i valori
MIN/MAX di lineage ripetuti su ogni riga superano il budget byte non compresso.

Il follow-up mantiene 50.000 righe / 48.000.000 byte e le 47 feature. Restituisce
COUNT e il flag globale `MIN = MAX` al posto dei lunghi valori MIN/MAX. I controlli
restano sullo snapshot completo prima del LIMIT; i NULL falliscono tramite COUNT
e flag mancanti/falsi falliscono lato applicazione. La verifica locale reale ha
letto tutte le 27.449 righe in circa 24 s, con DataFrame finale di 24.867.664 byte.
Anche questa correzione richiede verifica RSS nel runtime Render dopo il deploy.

## Verifica dei cicli successivi sul commit `7f6a303`

La summary production e tornata 200: 27.449 osservazioni, 307 linee, 435 linee nel
catalogo GTFS. Il run manuale di persistenza ha inserito 100 righe senza retry;
due refresh hanno aggiornato la stessa PR #32, senza duplicazioni o push su main.

La prima costruzione ha raggiunto 418.320.384 byte di picco RSS (circa 399 MiB).
La seconda, dopo la naturale scadenza della cache, ha raggiunto 492.261.376 byte
(circa 469 MiB): il margine richiede un'ulteriore correzione prima della release.
Un test con weak reference dimostra che il riferimento locale `cached` trattiene
la vecchia popolazione durante la nuova lettura, anche dopo l'azzeramento della
cache del servizio. Il fix elimina tale riferimento e raccoglie gli oggetti
irraggiungibili prima delle nuove allocazioni. I lettori attivi conservano i propri
riferimenti: nessuna lista viene svuotata in-place. L'effetto sul RSS va misurato
di nuovo nel runtime effettivo; il solo test di lifetime non prova un nuovo picco.
