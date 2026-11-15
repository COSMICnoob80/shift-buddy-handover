# SHARE FORMAT — one handover, every platform

The rule: **a handover is a bundle, not a message.** Any surface — WhatsApp,
Telegram, email, a printer, an EMR import — renders a view of the same bundle.
Nothing is written twice.

## 1. The bundle

```
handover-<ward>-<YYYY-MM-DD>-<shift>/
  handover.md        human-readable, platform-neutral markdown
  handover.json      the facts: patients, orders, owners, deadlines, provenance
  card-<MR>.png      one image per patient, ward-readable, WhatsApp-ready
  voice-<MR>.ogg     spoken version of that patient's over (opus, WhatsApp-native)
  print.pdf          A4, one page per patient, for the physical file
  manifest.json      bundle version, generated-at, source ids, hash of each file
```

`manifest.json` carries a SHA-256 per file. If someone forwards a handover and a
number looks wrong, you can prove which version they had.

## 2. Inputs — what the pipeline must swallow

| Kind | Format | Handling | Never |
| --- | --- | --- | --- |
| Voice note | `.opus`, `.ogg`, `.m4a` | Local ASR, speaker-tagged, timestamped | Sent to a cloud API |
| Chat text | WhatsApp `.txt` export, plain text | Parse to events: patient / action / owner / deadline | Trusted without timestamps |
| Progress-note photo | JPG/HEIC | Local OCR, confidence per line | Silently accepted if confidence < 0.6 |
| Screen photo | JPG | OCR + numeric extraction, flagged as *read from a screen* | Treated as a validated figure |
| PDF lab / discharge | PDF | Text layer first, OCR only if none | Invented values for unread fields |
| Spreadsheet | XLSX/CSV | Header-aware parse | Blind row mapping |
| MR number | digits | Join key, exact match only | Fuzzy-matched across patients |

Anything the pipeline cannot read is emitted as a **gap with a question**, never
as a guess. A handover that says "dose unreadable — photograph page 2" is worth
more than one that silently drops it.

## 3. Outputs — one bundle, five views

**A. `handover.md` (the source of truth in text)**

```markdown
## *PATIENT-INITIALS* — bed A3 — MR 123456
**Problem:** one line, plain words.
**Now:** what is happening this shift.
**Done:** what was done, with times.
**Pending:** *thing* — owner *name* — by *time*.
**Watch for:** the failure mode to catch.
**Source:** 6 messages, 2 voice notes, 1 photo (18:12–23:12)
```

**B. WhatsApp view — generated, not hand-typed**

- Bold only: `*text*`. No tables, no headings, no nested lists — WhatsApp renders
  them as garbage on a phone.
- One message per patient, under WhatsApp's 65,536-char limit by design.
- Patient block is self-contained so it can be forwarded alone.
- Numbers always with units; times always 24-hour.
- Ends with `---` then `Next: <name>, <name>` so the receiver knows if a piece is
  missing.

**C. Voice note — the over, spoken**

- One `.ogg` (opus, mono, 32 kbps) per patient, 20–45 seconds.
- Same words as the text block, spoken. No extra content, no omissions: if you
  only listen, you are not missing facts.
- Multilingual by design — Urdu/English code-switching is the ward's actual
  register, and the ASR/TTS pair must both handle it.
- Named `voice-<MR>.ogg` so WhatsApp shows it as a file, not a mystery blob.

**D. Card image — for the eye at arm's length**

- 1080 × 1350 PNG. Ward white, black text, one accent colour for *pending*.
- Name block top, pending orders in a bordered box, "call if" line at the bottom.
- No patient photo. No identifiers beyond initials, MR, bed.

**E. Print — A4, one page per patient**

- Same content, larger type, black on white, no colour dependence.
- Footer: generated-at, shift, who signed it.

## 4. Signing

The MO taps **Sign** in the bundle's `manifest.json` after reviewing. An unsigned
bundle is a *draft* and every view says so in its first line. Signed bundles are
append-only: a correction is a new entry, never an edit.

## 5. Platform matrix

| Platform | Gets | Notes |
| --- | --- | --- |
| WhatsApp | `handover.md` rendered + `card-<MR>.png` + `voice-<MR>.ogg` | Primary. One message per patient. |
| Telegram | Same bundle, markdown-native | Headings allowed here. |
| Email | `handover.md` + `print.pdf` attached | For consultants and records. |
| Printer | `print.pdf` | For the physical file the hospital keeps. |
| EMR (future) | `handover.json` only | Facts, not prose. |
| Anything else | the directory | If it can read a zip, it can read a handover. |

## 6. Non-negotiables in the format

1. Every number in `handover.md` exists in `handover.json`, which carries its
   source. A verifier fails the build otherwise.
2. Every pending item has an owner and a clock. "Pending" alone is a defect.
3. The bundle is complete or it is a draft. No partial signed bundles.
4. Rendering never adds facts — only layout.
