# auto-projs-checker

Project health checker for local repos, driven by a Google Sheet policy.

## Quickstart
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service_account.json
python runner.py --sheet-id <ID> --sa "$GOOGLE_SERVICE_ACCOUNT_FILE" --no-write
