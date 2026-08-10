# pkg-rpm-template

Template repository for creating RPM package repositories for Qualcomm® Linux.

Clone this template to create a `pkg-rpm-<component>` repo for **one** RPM
package. Your spec file and a small `sources` pointer go on a per-stream branch
(`c10s`); the shipped GitHub Actions workflows build the RPM on every PR and
publish it to Artifactory on demand. All build/release logic lives in the shared
[`qualcomm-linux/qcom-rpm-utils`](https://github.com/qualcomm-linux/qcom-rpm-utils)
repo — the workflows here are thin callers.

> [!IMPORTANT]
> **Get all the branches — the packaging files are not on `main`.**
>
> This repo uses one branch per distro stream: `main` holds the docs, and
> **`c10s`** holds the spec file and `sources` you actually edit.
>
> - **Creating from the template:** tick **"Include all branches"** in the *Use
>   this template* dialog. **It is off by default**, and with it off your new repo
>   gets only `main` — no `c10s`, and nothing to build.
> - **Cloning an existing repo:** a plain `git clone` fetches every branch, but
>   leaves you on the default one. Run `git checkout c10s` to reach the packaging
>   files.
>
> Already created a repo without the checkbox? Recover `c10s` with the snippet in
> [step 1](#1-create-your-repo-from-this-template).

---

## What you get

| Workflow | Trigger | Purpose |
|---|---|---|
| [`build-on-pr.yml`](.github/workflows/build-on-pr.yml) | Pull request | Build the RPM(s) so reviewers confirm the package still builds. Read-only — never publishes. |
| [`pkg-release.yml`](.github/workflows/pkg-release.yml) | Manual (`workflow_dispatch`) | Build **and** publish the RPM(s) to Artifactory, behind an approval gate. |

Both delegate to reusable workflows in `qcom-rpm-utils`, which run `rpmbuild`
inside the prebuilt `rpm-builder` container image for the runner's host
architecture.

---

## Branch model

This template follows the Fedora/CentOS **dist-git** convention: **one branch per
distro stream**, with the packaging files at that branch's root.

| Branch | Role | Contents |
|---|---|---|
| `main` | Template + docs home. **Nothing is built here.** | This README, [docs/](docs/), community files, workflows. |
| `c10s` | **CentOS 10 Stream package branch — where you work.** | Your `<component>.spec` + `sources` at the root, plus the workflows. |

Future streams get their own branch (`c11s`, …) off the same model, so one repo
can carry a package for several distro versions without branching history.

---

## Onboarding: step by step

### 1. Create your repo from this template
Use **"Use this template" → Create a new repository**, naming it
`pkg-rpm-<component>` (e.g. `pkg-rpm-audio`).

> **Tick "Include all branches"** (see the note at the top — it is off by
> default). If you already created the repo without it, recover `c10s` from the
> template:
> ```bash
> git remote add template https://github.com/qualcomm-linux/pkg-rpm-template.git
> git fetch template c10s
> git push -u origin refs/remotes/template/c10s:refs/heads/c10s
> git remote remove template
> ```

Clone it and switch to the package branch:

```bash
git clone https://github.com/qualcomm-linux/pkg-rpm-<component>.git
cd pkg-rpm-<component>
git checkout c10s
```

### 2. Configure GitHub settings (one-time)

| Setting | Kind | Where | Value / purpose |
|---|---|---|---|
| `pkg-release-approval` | **Environment** | Environments | Approval gate for publishing — add required reviewers. |

The build and publish jobs run on the shared AWS ephemeral ARM64 runner pool
(`runs-on: [self-hosted, platform-prd-u2404-arm64-large-od-ephem]`), which has
Docker available. That label is set inside the reusable workflows, so your repo
must have access to that runner pool, or the jobs will queue forever waiting for
a runner.

The build pulls the prebuilt `rpm-builder` image from GHCR
(`ghcr.io/qualcomm-linux/rpm-builder:centos10`). Both caller workflows therefore
grant `packages: read`; keep that permission if you edit them.

### 3. Add your package files on the `c10s` branch

The starter files are already at the root of `c10s`, carrying a `.example`
suffix. Rename them:

```bash
git checkout c10s
git mv mypackage.spec.example <component>.spec
git mv sources.example sources
```

The suffix exists so the build's single-`*.spec` glob ignores the skeleton until
you rename it — otherwise your first PR would fail with `Multiple spec files`.
After the rename the branch root holds:

```
<component>.spec     # exactly one RPM spec file
sources              # checksum + filename of each source tarball
```

- **`<component>.spec`** — your RPM spec. Its `Source0:`/`SourceN:` must be a
  real, fetchable URL whose **filename matches the `sources` entry** (use
  `%{name}`/`%{version}` macros, and the `#/` rename trick when the URL basename
  differs). Example:
  ```
  Source0: https://github.com/<org>/<proj>/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
  ```
- **`sources`** — one line per tarball, in `sha512sum --tag` (dist-git) format.
  **The tarball is never committed to git.** Generate the line with:
  ```bash
  sha512sum --tag <component>-1.0.tar.gz > sources
  ```
  which yields:
  ```
  SHA512 (mycomponent-1.0.tar.gz) = 3a7bd3e2360a3d29eea436fcfb7e44c735d117c...
  ```

### 4. Open a PR
Commit the spec + `sources` and open a PR **against `c10s`**. `build-on-pr`
fetches the tarball (from the cache, or from the spec's `Source` URL on a cache
miss), verifies its checksum, and builds the RPM(s). Download the built RPMs from
the run's **Artifacts**; the package list is in the run **Summary**.

### 5. Release (publish to Artifactory)
After merge, go to **Actions → Release → Run workflow** and select the `c10s`
branch:
- A reviewer approves the `pkg-release-approval` gate.
- Once approved, the RPM(s) are published to Artifactory.

---

## Updating the package version

This is the everyday workflow — **two edits on `c10s`, no tarball in git**:

1. Bump `Version:` in the spec (and the `Source0:` URL if its path changed).
2. Recompute the checksum for the new tarball:
   ```bash
   sha512sum --tag <component>-<newversion>.tar.gz > sources
   ```
3. Commit the spec + `sources`, open a PR (build verifies it), merge, then run
   **Release**. The first release fetches the new upstream tarball, verifies it,
   and caches it back to Artifactory automatically.

---

## How sources are resolved (cache → upstream → cache-back)

The dist-git **lookaside cache** model: git stores only the checksum; the tarball
lives in Artifactory, content-addressed by that checksum.

1. The build computes the cache path from `SRC_TARBALL_CACHE_BASE_URL` + the `sources` entry
   and checks whether the tarball is already cached.
2. **Cache hit** → download from the cache. **Cache miss** → download from the
   spec's `Source` URL.
3. The checksum is verified against `sources` (mismatch fails the build).
4. On **release**, a tarball fetched from upstream is cached back so future
   builds are hits.

Published layout in Artifactory (defaults):
```
qualcomm-dnf-repo/10-stream/BaseOS/Packages/<pkg>-<ver>.<arch>.rpm
qualcomm-dnf-repo/sources/<filename>/<hashtype>/<hash>/<filename>
```

All RPMs (binary and source) are dumped **flat** into
`10-stream/BaseOS/Packages/` — there are no `src/` or `output/` subfolders.
Artifactory's YUM indexer writes the `repodata/` (with YUM Metadata Folder Depth
`2`, at `qualcomm-dnf-repo/10-stream/BaseOS/repodata/`).

---

## Required configuration summary

| Name | Kind | Required | Purpose |
|---|---|---|---|
| `pkg-release-approval` | Environment | Release only | Approval gate before publishing. |
| Runner pool access | — | Yes | Build/publish run on `[self-hosted, platform-prd-u2404-arm64-large-od-ephem]`. |

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `cache-base-url is empty` | Define the `SRC_TARBALL_CACHE_BASE_URL` Actions **variable**. |
| `denied` / `unauthorized` pulling `rpm-builder` from GHCR | The caller workflow is missing `packages: read`. |
| Build job never starts (stuck *Queued*) | No runner from the `platform-prd-u2404-arm64-large-od-ephem` pool is available to the repo. |
| `No 'sources' file found` | Add a `sources` file at the root of the `c10s` branch (rename `sources.example`). |
| `Malformed line in 'sources'` | Each line must be `HASHTYPE (filename) = hexdigest`. Use `sha512sum --tag`. |
| `not in the cache and no matching SourceN: URL` | The tarball isn't cached and no spec `Source` URL matches its filename. Fix the `Source0:` filename or pre-seed the cache. |
| `Checksum mismatch` | The cached/upstream tarball doesn't match `sources`. Fix the checksum or the upstream URL. |
| `No '*.spec' file` / `Multiple spec files` | Keep exactly one spec on `c10s`. If you added your own alongside `mypackage.spec.example`, the suffix should have hidden it — check you didn't drop the `.example`. |
| No `c10s` branch in your new repo | You created it without ticking **Include all branches**. See the recovery snippet in step 1. |

See [`docs/workflows.md`](docs/workflows.md) for the full guide.
