#!/usr/bin/env bash
# Release what's on `test` to production screens: checks, merge into main, tag v<VERSION>, push.
# Then run deploy/cloudrun/deploy.sh production in Cloud Shell for the API.   Usage: make release
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
VERSION=$(cat VERSION)
fail() { printf '\033[1;31m%s\033[0m\n' "$*"; exit 1; }

[[ "$(git rev-parse --abbrev-ref HEAD)" == "test" ]] || fail "Run this from the test branch."
[[ -z "$(git status --porcelain)" ]] || fail "Commit or stash your changes first."
[[ "$VERSION" =~ ^20[0-9]{2}\.[0-9]{1,2}\.[0-9]+$ ]] || fail "VERSION must look like 2026.10.3 (it is '$VERSION')."
grep -q "^## ${VERSION//./\\.} " CHANGELOG.md || fail "CHANGELOG.md has no '## $VERSION ...' entry. Add one (what changed, in plain words)."
git fetch -q origin --tags
! git rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null || fail "v$VERSION is already released. Bump VERSION (and add a changelog entry)."

echo "Running the tests…"
make test

git checkout -q main
git pull -q --ff-only origin main
git merge --ff-only -q test || { git checkout -q test; fail "main has commits that test doesn't. Merge main into test first."; }
git tag -a "v$VERSION" -m "Release $VERSION"
git push -q origin main "v$VERSION"
git checkout -q test
printf '\n\033[1;32mReleased v%s: the screens are publishing now.\033[0m\n' "$VERSION"
echo "Next, in Cloud Shell:  cd ~/gasolina && git checkout main && git pull && bash deploy/cloudrun/deploy.sh production"
