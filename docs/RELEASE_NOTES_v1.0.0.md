# Rome Mobility Intelligence v1.0.0

### Public application
https://matteocavo.github.io/rome-mobility-intelligence/

### Highlights
- Popolazione scoring operativa corrente reale e aggregate server-side.
- Catalogo e geografia GTFS, dettaglio linea e pagination, filtri, ricerca e sort server-side.
- Prediction history PostgreSQL/Neon e grafici storici da aggregate orarie.
- Modello operativo sklearn e interfaccia IT/EN.
- Gestione cold start ed errori in production; nessun mock in production.

### Model semantics
- Target: ritardo importante alla prossima fermata >= 300 secondi.
- Output di probabilità/rischio; soglia 0.35 selezionata sul validation set per massimizzare F1.
- TEST: holdout temporale separato, valutato una volta.
- I secondi di ritardo osservati non sono secondi di ritardo previsti.

### Infrastructure
GitHub Pages, Render Free, Databricks e Neon. Target di costo infrastrutturale ricorrente:
0 EUR entro i limiti dei piani gratuiti. Codice Apache-2.0; artifact modello privato non distribuito.

### Known limitations
- Nessuno SLA real-time garantito; aggiornamento best-effort all'ultimo snapshot disponibile.
- Cold start Render Free possibili.
- Posizioni veicolo non esposte.
- Shape GTFS non sempre abbinabile ai trip ID realtime.
- Popolazione storica ancora limitata rispetto alla popolazione scoring corrente.
