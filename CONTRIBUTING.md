# Contributing to Guardians

Guardians is the cover of the family: the bundle, the catalogs, the `guardians` extension (`configure`, `verify`)
and the family-wide documentation. The three Guardians themselves live in their own repositories
([scopeGuard](https://github.com/rlgdev/spec-kit-scopeguard), [archiGuard](https://github.com/rlgdev/spec-kit-archiguard),
[auditGuard](https://github.com/rlgdev/spec-kit-auditguard)); a change to a gate, a collector or a config
schema goes there. What belongs here: a pin bump, a new cross-wiring or alignment check, the getting-started
guide, the family consistency check.

## Development loop

Python 3.9+, git, PyYAML for the tests (the extension itself falls back to a sibling's YAML reader), and for the
end-to-end check a `specify` on PATH.

```bash
python -m pip install pytest pyflakes pyyaml
python -m pytest -q                      # tests on the siblings' real config templates (AUDITGUARD_SRC enables the YAML-fallback test; all three *_SRC the check-family test)
python -m pyflakes scripts/python tools tests
shellcheck scripts/bash/guardians.sh tools/e2e-speckit.sh
python tools/build.py --check            # the Guardians version, the pins, the catalogs and action.yml agree
python tools/check-family.py             # the four repositories agree with each other (siblings as ../spec-kit-<id>, or *_SRC)
tools/e2e-speckit.sh                     # a real Spec Kit project: the siblings from checkouts, configure, verify, the bundle manifest
python tools/build.py                    # dist/guardians.zip, dist/guardians-bundle.zip, dist/SHA256SUMS
```

`tools/check-family.py` is the consistency check across the four repositories: every bundle pin equals the
sibling's own version; every catalog entry equals the sibling's own catalog entry; the siblings' CI pins and
the Guardians refs equal the bundle pins; archiGuard's and auditGuard's version ranges accept the pinned
versions; the fixtures under `tests/fixtures/` are the siblings' config templates at the pinned tags (read with
`git show v<pin>:config-template.yml`, or from the working tree when the checkout has no such tag); the
launchers of all four carry the same interpreter search; every README names its own current release. CI runs it
against the siblings' `main` branches (the pinned tags fetched for the fixtures): a sibling that bumps its
version on `main` turns the job red until the pins here follow it (step 5 of the sibling's `CONTRIBUTING.md`).

## Conventions

The same as the siblings' (see their `CONTRIBUTING.md`): extension files at the root, `.extensionignore` for the
rest, LF line endings, unknown config keys are errors, exit codes `0` / `1` / `2`, Keep a Changelog. In addition:

- **Guardians writes three settings of the siblings and nothing else of theirs** (hook priorities, scopeGuard's
  `integration`, archiGuard's `edit_guard.always_readonly`). A new cross-wiring needs the sibling's documentation to
  call for it first. Its two repairs of Spec Kit's own state (Spec Kit's catalogs back in a catalog file that lists
  only the family's; the agent events, through `specify extension disable/enable guardians`) touch nothing of
  another extension. Every edit keeps the edited file's line ending.
- **Interface to the siblings is their command line and config files**, never their Python modules (the YAML
  reader fallback is the one exception).
- Every `verify` check has a test that makes it fail by one fixture change and reports it by name.

## Releasing the family

A bundle version is a tested combination. The order matters, because the catalogs and the composite action point
at release assets by tag:

1. **Release the siblings first.** Each sibling's own `CONTRIBUTING.md` says how; the tag `vX.Y.Z` triggers its
   release workflow, which attaches `<id>.zip` (and the preset / workflow where the sibling has one) and
   `SHA256SUMS`. A Guardians release can only pin tags that exist with their assets.
2. **Bump the pins here**: `bundle/bundle.yml` (the sibling pins, and the bundle version with the `guardians` pin),
   `catalog/extensions.json`, `catalog/presets.json`, `catalog/bundles.json`, `action.yml` (`rlgdev/spec-kit-<id>@v...`),
   the `*_REF` values in `.github/workflows/ci.yml`, `tests/fixtures/<id>-config.yml` (copies of the siblings'
   `config-template.yml` at the pins), the constants in `scripts/python/guardians_core/siblings.py` if a sibling
   changed a default, and the version in `extension.yml` and `guardians_core/__init__.py`.
   `python tools/build.py --check` and `python tools/check-family.py` must pass.
3. **Run the e2e** against the new tags (`tools/e2e-speckit.sh` clones them), add the CHANGELOG entry with the
   pins, merge to `main`.
4. **Tag** `vX.Y.Z`. The release workflow attaches `guardians.zip`, `guardians-bundle.zip` and `SHA256SUMS`.
   From that moment the three catalog URLs on `main` resolve, `specify bundle install guardians` works, and
   `uses: rlgdev/spec-kit-guardians@vX.Y.Z` resolves the three sibling actions it is composed of.

The first release of the family followed the same order: auditGuard `v0.1.0`, then Guardians `v0.1.0` (scopeGuard
`v0.4.0` and archiGuard `v0.1.0` were already published). Guardians `v0.1.1` followed scopeGuard `v0.4.1` and
archiGuard `v0.1.1`.
