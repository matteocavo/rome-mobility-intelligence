# Architettura

## Confini

| Sistema | Responsabilità |
| --- | --- |
| Databricks / repository core | Ingestion, Bronze/Silver/enrichment, feature causali, etichette, Gold, serving datasets, qualità e dashboard |
| Questo repository | Configurazione, accesso SELECT, training/evaluation sklearn, persistenza, caricamento, inference interna e API FastAPI |
| n8n, futuro | Orchestrazione cross-system; nessun duplicato dei Job interni Databricks |
| React + Google AI Studio, futuro | App e progettazione UX/UI che consumano API validate |

Spark ML rimane ricerca/riferimento storico. Non si converte la Random Forest Spark;
il modello sklearn richiede selezione e valutazione proprie. Il core mantiene la preparazione
causale sull'intero storico: non viene ricalcolata sul campione locale.

## Struttura

```text
app/api/routes/       health, readiness e metadata modello
app/core/             environment e logging
app/contracts/        contratto upstream fissato e metadata Pydantic v2
app/data/             SELECT bounded, repository training e scoring input
app/ml/               preprocessing, candidati, metriche, soglia e bundle
app/services/         ModelService, caricamento unico e inference interna
scripts/              CLI training/validation e controlli repository
tests/                fixture sintetiche e test offline
artifacts/            bundle locali ignorati da Git
.github/workflows/    CI senza credenziali
```

La creazione dell'app non apre connessioni e non esegue training. L'avvio tenta un solo
caricamento dell'artifact, se configurato. Un errore mantiene il processo disponibile per
`/health` ma rende `/ready` 503; i dettagli sensibili non entrano nelle risposte pubbliche.
Nessun caricamento implicito di un modello storico o precedente in caso di errore.

## Provenienza

Source of truth: core HEAD remoto `7d263629b533f57af46ffaadcb56e4fcc0f296a7`, PR #7-#11 mergiate.
Il checkout core locale era ancora `a2dcae8f5a858a6ac4e7d08a5be8d67ff51e0a1e`;
è rimasto intatto. I sette file richiesti sono stati letti dalla revisione remota fissata.
JSON e generatore SQL del contratto risultano uguali al checkout locale, al netto dei fine riga.

Fonti upstream fissate:

- [Contratto JSON](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/contracts/operational_ml.json)
- [Proiezioni SQL](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/contracts/operational_ml.py)
- [Handoff](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/OPERATIONAL_ML_HANDOFF.md)
- [Model serving](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/MODEL_SERVING.md)
- [Current scoring](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/CURRENT_SCORING.md)
- [Decisioni](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/ARCHITECTURE_DECISIONS.md)
- [Roadmap](https://github.com/matteocavo/rome-public-transport-reliability/blob/7d263629b533f57af46ffaadcb56e4fcc0f296a7/docs/ROADMAP.md)

Stati storici nelle sezioni Spark non diventano impostazioni operative sklearn. Nessuna
autenticazione, scheduler, frontend, n8n, database prediction history o deploy cloud in questa fase.

## Stato dopo il primo training reale

È disponibile localmente il primo bundle sklearn reale validato; [evidenze](REAL_MODEL_EVALUATION.md).
ModelService e gli endpoint metadata/readiness sono stati verificati con questo artifact
in un’app ASGI locale. Nessun serving pubblico o scheduler inference abilitato.
Il modello e la cache rimangono fuori Git; Databricks e il repository core sono rimasti invariati.
