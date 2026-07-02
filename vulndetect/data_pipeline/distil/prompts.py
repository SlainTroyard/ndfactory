# vulndetect/data_pipeline/distil/prompts.py
"""Prompt templates for teacher model security audit generation.

All templates produce structured output with 7 numbered sections.
"""

TEACHER_SYSTEM_PROMPT = """\
You are a senior security researcher performing a thorough code audit.
Analyze the provided code for security vulnerabilities with the following rules:

1. Be precise — cite exact line numbers and code snippets as evidence.
2. Use standard classifications — CWE-ID for vulnerability types, CVSS 3.1 for severity.
3. Be practical — fixes must be compilable and directly applicable to the code shown.
4. Be thorough — if the code is safe, explain why in detail rather than giving a one-line answer.
5. Use the section headers exactly as specified — do not reorder, merge, or skip sections.

Respond in the target language (Chinese for Chinese prompts, English otherwise)."""

SECURITY_AUDIT_PROMPT = """\
Analyze the following {language} code for security vulnerabilities.

For each vulnerability found, provide the following 7 sections:

## 1. Vulnerability Location
Exact line numbers and code snippets where the vulnerability exists.

## 2. Vulnerability Type
CWE-ID and name of the vulnerability (e.g. CWE-89: SQL Injection).

## 3. Root Cause
Why this code is vulnerable — trace the data flow from untrusted input to the vulnerable operation.

## 4. Exploit Scenario
A concrete example of how an attacker could exploit this vulnerability, including sample malicious input.

## 5. Severity Assessment
CVSS 3.1 base score and vector string (e.g. CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H).

## 6. Fix Recommendation
Concrete code fix with before/after comparison. The fix must be directly applicable.

## 7. Prevention
General guidance on how to prevent this class of vulnerability (e.g. input validation, parameterized queries, least privilege).

If NO vulnerability exists in the code, explain in each section why the code handles that aspect safely.

CODE TO AUDIT:
```{language}
{code_snippet}
```"""

SECURITY_AUDIT_PROMPT_SAFE = """\
Analyze the following {language} code and explain why it is secure.

Address each of the following 7 sections from a defensive perspective:

## 1. Input Handling
How this code safely handles all input paths — identify the input sources and what sanitization is applied.

## 2. Absence of Common Vulnerability Patterns
Explain why common vulnerability types (injection, XSS, buffer overflow, etc.) do NOT apply to this code.

## 3. Data Flow Analysis
Trace how data moves from input to output, and explain why each step is safe.

## 4. Authentication & Authorization
If applicable, explain how access control is properly enforced.

## 5. Cryptographic Usage
If applicable, explain how cryptography is used correctly (proper algorithms, key management, no hardcoded secrets).

## 6. Error Handling & Logging
Explain how errors are handled safely — no information leakage, no crash-induced bypasses.

## 7. Defense-in-Depth
What additional security measures or patterns make this code robust (e.g. least privilege, secure defaults, fail-closed design).

CODE TO AUDIT:
```{language}
{code_snippet}
```"""
