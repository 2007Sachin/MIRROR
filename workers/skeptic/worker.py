from __future__ import annotations

import argparse
import asyncio
import socket

from app.dependencies import get_skeptic_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Process queued Skeptic shadow jobs")
    parser.add_argument("--worker-id", default=f"skeptic-{socket.gethostname()}")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    worker = get_skeptic_worker()
    if args.once:
        result = asyncio.run(worker.run_once(args.worker_id))
        print(result.model_dump_json())
    else:
        asyncio.run(worker.run_forever(args.worker_id, poll_seconds=args.poll_seconds))


if __name__ == "__main__":
    main()

