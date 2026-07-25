Record a vulnerability or security discovery on the scan blackboard.

Always use this tool during scan operations instead of only writing markdown files.

## Anti false-positive rules (mandatory)

- **Never report confirmed** unless you reproduced the issue with a real request/command
- High/critical **confirmed** requires POC with curl/HTTP/steps (min ~30 chars for high/critical)
- Scanner hits (nuclei, sqlmap, etc.) → status **candidate** until manually verified
- If unsure → severity **info** or **low**, status **candidate**, describe what needs verification
- Use **false_positive** when verification fails

Include concrete evidence in `description` and reproducible steps in `poc`.

Severity: critical, high, medium, low, info.
Status: candidate (default), confirmed (verified only), false_positive.
