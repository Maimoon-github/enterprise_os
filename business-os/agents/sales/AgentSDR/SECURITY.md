# Security policy

AgentSDR holds sales teams' contacts, conversations and the credentials of
the services they connect (LinkedIn and WhatsApp through Unipile, Gmail,
storage, AI providers). We take reports seriously and thank everyone who
reports responsibly.

## Supported versions

| Version | Supported |
|---|---|
| Latest release, and `main` | ✅ Security fixes |
| Older releases | ❌ Upgrade to the latest release |

Self-hosted deployments are operated by their owners; a fix reaches you when
you upgrade (see [docs/self-hosting.md](docs/self-hosting/production.mdx#upgrading)).

## Reporting a vulnerability

**Please do not open a public issue, discussion or pull request for a
security problem.**

1. **Preferred:** report privately through GitHub —
   [Security → Report a vulnerability](https://github.com/Kandid-ai/AgentSDR/security/advisories/new).
2. **Or email** **security@kandid.ai**.

Include what you can of:

- the affected version or commit, and whether it is self-hosted;
- the component (e.g. an API route, a webhook, the call-recorder extension);
- steps to reproduce or a proof of concept, and the impact you see;
- whether the issue is already public or being exploited.

## What to expect

| Step | Target |
|---|---|
| Acknowledgement | within 3 business days |
| Initial assessment (validity, severity) | within 7 business days |
| Fix or mitigation for critical / high issues | as fast as possible, typically within 30 days |
| Disclosure | coordinated with you once a fix is released |

We will keep you informed, credit you in the advisory if you wish, and
publish a GitHub Security Advisory (with a CVE where appropriate) when the
fix ships. There is no paid bug bounty.

## Scope

In scope — the code in this repository, for example:

- authentication, sessions, organization membership and roles;
- **tenant isolation**: any way for one organization to read, change or
  count another organization's data;
- the encryption and handling of stored integration credentials;
- public endpoints: webhooks (`/api/webhooks/*`, the Gmail push endpoint),
  unsubscribe links, the call-recorder extension API (`/api/call-recorder/*`);
- injection, XSS, SSRF (including the Tables HTTP column), CSRF on
  state-changing routes.

Out of scope:

- vulnerabilities in a specific self-hosted deployment's infrastructure,
  configuration or network (report to its operator);
- issues in third-party services (Unipile, Google, Cloudflare, OpenRouter,
  enrichment providers) — report to the vendor;
- denial of service by volume, spam, social engineering, physical attacks;
- missing security headers or best-practice suggestions without a
  demonstrated impact;
- reports from automated scanners without a working proof of concept.

## Safe harbor

We will not pursue legal action against researchers who act in good faith:
who avoid privacy violations, data destruction and service degradation;
who only access data they own or are explicitly authorised to access; and
who give us reasonable time to fix an issue before disclosing it.

## For operators

Hardening guidance for self-hosted instances — secrets, the encryption key,
public routes, the database connection limit — is in
[docs/self-hosting.md](docs/self-hosting.md).
