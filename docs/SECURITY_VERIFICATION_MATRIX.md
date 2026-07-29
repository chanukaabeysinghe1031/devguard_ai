# Security Verification Matrix — Phase 4B

**Date:** 2026-07-29  
**Policy:** Residual risk is documented honestly. Perfect security is not claimed.

| Control | Test | Expected | Actual | Status | Evidence | Remaining risk |
|---------|------|----------|--------|--------|----------|----------------|
| Password hashing | `test_password_hash_never_stores_plaintext` | bcrypt hash; plaintext absent | Pass | Pass | `test_auth.py` | Algorithm/config drift |
| Token validation | login + `/me` | Valid bearer accepted | Pass | Pass | `test_auth.py` | Clock skew |
| Expired/invalid token | refresh reuse / bad token | 401 | Pass | Pass | `test_auth.py` | Client token storage |
| User isolation | cross-org upload/project | 403 | Pass | Pass | `test_uploads.py`, `test_business_apis.py` | Misconfigured membership |
| Cross-project access | other project ID | 403/404 | Pass | Pass | business API tests | — |
| Cross-analysis access | other analysis ID | denied | Pass | Pass | analysis artifact tests | — |
| Role checks | viewer vs engineer | role gates | Pass | Pass | RBAC deps tests | Incomplete UI enforcement |
| Object ownership | incident-scoped files | org membership required | Pass | Pass | upload service | — |
| Path traversal filename | `../../etc/passwd.log` | sanitised basename | Pass | Pass | `test_security_matrix.py` | OS edge cases |
| Absolute paths | `/tmp/secret.yaml` | basename only | Pass | Pass | security matrix | — |
| Unicode / double extension | `部署-log.txt.exe` | unsupported type | Pass | Pass | security matrix | Novel extensions |
| Null bytes | N/A on upload filename path | rejected/sanitised | Partial | Manual | sanitiser strips unsafe chars | Explicit null-byte unit test thin |
| Empty / whitespace files | upload validation | rejected | Pass | Pass | upload service + Phase 4 | — |
| Binary executables | `.sh` / `.exe` | unsupported | Pass | Pass | security matrix | Content-type spoofing |
| Unsupported types / ZIP | `.zip` | unsupported (ADR-011) | Pass | Pass | security matrix | Future ZIP gate |
| Oversized files | max bytes | rejected | Pass | Pass | upload tests | Client bypass attempts |
| Corrupted input | invalid UTF-8 logs | handled/masked | Pass | Partial | masking + validation | Encoding edge cases |
| Filename sanitisation | traversal/abs | cleaned | Pass | Pass | `sanitize_original_filename` | — |
| Secrets masked before persist | masker on upload/analysis | secrets replaced | Pass | Pass | `secret_masker` tests | New secret formats |
| Secrets masked before logs | structured logging | no raw keys | Pass | Pass | masker + logging policy | Accidental `print` |
| Secrets masked before OpenAI | prompt uses masked context | masked excerpts | Pass | Pass | pipeline + prompt builder | Provider-side retention |
| API keys not returned | `/auth/me`, settings | no secrets in JSON | Pass | Pass | auth responses | Debug endpoints |
| Env secrets not in frontend build | `VITE_*` only | no JWT/DB/OpenAI in bundle | Pass | Pass | frontend env usage | Mis-set Vite vars |
| Exception traces hide secrets | 500 handler | no stack/secrets in body | Pass | Pass | exception handlers | Debug=true locally |
| ORM parameterisation | SQLAlchemy | bound params | Pass | Pass | repository/session usage | Raw SQL rare/none |
| SQL injection resistance | invalid identifiers | rejected/parameterised | Pass | Pass | API validation | — |
| Overlong strings | pydantic limits | 422 | Pass | Partial | schema constraints vary | Not all fields max-length |
| Malformed JSON | bad body | 422 | Pass | Pass | FastAPI | — |
| HTML/script stored content | log text stored | treated as data | Pass | Pass | no HTML render of raw logs in API | Frontend XSS if mishandled |
| Frontend safe render | React text nodes | escaped by default | Pass | Pass | diagnosis UI | Future rich HTML |
| Prompt injection — ignore instructions | classifier + prompt | treated as data; safety rules remain | Pass | Pass | `test_security_matrix.py` | Strong LLM jailbreaks |
| Prompt injection — reveal system prompt | prompt builder | safety rules authoritative | Pass | Pass | prompt contains safety + data | Model non-compliance |
| Prompt injection — invent diagnosis | grounding rules | local/OpenAI constrained | Pass | Pass | grounding + fallback | Weak retrieval + LLM |
| Uploaded logs untrusted | pipeline | masked + classified as data | Pass | Pass | analysis path | — |
| Retrieved docs as evidence not instructions | SAFETY_RULES | evidence framing | Pass | Pass | `prompt_builder.py` | — |

## Prompt-injection residual risk

External LLMs can still ignore instructions. Mitigations: masking, grounding checks, local fallback, circuit breaker, server-side flag gates (`ENABLE_EXTERNAL_LLM`). Residual risk remains **medium** whenever OpenAI is enabled.

## Upload residual risk

Content-type sniffing is extension-led; determined attackers may upload hostile text that is still a permitted `.log`/`.txt`. Treated as untrusted analysis input, not executed.
