# Identità workload Databricks read-only

Il 26 ottobre 2026 è stata configurata `rome-mobility-intelligence-readonly` nel workspace
Free Edition. Non è un membro di admins; entitlement esplicito: solo databricks-sql-access.
Nessuna ownership, nessun privilegio CREATE/MODIFY/MANAGE o permesso sui Job assegnato.

## Permessi minimi

| Oggetto | Privilegio |
| --- | --- |
| rome_transport | USE_CATALOG |
| rome_transport.features | USE_SCHEMA |
| features.next_stop_delay_labeled | SELECT |
| features.next_stop_delay_scoring | SELECT |
| Warehouse esistente 54e230332b887474 | CAN_USE |

Nessun grant al backend su Bronze, Gold, Silver o sul resto del catalogo.
Rimangono USE_CATALOG/USE_SCHEMA ereditati su workspace/workspace.default; non danno
SELECT sui dati né capacità di creazione/scrittura. L’accesso a dati di esempio pubblici
rimane governato dalla piattaforma.

## Default ereditati corretti

Il gruppo `_workspace_users_workspace_7474647743124164` assegnava CREATE_FUNCTION,
CREATE_MATERIALIZED_VIEW, CREATE_MODEL, CREATE_TABLE e CREATE_VOLUME su workspace.default.
Anche il nuovo service principal li ereditava: sono stati rimossi tutti e cinque dal gruppo.
USE_SCHEMA è rimasto. Al controllo era presente un solo utente umano e il nuovo principal.
L’account personale conserva appartenenza admins e ownership del catalogo/schema tramite
il gruppo amministrativo; non è stato rimosso alcun suo ruolo o ownership. Futuri utenti
non amministratori non riceveranno più quei diritti di creazione automaticamente.

Nessuna modifica a Job, run_as, schedule, notebook, pipeline o dati. Non è stato eseguito
alcun test di scrittura: l’assenza dei privilegi è verificata tramite metadata dei permessi.

## Autenticazione

OAuth M2M client credentials con secret limitato allo scope sql. Secret con durata 90 giorni:
creato 2026-10-26T17:02:12Z, scadenza **2027-01-24T17:02:12Z**. Richiede rinnovo prima della
scadenza; il rinnovo del secret non è automatico. Access token della durata di un’ora,
rinnovati in memoria con anticipo; nessuna persistenza o stampa del token.

Sul computer locale il secret è nel Credential Manager Windows, target
`rome-mobility-intelligence/databricks/oauth-m2m`. Client ID e target sono metadata non segreti;
la configurazione locale .env è ignorata da Git e non contiene il client secret.
Su altri host usare una sorgente privata controllata per DATABRICKS_CLIENT_SECRET e lasciare
DATABRICKS_CREDENTIAL_TARGET vuoto. Non trasferire il credential store personale al deployment.

L’app rifiuta DATABRICKS_TOKEN, fonti secret ambigue, hostname non Databricks AWS e scope
OAuth diversi da sql. Non usa databricks auth token né il profilo CLI dell’operatore.
TLS verificato, redirect OAuth rifiutati, timeout di 15 secondi per lo scambio token.
Prima di qualsiasi query richiesta, current_user() deve coincidere con il workload client ID.
Una discordanza blocca e chiude la connessione. Non sono necessari SDK nuovi.

## Verifiche reali

- Token M2M ottenuto con scope sql e expires_in=3600.
- current_user() corrisponde al service principal, non all’utente personale.
- SELECT di una riga su entrambe le tabelle autorizzate: PASS.
- information_schema.table_privileges riporta soltanto i due SELECT per il principal.
- SELECT su bronze.trip_updates e gold.analytics_refresh_metadata: PERMISSION DENIED.
- Permessi effettivi su workspace.default: solo USE_SCHEMA, nessun CREATE.
- Percorso applicativo completo Settings -> Credential Manager -> OAuth provider -> SQL: PASS.
- Nessun training/scoring o Job avviato; nessuna modifica ai dati per la verifica.

Le prove positive e negative sono state eseguite senza stampare righe reali, secret,
Authorization header o token. Nessuna credenziale o .env entra nella CI.

## Limiti

Questa modifica corregge l’identità usata dal canale applicativo locale. Il primo artifact
reale e i suoi metadata storici non vengono modificati o riaddestrati. Il bridge locale di
training ora usa il nuovo client workload, senza fallback personale. Il codice nel core
rimane invariato.

Non equivale a un’approvazione del deploy pubblico: prima servono isolamento dell’account
OS del servizio, storage secret del deployment, autenticazione API, limiti richieste e
provenienza fidata degli artifact. Free Edition continua ad avere limiti di disponibilità
ed amministrazione.

Riferimento: [OAuth M2M Databricks](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m).
