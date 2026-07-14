# pkg-rpm-template

Template repository for creating RPM package repositories for Qualcomm® Linux.

Clone this template to create a `pkg-rpm-<component>` repo for **one** RPM
package. You add your spec file and a small `sources` pointer; the shipped
GitHub Actions workflows build the RPM on every PR and publish it to Artifactory
on demand. All build/release logic lives in the shared
[`qualcomm-linux/qcom-rpm-utils`](https://github.com/qualcomm-linux/qcom-rpm-utils)
repo — the workflows here are thin callers.

---

## What you get

| Workflow | Trigger | Purpose |
|---|---|---|
| [`build-on-pr.yml`](.github/workflows/build-on-pr.yml) | Pull request | Build the RPM(s) so reviewers confirm the package still builds. Read-only — never publishes. |
| [`pkg-release.yml`](.github/workflows/pkg-release.yml) | Manual (`workflow_dispatch`) | Build **and** publish the RPM(s) to Artifactory, behind an approval gate. |

Both delegate to reusable workflows in `qcom-rpm-utils`, which run a
containerised `rpmbuild` for the runner's host architecture.

---

## Onboarding: step by step

### 1. Create your repo from this template
Use **"Use this template" → Create a new repository**, naming it
`pkg-rpm-<component>` (e.g. `pkg-rpm-audio`). Clone it locally:

```bash
git clone https://github.com/qualcomm-linux/pkg-rpm-<component>.git
cd pkg-rpm-<component>
```

### 2. Configure GitHub settings (one-time)

> Template repositories copy **files only** — not variables, secrets, or
> environments. You must set these on your new repo (Settings → …). If they are
> defined at the **organization** level and shared with `pkg-rpm-*` repos, you
> can skip the ones already inherited.

| Setting | Kind | Where | Value / purpose |
|---|---|---|---|
| `CACHE_BASE_URL` | **Variable** | Secrets and variables → Actions → *Variables* | Base URL of the Artifactory lookaside cache, e.g. `https://qartifactory.qualcomm.com/artifactory/qualcomm-dnf-repo/sources` |
| `ARTIFACTORY_ACCESS_TOKEN` | **Secret** | Secrets and variables → Actions → *Secrets* | Artifactory access token used to publish RPMs and cache sources back. Release only. **Current recommended credential.** |
| `pkg-release-approval` | **Environment** | Environments | Approval gate for publishing — add required reviewers. |

> **Publishing access:** the account behind `ARTIFACTORY_ACCESS_TOKEN` must be a
> member of the [`centos.rpm.devs`](https://lists.qualcomm.com/ListManager?id=centos.rpm.devs)
> Qualcomm list, or Artifactory will reject the upload. Request membership before
> your first release.

> **Note:** a `QSC_API_KEY` secret (exchanged for an Artifactory token, and taking
> precedence over `ARTIFACTORY_ACCESS_TOKEN` when set) is also supported by the
> release workflow. It is **not** the recommended path yet; this README will be
> updated to prefer it once the QSC key issue is resolved.

You also need a **self-hosted runner** available to the repo (the build/publish
jobs use `runs-on: [self-hosted]`), with **Docker** installed.

### 3. Add your package files at the repo root

```
<component>.spec     # exactly one RPM spec file
sources              # checksum + filename of each source tarball
```

Starter copies are in [`examples/`](examples/) — copy them to the root and edit:

```bash
cp examples/mypackage.spec <component>.spec
cp examples/sources sources
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
Commit the spec + `sources` and open a PR. `build-on-pr` fetches the tarball
(from the cache, or from the spec's `Source` URL on a cache miss), verifies its
checksum, and builds the RPM(s). Download the built RPMs from the run's
**Artifacts**; the package list is in the run **Summary**.

### 5. Release (publish to Artifactory)
After merge, go to **Actions → Release → Run workflow**:
- A reviewer approves the `pkg-release-approval` gate.
- Once approved, the RPM(s) are published to Artifactory.

---

## Updating the package version

This is the everyday workflow — **two edits, no tarball in git**:

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

1. The build computes the cache path from `CACHE_BASE_URL` + the `sources` entry
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
| `CACHE_BASE_URL` | Variable | **Yes** | Lookaside cache base URL. Build fails fast if unset. |
| `ARTIFACTORY_ACCESS_TOKEN` | Secret | Release only | Artifactory token for publishing/cache-back. Current recommended credential. |
| `QSC_API_KEY` | Secret | Optional | Exchanged for an Artifactory token; takes precedence over `ARTIFACTORY_ACCESS_TOKEN`. Not the recommended path yet. |
| `centos.rpm.devs` membership | Qualcomm list | Release only | The publishing account must belong to [`centos.rpm.devs`](https://lists.qualcomm.com/ListManager?id=centos.rpm.devs). |
| `pkg-release-approval` | Environment | Release only | Approval gate before publishing. |
| Self-hosted runner | — | Yes | Runs the build/publish jobs (Docker). |

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `cache-base-url is empty` | Define the `CACHE_BASE_URL` Actions **variable**. |
| `No 'sources' file found` | Add a `sources` file at the repo root. |
| `Malformed line in 'sources'` | Each line must be `HASHTYPE (filename) = hexdigest`. Use `sha512sum --tag`. |
| `not in the cache and no matching SourceN: URL` | The tarball isn't cached and no spec `Source` URL matches its filename. Fix the `Source0:` filename or pre-seed the cache. |
| `Checksum mismatch` | The cached/upstream tarball doesn't match `sources`. Fix the checksum or the upstream URL. |
| `No '*.spec' file` / `Multiple spec files` | Keep exactly one spec at the repo root. |
| `403` on publish | The publishing account lacks Deploy permission on the target repo, or is not a member of the [`centos.rpm.devs`](https://lists.qualcomm.com/ListManager?id=centos.rpm.devs) list. Request access. |

See [`docs/workflows.md`](docs/workflows.md) for the full guide.
