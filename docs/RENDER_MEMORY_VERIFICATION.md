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

## Rilascio della heap libera: verifica ancora necessaria

Sul main `e8cfe6d`, il processo `vrmss` ha completato due cicli reali con 27.449
osservazioni: picco 422.850.560 byte (403,26 MiB) al primo e 483.692.544 byte
(461,29 MiB) al secondo. Nessun nuovo OOM osservato in questi due cicli, ma il
gate resta bloccato. Il solo rilascio dei riferimenti Python non dimostra che la
heap nativa libera venga restituita al sistema operativo; non e una diagnosi
conclusiva di memory leak o dell'allocator responsabile.

Il follow-up richiede `malloc_trim(0)` alla libc del processo Linux dopo la
raccolta degli oggetti irraggiungibili: prima della nuova lettura, dopo il ritiro
della cache scaduta, e dopo il rilascio di DataFrame/probabilita temporanei. Non
viene eseguito sulle letture della cache valida. La funzione restituisce solo
pagine gia libere: modello, cache corrente e riferimenti dei lettori attivi
restano validi. Sulle piattaforme senza il simbolo si conserva il comportamento
precedente. Non si modifica l'allocator e non si caricano librerie da path esterni.

Riferimento: [Linux malloc_trim](https://www.kernel.org/pub/linux/docs/man-pages/book/man-pages-6.12.pdf),
rilascio best-effort di pagine libere della heap, thread-safe. Non garantisce un
RSS massimo e non recupera memoria ancora referenziata o tutti i pool Arrow.
I log numerici `reclaim_before` / `reclaim_after` permettono di misurare l'effetto.

La CI Linux verifica in un subprocess che heap libera di un worker venga
effettivamente restituita senza alterare un'allocazione ancora viva. I test della
popolazione verificano anche i lettori della vecchia cache e l'assenza di reclaim
nel percorso cache-hit. Queste prove non sostituiscono il runtime con il modello
production: dopo merge/deploy serve verificare primo build e almeno tre rebuild
consecutivi dopo TTL naturale, stesso processo, picchi/RSS e assenza di restart.
Nessuna persistenza aggiuntiva e necessaria per questa misura. La release resta
bloccata finche il margine non e dimostrato; nessun cap dati ridotto, piano paid,
cambio modello, credenziale o modifica Databricks/Neon.

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

## Verifica production dopo PR #34: completata

Il 30 ottobre 2026, dalle 13:02 alle 13:21 (Europe/Amsterdam), il deploy
`ce8320118725d40f335f6a6eaf7fac1ac27049e0` ha completato una prima costruzione e
tre rebuild dopo TTL naturale di 300 s nello stesso processo `gfkmj`.
Ogni ciclo ha letto l'intera popolazione disponibile: 21.205 osservazioni,
292 linee, watermark `2026-10-30T09:47:41Z`. Le richieste di verifica erano
sequenziali; summary, pagina current e aggregate sono risultati coerenti.

| Ciclo | Picco cumulativo campionato (MiB) | RSS cache pronta (MiB) |
| --- | ---: | ---: |
| 1 | 354,48 | 338,21 |
| 2 | 402,04 | 386,47 |
| 3 | 417,03 | 400,27 |
| 4 | 417,03 | 399,75 |

Il picco usa il massimo dei campioni RSS/VmHWM gia osservati: le letture `/proc`
non sono un campionatore continuo del cgroup. Dopo il quarto ciclo la memoria
non e cresciuta rispetto al terzo. I log prima/dopo mostrano il rilascio di
circa 16-17 MiB al termine di ciascuna costruzione. Gli Events non mostrano OOM
o restart successivi al deploy durante questa verifica. Il margine osservato e
circa 95 MiB rispetto ai 512 MiB nominali del piano Free.

Esito: gate positivo **nel carico osservato**. La precedente prova su 27.449 righe
aveva una popolazione diversa: non attribuire tutta la differenza al fix e non
estrapolare una garanzia sul cap di 50.000 righe o su concorrenza arbitraria.
Restano necessari monitoraggio e comportamento fail-closed sui budget; nessun
SLA real-time o garanzia assoluta di assenza di OOM. La verifica non ha eseguito
nuove persistenze, cambi di piano, modello, credenziali o risorse Databricks/Neon.
