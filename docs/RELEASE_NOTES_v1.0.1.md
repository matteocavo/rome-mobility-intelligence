# Rome Mobility Intelligence v1.0.1 — release candidate

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

## Refresh del bundle

Il workflow manuale conserva il file validato durante il cambio branch, aggiorna
`snapshot-refresh` e riutilizza la PR aperta. I soli cambiamenti di `capturedAt`
non generano commit. I check vengono avviati tramite dispatch prima del merge umano.
Serve il permesso repository che consente ad Actions di creare PR; non viene
abilitato da questa patch. Nessun merge o deploy automatico nel workflow refresh.

## Gate production ancora necessario

La v1.0.0 e il suo tag pubblicato restano invariati. Il backend production ha
registrato un OOM oltre 512 MB sul commit `103ec73` il 30 ottobre 2026.
La riduzione dei buffer e i log `serving_memory` richiedono una verifica sul runtime
Render: i test locali non dimostrano da soli l'assenza di ulteriori OOM.

Prima del tag stabile: merge e deploy autorizzati, smoke pubblico e persistenza
controllata, misura della memoria durante prima costruzione e ricostruzione della
popolazione, verifica del refresh PR e dei check sullo SHA corretto. Nessun upgrade
paid, modifica Databricks/Neon, cambio modello o riuso di history come nuovi dati current.
