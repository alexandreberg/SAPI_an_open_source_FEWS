# Provenance of this repository

SAPI was developed in a private repository (~520 commits, 2024–2026). This public
repository was built from it on 2026-09-24/25 so that it contains only what was
**released** and what runs in **production**, with no credential or personal identifier.
This document records how each part was obtained and what was changed.

## How the history was built

- **One commit per release, in chronological order.** Each tag points at a commit whose
  component is exactly that release's version; later releases are added on top.
- **Author date = original release date; committer date = import date.**
- The tag names are the original ones, so a tag cited in the dissertation or in an old
  note resolves here too.
- Before each commit, every file was compared with the original tag and the tree was
  audited (`tools/audit.sh`: gitleaks over the working tree and the whole history, checks
  for real identifiers, credential-like file names, large non-LFS files, and a test that
  `.gitignore` keeps credential files out).

| Tag here | Commit here | Original tag (commit in the private repo) | Source of the files | Comparison with the original tag |
|---|---|---|---|---|
| `station-03-v1.0.0` | `b280e637` | `station-03-v1.0.0` (`b6c7827e`) | production copy of the Station-03 firmware | see note 1 |
| `station-02-v1.0.0` | `426e9d11` | `station-02-v1.0.0` (`9d84e9b6`) | production copy | 7 identical, 7 differ only by the licence header |
| `gateway-01-v2.0.0` | `608902d1` | `gateway-01-v2.0.0` (`a569636e`) | production copy | 3 identical, 7 licence header only |
| `station-01-v1.0.0` | `ee4cb6ae` | `station-01-v1.0.0` (`6347a70f`) | production copy | 2 identical, 2 licence header only |
| `merge2mysql-v1.0.0` | `7c18628e` | `merge2mysql-v1.0.0` (`24462dff`) | production copy | 9 identical, 3 licence header only |
| `webserver-v1.0.0` | `e979b5db` | `webserver-v1.0.0` (`d22d4f58`) | the tag itself | 39 identical, 17 differ only by the account-id replacement (note 2) |
| `shield-morpho-v1.2.0` | `11e21daa` | `shield-morpho-v1.2.0` (`06032298`) | the tag itself | 198 identical, 80 LFS objects verified by SHA-256 |
| `shield-lora-arduino-v1.0.0` | `ec481f95` | `shield-lora-arduino-v1.0.0` (`06032298`) | the tag itself | 192 identical, 80 LFS objects verified by SHA-256 |
| `model4-lgbm-v2.0.0`, `model6-mlr-v2.0.0` | `9b54a63c` | same names (`144ae66b`, one commit for both) | code from the tag; READMEs and result figures as corrected afterwards; the audit PDF from the commit the dissertation cites (`123ea19a`) | 42 identical, 1 account-id replacement |
| `webserver-v1.1.0` | `c55f6ea9` | *new tag* | the deployed state (private `development` at `76c38ba7`) | — (note 3) |

**Licence headers.** The AGPL/SPDX header was added to every source file on 2026-07-28,
after most tags were cut. The imported files carry it; the comparison allowed exactly that
header block and nothing else.

**Note 1 — Station-03.** The original tag points at a test `main.cpp` that does not match
the released binary. The binary was built from the production copy promoted on
2026-03-01, so that copy is what was imported. Rebuilding it gives a 60,604-byte firmware
against the released 60,572 bytes — not bit-identical, because library versions resolve
differently today — with all 193 embedded strings identical.

**Note 2 — hosting account id.** The real Hostinger account id is replaced by
`<HOSTINGER_USER>` in every file, production code included; the SQL schema snapshot
that was named after it is now `webserver/database/schema_20260313.sql`.

**Note 3 — webserver-v1.1.0.** `webserver-v1.0.0` was 12 commits behind what runs on
the server. The deployed state is published as the new tag `webserver-v1.1.0`, so the
difference between the two tags is exactly those fixes.

## Release assets

Assets reused **unchanged** from the private releases (same bytes; SHA-256):

| File | SHA-256 |
|---|---|
| `station-01-v1.0.0-bluepill_f103c8.bin` | `4adfc8ad3a26c60278dbf4e7ade9f014915a46f5a4727a7451d2026a0c5ab480` |
| `station-02-v1.0.0-nucleo_f103rb.bin` | `2a3cac9e8a8a1c497fe308538eb5c3426211b2bee6c325d0367e7a9de1d464e4` |
| `station-03-v1.0.0-nucleo_l476rg.bin` | `cc8e01a3c42d6ff070c94caf8f9bccdb1e9769dab2a5102be3dc71ec4e7aa4ff` |
| `model4_lgbm.pkl` | `ac9151eee0b97b2017f3fd4a37a736accb1fab1aa06d3e633dea87ace8e03cf1` |
| `model4_lgbm.meta.json` | `2888d7199ce57f484a1e200884fd9be7142c853dd8cc3a5baa251d9271cac6f1` |
| `model6_mlr.pkl` | `50383cc248c7224518fa0296244073b5f4c75df633762793bd5a833bd0bb74d6` |
| `model6_mlr.meta.json` | `d8f48d070df491b81288d68077787ea5e73e229f0cb8fc27a11c3c55ba3d45c6` |
| `model4-lgbm-v2.0.0-training-code.tar.gz` | `24ecefd8be724667473ff02b3244454d574b39e5f861a927c5bb529418062998` |
| `model6-mlr-v2.0.0-training-code.tar.gz` | `46159bc21755ced1b2bfaef5ff179d75bedc87b9ddad89503cb3314f68a38688` |
| `predictive-models-v2.0.0-training-data.tar.gz` | `1f21409953fd2505d893c5bb5b038c47fe0642e88f1d66f252a264f11e801076` |

All of them were scanned before publication (gitleaks, and a search for account ids, SIM
and modem identifiers, Telegram ids and tokens, private keys) with no finding.

**Regenerated** from this repository's tags, because the originals contained the hosting
account id or were snapshots of the private tree: `merge2mysql-v1.0.0.tar.gz`,
`webserver-v1.0.0.tar.gz`, `webserver-v1.1.0.tar.gz` and the two KiCad `.tar.gz` (built
from the tag's file list with the 3D models as real files).

**Not published:** the gateway binary (`gateway-01-v2.0.0`). A build embeds the Wi-Fi
password and the API key, so the release carries the source and the build instructions
instead.

**Model provenance.** The `.meta.json` files record `git_commit: 0f2b1d9-dirty`, a commit
of the private repository. The code it refers to is the one in this repository under
`predictive-models/` at the `model4-lgbm-v2.0.0` tag.

## What was left out

- Experiments, test sketches and superseded model versions (`gateway-01-v1.0.0`,
  `model4-lgbm-v1.0.0`, `model6-mlr-v1.0.0`), deprecated trainers, archived results.
- The KiCad project of the BluePill V3 board, which had no release.
- Credential files (only `*-sample*` templates are included), compiled binaries and model
  pickles in the tree (they are release assets), editor and build folders.
- From the documentation: qualification documents, presentations, papers, internal notes,
  the retired Kalman-filter write-ups, vendor datasheets of the sensors.
- From the bench tests: a video, phone screenshots from the cellular tests, and the PDF
  export of the Portuguese M2M report (it predates the masking of the SIM and modem
  identifiers; the Markdown reports are masked). Photos were re-encoded without EXIF
  metadata, and the Telegram/Gmail screenshots cropped to the message content.

## Documents

The files in `docs/` were copied from the private repository's `Documentation/` with their
paths and links rewritten to this layout. Links to issues of the private repository were
turned into plain text.
