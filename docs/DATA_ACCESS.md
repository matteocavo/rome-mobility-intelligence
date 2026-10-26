# Accesso dati read-only e budget

Il trasporto scelto per questa foundation è **Databricks SQL Connector for Python**,
con parametri nativi e `use_inline_params=False`. È una scelta esplicita rispetto al
trasporto Statement Execution API esplorato nell'handoff core: contratto, proiezioni,
versioni fissate, purging e controlli sono preservati. Non si copiano i notebook.
[Documentazione ufficiale connector](https://docs.databricks.com/aws/en/dev-tools/python-sql-connector).

Il guardrail analizza l'AST SQL (dialetto Databricks), accetta una sola SELECT e rifiuta
DDL/DML/command/SELECT INTO, anche annidati. Non costituisce un confine di autorizzazione:
il principal Databricks deve avere solo i privilegi SELECT necessari. Nessun metodo writer.
Identificatori catalog/schema/tabella validati separatamente; valori tramite parameter binding.
Cursor/connessione chiusi anche su errore. Nessun retry automatico o log di parametri/token.
Questa iterazione non ha aperto connessioni reali né modificato workspace o Job.

## Export riproducibile

1. Congelare tabella, versione **12**, SHA codice e confini temporali prima della selezione.
2. Contare la popolazione e le esclusioni; anomalie di qualità o duplicate grain bloccano.
3. Misurare un pilota sull'host: byte, righe, RSS durante fit dei candidati e RAM utilizzabile
   con riserva. Non dedurre capacità dalla sola dimensione compressa Delta.
4. TRAIN: entro budget prendere tutte le righe. Altrimenti strati
   `service_date × route_id × feed_hour × classe`; con `S` strati e `N` righe,
   quota `min(n, floor(n*(budget-S)/N)+1)`. La somma non supera il budget;
   ogni strato mantiene almeno una riga. Budget <= S rifiutato prudenzialmente.
5. Ordinare entro strato con `xxhash64(chiave completa, seed)`, poi chiave completa.
   Registrare SQL esatto, seed, conteggi, quote/probabilità tramite `n` e quota,
   pesi inversi e checksum delle chiavi. Nessun `rand()` e nessun LIMIT arbitrario.
6. Validation/TEST completi, temporali e a prevalenza naturale. Se superano il budget,
   **fermarsi**: la foundation non introduce campionamento di valutazione implicito.
7. Il client legge batch di massimo 1000 righe, con limite totale righe e byte pandas.
   Una riga oltre il limite o il budget byte causa errore, mai una restituzione parziale.
   Il consumo transitorio di un batch e le copie pandas vanno inclusi nelle misure pilota.

La selezione avviene lato server; nessun `SELECT *` indiscriminato, `toPandas()` o download
dei 10 milioni di record. Le proiezioni esterne sono esplicite; un eventuale `eligible.*`
interno appartiene soltanto alla subquery già proiettata sul contratto.
L'export validato può essere memorizzato in una cache privata immutabile fuori Git;
questa prima versione non implementa una cache persistente e rilegge la selezione a ogni
invocazione reale esplicita. Non programmare training ripetuti prima di introdurla.

## Piano privato CLI

Creare fuori Git `data_exports/private-plan.json` solo dopo aver misurato il pilota.
Campi richiesti (nessun budget di produzione precompilato):

```text
version: 12
temporal_plan: {start, validation_start, test_start, end, evaluation_cutoff}
train_budget: intero misurato
evaluation_budget: limite per ciascuna partizione di valutazione completa
max_bytes: limite per export
capacity_evidence:
  pilot_rows, pilot_bytes, peak_rss_bytes, available_ram_bytes, reserved_ram_bytes
  measured_at, host, code_sha
```

`code_sha` deve coincidere con HEAD pulito. La CLI verifica budget complessivo contro
capacità stimata dal picco misurato/righe e riserva. È una stima cautelativa iniziale,
non una misura automatica o un'approvazione della sostenibilità. Misure/finestre invalide
o insufficienti devono essere corrette prima dell'esecuzione. Non inventare evidenze.

## Scoring input

`InferenceRepository.snapshot` richiede versione, epoca, conteggio e limite di freshness
approvato esplicitamente. SELECT allowlist del contratto; nessun target realizzato.
Verifica conteggio, grain, hash, sequenza fermata successiva, unica lineage/preparazione,
timestamp non futuri e age di feed/preparazione. Nessun fallback a una versione/epoca
precedente. Il servizio non pianifica inference e non scrive prediction.

`DATABRICKS_TOKEN` è un SecretStr privato nell'environment; l'esempio contiene placeholder.
Rinnovo autenticazione, quota Free, disponibilità warehouse, autenticazione API e deploy
rimangono verifiche successive. I test usano mock/fixture senza credenziali.
