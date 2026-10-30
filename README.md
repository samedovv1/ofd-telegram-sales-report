# OFD → Telegram Daily Sales Report

A practical **n8n automation project** that collects daily sales data from the Taxcom OFD API, builds a structured retail report, and sends it to Telegram.

> This repository contains a sanitized public version of the workflow. Real credentials, account identifiers, Telegram chat IDs and private n8n metadata are not included.

## What it does

The workflow runs on a schedule and:

1. Authenticates with the Taxcom OFD API.
2. Loads the configured outlet and cash register.
3. Finds the current shift.
4. Loads shift details and fiscal documents.
5. Retrieves detailed information for every document.
6. Aggregates sold products in a Code node.
7. Calculates revenue, cash, card payments and receipt count.
8. Sends the formatted daily report to Telegram.

## Workflow

```text
Schedule Trigger
      ↓
Taxcom Login
      ↓
Get Outlets
      ↓
Get KKT
      ↓
Get Shifts
      ↓
Get Shift Info
      ↓
Get Documents
      ↓
Split Out
      ↓
Get Document Info
      ↓
Build Sales Report
      ↓
Telegram
```

## Example report

```text
📊 Продажи за 25.09.2026
Продавец: Employee

Product A — 2 — 12 000 ₽
Product B — 1 — 7 500 ₽

💰 Выручка: 19 500 ₽
💵 Наличные: 7 000 ₽
💳 Безнал: 12 500 ₽
🧾 Чеков: 3
```

The example uses fictional data.

## Stack

- n8n
- Taxcom OFD REST API
- JavaScript (n8n Code node)
- Telegram Bot API
- Docker / self-hosted n8n

## Configuration

This public workflow references environment variables instead of real account values.

Copy:

```bash
cp .env.example .env
```

Keep every value in `.env.example` empty. Fill in your own values **only in the local `.env` copy**, and pass them into the n8n process using your deployment's environment configuration. Copying the file alone does not configure a running container:

```env
TAXCOM_INTEGRATOR_ID=
TAXCOM_LOGIN=
TAXCOM_PASSWORD=
TAXCOM_AGREEMENT_NUMBER=
TAXCOM_OUTLET_ID=

TELEGRAM_CHAT_ID_PRIMARY=
TELEGRAM_CHAT_ID_SECONDARY=
```

After importing `workflow.public.json` into n8n, select or create your own **Telegram credential** in both Telegram nodes.

### Note about n8n environment variables

This export uses `$env.*` and requires a trusted deployment where node-level environment access is deliberately permitted. Do not disable environment-access restrictions on shared instances just to run this template. For shared deployments, move Taxcom authentication into an n8n HTTP Request [Custom Auth credential](https://docs.n8n.io/integrations/builtin/credentials/httprequest/#using-custom-auth) and provide the remaining outlet/chat configuration through an approved per-workflow mechanism. Never replace expressions with real secret values in a public export.

## Run with Docker

This project does not include a production Docker configuration because n8n deployments differ. A self-hosted n8n instance can be run with Docker, while secrets should be passed through environment variables or another secret-management mechanism.

## Security

Never commit:

- Taxcom login/password
- API or integration tokens
- Telegram bot tokens
- real Telegram chat IDs or Taxcom account/outlet identifiers
- `.env`
- n8n databases, their WAL/SHM sidecar files, local data directories and backups
- raw workflow exports, credential exports, pinned data and execution payloads

The supplied workflow was sanitized specifically for public GitHub use. Ignore rules only cover the listed names; they do not protect secrets added to tracked files or remove old commits.

### Execution data

The workflow handles Taxcom session tokens, fiscal documents and cashier information at runtime. The public template disables saving successful, failed and manual execution payloads, and execution progress. This reduces retained sensitive data and also limits debugging history.

Keep production payloads out of pinned data, exports, screenshots and logs. These workflow settings do not redact live data, sanitize server logs or delete previously saved executions. Use synthetic data for debugging, or a separately reviewed, restricted and short-lived diagnostic policy.

### Before publishing

Run these checks from the repository root using Python 3.10 or newer:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_public_export.py --history
git diff --cached --check
git diff --cached
```

The security workflow runs the same automated checks on pushes and pull requests with read-only repository permissions. It scans the checked-out files and every reachable Git revision for known secret formats, private file names, filled environment templates and private n8n export data. It also checks the current retention settings. History scanning requires a full clone; shallow clones are rejected.

The check reports paths and reasons without printing matched values. It is tailored to this template and cannot identify every arbitrary password, chat ID or business record. Manually inspect every new URL, header, body, chat ID and code string. Publish only the reviewed `workflow.public.json`; store raw exports and backups outside Git. Do not pin real responses or commit credential bindings, instance metadata or production payloads.

A CI failure occurs after a push and does not undo a public exposure. Run the checks locally before pushing. If a real secret is ever published, revoke or rotate it first; deleting the latest copy alone is insufficient.

### Commit email privacy

For future local commits, use the verified noreply address shown in [GitHub email settings](https://github.com/settings/emails). Set it for this repository with `git config --local user.email YOUR_GITHUB_NOREPLY_ADDRESS`, replacing the placeholder with that address. Enable GitHub's email privacy controls if desired. This does not change email addresses already present in old commits.

## Project status

This is a **practical automation project** built while learning backend development and automation. It solves a real operational task: turning raw OFD sales data into a human-readable daily Telegram report automatically.
