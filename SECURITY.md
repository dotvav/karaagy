# Security Policy 🔒

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

---

## Reporting a Vulnerability

The Karaagy team takes security and privacy seriously. Because Karaagy interacts with underlying Antigravity OAuth tokens and relays API communications, maintaining strict confidentiality is critical.

If you discover a security vulnerability:

1. **Do NOT open a public GitHub issue.**
2. Please privately disclose the vulnerability via [GitHub Security Advisories](https://github.com/roukine/karaagy/security/advisories/new) or by contacting the maintainer directly.
3. Provide:
   - A detailed description of the vulnerability.
   - Steps to reproduce or proof-of-concept payload.
   - Potential impact on host credentials or environment isolation.

You will receive an acknowledgment within 48 hours, and any verified security issues will be patched promptly with an advisory release.

---

## Sensitive Information Hygiene

* Karaagy automatically masks environment variables matching `TOKEN`, `KEY`, `SECRET`, `AUTH`, and `PASS` in diagnostic endpoints.
* Never commit real OAuth tokens, API keys, or private credential folders (`~/.gemini`) to source control.
