# Automated tuner API

Install and start from the repository root using [local development](../../docs/LOCAL_DEVELOPMENT.md).

`autotuner_api.app.create_app` is the composition root. Routes handle HTTP validation and serialization; future application services own use cases. No SQL driver, collector, executor, or model is loaded on startup.

`GET /api/v1/health` reports process liveness, not database readiness. Interactive API documentation is at `/docs`. Target registration, collection jobs, authentication, and persistence are subsequent tasks.
