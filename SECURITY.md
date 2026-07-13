# Security Policy

## Supported version

Security fixes are applied to the latest version on the default branch.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature when available. Do not
open a public issue containing credentials, cookies, private document text, or
an exploitable proof of concept.

## Local service boundary

The web interface binds to `127.0.0.1` by default and has no built-in user
authentication. Keep that default on personal computers. Binding to another
host requires `--allow-remote` and should only be done behind authentication,
TLS, upload limits, and network access controls.

Uploaded documents, job logs, intermediate files, and generated audio are
stored in `.webui/` by default. Delete jobs in the interface or remove that
directory when the data is no longer needed.

Browser-based providers read an existing local Chrome session. Treat the
browser profile as sensitive and never commit or share it.
