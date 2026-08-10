# CI / Build Workflows

This document describes the GitHub Actions workflows shipped in this RPM package
template repository, and the conventions a component team must follow to onboard
their package.

---

## Overview

This template provides automated CI for **one RPM package per repository**. When
you clone this template for your component, you add your package's spec file and
a `sources` file on the `c10s` branch; the workflows then build (on every PR) and
release (on demand) the RPM for you.

| Workflow | Trigger | Purpose |
|---|---|---|
| [`build-on-pr.yml`](../.github/workflows/build-on-pr.yml) | Pull request | Build the RPM(s) on every PR so reviewers can confirm the package still builds. |
| [`pkg-release.yml`](../.github/workflows/pkg-release.yml) | Manual (`workflow_dispatch`) | Build and publish the RPM(s) to Artifactory, behind an approval gate. |

The build and release logic is **not** duplicated here. Both workflows are thin
callers that delegate to reusable workflows in
[`qualcomm-linux/qcom-rpm-utils`](https://github.com/qualcomm-linux/qcom-rpm-utils):

- `pkg-build-reusable-workflow.yml` — resolves sources and runs the build.
- `pkg-release-reusable-workflow.yml` — builds then publishes to Artifactory.

These reuse [`scripts/build-rpm.sh`](https://github.com/qualcomm-linux/qcom-rpm-utils/blob/main/scripts/build-rpm.sh),
which runs `rpmbuild` for the runner's host architecture inside the prebuilt
[`rpm-builder`](https://github.com/qualcomm-linux/qcom-rpm-utils/blob/main/docker/Dockerfile.rpm-builder)
image, pulled from GHCR as `ghcr.io/qualcomm-linux/rpm-builder:centos10`. Because
the image is prebuilt and published separately, the caller must grant `packages: read` so the
pull is authorised. See the
[reusable-workflows docs](https://github.com/qualcomm-linux/qcom-rpm-utils/blob/main/docs/reusable-workflows.md)
for their full input/secret reference.

---

## End-to-end flow

**Build on PR** — runs on every pull request; the cache is read-only (no
`QSC_API_KEY` is passed):

```
Developer opens PR (bumps Version: in spec + SHA in `sources`)
   │
   ▼
build-on-pr.yml ──calls──▶ pkg-build-reusable-workflow.yml (qcom-rpm-utils)
   │
   ├─ checkout repo + tooling, find the one *.spec
   ├─ resolve-sources.sh, per `sources` line:
   │      HEAD cache  qualcomm-dnf-repo/sources/<sha>/...
   │          ├─ HIT  → download from cache
   │          └─ MISS → read Source0: URL from spec → download upstream
   │      verify SHA against `sources`   ──mismatch──▶ ✗ FAIL
   ├─ build-rpm.sh → docker build (host arch) → ./output
   └─ upload-artifact "rpms-<pkg>-<run_id>" (7 days)
   │
   ▼
Reviewer sees ✓ and downloads the RPMs from the run's Artifacts
```

**Release** — manual, with cache-back and an approval gate:

```
Maintainer: Actions ▸ Release ▸ Run
   │
   ▼
pkg-release.yml ──calls──▶ pkg-release-reusable-workflow.yml (qcom-rpm-utils)
   │
   ├─ job: build  (same as above, release=true)
   │      on a cache MISS, the verified upstream tarball is CACHED BACK
   │      ──▶ qualcomm-dnf-repo/sources/<file>/<hashtype>/<hash>/...  (needs an Artifactory credential)
   │
   ▼
   └─ job: publish   ⛔ environment: pkg-release-approval (human approves)
          RPM_ARTIFACTORY_ACCESS_TOKEN (or QSC_API_KEY) → jf rt upload
             *.rpm     ──▶ qualcomm-dnf-repo/10-stream/BaseOS/Packages/
             *.src.rpm ──▶ qualcomm-dnf-repo/10-stream/BaseOS/Packages/
```

Git stores only the spec and a checksum. The tarball is discovered from the
spec's `Source0:` URL on first use, verified against `sources`, and cached in
Artifactory so later builds reuse it — the Fedora/CentOS dist-git model.

---

## Repository layout

Packaging files live on a **per-stream branch**, at that branch's root —
following the dist-git convention of one branch per distro release:

| Branch | Role |
|---|---|
| `main` | Template + docs home. Nothing is built here. |
| `c10s` | CentOS 10 Stream package branch — where maintainers work. |

On `c10s`:

```
<your-package>.spec     # the RPM spec file (exactly one)
sources                 # checksum + filename of each source tarball (see below)
```

The branch ships these as `mypackage.spec.example` and `sources.example`; rename
them with `git mv` on first use. The `.example` suffix keeps the skeleton
invisible to the build's single-`*.spec` glob, so a fresh repo's first PR doesn't
fail with `Multiple spec files`.

- **`<your-package>.spec`** — your RPM spec. The workflows expect exactly one
  `*.spec` file at the branch root. Its `Source0:`/`SourceN:` URLs must point at
  fetchable upstream tarballs (see the cache model below).
- **`sources`** — a small text file pointing at your source tarball(s) by
  checksum.

> **Note:** the branch name does not yet select the target stream. The builder
> image is pinned to `rpm-builder:centos10` and the publish path defaults to
> `10-stream/BaseOS/Packages/` inside `qcom-rpm-utils`. A future `c11s` branch
> will need the caller workflows to pass the stream explicitly.

> **Tarballs are never committed to git.** Binary tarballs bloat git history and
> produce meaningless diffs. They live in a *lookaside cache* instead; git only
> tracks the small `sources` pointer file.

---

## The dist-git `sources` / lookaside cache model

This template follows the same model that Fedora and CentOS use, called
**dist-git**
([release-engineering/dist-git](https://github.com/release-engineering/dist-git)):
the git repository tracks the spec file, any downstream patches, and a text file
called `sources` that contains the checksum and name of each source tarball. The
tarballs themselves are stored in a separate **lookaside cache**, keyed by their
checksum.

### `sources` file format

Each line uses the BSD checksum format produced by `sha512sum --tag`:

```
HASHTYPE (filename) = hexdigest
```

Worked example:

```
SHA512 (mypackage-1.0.tar.gz) = 3a7bd3e2360a3d29eea436fcfb7e44c735d117c42d1c1835420b6b9942dd4f1b...
```

- `HASHTYPE` — the digest algorithm. **`SHA512` is the default** (matching
  dist-git); `SHA256` is also supported. The workflow picks the matching
  `*sum` tool automatically.
- `filename` — the tarball's filename. This must match the `Source0:` filename
  referenced by your spec file.
- `hexdigest` — the hex checksum of the tarball.

Blank lines and lines starting with `#` are ignored. Multiple tarballs may be
listed (one per line); the build's primary `--tarball` is the first one (sorted).

To generate the line for a tarball:

```bash
sha512sum --tag mypackage-1.0.tar.gz >> sources
```

### How a source is resolved (cache → upstream → cache-back)

Before building, the reusable workflow runs
[`resolve-sources.sh`](https://github.com/qualcomm-linux/qcom-rpm-utils/blob/main/scripts/resolve-sources.sh)
for each entry in `sources`:

1. **Cache lookup.** It computes the lookaside path under `SRC_TARBALL_CACHE_BASE_URL`
   (default layout `{filename}/{hashtype}/{hash}/{filename}`), checks whether the tarball already
   exists there.
2. **Cache hit** → download the tarball from the cache.
   **Cache miss** → expand your spec, find the `SourceN:` URL whose filename
   matches, and download it directly from **upstream**.
3. **Verify** the tarball's checksum against `sources`. A mismatch — from either
   source — fails the build. This is what makes the cache trustworthy.
4. **Cache-back** (release builds only): a tarball that had to be fetched from
   upstream is uploaded to the cache so future builds get a cache hit. This needs
   an Artifactory credential (`RPM_ARTIFACTORY_ACCESS_TOKEN`, or `QSC_API_KEY`) and
   runs only in the release flow, not on PRs.

To bump the version, edit the spec's `Version:` and the checksum in `sources`.
The next release build fetches the new upstream tarball, verifies it, and
populates the cache.

### Lookaside cache layout

The default path template is the dist-git layout:

```
{filename}/{hashtype}/{hash}/{filename}
```

| Placeholder | Value |
|---|---|
| `{filename}` | the tarball filename from `sources` |
| `{hashtype}` | lowercased hash type, e.g. `sha512` |
| `{hash}` | the hex digest from `sources` |

If your cache uses a different layout, override it with the
`cache-path-template` input on the reusable workflow.

---

## Required configuration

The following github env is required for the workflows to run successfully:

You also need an **environment** named `pkg-release-approval` (Settings →
Environments). Add required reviewers to it — the release workflow's publish step
runs in this environment, so a maintainer must approve each release before
anything is uploaded.

Both caller workflows declare `permissions: packages: read` so the reusable build
workflow can pull the `rpm-builder` image from GHCR. The build and publish jobs run on
`[self-hosted, platform-prd-u2404-arm64-large-od-ephem]` — a label set inside the
reusable workflows — so your repo needs access to that runner pool.

---

## Adding or updating a source tarball

1. Bump `Version:` in your spec (and the `Source0:` URL if its layout changed).
2. Record the new tarball's checksum in `sources`:
   ```bash
   sha512sum --tag mypackage-2.0.tar.gz > sources
   ```
3. Commit the spec + `sources` change and open a PR. The PR build verifies the
   tarball (from the cache, or from upstream on a miss). The first **release**
   then caches the upstream tarball back automatically — you do not upload
   tarballs by hand.

---

## Workflows

### `build-on-pr.yml` — Build on PR

**Trigger:** every pull request (changes touching only `**/*.md` are skipped).

**What it does:** calls `pkg-build-reusable-workflow.yml`, which checks out your
repo + the shared tooling, resolves each source (cache → upstream → verify),
locates the single `*.spec`, runs `build-rpm.sh`, then uploads the
built RPMs as a build artifact (`rpms-<pkg>-<run_id>`, retained 7 days) and lists
them in the run summary. No `QSC_API_KEY` is passed on PRs, so the cache stays
read-only (no cache-back).

**Reading results:** open the PR's checks → the *Build on PR* run. The built RPMs
are under the run's **Artifacts**; the package list is in the **Summary**.

**Troubleshooting:**

| Symptom | Cause / fix |
|---|---|
| `No 'sources' file found` | Add a `sources` file at the root of the `c10s` branch (rename `sources.example`). |
| `cache-base-url is empty` | Define the `SRC_TARBALL_CACHE_BASE_URL` Actions variable. |
| `Malformed line in 'sources'` | Each line must be `HASHTYPE (filename) = hexdigest`. Use `sha512sum --tag`. |
| `not in the cache and no matching SourceN: URL` | The tarball was not cached and no spec `Source` URL matches its filename. Fix the `Source0:` filename or pre-seed the cache. |
| `Checksum mismatch` | The cached/upstream tarball doesn't match `sources`. Fix the checksum (or the upstream URL). |
| `No '*.spec' file found` / `Multiple spec files` | Keep exactly one spec file at the branch root. Check you renamed `mypackage.spec.example` rather than copying it. |
| `Build produced no RPMs` | The `rpmbuild` failed — check the *Build RPMs* step logs. |
| `denied` / `unauthorized` pulling `rpm-builder` from GHCR | The caller workflow lacks `packages: read`. |
| Job stuck in *Queued* | No runner from the `platform-prd-u2404-arm64-large-od-ephem` pool is available to the repo. |

### `pkg-release.yml` — Release

**Trigger:** manual `workflow_dispatch`.

**What it does:** calls `pkg-release-reusable-workflow.yml`, which:
1. Builds the RPM(s) via the same reusable build workflow (with cache-back enabled).
2. In the **`pkg-release-approval`** environment (approval gate), uploads the
   RPMs to Artifactory (`qualcomm-dnf-repo` by default) flat under
   `10-stream/BaseOS/Packages/` — binary and source RPMs alike, with no `src/`
   or `output/` subfolders. Artifactory's YUM indexer then generates the
   `repodata/` (at `10-stream/BaseOS/repodata/` with YUM Metadata Folder Depth `2`).

A maintainer must approve the `pkg-release-approval` gate before anything is
uploaded.

---

## Reused tooling

This repo intentionally does **not** fork the RPM build/release logic. It
consumes the reusable workflows, scripts, and composite action in
[`qualcomm-linux/qcom-rpm-utils`](https://github.com/qualcomm-linux/qcom-rpm-utils).
Pin the consumed ref via the `qcom-rpm-utils-ref` input in
[`build-on-pr.yml`](../.github/workflows/build-on-pr.yml) and
[`pkg-release.yml`](../.github/workflows/pkg-release.yml).
