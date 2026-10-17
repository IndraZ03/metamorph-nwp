from __future__ import annotations

import logging
import sys
import time

from . import config
from .fetch import discover_latest_run, discover_via_client
from .run import process_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("ecmwf.poll")


def loop() -> None:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("poll every %ss", config.POLL_SECONDS)
    while True:
        try:
            run_time = discover_via_client() or discover_latest_run()
            if run_time is None:
                log.warning("no run discovered")
            else:
                process_run(run_time, skip_if_same=True)
        except KeyboardInterrupt:
            log.info("stop")
            return
        except Exception:
            log.exception("poll cycle failed")
        time.sleep(config.POLL_SECONDS)


def main() -> int:
    loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
