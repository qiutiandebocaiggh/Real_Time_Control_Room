## What changed
- Redesigned the dashboard around pipeline status, event freshness, accepted events and validation controls.
- Added an operational-attention panel based on persisted ingestion state.
- Improved table hierarchy and responsive business-facing presentation.

## Validation
- `python -m compileall -q app run.py ingest.py simulator`
- `python -m ruff check app run.py ingest.py simulator`
