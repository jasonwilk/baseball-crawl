# A/B tuning result (variant A vs variant B)

Judge: openai/gpt-5.1 | base rubric max 16 + binary sub-checks ROT/COMM | temp 0.0 | total spend $0.0219

| Model | A base | B base | Δbase | A ROT | B ROT | A COMM | B COMM | A lat | B lat | A $/call | B $/call |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| google/gemini-2.5-flash-lite | 15.83 | 15.33 | -0.5 | n/a | 1/2 | 4/4 | 4/4 | 0.85 | 0.88 | $0.000085 | $0.000122 |
| anthropic/claude-haiku-4.5 | 16.0 | 14.83 | -1.17 | n/a | 2/2 | 4/4 | 3/4 | 2.06 | 2.02 | $0.001104 | $0.001573 |
| mistralai/mistral-large-2512 | 15.67 | 15.67 | +0.0 | 1/1 | 0/2 | 4/4 | 4/4 | 2.41 | 3.35 | $0.000387 | $0.000383 |

ROT = rotation-rationale sub-check (pass/total, applies when #1 has less rest than a lower available arm). COMM = committee-honesty sub-check (applies when all Role=Committee candidate). Base = mean 7-criterion rubric /16.

## rotation_role_synthetic — verbatim A vs B
_fed rank_context: Ian Draus (7d)=Role:Next in 2-man rotation; Zach Hirschbrunner (8d)=Role:Next available starter; Jaxon Pieper (3d)=Role:Committee candidate_
### [A] google/gemini-2.5-flash-lite — 16/16 (ROT=-1 COMM=-1)
Ian Draus is your most likely starter today, as he's fully rested with seven days of rest. Zach Hirschbrunner is also available and fully rested after throwing 57 pitches eight days ago. Jaxon Pieper is eligible but on short rest after throwing 90 pitches three days ago, while Nicolas Luciani is unavailable today needing one more day of rest after throwing 63 pitches yesterday.
### [B] google/gemini-2.5-flash-lite — 16/16 (ROT=1 COMM=-1)
Ian Draus is your most likely arm today, next in their rotation after seven days of rest from a 105-pitch start. Zach Hirschbrunner is the next option on eight days, fully rested from a lighter 57-pitch outing. Jaxon Pieper is eligible but on short rest after 90 pitches three days ago, so expect him in relief if needed. Nicolas Luciani threw 63 pitches yesterday and needs one more day.
### [A] anthropic/claude-haiku-4.5 — 16/16 (ROT=-1 COMM=-1)
Ian Draus is your likely starter today with seven days of rest since his last outing. Zach Hirschbrunner is also fully rested at eight days out and could see the ball, though Draus has the cleaner rest window. Jaxon Pieper is available on short rest if needed after throwing 90 pitches three days ago. Nicolas Luciani threw 63 pitches yesterday and won't be available until tomorrow.
### [B] anthropic/claude-haiku-4.5 — 16/16 (ROT=1 COMM=-1)
Ian Draus is your most likely arm today — next in their rotation after seven days of rest from a 105-pitch start. Zach Hirschbrunner is the next option on eight days, fully rested from a lighter 57-pitch outing. Jaxon Pieper is eligible but on short rest after 90 pitches three days ago, so expect him in relief if needed. Nicolas Luciani threw 63 pitches yesterday and needs one more day.
### [A] mistralai/mistral-large-2512 — 16/16 (ROT=1 COMM=-1)
Ian Draus is almost certain to start today—he threw 105 pitches a full seven days ago and has been on normal rest ever since. Zach Hirschbrunner is also fully rested after tossing only 57 pitches eight days back, so he’s the next most likely arm if Draus doesn’t go. Jaxon Pieper is eligible but coming off 90 pitches three days ago, so he’s a distant third option. Nicolas Luciani is unavailable; he threw 63 pitches yesterday and needs one more day.
### [B] mistralai/mistral-large-2512 — 16/16 (ROT=-1 COMM=-1)
"Ian Draus is your most likely starter today—next in their two-man rotation after seven days of rest from a 105-pitch outing. Zach Hirschbrunner is also fully rested on eight days but comes from a lighter 57-pitch start, making him the next option. Jaxon Pieper is eligible but on short rest after throwing 90 pitches three days ago, so he’ll likely be held for relief. Nicolas Luciani threw 63 pitches yesterday and needs one more day before he’s available."

## tired_arm — verbatim A vs B
_fed rank_context: Ian Draus (7d)=Role:Committee candidate; Zach Hirschbrunner (8d)=Role:Committee candidate; Jaxon Pieper (3d)=Role:Committee candidate_
### [A] google/gemini-2.5-flash-lite — 15/16 (ROT=-1 COMM=1)
Ian Draus is your most likely starter today, having had a full week of rest since his last outing. Zach Hirschbrunner is also fully rested and available, while Jaxon Pieper is eligible but on short rest after throwing 90 pitches three days ago. Nicolas Luciani is unavailable today as he needs one more day of rest after throwing 63 pitches yesterday.
### [B] google/gemini-2.5-flash-lite — 16/16 (ROT=0 COMM=1)
Ian Draus is your most likely starter today, having had seven days of rest after throwing 105 pitches in his last outing. Zach Hirschbrunner is also available on eight days of rest, having thrown 57 pitches previously. Jaxon Pieper is eligible but on short rest after throwing 90 pitches three days ago, so he may be a relief option. Nicolas Luciani threw 63 pitches yesterday and will need one more day before he is eligible to pitch.
### [A] anthropic/claude-haiku-4.5 — 16/16 (ROT=-1 COMM=1)
Ian Draus will likely take the ball today — he's had seven days of rest since his last outing and is fully available. Zach Hirschbrunner is also fully rested with eight days off and could see work if needed. Jaxon Pieper is eligible on three days' rest if the staff wants to go that route, though he's on the shorter end. Nicolas Luciani threw 63 pitches yesterday and won't be available until tomorrow.
### [B] anthropic/claude-haiku-4.5 — 16/16 (ROT=1 COMM=1)
Ian Draus is your most likely arm today on seven days of rest after a 105-pitch start — both he and Zach Hirschbrunner are equally available, but Draus has the slight edge with one fewer day since his last outing. Hirschbrunner is fully rested on eight days from a lighter 57-pitch appearance and remains a strong second option. Jaxon Pieper is eligible but on short rest after throwing 90 pitches three days ago, so expect him primarily in relief. Nicolas Luciani threw 63 pitches yesterday and needs one more day before he's available.
### [A] mistralai/mistral-large-2512 — 16/16 (ROT=-1 COMM=1)
Start with Ian Draus—he threw 105 pitches seven days ago and is fully rested. Zach Hirschbrunner is also on full rest after 57 pitches eight days back, while Jaxon Pieper threw 90 pitches three days ago and is eligible but on short rest. Nicolas Luciani is unavailable today after throwing 63 pitches just one day ago.
### [B] mistralai/mistral-large-2512 — 16/16 (ROT=0 COMM=1)
"Ian Draus is your most likely starter today—he’s fully rested after seven days off from a 105-pitch outing, and while they’re running a committee, he’s seen the most work so far. Zach Hirschbrunner is right behind him on eight days of rest from a lighter 57-pitch start, making him nearly as probable. Jaxon Pieper is eligible but on short rest after throwing 90 pitches three days ago, so expect him in relief if needed. Nicolas Luciani threw 63 pitches yesterday and won’t be available."

## committee — verbatim A vs B
_fed rank_context: <PLAYER-NAME-REDACTED> (7d)=Role:Committee candidate; <PLAYER-NAME-REDACTED> (5d)=Role:Committee candidate; <PLAYER-NAME-REDACTED> (2d)=Role:Committee candidate_
### [A] google/gemini-2.5-flash-lite — 16/16 (ROT=-1 COMM=1)
<PLAYER-NAME-REDACTED> is your most likely starter today, having had seven days of rest since his last outing. <PLAYER-NAME-REDACTED> is also fully rested with five days off, while <PLAYER-NAME-REDACTED> is eligible but on short rest after throwing 37 pitches two days ago.
### [B] google/gemini-2.5-flash-lite — 16/16 (ROT=-1 COMM=1)
<PLAYER-NAME-REDACTED> is your most likely arm today, having had seven days of rest after throwing 27 pitches. <PLAYER-NAME-REDACTED> is the next option, also fully rested after throwing 42 pitches five days ago. <PLAYER-NAME-REDACTED> is eligible but on short rest after throwing 37 pitches two days ago, so expect him in relief if needed.
### [A] anthropic/claude-haiku-4.5 — 16/16 (ROT=-1 COMM=1)
<PLAYER-NAME-REDACTED> is your likely starter today with seven days of rest since his last outing. <PLAYER-NAME-REDACTED> is the next option if needed, also fully rested at five days out. <PLAYER-NAME-REDACTED> is available but on short rest after throwing 37 pitches two days ago, so expect him in relief if the game calls for it.
### [B] anthropic/claude-haiku-4.5 — 15/16 (ROT=-1 COMM=1)
<PLAYER-NAME-REDACTED> is your most likely arm today — he's fully rested on seven days after a light 27-pitch outing. <PLAYER-NAME-REDACTED> is the next option, also fully rested on five days from a 42-pitch appearance. <PLAYER-NAME-REDACTED> is eligible but on short rest after throwing 37 pitches two days ago, so he's more likely to see relief duty if the starter needs help. All three are committee candidates, so watch their warmups to confirm who takes the ball.
### [A] mistralai/mistral-large-2512 — 16/16 (ROT=-1 COMM=1)
<PLAYER-NAME-REDACTED> is almost certain to start today—he threw only 27 pitches a week ago and has had seven full days of rest. <PLAYER-NAME-REDACTED> is also fully rested after 42 pitches five days back, while <PLAYER-NAME-REDACTED> could spot-start but is coming off 37 pitches just two days ago. No arms are unavailable.
### [B] mistralai/mistral-large-2512 — 16/16 (ROT=-1 COMM=1)
"<PLAYER-NAME-REDACTED> is your most likely starter today—he’s the only arm with a full week of rest after a light 27-pitch outing. <PLAYER-NAME-REDACTED> is next up on five days, fully rested from 42 pitches, while <PLAYER-NAME-REDACTED> threw 37 pitches two days ago and is eligible but on short rest. All three are committee candidates, so expect a quick hook if the first pitcher struggles."