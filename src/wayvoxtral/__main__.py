"""Entry point for WayVoxtral daemon."""

import asyncio
import logging
import sys

from wayvoxtral.daemon import WayVoxtralDaemon


def setup_logging() -> None:
    """Configure logging for the daemon."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    """Run the WayVoxtral daemon."""
    setup_logging()
    logger = logging.getLogger("wayvoxtral")
    logger.info("Starting WayVoxtral daemon v0.1.0")

    try:
        daemon = WayVoxtralDaemon()
        daemon.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
