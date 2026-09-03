from __future__ import annotations

import argparse
import asyncio
import socket

from app.dependencies import get_assessment_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Process queued post-session assessment jobs")
    parser.add_argument("--worker-id", default=f"assessor-{socket.gethostname()}")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    worker = get_assessment_worker()
    if args.once:
        print(asyncio.run(worker.run_once(args.worker_id)).model_dump_json())
    else:
        asyncio.run(worker.run_forever(args.worker_id, poll_seconds=args.poll_seconds))


if __name__ == "__main__":
    main()
