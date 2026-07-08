<!--
Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
SPDX-License-Identifier: BSD-3-Clause
-->
# Starter files

Copy these to the **root** of your package repository and edit them for your
component:

| File here | Copy to root as | Purpose |
|---|---|---|
| [`mypackage.spec`](mypackage.spec) | `<your-package>.spec` | Your RPM spec file (exactly one at the root). |
| [`sources`](sources) | `sources` | Checksum + filename of each source tarball. |

They live under `examples/` rather than the repo root so the template's own
`build-on-pr` workflow does not try to build the sample package. Once you copy
them to the root and replace the placeholders, CI builds your RPM on every PR.

See [../docs/workflows.md](../docs/workflows.md) for the full onboarding guide.
