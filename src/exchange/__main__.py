from __future__ import annotations

import uvicorn

from exchange.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "exchange.main:app",
        host="0.0.0.0",
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
