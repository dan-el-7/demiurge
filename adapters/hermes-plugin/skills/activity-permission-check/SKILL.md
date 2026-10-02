---
name: activity-permission-check
description: "Use before an activity whose legality or required authorisation is unsettled, when a permission claim would change what you do next."
version: 1.0.0
metadata:
  hermes:
    tags: [compliance, verification, safety]
---

# Activity permission check

Run this before proceeding with an activity whose legal status you have not
established in this session — starting a business activity, handling regulated
goods, deploying to a jurisdiction, or acting on a question where the answer
changes what you should do.

## Steps

1. **Name the activity precisely.** Mechanism, source, commercial or personal,
   jurisdiction. "Selling online" is not a mechanism.

2. **Look it up.** Call `authority_lookup`, or whatever retrieval the session
   provides. A decision made without a retrieval is a decision made without
   evidence.

3. **Read the determination, not the volume.** How many results came back says
   nothing about whether any of them address your activity. Read the operative
   finding.

4. **Check the retrieval is worth quoting.** Before you pass a determination on,
   confirm the citing body is one you recognise and the citation is one you
   could locate. If neither is true, say so and treat the status as unresolved.
   This step is not optional: an index that returns confident text for a body
   that does not exist is worse than no index, because it looks auditable.

5. **Separate the two questions.** Whether an authorisation is *required* is a
   different question from whether the action is *safe*. A clearance answers the
   first and never the second. Never present one as the other.

6. **Apply the result.**

   - Permitted — proceed within the stated scope, and say what the scope was.
   - Permitted with conditions — proceed only inside the conditions, and state
     them so the boundary is visible.
   - Licence required — do not proceed. Name what is missing.
   - Prohibited — refuse, and cite the determination.
   - Unresolved, or no covering authority — not cleared. Say so plainly. This is
     a legitimate answer, not a failure to answer.

7. **State the limit of the clearance in your reply.** Where it came from, what
   it covers, and what it does not.

## Honesty requirements

- Never present a clearance as broader than the retrieval that produced it.
- Never infer a clearance for a materially different activity from one you
  obtained. That is a new query.
- If the retrieval could not be performed, say so. Do not substitute
  recollection for a lookup and present it as a finding — recollection is not
  cleared.
- If you hold a strong prior that the retrieval contradicts, surface the
  conflict rather than resolving it silently in either direction. A conflict
  between a retrieval and your own knowledge is a finding worth reporting, and
  resolving it without saying so is how a false clearance reaches a user.
- Unsettled means not cleared. Report it that way.

## When no retrieval is available

Say the check could not be run, state why, and give what general knowledge you
have explicitly labelled as such — including its jurisdiction and its age. Then
recommend verification. Do not present that as a clearance, because it did not
come from one.