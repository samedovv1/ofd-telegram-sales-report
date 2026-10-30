#!/usr/bin/env python3
"""Check this public template without printing potentially sensitive values."""

import argparse
import fnmatch
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 2 * 1024 * 1024
SECRET_PATTERNS = {
    "Telegram bot token": re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
    "GitHub token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{30,})\b"
    ),
    "private key": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "API key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "credentials in URL": re.compile(r"https?://[^\s/@:]+:[^\s/@]+@"),
}
PRIVATE_NAMES = (
    ".env", ".env.*", "*.env", "*.sqlite", "*.sqlite-*", "*.sqlite3",
    "*.sqlite3-*", "*.db", "*.db-*", "credentials*.json", "workflow*.json",
    "*.pem", "*.key", "*.p12", "*.pfx",
)
PRIVATE_DIRS = {".n8n", "n8n_data", "n8n-data", "backups", "exports"}
PRIVATE_KEYS = {
    "credentials", "instanceId", "webhookId", "versionId", "staticData",
    "executionData", "executions", "shared", "ownedBy", "cachedResultName",
    "cachedResultUrl",
}
RETENTION = {
    "saveDataErrorExecution": "none",
    "saveDataSuccessExecution": "none",
    "saveManualExecutions": False,
    "saveExecutionProgress": False,
}
ENV_EXPRESSION = re.compile(r"^=\{\{\s*\$env\.[A-Z][A-Z0-9_]*\s*\}\}$")
CHAT_EXPRESSION = re.compile(
    r"^=\{\{\s*\$env\.TELEGRAM_CHAT_ID_(?:PRIMARY|SECONDARY)\s*\}\}$"
)


def private_path(path):
    """Only these two explicitly public exports bypass private-name rules."""
    if path in {".env.example", "workflow.public.json"}:
        return False
    parts = PurePosixPath(path).parts
    return bool(PRIVATE_DIRS.intersection(parts[:-1])) or any(
        fnmatch.fnmatchcase(parts[-1].lower(), pattern) for pattern in PRIVATE_NAMES
    )


def scan_text(text):
    # Return descriptions and line numbers, never matching values.
    return [
        f"line {text.count(chr(10), 0, match.start()) + 1}: possible {label}"
        for label, pattern in SECRET_PATTERNS.items()
        for match in pattern.finditer(text)
    ]


def check_workflow(data, current=True):
    errors = []
    if not isinstance(data, dict):
        return ["workflow must be a JSON object"]
    if data.get("pinData") != {}:
        errors.append("pinData must be an empty object")
    if data.get("active") is not False:
        errors.append("public workflow must be inactive")
    if "id" in data:
        errors.append("remove the instance-specific workflow id")

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in PRIVATE_KEYS:
                    errors.append("private n8n metadata or credential binding present")
                if key in {"chatId", "chat_id"} and (
                    not isinstance(child, str) or not CHAT_EXPRESSION.fullmatch(child)
                ):
                    errors.append("chat ID must reference the approved environment variable")
                if key.lower() in {"password", "login", "agreementnumber", "token", "apikey"}:
                    if not isinstance(child, str) or not ENV_EXPRESSION.fullmatch(child):
                        errors.append("literal authentication or account value present")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return errors + ["workflow nodes must be a non-empty list"]
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("parameters"), dict):
            errors.append("invalid workflow node")
            continue
        parameters = node["parameters"]
        if node.get("type") == "n8n-nodes-base.httpRequest":
            url = parameters.get("url", "")
            try:
                parsed = urlsplit(url)
                safe_url = (
                    parsed.scheme == "https" and parsed.hostname == "api-lk-ofd.taxcom.ru"
                    and parsed.username is None and parsed.password is None
                    and parsed.port in {None, 443} and not parsed.query and not parsed.fragment
                )
            except (TypeError, ValueError):
                safe_url = False
            if not safe_url:
                errors.append("HTTP destination is outside the reviewed Taxcom HTTPS endpoint")
            for header in parameters.get("headerParameters", {}).get("parameters", []):
                name, value = header.get("name", "").lower(), header.get("value", "")
                if name == "integrator-id" and not ENV_EXPRESSION.fullmatch(str(value)):
                    errors.append("Integrator-ID must use an environment expression")
                if name == "session-token" and value not in {
                    "={{ $json.sessionToken }}",
                    "={{ $('Taxcom Login').item.json.sessionToken }}",
                }:
                    errors.append("Session-Token must reference the login response")
                if name in {"authorization", "x-api-key"}:
                    errors.append("unreviewed authentication header present")
            if "jsonBody" in parameters:
                body = parameters["jsonBody"]
                approved = (
                    "={{JSON.stringify({login:$env.TAXCOM_LOGIN,"
                    "password:$env.TAXCOM_PASSWORD,"
                    "agreementNumber:$env.TAXCOM_AGREEMENT_NUMBER})}}"
                )
                if not isinstance(body, str) or re.sub(r"\s+", "", body) != approved:
                    errors.append("HTTP JSON body differs from the reviewed environment-only login")
            for query in parameters.get("queryParameters", {}).get("parameters", []):
                if query.get("name") in {"id", "fn", "fd", "shift"}:
                    value = query.get("value", "")
                    if not isinstance(value, str) or not (value.startswith("={{") and value.endswith("}}")):
                        errors.append("Taxcom account/document identifiers must use expressions")
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        return errors + ["invalid workflow settings"]
    if settings.get("availableInMCP") is not False:
        errors.append("public workflow must not be available in MCP")
    if current:
        for key, expected in RETENTION.items():
            if settings.get(key) != expected:
                errors.append(f"unsafe or missing execution setting: {key}")
    return errors


def check_file(path, payload, current=True):
    errors = []
    if private_path(path):
        errors.append("private file name must not be tracked")
    if len(payload) > MAX_BYTES:
        return errors + ["file exceeds the public-template review limit"]
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return errors + ["binary/non-UTF-8 file needs separate review before publication"]
    errors.extend(scan_text(text))
    if path == ".env.example":
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "=" not in line or line.split("=", 1)[1].strip():
                errors.append("environment template must contain empty assignments only")
    if path.endswith(".json"):
        try:
            data = json.loads(text)
            if path == "workflow.public.json":
                errors.extend(check_workflow(data, current=current))
            else:
                # Catch raw exports even if renamed to an arbitrary JSON filename.
                def private_json(value):
                    if isinstance(value, dict):
                        if PRIVATE_KEYS.intersection(value) or {"nodes", "connections"} <= value.keys():
                            return True
                        if {"type", "data"} <= value.keys() and isinstance(value["data"], dict):
                            return True
                        if any(key.lower() in {"password", "bottoken", "sessiontoken", "apikey", "secret"}
                               and child not in (None, "") for key, child in value.items()):
                            return True
                        return any(private_json(child) for child in value.values())
                    return isinstance(value, list) and any(private_json(child) for child in value)
                if private_json(data):
                    errors.append("possible raw n8n/credential JSON export under an unapproved filename")
        except (ValueError, TypeError, AttributeError):
            errors.append("invalid or malformed JSON")
    return errors


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="also scan all reachable Git blobs")
    args = parser.parse_args()
    failures = []
    paths = set(git("ls-files", "-z").decode().split("\0"))
    paths.update(git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"))
    for path in sorted(paths - {""}):
        file = ROOT / path
        if not file.is_file() or file.is_symlink():
            failures.append(f"{path}: missing, non-regular or symlinked file")
            continue
        failures.extend(f"{path}: {error}" for error in check_file(path, file.read_bytes()))
    historical_blobs = set()
    if args.history:
        if git("rev-parse", "--is-shallow-repository").strip() != b"false":
            failures.append("history: full clone required; fetch the complete history first")
        else:
            for commit in git("rev-list", "--all").decode().splitlines():
                for entry in git("ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
                    if not entry:
                        continue
                    metadata, path_bytes = entry.split(b"\t", 1)
                    mode, kind, oid = metadata.decode().split()
                    path = path_bytes.decode("utf-8")
                    if kind != "blob" or mode not in {"100644", "100755"}:
                        failures.append(f"history {commit[:12]} {path}: non-regular file")
                        continue
                    key = (oid, path)
                    if key in historical_blobs:
                        continue
                    historical_blobs.add(key)
                    payload = git("cat-file", "blob", oid)
                    failures.extend(
                        f"history {commit[:12]} {path}: {error}"
                        for error in check_file(path, payload, current=False)
                    )
    for failure in sorted(set(failures)):
        print(failure, file=sys.stderr)
    if failures:
        print("Public export check failed; matched values were not printed.", file=sys.stderr)
        return 1
    print(f"Public export check passed: {len(paths - {''})} files, {len(historical_blobs)} historical blobs.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        print("Public export check could not read repository data; refusing to pass.", file=sys.stderr)
        sys.exit(1)
