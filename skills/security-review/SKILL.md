---
name: security-review
description: Audit code for vulnerabilities — injection, secrets, authz, unsafe input handling.
trigger: when the user asks for a security review, audit, or "is this safe?"
---
## When to use
The user asks about security, vulnerabilities, or safety of code they point at.

## How
1. `read_file` everything in scope; `grep` for danger patterns:
   `eval(`, `exec(`, `shell=True`, `pickle.load`, `yaml.load(`, f-string SQL,
   `verify=False`, hardcoded keys/tokens/passwords.
2. Check in priority order:
   - **Injection** — SQL/command/path built from user input without
     parameterization or sanitization.
   - **Secrets** — credentials in code, logs, or error messages.
   - **Input trust** — file uploads, deserialization, external API data used
     unvalidated; path traversal (`..`) on user-supplied paths.
   - **AuthZ** — missing ownership/tenant checks on data access.
   - **Crypto/transport** — weak hashing for passwords, disabled TLS checks.
3. For each finding: location, attack scenario in one sentence, concrete fix.
4. Rate severity: critical / high / medium / low. Lead with criticals.

## Avoid
- Theoretical findings with no reachable attack path — mark them "hardening".
- Pasting secret values back into the conversation; name the location only.
- Rewriting whole files; give targeted fixes.

## Done well
A severity-ordered findings list — each with location, one-line attack
scenario, and a fix the author can apply now. "No findings" is a valid result;
say it plainly.
