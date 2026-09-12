# Week 12 Production Deployment Report

## Overview

This week deployed the complete IDX Exchange product to Oracle Cloud. The production stack preserves the local product architecture: compliance-screened search, structured filtering, three retrieval profiles, original listing details, Redis-backed operational metrics, and an internal FastAPI service.

## Production Deployment

- Deployed the application on an Oracle Cloud Ubuntu 24.04 VM with Docker Compose. The running stack includes Caddy, public and administrator Streamlit applications, FastAPI, MySQL, and Redis.
- Configured Caddy as the only public entry point. It terminates HTTPS for the public and administrator sites, while the administrator site is protected by Basic Auth.
- Kept FastAPI bound to the VM loopback interface. MySQL, Redis, Streamlit, and the search API communicate only on the Docker network; Caddy alone publishes application traffic on ports `80` and `443`.
- Uploaded the active pass-only search snapshot, query-intent artifact, and required `rets_property.sql` file without adding raw MLS data or model artifacts to Git.
- Created a least-privilege MySQL application account with read access only to `rets_property`.
- Resolved the production dependency mismatch by aligning the runtime with the saved intent-classifier artifact: `scikit-learn==1.3.2` and `joblib==1.5.2`.
- Added a separate public/admin UI configuration. Public users can select `fast`, `balanced`, or `quality`; Metrics and profile comparison remain administrator-only.
- Added session-scoped request limiting and serialized Cross Encoder execution for the quality profile. A busy rerank queue returns an explicit retryable response instead of silently changing retrieval behavior.

## Current Artifacts

- `infra/compose/production.yml`
  - Production service topology, health checks, restart policy, local log rotation, and loopback-only API publishing.

- `infra/proxy/caddy_config`
  - HTTPS reverse proxy for public and administrator sites, including administrator Basic Auth.

- `infra/env/production_template.env`
  - Template for deployment-only domains, paths, secrets, and service limits.

- `infra/database/mysql_readonly_user_init.sh`
  - Creates the read-only MySQL account during first database initialization.

- `notebooks/12_deployment_validation.ipynb`
  - Reuses the frozen Week 11 API evaluation through an SSH tunnel and includes quality-rerank queue checks.

- `docs/deployment_record_CN.md`
  - Local Chinese deployment record with infrastructure choices, recovery steps, and operational commands.

## Validation

- Confirmed Caddy obtained TLS certificates and both public and administrator sites are reachable over HTTPS.
- Confirmed public search, all three profiles, relevance and price sorting, pagination, listing details, and administrator access.
- Confirmed the production API and MySQL services report healthy after initialization; MySQL imported `53,122` `rets_property` records.
- Verified the application account can read the structured filtering table and that city/bedroom queries recover after service initialization.
- Re-ran the deployment-validation notebook through an SSH tunnel. The active API matched the frozen benchmark on public and retrievable listing counts, `federal-1.1` compliance rules, and the MiniLM dense model.
- Reproduced the held-out quality baseline across the deployed profiles: `fast` / `balanced` / `quality` Precision@5 of `0.667` / `0.800` / `0.867`, NDCG@5 of `0.566` / `0.744` / `0.901`, and MRR@5 of `0.794` / `0.917` / `0.917`. All explicit city, price, and bedroom constraints remained valid.
- Observed cache hits at roughly `67-78 ms` P50 across profiles. Cache-miss P50/P95 were `162/553 ms` for `fast`, `173/729 ms` for `balanced`, and `4,133/4,653 ms` for `quality`; the quality cost is dominated by serialized Cross Encoder reranking on the VM.
- Ran the repository test suite before deployment preparation: `355 passed, 1 skipped`.
- Validated the production Compose configuration without starting containers locally.

## Notes

- The current VM is an Oracle `VM.Standard.E5.Flex` trial-credit instance because the intended Always Free ARM shape had no available capacity. Cost and migration options should be reviewed before trial credits expire.
- The initial public URLs use `nip.io` for deployment validation. A stable owned domain and reserved public IP are preferable for longer-term use.
- Credentials, raw MLS data, snapshots, and model artifacts remain outside version control. The Week 12 notebook is the release-parity and latency validation path for the deployed API.
