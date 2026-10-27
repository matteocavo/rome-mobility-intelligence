# Runtime security: artifact trust e query budgets

## Runtime candidato a costo zero

Il trigger production previsto e' GitHub Actions, con service key privata e sole chiamate
HTTPS FastAPI; n8n resta **OPTIONAL / DEMO / USER-PROVIDED EXTERNAL ORCHESTRATOR**.
La delivery preferita usa BuildKit secrets durante la build privata Render: manifest pin
indipendente, download/extraction bounded, pubblicazione atomica e loader F02 invariato.
Root/file del modello appartengono a root, runtime UID 10001 legge soltanto. Il bootstrap
runtime alternativo e' disabilitato di default e non risolve l'egress a ogni cold start.
Nessun secret o artifact reale in Git/image pubblica/Actions artifact. [Limiti](ZERO_COST_DEPLOYMENT.md).

## HTTP e deployment

X-RMI-Service-Key protegge tutte le route operative in ogni ambiente. N8N_SERVICE_API_KEY è
SecretStr, minimo 32 caratteri, confronto timing-safe e distinto dal webhook secret.
La readiness anonima è ridotta; nessun credential/host/path viene esposto. Auth precede il
parsing, con body cap, budget globali bounded distinti inference/write/read e HTTP 429.
CORS vuoto, Host allowlist, nessuna fiducia nei forwarded headers e log senza payload/query.
Runtime production fail-closed, container non-root senza artifact/secret inclusi, un worker.
Nessun deployment pubblico o Cloud smoke. [Dettagli e limiti](SECURE_DEPLOYMENT.md).

## Boundary n8n Cloud

Nessuna API key amministrativa n8n entra nell'applicazione. N8nClient non accetta URL/payload
HTTP arbitrari: usa URL SecretStr e secret server-side, HTTPS con host Cloud esatto configurato,
path webhook allowlisted, nessun redirect/proxy e risposta bounded. Timeout/errori sono
sanitizzati. Nessuna notifica automatica o nuova route pubblica è introdotta.
Header Auth nativo va configurato manualmente sul Webhook Cloud prima di utilizzarlo;
l'export omette riferimenti/valori credential. Il workflow ACK non richiama FastAPI.
Lo schedule separato è inattivo e chiama solo endpoint FastAPI configurati, con retry bounded.
Dati di esecuzione disabilitati, summary senza righe complete, nessuna credential DB/Databricks.
Nessun Docker, listener, tunnel o deploy pubblico. [Confini e setup](N8N_CLOUD_ORCHESTRATION.md).

L'API inference stateless estende questi stessi controlli, senza loader o connector paralleli.
Schema HTTP chiuso per le 47 feature, nessun override di path/threshold/SQL e max batch 100.
Query current fissa sul dataset scoring; log sanitizzati, errori senza input riflessi.
I controlli di readiness non aprono connessioni Databricks. [Contratto API](INFERENCE_API.md).
Public deployment is NOT yet approved: rimane necessario un account OS servizio separato,
senza ownership dello storage modello e senza accesso al credential store personale.

## Persistence PostgreSQL opzionale

Il trigger manual/local/internal richiede ENABLE_PREDICTION_PERSISTENCE=true (default false)
e una DATABASE_URL privata; nessuna autenticazione Internet-facing viene dichiarata.
Solo PostgreSQL riceve gli INSERT idempotenti, in transazione e con constraint DB reale.
Pool bounded senza overflow, timeout di connessione/pool e statement/lock timeout di sessione;
DSN SecretStr, SQL/parametri e diagnostica driver esclusi dai log/API.
Nessun raw feature vector, target realizzato o identificativo utente persistito.
Migration role e runtime role devono essere separati; runtime SELECT/INSERT senza DDL/superuser.
F01–F06 restano attivi e nessuna query Databricks viene bypassata. Nessun OS service modificato.
[Schema, test e validazione nativa ancora da eseguire](PREDICTION_HISTORY.md).

## Trust degli artifact

L’app riceve MODEL_ARTIFACT_PATH, MODEL_ARTIFACT_ROOT e MODEL_ARTIFACT_MANIFEST_SHA256
solo dalla configurazione dell’operatore. Nessun parametro HTTP può cambiarli. I path devono
essere assoluti e il modello deve trovarsi sotto la root configurata; parent traversal,
symlink e qualunque reparse point in file o antenati sono rifiutati prima del caricamento.

Il SHA-256 atteso del checksums.json proviene da una sorgente fidata esterna al bundle.
Non si calcola automaticamente al load dal bundle stesso. In seguito si verificano tutti i
payload contro il manifest ancorato. File regolari, limiti byte, identità del file aperto e
stabilità durante la lettura sono verificati. Il joblib viene caricato da BytesIO degli
stessi byte già verificati: non viene riaperto un path dopo il controllo (TOCTOU).
La cache export applica lo stesso schema: export_manifest_sha256 nel piano esterno, poi
checksum dati e deserializzazione dei byte verificati. Il piano non può risiedere nella cache.

## Copia reale locale

La pin del primo modello reale era già registrata nella validazione/audit precedente:
fb68e01e6893c841236687ed4297d940fda0322824e025c7d3fe6bc00403332e.
La promozione ha verificato prima questa pin indipendente e tutti i payload, poi copiato
il bundle senza riaddestrarlo in %LOCALAPPDATA%/rome-mobility-intelligence/models/.
Il modello sotto artifacts/ rimane una copia storica ignorata, non il path servito.
La configurazione locale, fuori Git, contiene root, path e pin esterna al bundle.

Sul nuovo storage è stata disabilitata l’eredità ACL: utente corrente ReadAndExecute,
SYSTEM e Administrators FullControl, senza accesso del gruppo sandbox. Non sono stati
cambiati dati, parametri ML o metriche; la pipeline conserva il suo checksum originale.
Su POSIX il loader rifiuta directory sotto root e file group/world writable; su Windows
lo storage è stato protetto tramite ACL, da riprodurre e verificare nel deployment.

La pin non è un segreto: la sua integrità dipende dalla configurazione protetta. Un attaccante
che controlla anche configurazione o account OS dell’operatore può sostituire l’ancora.
L’owner Windows può amministrare le ACL: prima del deploy usare un account servizio separato,
non proprietario dello storage/config, con soli diritti di lettura. Non si dichiara isolamento
da compromissione completa dell’host o dell’account amministrativo. Joblib resta eseguibile;
non sono ammessi bundle arbitrari caricati da richieste o semplicemente auto-approvati.

## Deadline e cancellazione SQL

Default: deadline dopo ammissione 120s, attesa coda 1s, un worker SQL per warehouse/processo.
Valori configurabili entro limiti validati (timeout massimo 600s, concorrenza massima 4).
Il deadline comprende OAuth/connessione, controllo identità, query e fetch. Alla scadenza
il chiamante riceve errore e cursor.cancel() è richiesto da un thread dedicato. Il worker
rimane titolare dello slot fino alla fine del cleanup: richieste successive non generano
un numero illimitato di worker orfani se cancel o il connector sono bloccati.

STATEMENT_TIMEOUT è impostato nella sola sessione, con valore arrotondato in secondi.
Il socket ha timeout <=15s e i retry connector sono limitati. Tutte le SELECT richieste
sono avvolte in un SELECT esterno LIMIT max_rows+1 con parametro riservato, per rilevare
un risultato oltre budget senza restituire dati parziali. Il budget byte pandas rimane
client-side; non viene dichiarato un limite server-side di byte o di scansione fisica.
Anche un aggregato con una sola riga può scansire molti dati: il limite tempo è essenziale.

La cancellazione è una richiesta, non una falsa conferma di stop remoto. In caso di problemi
rete il timeout della sessione è il backstop server. Python non può interrompere forzatamente
una chiamata native bloccata: il thread è daemon, i tentativi sono limitati e lo slot resta
occupato. Un processo/servizio compromesso non viene isolato da questi controlli.
Per più processi o repliche occorre un gate/rate limit distribuito e un budget complessivo.

## Prove e confini

Test: bundle sostituito con manifest interno ricalcolato, pin mancante, traversal, symlink,
reparse Windows simulato, permessi POSIX e sostituzione dopo verifica; joblib non viene
invocato per contenuti non approvati. Il roundtrip in processo nuovo rimane presente.
Test query: deadline con execute bloccato, cancel esplicito, connessione lenta senza SQL
tardivo, slot conservato fino al cleanup, parametri riservati e cap server-side.

La copia reale protetta è stata caricata con successo; /ready e /model/info verificati.
Una SELECT reale con l’identità workload, configurazione STATEMENT_TIMEOUT di sessione e
cap righe esterno è riuscita. I test di cancellazione usano mock sincronizzati: non è stata
lanciata una query pesante per forzare consumo compute. Nessun nuovo training, scoring di
produzione, modifica Job/schedule/warehouse globale o dato Databricks.

Riferimenti: [SQL statement timeout](https://docs.databricks.com/aws/en/sql/language-manual/parameters/statement_timeout),
[persistenza sklearn](https://scikit-learn.org/stable/model_persistence.html).
