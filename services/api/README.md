# Automated tuner API

Install and start from the repository root using [local development](../../docs/LOCAL_DEVELOPMENT.md).

`autotuner_api.app.create_app` is the composition root. Routes handle HTTP validation and serialization; future application services own use cases. The collector is imported on startup, but database connections are opened only for explicit connection-test requests.

`GET /api/v1/health` reports process liveness, not database readiness. Interactive API documentation is at `/docs`. `POST /api/v1/targets/test-connection` validates a supplied configuration without saving it; see [Target API](../../docs/TARGET_API.md). Saving targets, collection jobs, API authentication, and persistence are subsequent tasks.
