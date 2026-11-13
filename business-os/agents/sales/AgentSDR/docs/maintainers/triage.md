# Issue triage

## Labels

| Label | Meaning |
|---|---|
| `bug` | Something is broken or behaves contrary to the documentation. |
| `enhancement` | A feature request or improvement. |
| `documentation` | A docs fix or addition. |
| `good first issue` | Small, well-scoped, with a clear pointer to the code. Keep a few of these open. |
| `help wanted` | We would welcome a contribution; not on the maintainers' near-term list. |
| `needs-triage` | Applied automatically to new issues; removed once a maintainer has read it. |
| `pinned` | Exempt from the stale bot. |
| `security` | See below. Never discussed in a public issue. |

Add area labels (`outreach`, `linkedin`, `whatsapp`, `crm`, `tables`,
`self-hosting`) if they help you filter.

All labels live in `.github/labels.yml`; the Labels workflow creates and
updates them when that file changes on `main` (or when run by hand), so edit
the file rather than the labels page.

## Triage routine

For each `needs-triage` issue:

1. Is it a duplicate? Link the original, close, and say so.
2. Is the report complete (version or commit, how it was installed, steps,
   expected and actual behaviour, relevant log lines with secrets removed)? If
   not, ask for what is missing and wait.
3. Reproduce when you can. A bug that reproduces gets `bug`; one that does not
   gets a comment saying what you tried.
4. Decide: accept (label, optionally `good first issue` or `help wanted`),
   redirect (a question belongs in Discussions or SUPPORT.md), or decline with a
   short reason.
5. Remove `needs-triage`.

## Discussions

Questions, ideas and show-and-tell live in
[Discussions](https://github.com/Kandid-ai/AgentSDR/discussions), not issues.

- **Q&A:** answer, or point to the docs page that answers it, and mark the
  answer. A question that reveals a gap in the docs gets a `documentation`
  issue, so the next person finds it on docs.agentsdr.ai.
- **A question filed as an issue:** use "Convert to discussion" (Q&A) rather
  than closing it.
- **Ideas:** when one is accepted, open an `enhancement` issue that links the
  discussion; when it is declined, say why in the thread.
- **A bug reported in Discussions:** ask for the bug form, or open the issue
  yourself and link it.

## Where reports come from

People reach the forms from the app's **Help** menu (Report a bug fills in
the version), the "Get help" page and footer of docs.agentsdr.ai, the README
and `SUPPORT.md`. Keep `.github/ISSUE_TEMPLATE/` and those links in step when
a form changes.

## Closing the loop

Reference the issue in the fix's commit (`Fixes #123`) so it closes when the
fix lands, and list it in `CHANGELOG.md` under the release. Reply on the
issue with the version that contains the fix.

## Response expectations

These are goals for a volunteer-run project, not guarantees:

- A first human reply to a new issue or pull request within about 5 working
  days.
- Security reports acknowledged promptly, on the timelines `SECURITY.md`
  publishes.
- Be explicit when something will not be done, so people can fork or move on.

## Security reports

Vulnerabilities are reported privately: through GitHub private vulnerability
reporting on the repository, or the security contact in `SECURITY.md`.

If someone posts a vulnerability, secret or personal data in a public issue:

1. Remove or hide the sensitive content (edit the issue, or delete the comment)
   and tell the reporter to use the private channel.
2. Label the issue `security` and, if needed, close and re-open the report as a
   private advisory.
3. If a real credential was exposed, tell the owner to rotate it at once;
   deleting the text does not un-leak it.
4. Never discuss exploit details in public before a fix is released.

## Stale policy

The stale bot (`stale.yml`) marks issues and pull requests with no activity for
**90 days** as stale and closes them after **180 days** in total if there is
still no response. Issues labelled `pinned` or `security` are exempt. A closed
stale issue can be reopened by anyone with new information. Do not use the bot
to dismiss valid bugs: if something is real and unscheduled, label it
`help wanted` and `pinned`.
