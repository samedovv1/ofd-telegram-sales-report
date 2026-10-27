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

Fill in your own values:

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

The workflow uses `$env.*` expressions. If your n8n instance blocks environment-variable access inside nodes, either enable the appropriate n8n setting for your deployment or replace the placeholders with another secure credential/configuration mechanism. Do not commit real credentials to Git.

## Run with Docker

This project does not include a production Docker configuration because n8n deployments differ. A self-hosted n8n instance can be run with Docker, while secrets should be passed through environment variables or another secret-management mechanism.

## Security

Never commit:

- Taxcom login/password
- API or integration tokens
- Telegram bot tokens
- real Telegram chat IDs if you want to keep them private
- `.env`
- n8n database files
- credential exports

The supplied workflow was sanitized specifically for public GitHub use.

## Project status

This is a **practical automation project** built while learning backend development and automation. It solves a real operational task: turning raw OFD sales data into a human-readable daily Telegram report automatically.
