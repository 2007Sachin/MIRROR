# Skeptic worker

The worker consumes `SKEPTIC_TURN_ANALYSIS` PostgreSQL jobs and runs the
versioned Skeptic Agent in shadow mode. It persists structured findings but
never owns live orchestration or feeds flags to the Interviewer.

Run one queued job from the repository root with `apps/api` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH='apps/api'
python workers/skeptic/worker.py --worker-id skeptic-local-1
```

The command polls continuously. Add `--once` for a single scheduler invocation;
production supervisors can use either this loop or the same `run_once` boundary.

