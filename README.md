# GitHub Repo Trust Lens

Complementary trust analysis for GitHub repositories.

This project intentionally avoids checks that are already covered by OpenSSF Scorecard. OpenSSF Scorecard already covers areas such as branch protection, CI tests, code review, dependency update tooling, license detection, maintained status, packaging, pinned dependencies, SAST, SBOM, security policy, signed releases, token permissions, vulnerabilities, webhooks, and binary artifacts.

Trust Lens focuses on social, governance, and maintainer-risk signals that are useful when deciding whether a repository feels trustworthy, but that are not the same checks as Scorecard.

## What It Checks

- Maintainer discoverability: `CODEOWNERS`, `MAINTAINERS`, or `GOVERNANCE` files that make responsibility visible.
- Maintainer role inference: declared, active, probable, and trusted contributor roles from ownership files and activity.
- Maintainer bus factor: whether recent merged PRs are concentrated in one merger account.
- Maintainer account maturity: whether recent merger accounts look newly created or minimally established.
- Maintainer transparency: whether recent merger accounts publish basic public profile information.
- Issue handling transparency: whether recent closed issues have maintainers, labels, closure reasons, or linked work that make the outcome auditable.
- Release note quality: whether recent release notes explain changes beyond a tag name.
- Governance surface: presence of non-security governance/support/contribution docs.
- Suspicious churn: whether a new merger account suddenly dominates the newest merged PRs.

These signals are heuristics. They should support a human review, not replace it.

## Install

No package dependencies are required.

```powershell
cd github-repo-trust-lens
python -m trust_lens owner/repo
```

For better rate limits, set a GitHub token:

```powershell
$env:GITHUB_TOKEN = "ghp_..."
python -m trust_lens ossf/scorecard
```

## Output

Human-readable output:

```powershell
python -m trust_lens owner/repo
```

JSON output:

```powershell
python -m trust_lens owner/repo --json
```

Save a report:

```powershell
python -m trust_lens owner/repo --json --output report.json
```

## Local UI

Start the simple browser UI:

```powershell
python -m trust_lens.web
```

Then open:

```text
http://127.0.0.1:8787
```

The UI uses the same analyzer as the CLI. The token field is optional and is only sent to the local server process for that one analysis request.

## Score Meaning

- `A`: strong complementary trust signals
- `B`: generally healthy, minor concerns
- `C`: mixed or thin evidence
- `D`: weak evidence or notable concentration risk
- `E`: high concern

The score is not an OpenSSF Scorecard replacement. It is designed to sit next to Scorecard and ask a different set of questions.
