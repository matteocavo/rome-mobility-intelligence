# API connection, source age and batch regularity

The header reports API reachability independently of the freshness of the
snapshot currently displayed. A successful coherent summary/current acquisition
sets provenance API and records the client acquisition time. A failed refresh
retains the last usable snapshot, switches its provenance to LKG, and preserves
the original successful acquisition time. The initial bundled snapshot uses its
capturedAt value. An absent capture time is shown as unknown.

| Data state | Rule |
| --- | --- |
| LIVE | Validated API snapshot, source age from zero through 120 seconds inclusive |
| DELAYED | Validated API snapshot, source age above 120 through 16,200 seconds inclusive; batch data, not real-time |
| STALE | Source age above 16,200 seconds, or retained/bundled LKG provenance |
| UNAVAILABLE | No usable source timestamp/provenance, including missing, malformed or future timestamps |

Source time later than acquisition time is invalid. Future or malformed live
source timestamps cannot replace the retained valid population. A valid empty
response retains the existing table empty state, independently of API reachability.
Historical rows keep their persisted-history origin and pagination.

The displayed source watermark determines age. A new API response or newly
generated prediction cannot reset it. Local timers update age at most every
30 seconds and also at the 120/16,200-second boundaries. These timers perform no
network polling. Focus/visibility changes reclassify a resumed tab immediately.
The UI shows the complete source time and last valid acquisition
time in Europe/Rome, with date, seconds and timezone. API success with an expired
source remains visibly STALE. API failure with usable LKG keeps data visible as
STALE while the connection indicator reports the API failure.

## Actual source freshness

The source watermark is the GTFS-RT feed timestamp preserved through the pipeline,
not the Bronze acquisition, feature preparation, inference or API refresh time.
The displayed age remains the elapsed time since that source timestamp. LIVE
still requires at most 120 seconds; the wider batch window does not make old data
LIVE. For example, a 73-minute source remains visibly 73 minutes old.

## Operational batch regularity

The DELAYED state is labelled "Dati batch · non in tempo reale" in Italian and
"Batch data · not real-time" in English. Its 4h30 window accommodates the existing
three-hour downstream interval, approximately one hour of processing, up to
20 minutes between ingestion runs and a further 10 minutes of margin including
the API cache. This is an initial operational allowance, not a latency guarantee
or a measurement of passenger usefulness. Missing cycles or longer execution
times can still exceed it. No scheduler or backend cache setting changes.

LKG remains STALE regardless of age, and invalid/future timestamps remain
UNAVAILABLE. API connection status remains independent of both source age and
batch classification. Historical rows retain their separate archive provenance.

## Temporal usefulness for a passenger

A source within the batch window can still describe events that have already
happened. A useful passenger prediction must precede its target event and satisfy
the separate model/target temporal validation requirements. DELAYED is not proof
of that validity, nor permission to persist expired operational predictions.
This frontend classification changes no model, inference or persistence guard.
