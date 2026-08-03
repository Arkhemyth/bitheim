# Security Policy

The Bitheim project takes the security and privacy of our software, experimental tooling, and contributor community seriously.

---

## 1. Supported Versions

Bitheim is currently in pre-release development leading up to initial milestone releases (`v0.1.0 — Foundation`).

| Version / Target | Supported | Description |
| :--- | :--- | :--- |
| `main` branch (source) | :white_check_mark: | Active development source tree; receives current security fixes. |
| Tagged pre-releases (`< 0.1.0`) | :x: | Historical or intermediate builds are not individually patched. |

Prior to formal stable releases (`v1.0.0`), security fixes are developed and integrated directly into the `main` source branch. The `main` branch represents ongoing development rather than a stable production release.

---

## 2. Reporting a Vulnerability

If you discover a potential security vulnerability or exploit in Bitheim, please report it privately. **Do not disclose vulnerabilities through public GitHub issues, pull requests, or public discussions.**

### Preferred Channel: GitHub Security Advisories

Please report security issues using **GitHub Private Vulnerability Reporting**:
- [Open a Security Advisory Report](https://github.com/Arkhemyth/bitheim/security/advisories/new)

### Alternative Security Mailbox

If GitHub Security Advisories is inaccessible, you can contact the project security mailbox:
- **Email:** `security@arkhemyth.com`

*Note: Please use this mailbox exclusively for security vulnerabilities. Do not send general inquiries or conduct reports to this address.*

---

## 3. What to Include in a Report

To assist maintainers in evaluating and reproducing the issue, please include:

1. **Description:** A technical explanation of the vulnerability and its potential security impact.
2. **Affected Components:** Specific files, CLI subcommands, container configurations, or API interfaces involved.
3. **Reproduction Steps:** Step-by-step instructions or a minimal proof of concept (PoC) without causing damage or disclosing live credentials.
4. **Environment Details:** Operating system, Python runtime version, hardware architecture (`amd64` / `arm64`), and configuration context.
5. **Proposed Mitigation:** Any suggested remediation or patch, if available.

---

## 4. Vulnerability Handling and Coordinated Disclosure

Reports are evaluated and remediated on a **best-effort basis** according to risk and impact:

1. **Receipt & Evaluation:** Maintainers triage the report, verify the behavior in an isolated environment, and assess severity and exploitability.
2. **Private Remediation:** When appropriate, maintainers prepare, test, and review remediation privately (e.g., using GitHub Security Advisory private forks) to avoid premature public exposure of attack vectors.
3. **Coordinated Release & Disclosure:** Fix availability and public communication are coordinated so vulnerability details are not exposed before a remediation is available. Depending on severity, exploitability, and whether affected artifacts are pre-release source code or tagged distributions, maintainers may sequence or synchronize public branch integration, release publication, and advisory notices.
4. **Advisories & Attribution:** Public advisories or release notes are issued when warranted by the nature and scope of the vulnerability. Reporter credit is strictly opt-in and provided only with the reporter's explicit consent.

---

## 5. Service Level Expectations

Bitheim is an open-source project maintained on a best-effort basis. The project does not offer commercial Service Level Agreements (SLAs), guaranteed turnaround times, or fixed response schedules.
