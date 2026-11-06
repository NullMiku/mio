[English](SECURITY.md) | [简体中文](docs/SECURITY.zh-CN.md) | [日本語](docs/SECURITY.ja.md)

---

# Security Policy

Thank you for helping keep Mio and its users safe. This policy explains which versions receive security maintenance and how to report potential vulnerabilities.

## Supported versions

Security maintenance begins with **Mio v2.1**.

| Version | Security support |
| --- | --- |
| Mio v2.1 | Supported while actively maintained |
| Mio v2.2 and later | Supported when released and actively maintained |
| Mio v2.0 and earlier | Not supported |

Security fixes are prioritized for actively maintained versions. Backports are considered based on severity, compatibility, and maintenance resources. Support is not indefinite; this table will be updated as releases move through their maintenance lifecycle.

## Reporting a vulnerability

Mio uses **GitHub Private Vulnerability Reporting**. Please open the repository's [Security Advisories](https://github.com/mio-kobo/mio/security/advisories) page and select **Report a vulnerability**.

**Do not disclose unpatched security vulnerabilities in public Issues, Pull Requests, or Discussions.**

Include as much of the following as possible:

- Affected Mio version or commit SHA.
- Operating system and CPU architecture.
- A description of the issue and its possible security impact.
- Reproduction steps and a minimal proof of concept, if available.
- Relevant logs, diagnostic output, or a possible mitigation.

Do not include real credentials, access tokens, or sensitive personal information. If you are unsure whether a bug has security implications, you may still report it privately.

## Scope

Potential security issues include, but are not limited to:

- Unexpected code execution or memory corruption when the compiler processes crafted input.
- Memory-safety defects in the compiler, runtime, garbage collector, or Bunko standard library.
- Unintended file access, data disclosure, or privilege escalation.
- Compromised build, installation, or release integrity.
- Denial of service with a meaningful security impact.

Mio's type system, GC, and native compilation do **not** constitute an operating-system security sandbox. Use appropriate OS-level permissions and isolation when running untrusted programs. This does not exclude vulnerabilities that arise when the compiler or runtime processes untrusted input.

## Handling and disclosure

Maintainers will make reasonable efforts to reproduce reports, assess their impact, investigate a fix or mitigation, and coordinate disclosure when appropriate. Response and remediation times depend on severity, complexity, and available resources; **no fixed response or resolution time is guaranteed**.

Mio encourages coordinated vulnerability disclosure. Please allow time for investigation and remediation before making exploit details public. Conversations about reported vulnerabilities take place through GitHub's private security advisory system.

Researchers may be credited publicly with their consent. Requests to remain anonymous will be respected.
