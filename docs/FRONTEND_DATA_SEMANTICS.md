# Frontend data semantics

The map shows static GTFS stops associated with observations on the visible page. Bordeaux is the stop outline, not a risk class; numbers are stop sequence, never cluster counts. The stop count is unique mapped stops, not population size. The side ranking uses whole-network server aggregates, independent of pagination.

Individual ML risk: high at p >= the model threshold (0.35), moderate at 0.20 <= p < threshold, low below 0.20. Moderate is a UI band, not another model decision. Observed delay is separate; NULL is unavailable, measured zero remains zero. The hero percentage is the proportion classified positive, not average probability or an overall HIGH designation. IT/EN labels follow the same rules. No source timestamps, model, API, freshness thresholds or persistence behavior changed.
