# Rome Mobility Intelligence v1.0.1

## Correzioni

- Primo render da dati production validati, seguito dalla lettura delle API live.
- Summary e osservazioni vengono promossi insieme, solo per la richiesta corrente.
- Un errore o una risposta fuori ordine non sostituiscono gli ultimi dati validi.
- Lo stato online richiede il successo di summary e current; la freschezza deriva
  dal timestamp sorgente e si aggiorna anche lasciando aperta la pagina.
- Un solo validatore controlla il bundle nel generatore e nel frontend, inclusi
  coverage, conteggi, paginazione e coerenza temporale. History resta distinta da current.
- Diagnostiche Databricks e persistenza con categorie e percorsi allowlisted,
  senza body, credenziali o URL arbitrari nei log.
- CloudFetch rimane attivo, con un download parallelo e buffer diretto da 1 MiB;
  la validazione delle 47 feature usa blocchi da 1.024 righe. Nessuna popolazione
  viene ridotta alle sole righe mostrate dal frontend.
- Versione API e package allineata a 1.0.1.
- Audit globale di lineage compatto, senza aumentare i budget della popolazione.
- Cache ritirata e temporanei rilasciati prima delle nuove allocazioni; rilascio
  best-effort delle pagine heap gia libere durante le ricostruzioni su Linux.

## Refresh del bundle

Il workflow manuale conserva il file validato durante il cambio branch, aggiorna
`snapshot-refresh` e riutilizza la PR aperta. I soli cambiamenti di `capturedAt`
non generano commit. I check vengono avviati tramite dispatch prima del merge umano.
Serve il permesso repository che consente ad Actions di creare PR; non viene
abilitato da questa patch. Nessun merge o deploy automatico nel workflow refresh.

## Verifica production completata

La v1.0.0 e il suo tag pubblicato restano invariati. Il backend production ha
registrato un OOM oltre 512 MB sul commit `103ec73` il 30 ottobre 2026.
Il follow-up `ce83201` e stato verificato su Render Free il 30 ottobre 2026:
prima costruzione e tre rebuild dopo TTL naturale, stesso processo `gfkmj`,
21.205 osservazioni e 292 linee. Il picco massimo campionato e circa 417 MiB su
512 MiB; RSS dopo il terzo/quarto ciclo circa 400/400 MiB, senza restart osservati.
La popolazione precedente era diversa: non e un confronto prestazionale a parita
di righe e non garantisce assenza di OOM con carichi futuri o qualsiasi concorrenza.
[Serie dei campioni e limiti](RENDER_MEMORY_VERIFICATION.md).

API pubbliche, pagination, aggregate e CORS verificati; catalogo GTFS 435 linee,
storico 600 righe. Un run manuale ha inserito 100 righe; il successivo
[run automatico](https://github.com/matteocavo/rome-mobility-intelligence/actions/runs/41038146805)
con trigger `schedule` ha trovato le stesse 100 righe gia presenti, senza retry
o nuove scritture. Due refresh hanno riutilizzato la stessa PR #32.

Il bundle last-known-good conserva dati reali validati e il loro watermark;
non rappresenta una promessa di aggiornamento real-time. History resta distinta
dal current. Nessun upgrade paid, modifica Databricks/schema Neon, cambio modello
o riuso di history come nuove previsioni correnti. Cold start e 503 temporanei
durante una costruzione gia in corso restano possibili nel piano Free.
