# Releasing pi-coding-agent

Releases are tag-driven: pushing a `v*` tag builds the package, publishes it
to PyPI via **trusted publishing** (no API tokens anywhere), and creates the
GitHub release with the matching CHANGELOG section.

## One-time setup (before the first release)

1. Create / log in to your account on <https://pypi.org>.
2. Open <https://pypi.org/manage/account/publishing/> → **Add a new pending
   publisher** and fill the form exactly:

   | Field | Value |
   |---|---|
   | PyPI project name | `pi-coding-agent` |
   | Owner | `Ashutosh0428` |
   | Repository name | `pi-agent` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

3. In the GitHub repo: **Settings → Environments → New environment** named
   `pypi` (no secrets needed — it only scopes the OIDC identity).

That's it. The first successful workflow run claims the project name and
publishes in one step.

## Every release

```bash
# 1. bump the version (single source of truth)
$EDITOR src/pi_agent/__init__.py        # __version__ = "X.Y.Z"

# 2. add a CHANGELOG section: ## [X.Y.Z] — YYYY-MM-DD
$EDITOR CHANGELOG.md

# 3. commit, tag, push
git add -A && git commit -m "release: vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

The `Publish` workflow does the rest. Verify at
<https://pypi.org/project/pi-coding-agent/> and the repo's Releases page.

## If a release fails

- The tag already exists on PyPI → bump to a new patch version; PyPI never
  re-accepts a used version number.
- Trusted-publisher mismatch → re-check the five form fields above; the
  workflow file name and environment must match exactly.
