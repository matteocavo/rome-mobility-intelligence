# Third-party notices and licensing scope

## Original code

Original FastAPI code, security layer, ML serving, persistence, scripts, tests,
deployment configuration, n8n workflow definitions and documentation:

Copyright 2026 Matteo Cavo

Licensed under Apache License 2.0 unless otherwise noted. See [LICENSE](LICENSE).
This grant covers original project work, not third-party components or data.

## Alembic template (MIT)

`alembic/script.py.mako` is derived from the SQLAlchemy/Alembic migration template
and retains its upstream MIT license. This exception is not relicensed by the
root Apache-2.0 license. The required upstream copyright and permission notice
are preserved below, from [Alembic LICENSE](https://github.com/sqlalchemy/alembic/blob/main/LICENSE).

```text
Copyright 2009-2026 Michael Bayer.

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Public transport data

Fonte dati: Roma Capitale / Roma Servizi per la Mobilità S.r.l. — dati GTFS Statici e GTFS-Realtime del trasporto pubblico locale (ATAC S.p.A. / Roma TPL).

Source: https://romamobilita.it/it/tecnologie/open-data

Public transport data, values and metrics are not relicensed under Apache-2.0.
They remain subject to the applicable upstream open-data licenses, including
CC BY 4.0 / IODL 2.0 where applicable. Consult the source dataset's terms for
its applicable license, attribution requirements and updates. This includes raw
GTFS, stop names, coordinates, route identifiers, timetable values and metrics
derived from public data; Apache-2.0 applies to the original implementation,
not a replacement license for these underlying data.

## Operational ML contract

The original `contracts/operational_ml.json` contract in the core repository and
its synchronized application copy `app/contracts/operational_ml.json` are
Apache-2.0 original project work. Underlying transit data semantics and values
retain their upstream data licensing; synchronization does not change that policy.

## External dependencies and services

Dependencies, container images and external services retain their own upstream
licenses and service terms. They are not relicensed by this project. Consult
the exact installed version and its bundled notices when redistributing:

| Component | Upstream licensing reference |
| --- | --- |
| psycopg / psycopg-binary | https://www.psycopg.org/docs/license.html (including bundled library notices) |
| databricks-sql-connector | https://github.com/databricks/databricks-sql-python/blob/main/LICENSE |
| FastAPI | https://github.com/fastapi/fastapi/blob/master/LICENSE |
| Pydantic | https://github.com/pydantic/pydantic/blob/main/LICENSE |
| SQLAlchemy | https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE |
| Alembic | https://github.com/sqlalchemy/alembic/blob/main/LICENSE |
| scikit-learn | https://github.com/scikit-learn/scikit-learn/blob/main/COPYING |
| pandas | https://github.com/pandas-dev/pandas/blob/main/LICENSE |
| NumPy | https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| SciPy | https://github.com/scipy/scipy/blob/main/LICENSE.txt |
| certifi | https://github.com/certifi/python-certifi/blob/master/LICENSE |
| n8n | https://docs.n8n.io/sustainable-use-license/ (Sustainable Use License and applicable enterprise terms; not Apache-2.0) |
| Caddy | https://github.com/caddyserver/caddy/blob/master/LICENSE |

This is a scope and attribution notice, not an exhaustive dependency inventory
or a substitute for licenses bundled with distributed dependencies and images.
