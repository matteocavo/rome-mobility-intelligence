# Training e valutazione sklearn

## Dati e split

Training source: `rome_transport.features.next_stop_delay_labeled`, **v12** compatibile
validata dal core. v8 è solo riferimento storico, non un fallback. I dati di TEST storici
sono già stati esplorati: una nuova valutazione sugli stessi giorni è diagnostica, non
nuova evidenza di generalizzazione futura. Servono nuove date indipendenti prima del rilascio reale.

Definire prima di qualunque fit i limiti UTC semiaperti `[start, validation_start)`,
`[validation_start, test_start)`, `[test_start, end)`. Tutte le righe della stessa epoca
feed restano insieme. Il cutoff etichette train è l'inizio validation; quello validation
è l'inizio TEST; per TEST si specifica un evaluation cutoff. Sono ammesse solo etichette
con timestamp sorgente strettamente precedente al cutoff. Il purging è contato nel manifest.
Non si usano random split o early stopping con partizione casuale interna.

Chiavi complete non NULL/uniche; etichetta memorizzata uguale a `delay >= 300`,
`abs(delay) <= 43200`, orizzonte tra 1 e 1800 secondi e coerente con i timestamp.
Esclusioni inattese bloccano l'export, non vengono nascoste da filtri correttivi.

## Candidati e preprocessing

- LogisticRegression: mediana numerica appresa sul TRAIN, StandardScaler, one-hot categorico sparso.
- HistGradientBoostingClassifier: mediana numerica, one-hot denso limitato a 32 categorie
  per feature, nessuno scaler e `early_stopping=False` per evitare split casuale.

Missing categorici in un valore esplicito, categorie sconosciute ignorate dal vocabolario
appreso. Nomi di colonna obbligatori, ordine arbitrario accettato e riordinato internamente;
colonne mancanti, extra o duplicate e numeriche non coercibili/infinite sono rifiutate.
NaN rappresenta missing numerico da imputare. Feature numeriche interamente mancanti nel
TRAIN bloccano il fit. La matrice densa viene limitata preventivamente a 256 MB; non è
una garanzia del picco totale di RAM. RandomForest non aggiunta per mantenere contenuto
il costo iniziale. Nessuna equivalenza dichiarata con Spark.

Se il training viene campionato, confrontare varianti con e senza pesi inversi di inclusione
sul validation naturale; la pesatura non influenza il fit dell'imputer/scaler. La scelta
di modello e variante usa F1 validation, poi average precision e un tie-break deterministico.
Le capacità reali e la copertura delle categorie devono comunque essere misurate sul pilota.

## Soglia e metriche

Grid di soglie 0.05-0.95, passo 0.05, applicata **solo sul validation set**. Per ogni soglia:
precision, recall, F1. Criterio candidato: massimo F1, poi precision, poi soglia più alta.
La soglia Spark storica non è copiata. Regola sklearn documentata: **p >= soglia salvata**.
Per uso reale il criterio operativo può richiedere costi/recall minimo prima di congelare
il protocollo; la scelta corrente è una baseline dichiarata.

Solo dopo aver congelato modello e soglia si calcolano una volta le metriche TEST:
precision, recall, F1, ROC-AUC, PR-AUC definita come **average precision**, confusion matrix,
positive rate naturale, predicted positive rate e accuracy accessoria. Nessun refit su
train+validation dopo la selezione. Il codice non impedisce una nuova invocazione umana
sugli stessi dati: il protocollo e il manifest devono tenere traccia dei TEST già consultati.

## Bundle e roundtrip

Directory immutabile: `pipeline.joblib`, `metadata.json`, `contract.json`, `checksums.json`.
Preprocessing e classificatore sono nella stessa Pipeline; metadata includono soglia,
versione sklearn, timestamp UTC, SHA codice, hash/digest contratto, riferimento dati,
confini e campionamento, candidati/metriche validation e metriche TEST. No credenziali o righe reali.

Loader: checksum, schema metadata, contratto completo, versione sklearn esatta, feature
names e ordine classi `[0,1]`. Fidarsi solo di bundle locali controllati, perché joblib
può eseguire codice. Nessun pickle esterno accettato dall'API.

Il test obbligatorio salva la pipeline, avvia un **nuovo processo Python**, ricarica e
confronta `predict_proba` con `rtol=atol=1e-12`, incluse categorie nuove e NULL.
`validate_model_artifact` valida metadata/hash/soglia ed esegue uno smoke sintetico;
un errore produce exit code non zero. Non dimostra qualità sui dati reali.
