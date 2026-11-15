# MANIFESTO — why shift-buddy-handover exists

*Written from a real 16-day record: one medical officer on ad-hoc deputation
from MSD to Radiation Oncology, 29 Oct – 14 Nov 2026.
325 WhatsApp messages, 41 voice notes, 14 photographs, 2 spreadsheets, 1 scanned
PDF, 5 people. Every claim below is traceable to a timestamp in that record; the
evidence appendix lives offline because it contains patient data.*

---

## 1. The thing that broke is not a document. It is a stream.

Every hospital in this country already has a handover. It is not the SBAR in a
textbook. It is a WhatsApp group, a stack of paper files, and a phone that rings
at 2 a.m. The information exists — it is simply **in a shape that cannot be
carried by a human being at shift change**.

In sixteen days this one MO handled sixteen oncology in-patients across two
floors, took handovers in four different formats from four different people,
gave handovers in three, and answered an estimated 200 clinical questions by
message — several of them at 3 a.m., several of them about whether a patient was
about to have a serious complication.

Nothing here is anyone's fault. The registrars were kind, the consultants
answered, the MO learned fast. The failure is structural: **the handover is
delivered at the moment of maximum time pressure, in the medium of minimum
structure, to a person with the least context in the building.**

## 2. Eight ways it fails — seen, not theorised

**a. The over is verbal, then evaporates.**
"Over?" is asked into the group and answered with a voice note, a name, a bed
number, and "baqi sab file mein likha hua hai" — *the rest is in the file*.
The verbal over is the one that actually transfers care; it is also the only one
that leaves no record. Ask the same question two days later and you get a
different answer, because the answer lived in a person's short-term memory.

**b. Critical orders arrive inside conversation, not as orders.**
A nasogastric tube decision for a patient with a fungating head-and-neck wound
took **nine hours** (14:04 → 23:12) to resolve, across ~20 messages and eight
voice notes, one CXR that could not show the tube, one consultant who was
supportive, one who was away, and a deadline that mattered ("priorities: NGT
before radiation starts"). It ended correctly. It could have ended at 15:00.

**c. Messages self-destruct.**
Nine messages in this record were deleted after sending — seven of them inside a
single 48-hour stretch. One of them, in all probability,
carried a dose or a decision. There is no audit trail, no diff, no
"this overruled that". A handover you can edit is a handover you cannot defend.

**d. The doctor is interrupted before the doctor finishes.**
While managing one family at one bed, the MO is called to another floor because
"staff is waiting there" — and forty minutes later is pulled back by the same
family, who are "getting irritable". Human attention is the scarcest resource on
a ward, and nothing in the system protects it.

**e. Reading a photo is not reading a record.**
A blood requisition showed two line items. The MO read it as *two units of packed
cells*. It was one unit plus one cross-match. A consultant corrected it in ninety
seconds — because a human happened to be online. Imaging, doses and consent all
get transmitted as pixels, and pixels are interpreted, not parsed.

**f. Local knowledge is not written down anywhere, and it bites.**
"Injections have to be entered in MOAR for panel patients" — nobody said so. The
consequence landed on a patient at discharge, and on the MO's confidence. Charges
change at midnight. Radiology prefers in-patients late at night. A consultant
stops answering at 12. None of this is in a policy; all of it changes what you do
at 22:00.

**g. Escalation paths are implicit and contradictory.**
"Call Dr Uzma — she won't attend after 12." "No consults please." "Inform Dr
Hira and get medicine on board." "Continue the chemo slowly." Four seniors, four
rules, one MO holding the phone, deciding at 23:30 whether to restart an infusion
that caused rigors.

**h. Credentials get shared because care is urgent.**
A nurse asked for the MO's EMR login to look something up. He gave it, instantly,
because the alternative was delay. That is not a character flaw — it is what a
badly designed system forces. Every such moment is a data breach waiting to be
discovered by someone who is not friendly.

## 3. Why the existing answers don't answer

- **Paper files** are authoritative and unsearchable. They are also on the ward,
  and you are not.
- **The EMR** is authoritative and unusable at 3 a.m. on a phone, and it does not
  contain the reasoning — only the residue of it.
- **WhatsApp** is fast, universal, multimodal, and deliberately ephemeral. It is
  a chat app doing a medical record's job badly, and it will never be auditable.
- **A "better SBAR template"** is a document. The problem is the stream.

## 4. What shift-buddy-handover must be

**One artefact per shift, produced from the mess that already exists.**

Not a new app to learn. Not another login. A pipeline that eats what the ward
already produces and emits one thing everyone can read, hear, and print.

### Multimodal in — because the ward is multimodal

| Input | Reality on the ward | What we do |
| --- | --- | --- |
| Voice note (opus) | 41 in 16 days; the fastest way to transfer a nuance | Local ASR → transcript with timestamps and speaker |
| Text message | 325 in 16 days; where the decisions actually live | Parse into events: patient, action, owner, deadline |
| Photo of a progress note / MR page | The paper system's only digital form | OCR → structured facts, with confidence |
| Photo of a monitor, EMR screen, requisition | Emergency communication of record data | OCR + numeric extraction, never trusted silently |
| PDF / XLSX | Discharge summaries, pharmacy lists | Text extraction, table-aware |
| The patient's own file (MR number) | The join key | Normalise, never guess, never invent |

### Multimodal out — because the ward reads and hears differently

| Output | Who it is for | Form |
| --- | --- | --- |
| Handover card (PNG) | WhatsApp group, phone screen, print | One page, ward-white, readable at arm's length |
| Voice note | The oncoming MO walking to the ward | Same words, spoken, Urdu/English switch allowed |
| Structured text | WhatsApp, plain and bold-only | `*NAME*` style, no tables, mobile-native |
| Markdown + JSON bundle | Any other platform — Telegram, Slack, EMR import | One zip: `.md`, `.json`, `.png`, `.txt` |
| Printable A4 | The physical file the hospital actually keeps | PDF, one page per patient |

**The bundle is the contract.** Any tool that can read a zip can consume a
handover. That is what "shareable across multiple platforms" has to mean if it is
going to survive contact with a real department.

## 5. Non-negotiables

1. **No invented numbers.** Every figure in the prose must exist in the extracted
   facts. The verifier fails the run if a dose, a count, or a date is not in the
   source. An LLM asked to smooth over a gap will smooth over a dose.
2. **Every sentence carries provenance.** Click, and you get the message
   timestamp, the voice note, or the photo it came from.
3. **Deletion is not a feature.** Overs are append-only. A correction is a new
   entry, never an edit.
4. **Owners and deadlines are explicit.** "Pending" without a name and a clock is
   the failure mode we are eliminating.
5. **Offline-first.** A ward with no signal is the normal case. Model runs local;
   nothing patient-identifying leaves the machine.
6. **Human confirms, machine drafts.** The MO signs. The tool never files an
   order, never messages a family, never speaks for a doctor.

## 6. What success looks like

Measured on real shifts, not on vibes:

- **Time to a complete over:** under 10 minutes, from "Over?" to signed card.
- **Missed-order rate:** zero critical orders that were in the source and absent
  from the over.
- **Re-question rate:** the oncoming doctor asks fewer than 3 clarifying
  questions per patient, down from the current norm of a dozen.
- **Night-time escalation:** every 2 a.m. decision has a named owner and a
  written plan before 12 p.m.
- **A handover that survives a week:** someone can reconstruct *why* an order was
  given, after the people who gave it have rotated out.

## 7. What it must never become

- A chatbot that answers clinical questions. It organises; it does not practise.
- A replacement for the EMR or the paper file. It is the bridge between them.
- A surveillance tool. The audit trail protects the doctor, it does not grade him.
- Another place to write things down that nobody reads.

## 8. The one sentence

> **A shift ends; the care does not. This exists so that nothing a doctor knew at
> 8 a.m. is lost by 8 p.m. — not the dose, not the deadline, not the reason.**
