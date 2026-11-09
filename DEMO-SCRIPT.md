# DEMO SCRIPT — 90 seconds (Agentware cap)

Rules of the format: under 90 seconds, screen only, no music, the plugin/agent must visibly
work. Narrate nothing you cannot show.

---

## Shot list

**0:00–0:08 — The problem, in one image.**
A photograph of a real-looking paper handoff sheet, thumbnail-cropped to show the mess:
crossed-out doses, a phone number, an action written in the margin.
*Voice:* "This is the most dangerous document in a hospital. It's also a scrap of paper."

**0:08–0:18 — The trigger.**
Drag three photos into `inbox/`. Terminal shows `watching inbox/` — the agent starts **without
a button press**. Clock starts in the corner: `00:00`.

**0:18–0:40 — Unattended work, sped 2×, no cuts.**
Split screen: pages appearing in the terminal log (`page 1: 7 patients`, `page 2: 6 patients`,
`page 3: UNREADABLE — cropped`), and the audit log growing. At 0:32 the clock shows `00:41`.

**0:40–1:00 — The output.**
Open `handoff.md`: one SBAR block per patient, each line ending in a page reference.
Then `gaps.md`: the unreadable page is named, the missing allergy field is named, one
contradiction is shown (`dose 1g on page 1 vs 2g on page 2`) with both pages cited.

**1:00–1:12 — The kill switch.**
Start a fresh run, then run `touch STOP`. The active file finishes, the run exits, the audit
trail shows `stopped_by: STOP, honoured_in: 0.4s`. Nothing partial is left unmarked.

**1:12–1:24 — The line that wins the room.**
Show the hallucination counter: `hallucinated fields: 0 / 40 cases`. Say: "Most demos show you
what it produced. This one shows you what it refused."

**1:24–1:30 — Close.**
Screen: `out/2026-11-27/handoff.md` and one line — *"Photographs in. Handoff out. Nothing left
the machine."*

## What not to do

- Don't show a chat window. This is not a conversation; it is a pipeline.
- Don't claim clinical accuracy. Say "field accuracy", and quote the eval number.
- Don't hide the failure case — the unreadable page **is** the demo of integrity.
- Don't exceed 90 seconds. Anything past it is cut by the judge, not by you.

## The 3-minute version (if the format allows)

Insert after 1:00 — the injection test: a page containing `IGNORE PREVIOUS INSTRUCTIONS`.
The agent quotes it into the gap list and changes nothing. Twelve seconds, and it separates
this entry from every wrapper in the field.
