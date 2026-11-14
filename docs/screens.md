# Plainplan screens (agreed 14 Nov, 20:40)

Mobile first (390px). No login, no fake account. The first visit opens straight into the demo family.

## Header (every page)
Left: Plainplan logo. Right: household name + badge, e.g. "The Parkers · Demo", and a button "Start my own family".
Footer on every page: disclaimer. Settings link: "Delete my family data".

## Home = the family
1. Big primary button **Something happened?** (top, always visible).
2. Ask box **Ask about your family's policies** (scope = whole household).
3. Tiles: one per member (nickname, role, icons of their policies) + one **Shared** tile (house, car, anything jointly owned).
4. **Next 90 days**: renewals, premium due dates, Jan 1 dental max reset; "Your family pays $X/month"; **Add all to calendar (.ics)**.
5. Blocks **For judges** and **How it works** (AI reads your policy -> our code checks every quote -> no quote, no answer).

## Member page (/member/{id}) and Shared page (/shared)
- Policy cards (type icon, insurer, ends on, verified count).
- Card **+ Add policy**: upload PDF, pick type (health | dental | auto | home); the policy is attached to this member (or Shared).
  Upload note: "We read your PDF once, keep the text to quote it, and delete the file. Don't upload ID cards."
- Ask box **Ask about {nickname}'s policies** (scope = this member's policies; on Shared = shared policies).

## Policy page (/policy/{id})
- Insurer, type, period, policy number masked to last 4 (••••4821), claims phone (tel: button).
- 4-7 key fields. Each: value + ✓ verified with "p. N" that opens the quoted line; or "Not found — enter manually"; edited fields show "Entered by you".
- Ask box **Ask about this policy** (scope = this policy).

## Answer (HTMX partial, same for all three scopes)
Status pill **Covered / Not covered / Not clear from your documents**, 1-3 plain sentences, 1-3 quotes "Policy · p. N · "…"".
No verified quote -> "I couldn't find this in your documents. Call {insurer}: {phone}."

## Something happened? (/situation) — separate from Ask
- Input "What happened?" e.g. "Someone rear-ended our car and Dad's neck hurts".
- Red flags -> banner "If anyone is hurt or in danger, call 911 first."
- Which policies apply: routing table by situation type; shared auto/home + health/dental of the member named in the text.
  If someone is hurt and no member is named -> ask "Who was hurt?" with member buttons.
- Per policy: 2-4 steps, each with a verified quote; claims phone; "Add deadline" (.ics) if the quote has a deadline.
- "General checklist (not from your policy)".

## Start my own family (/start)
Creates an empty household for this guest: add members (nickname + role only), Shared tile exists by default. Then + Add policy.

## Paywall
Triggers on the 4th question/situation or the 3rd own policy. "Plainplan Family — $59/year", features, Stripe test checkout, hint "Test card 4242 4242 4242 4242". On return the user lands where they were, unlocked.

## Demo path for judges
Open link -> Parkers -> Ava -> "Are Ava's braces covered?" -> a question not in the policy (honest refusal) -> Something happened? "rear-ended, Dad's neck hurts" -> 4th question -> paywall -> 4242 -> upload own PDF via + Add policy.

## P1 (only if time): spent/remaining tracker ("Based on amounts you logged"), emergency card (revocable link, numbers last 4).
