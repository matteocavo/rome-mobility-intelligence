# API connection and source freshness

The header reports API reachability independently of the freshness of the
snapshot currently displayed. A successful coherent summary/current acquisition
sets provenance API and records the client acquisition time. A failed refresh
retains the last usable snapshot, switches its provenance to LKG, and preserves
the original successful acquisition time. The initial bundled snapshot uses its
capturedAt value. An absent capture time is shown as unknown.

| Data state | Rule |
| --- | --- |
| LIVE | Validated API snapshot, source age from zero through 120 seconds inclusive |
| DELAYED | Validated API snapshot, source age above 120 through 900 seconds inclusive |
| STALE | Source age above 900 seconds, or retained/bundled LKG provenance |
| UNAVAILABLE | No usable source timestamp/provenance, including missing, malformed or future timestamps |

Source time later than acquisition time is invalid. Future or malformed live
source timestamps cannot replace the retained valid population. A valid empty
response retains the existing table empty state, independently of API reachability.
Historical rows keep their persisted-history origin and pagination.

The displayed source watermark determines age. A new API response or newly
generated prediction cannot reset it. Local timers update age at most every
30 seconds and also at the 120/900-second boundaries. These timers perform no
network polling. Focus/visibility changes reclassify a resumed tab immediately.
The UI shows the complete source time and last valid acquisition
time in Europe/Rome, with date, seconds and timezone. API success with an expired
source remains visibly STALE. API failure with usable LKG keeps data visible as
STALE while the connection indicator reports the API failure.

LIVE qualifies source-data freshness. Passenger-target validity remains governed
by the separate model/target validation work. The thresholds are product criteria
for the reviewed v1.0.1 UI, independent of the scheduling pilot.
