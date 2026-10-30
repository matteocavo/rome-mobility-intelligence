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
