# Primo modello sklearn reale: valutazione del 26 ottobre 2026

**Artifact reale pronto per review, non live.** Training/evaluation locale su labeled Delta v12; nessun deployment o scheduler inference. Tutti i dati e bundle restano privati e ignorati da Git.

Base main: `4b4b79489feb4f01b5dfe284187b74ed88595c67`, PR #1 mergiata. Codice effettivo del training: `f9dbf187185a2c9426970b42f2dfa9748615f45d`. Timestamp trained_at: **2026-10-26T15:53:02.773386+00:00**. Seed TRAIN **42**, validation **43**, TEST **44**.

## Sorgente e controlli

`rome_transport.features.next_stop_delay_labeled VERSION AS OF 12`: **9,975,703 righe**, **964 snapshot**, **8 service dates**. Feed UTC dal **2026-09-25T11:08:00Z** al **2026-10-02T08:03:57Z**; quota positiva **18.83144476%**. v8 resta riferimento storico, nessun fallback latest.

Schema verificato: 134 colonne sorgente, presenti tutte le 47 raw feature (42 numeriche, 5 categoriche). Contratto invariato, trip_progress_ratio esclusa. Hash: `11682b3cc1ab5c1d8440af4f6294e932e815126c3dd86ab609f4d5f8f35c41a5`. Evento next_stop_delay_ge_300s: ritardo realizzato >=300 secondi. Zero etichette incoerenti/orizzonti invalidi, duplicate grain e NaN/inf numerici. Nessuna feature completamente NULL.

NULL principali: `current_departure_delay_seconds` 76.70%, `scheduled_seconds_to_next_stop` 53.36%, `distance_to_next_stop_meters` 53.36%, `vehicle_speed` 85.06%, `vehicle_bearing` 85.76%, `route_type` 53.35%, `agency_id` 53.35%. La mediana è appresa solo sul TRAIN; categorie missing/unknown sono gestite dal preprocessing persistito. Nessun fit su validation/TEST.

## Split congelato prima del fit

Intervalli feed UTC semiaperti, tutte le epoche coincidenti assegnate prima del campionamento. Cutoff etichette strettamente precedente alla partizione successiva; per TEST cutoff **2026-10-02T08:33:58+00:00**.

| Partizione | Confini UTC [inizio, fine) | Snapshot prima del purge | Righe sorgente | Purged | Ammissibili | Positive ammissibili |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2026-09-25T11:08:00+00:00 / 2026-10-01T00:00:00+00:00 | 771 | 7,773,197 | 2,150 | 7,771,047 | 19.248011% |
| validation | 2026-10-01T00:00:00+00:00 / 2026-10-02T00:00:00+00:00 | 144 | 1,720,805 | 2,287 | 1,718,518 | 19.331831% |
| test | 2026-10-02T00:00:00+00:00 / 2026-10-02T08:03:58+00:00 | 49 | 481,701 | 0 | 481,701 | 10.418081% |

| Export | Righe | Positive | Snapshot | Min / max feed osservato UTC |
| --- | ---: | ---: | ---: | --- |
| train | 81,014 | 26.533686% | 767 | 2026-09-25T11:08:00+00:00 / 2026-09-30T23:44:09+00:00 |
| validation | 25,000 | 19.304000% | 143 | 2026-10-01T00:04:01+00:00 / 2026-10-01T23:44:12+00:00 |
| test | 25,000 | 10.332000% | 49 | 2026-10-02T00:04:05+00:00 / 2026-10-02T08:03:57+00:00 |

Le 8 date di servizio totali sono 25 settembre-2 ottobre. I confini feed usano UTC, non le date di servizio Rome: possono includere una porzione della stessa data di servizio su lati diversi, ma nessuna epoca feed è condivisa e le etichette sono purgate. Le snapshot possono contenere la stessa corsa in momenti diversi; non è una validazione group-by-trip di generalizzazione a corse mai viste.

## Campionamento, capacità e footprint

TRAIN: budget 100,000; **48,686 strati** service_date/route_id/feed_hour/classe, tutti preservati. Quota min(n, floor(n*(budget-S)/N)+1), hash xxhash64(chiave completa, seed), tie-break chiave completa. Export effettivo 81,014 righe, con probabilità e pesi inversi di inclusione nel manifest privato. Il minimo per strato altera la prevalenza (26.5337% contro circa 19.248% ammissibile): confrontate varianti pesate e non pesate sul validation.

Validation/TEST: opt-in esplicito al campionamento uniforme deterministico per hash della chiave completa, **senza usare classe o feature nel ranking**, 25,000 righe ciascuno. Non sono i set completi; nessun bilanciamento delle classi. Pesi costanti N/n non cambiano le metriche normalizzate; confusion matrix e conteggi si riferiscono ai campioni, non a stime di conteggi dell’intera popolazione.

- validation: frazione 1.454742%; prevalenza campione 19.304000%, popolazione ammissibile 19.331831%. Margine binomiale descrittivo 95% circa ±0.486 punti percentuali con correzione finita.
- test: frazione 5.189941%; prevalenza campione 10.332000%, popolazione ammissibile 10.418081%. Margine binomiale descrittivo 95% circa ±0.367 punti percentuali con correzione finita.

Questa approssimazione riguarda la sola prevalenza del campione, assume un hash assimilabile a estrazione uniforme e non considera dipendenze temporali/corse: non è un intervallo di generalizzazione o una CI delle metriche del modello. Nessuna ottimizzazione o riequilibrio del TEST.

Pilota solo TRAIN: 10,000 righe, 10,378,611 byte pandas; baseline RSS 150,175,744, picco processo 192,208,896 byte. Fit pilota LR 0.226s e HGB 0.608s. Nessuna metrica validation/TEST usata nel pilota. RAM libera misurata prima dell’export 5,267,185,664 byte, riserva 1,073,741,824; proiezione cautelativa su budget massimo 150,000 righe: 2,883,133,440 byte RSS. È una stima da pilota, non un picco finale misurato.

Export reale: **131,014 righe**, **137,939,766 byte pandas**; cache joblib privata **73,061,941 byte**. Tempo export 78.142s; confronto candidati e valutazione finale circa **18.449s**. Nessun SELECT * indiscriminato o fetch completo della tabella. Cache immutabile verificata per checksum/versione/seed/confini/SHA.

## Confronto candidati sul validation

Pipeline foundation invariata: mediana numerica, scaling solo LR, one-hot con gestione unknown; HGB max_iter=60/max_leaf_nodes=15/early_stopping=False. RandomForest non eseguita: candidato opzionale rinviato per contenere il budget, senza affermare che sia tecnicamente impossibile.

| Candidato | Soglia | Precision | Recall | F1 | ROC-AUC | PR-AUC/AP | Positive | Confusion [[TN,FP],[FN,TP]] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| logistic_regression_unweighted | 0.550 | 0.861148 | 0.795483 | 0.827014 | 0.963988 | 0.904906 | 19.30400% | [[19555, 619], [987, 3839]] |
| logistic_regression_inclusion_weighted | 0.350 | 0.820440 | 0.841691 | 0.830930 | 0.965858 | 0.908466 | 19.30400% | [[19285, 889], [764, 4062]] |
| hist_gradient_boosting_unweighted | 0.575 | 0.840050 | 0.833610 | 0.836817 | 0.970117 | 0.913242 | 19.30400% | [[19408, 766], [803, 4023]] |
| hist_gradient_boosting_inclusion_weighted | 0.350 | 0.825256 | 0.850394 | 0.837636 | 0.971573 | 0.916106 | 19.30400% | [[19305, 869], [722, 4104]] |

Criterio prefissato: massimo F1 validation, poi PR-AUC/AP, poi tie-break deterministico. Scelto **hist_gradient_boosting_inclusion_weighted**, soglia **0.35**, regola **p >= 0.35**. Il vantaggio F1 rispetto a HGB non pesato è piccolo e non è dichiarato statisticamente significativo. Accuracy non usata per selezionare. PR-AUC qui è [average precision sklearn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html), non integrazione trapezoidale.

## Grid validation del modello scelto

37 soglie da 0.05 a 0.95, passo 0.025; 0.45 è solo un punto di confronto, senza preferenza.

| Soglia | Precision | Recall | F1 | Predicted positive | TP | FP | TN | FN |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.050 | 0.522103 | 0.969126 | 0.678613 | 35.83200% | 4677 | 4281 | 15893 | 149 |
| 0.075 | 0.593489 | 0.955657 | 0.732238 | 31.08400% | 4612 | 3159 | 17015 | 214 |
| 0.100 | 0.637177 | 0.944675 | 0.761038 | 28.62000% | 4559 | 2596 | 17578 | 267 |
| 0.125 | 0.675105 | 0.933900 | 0.783690 | 26.70400% | 4507 | 2169 | 18005 | 319 |
| 0.150 | 0.701195 | 0.924368 | 0.797462 | 25.44800% | 4461 | 1901 | 18273 | 365 |
| 0.175 | 0.721531 | 0.913800 | 0.806363 | 24.44800% | 4410 | 1702 | 18472 | 416 |
| 0.200 | 0.740979 | 0.906341 | 0.815360 | 23.61200% | 4374 | 1529 | 18645 | 452 |
| 0.225 | 0.755660 | 0.899088 | 0.821158 | 22.96800% | 4339 | 1403 | 18771 | 487 |
| 0.250 | 0.770321 | 0.889557 | 0.825656 | 22.29200% | 4293 | 1280 | 18894 | 533 |
| 0.275 | 0.783938 | 0.881890 | 0.830034 | 21.71600% | 4256 | 1173 | 19001 | 570 |
| 0.300 | 0.798405 | 0.871529 | 0.833366 | 21.07200% | 4206 | 1062 | 19112 | 620 |
| 0.325 | 0.813725 | 0.859925 | 0.836188 | 20.40000% | 4150 | 950 | 19224 | 676 |
| 0.350 | 0.825256 | 0.850394 | 0.837636 | 19.89200% | 4104 | 869 | 19305 | 722 |
| 0.375 | 0.830954 | 0.844385 | 0.837616 | 19.61600% | 4075 | 829 | 19345 | 751 |
| 0.400 | 0.836435 | 0.838168 | 0.837301 | 19.34400% | 4045 | 791 | 19383 | 781 |
| 0.425 | 0.841300 | 0.831538 | 0.836390 | 19.08000% | 4013 | 757 | 19417 | 813 |
| 0.450 | 0.848271 | 0.823663 | 0.835786 | 18.74400% | 3975 | 711 | 19463 | 851 |
| 0.475 | 0.857298 | 0.815375 | 0.835811 | 18.36000% | 3935 | 655 | 19519 | 891 |
| 0.500 | 0.866282 | 0.808123 | 0.836192 | 18.00800% | 3900 | 602 | 19572 | 926 |
| 0.525 | 0.872389 | 0.796104 | 0.832503 | 17.61600% | 3842 | 562 | 19612 | 984 |
| 0.550 | 0.878858 | 0.784708 | 0.829119 | 17.23600% | 3787 | 522 | 19652 | 1039 |
| 0.575 | 0.886100 | 0.775383 | 0.827053 | 16.89200% | 3742 | 481 | 19693 | 1084 |
| 0.600 | 0.891493 | 0.764401 | 0.823070 | 16.55200% | 3689 | 449 | 19725 | 1137 |
| 0.625 | 0.897626 | 0.752176 | 0.818489 | 16.17600% | 3630 | 414 | 19760 | 1196 |
| 0.650 | 0.903553 | 0.737671 | 0.812229 | 15.76000% | 3560 | 380 | 19794 | 1266 |
| 0.675 | 0.908832 | 0.727103 | 0.807874 | 15.44400% | 3509 | 352 | 19822 | 1317 |
| 0.700 | 0.915295 | 0.714256 | 0.802374 | 15.06400% | 3447 | 319 | 19855 | 1379 |
| 0.725 | 0.920895 | 0.699544 | 0.795101 | 14.66400% | 3376 | 290 | 19884 | 1450 |
| 0.750 | 0.927268 | 0.684211 | 0.787409 | 14.24400% | 3302 | 259 | 19915 | 1524 |
| 0.775 | 0.933102 | 0.667634 | 0.778355 | 13.81200% | 3222 | 231 | 19943 | 1604 |
| 0.800 | 0.941159 | 0.646291 | 0.766339 | 13.25600% | 3119 | 195 | 19979 | 1707 |
| 0.825 | 0.948808 | 0.618317 | 0.748714 | 12.58000% | 2984 | 161 | 20013 | 1842 |
| 0.850 | 0.956088 | 0.595524 | 0.733912 | 12.02400% | 2874 | 132 | 20042 | 1952 |
| 0.875 | 0.961795 | 0.568587 | 0.714676 | 11.41200% | 2744 | 109 | 20065 | 2082 |
| 0.900 | 0.970337 | 0.542271 | 0.695733 | 10.78800% | 2617 | 80 | 20094 | 2209 |
| 0.925 | 0.976190 | 0.492748 | 0.654916 | 9.74400% | 2378 | 58 | 20116 | 2448 |
| 0.950 | 0.982642 | 0.422296 | 0.590725 | 8.29600% | 2038 | 36 | 20138 | 2788 |

Il confronto 0.45 usa la pipeline sklearn selezionata e p>=0.45: non è una riesecuzione del modello Spark, che usava p>0.45.

## TEST finale, una sola valutazione

Il gate privato `<artifact>-selection/selection.json` salva scelta, soglia, timestamp e checksum pipeline **prima** della chiamata predict_proba(TEST); directory esistente rifiutata. Nessun refit o ritocco dopo il TEST. Fit finale sui soli dati TRAIN, senza refit train+validation.

| Metrica | sklearn reale | Spark TEST storico, non equivalente |
| --- | ---: | ---: |
| accuracy | 0.956520 | 0.9401 |
| precision | 0.784195 | 0.8450 |
| recall | 0.799071 | 0.8123 |
| f1 | 0.791563 | 0.8283 |
| roc_auc | 0.971677 | 0.9690 |
| pr_auc | 0.874161 | 0.9063 |

Confusion matrix **[[21849, 568], [519, 2064]]**: TN 21,849, FP 568, FN 519, TP 2,064. Actual positive rate **10.33200%**, predicted positive rate **10.52800%**.

Implementazione, mediana/encoding/categorie raggruppate, modello, pesi/campione, versione Delta e split temporali differiscono da Spark. Anche PR-AUC può usare una definizione diversa. Il diverso positive rate influenza soprattutto precision e PR; accuracy più alta non prova un modello migliore. v12 compatibile non dimostra equivalenza diretta v8/v12. I giorni storici erano già analizzati da Spark: questo holdout è separato per la nuova procedura, non un TEST futuro mai esplorato. Nessuna dichiarazione di superiorità o disponibilità production.

## Artifact, roundtrip e servizio

Percorso runtime locale: `artifacts/real-sklearn-20261026-v1/`. Bundle completo con pipeline/preprocessing, metadata, contratto e checksums; dimensione totale **14,583,500 byte**, non versionato.

- SHA-256 pipeline: `5354b186409bcfe066e61eab81e38de5fc843f6df9a1dcaf31699b2f8182f756`
- SHA-256 manifest checksums.json: `fb68e01e6893c841236687ed4297d940fda0322824e025c7d3fe6bc00403332e`
- sklearn: **1.7.2**; dipendenze esatte in requirements-dev.lock.

Validation CLI PASS. Processo training terminato; nuovo processo carica l’artifact e confronta le probabilità calcolate **prima del save** su 32 input reali separati: **massima differenza 0.0**, tolleranza rtol/atol 1e-12. Il probe proviene da scoring input v11, feed **1793022443**, data 26 ottobre, distinto da training/validation/TEST. Predict_proba finito e in [0,1], mapping sulla soglia salvata PASS. Nessuna nuova predizione sul TEST per il roundtrip.

ModelService load PASS; app ASGI locale configurata con questo artifact: `/ready` 200/loaded, `/model/info` 200 con synthetic=false, modello, trained_at, contratto/hash, soglia, metriche e training reference compatta. Il servizio conserva un solo oggetto per lifespan; query SQL e allocazioni private non sono restituite da model/info. Non è stato avviato un servizio pubblico persistente. `/predict` resta assente.

## Limiti e confini

Solo SQL SELECT e lettura del profilo locale esistente; nessun token scritto in file o log. Nessuna modifica a core, Databricks, Delta, Job, schedule, Spark o MLflow. Nessun frontend/n8n/prediction history/deploy. Export, probe, cache, log privati e artifact sono ignorati. La modifica non abilita inference live. Prima del serving reale servono nuove date indipendenti, accettazione di qualità/freshness, autenticazione, capacità e deploy.
