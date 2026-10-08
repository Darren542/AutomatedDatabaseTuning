import uvicorn

from autotuner_api.app import create_app
from autotuner_api.config import Settings


def main() -> None:
    settings = Settings.load()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
