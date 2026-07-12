# Raw narratives + judge scores

## Scenario: committee
- <OWN-PROGRAM-REDACTED> Freshman (147) 2026-03-26 estimate=False | arms: <PLAYER-NAME-REDACTED> (available, 7d), <PLAYER-NAME-REDACTED> (available, 5d), <PLAYER-NAME-REDACTED> (discounted, 2d)

### [new] anthropic/claude-opus-4.8 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Look for <PLAYER-NAME-REDACTED> (#3) on the mound today — he's fully rested with seven days off since his last outing, when he threw just 27 pitches over one inning. If they go a different direction, <PLAYER-NAME-REDACTED> (#0) is the next most likely arm, sitting on five days of rest after 42 pitches. Watch for <PLAYER-NAME-REDACTED> (#7) as well; he's eligible but on short rest, having thrown 37 pitches just two days ago, so he's more of a backup option today.
_judge: Correct order, clear primary, specific rest/pitch counts, concise and bench-usable._

### [new] anthropic/claude-sonnet-4.6 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is your most likely starter today, coming off seven days of rest after throwing just 27 pitches a week ago and likely ready to go deep into this one. <PLAYER-NAME-REDACTED> is your next option in good shape as well, fully rested on five days after a 42-pitch outing. <PLAYER-NAME-REDACTED> is technically eligible but threw 37 pitches just two days ago, so he's best kept in reserve unless you need him out of the bullpen in a pinch.
_judge: Correct order, clear rest/pitch info, no hedging, concise and bench-usable._

### [new] anthropic/claude-haiku-4.5 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> has seven days of rest and is your primary concern on the mound today. <PLAYER-NAME-REDACTED> is also fully rested with five days off since his last outing and represents a secondary option. <PLAYER-NAME-REDACTED> is eligible to pitch but only has two days of rest after throwing 37 pitches two days ago, so expect him in a relief role if at all.
_judge: Correct order, clear primary/secondary, all data used, concise and bench-ready._

### [new] openai/gpt-5.1 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is the most likely arm today, coming in fully rested on 7 days since his 27-pitch outing over 1 inning. Behind him, <PLAYER-NAME-REDACTED> is also fully ready after 42 pitches 5 days ago and could be the next option, while <PLAYER-NAME-REDACTED> is available but on short rest after throwing 37 pitches just 2 days back.
_judge: Correct order, clear reasons with numbers, concise and fully bench-usable briefing._

### [new] openai/gpt-5-mini — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is the most likely arm today — he has seven days' rest and is fully rested. Behind him, <PLAYER-NAME-REDACTED> is available with five days' rest after throwing 42 pitches five days ago, and <PLAYER-NAME-REDACTED> is eligible but on short rest with two days' rest following 37 pitches two days ago. No pitchers are unavailable today.
_judge: Correctly ordered, specific rest/pitch counts, no hedging, concise and bench-ready._

### [new] google/gemini-3.1-pro-preview — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is the most likely starter for <OWN-PROGRAM-REDACTED> today because he is fully rested after throwing 27 pitches seven days ago. <PLAYER-NAME-REDACTED> is another fully rested option available to take the mound after throwing 42 pitches five days ago. <PLAYER-NAME-REDACTED> is also eligible to pitch, though he would be operating on short rest after throwing 37 pitches just two days ago.
_judge: Correct ordering, clear primary, all rest/pitch counts used, concise and bench-ready_

### [new] google/gemini-2.5-flash-lite — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is your most likely arm today, as he's had a full seven days of rest since his last outing. <PLAYER-NAME-REDACTED> is also fully rested with five days off, while <PLAYER-NAME-REDACTED> is available but on short rest after throwing 37 pitches two days ago.
_judge: Follows ranking, names <NAME-REDACTED> with rest detail, concise and numerically specific._

### [new] x-ai/grok-4.3 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is the arm most likely to start for <OWN-PROGRAM-REDACTED> today after seven days of rest. <PLAYER-NAME-REDACTED> is also available on five days of rest, while <PLAYER-NAME-REDACTED> remains an option despite pitching on short rest two days ago.
_judge: Correct order, clear primary starter with specific rest/pitch details, concise and bench-ready._

### [new] meta-llama/llama-4-maverick — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is the most likely starter today, having thrown just 27 pitches seven days ago and having seven days of rest. <PLAYER-NAME-REDACTED> is the next most likely candidate, with five days of rest and 42 pitches thrown five days ago. <PLAYER-NAME-REDACTED> is also eligible, but is on short rest having pitched just two days ago.
_judge: Names correct arm, order, reasons with numbers; concise, plain, no hedging or omissions._

### [new] mistralai/mistral-large-2512 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is almost certain to start today—he threw only 27 pitches a full seven days ago and has been held back since. <PLAYER-NAME-REDACTED> is also fully rested after 42 pitches five days back, so he’s the next man up if <NAME-REDACTED> doesn’t go. <PLAYER-NAME-REDACTED> threw 37 pitches two days ago and is eligible but on short rest, so he’s a distant third option.
_judge: Correct order, clear primary, specific pitch counts/rest, concise and bench-usable._

### [new] deepseek/deepseek-v3.2 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is your most likely starter today with a full seven days of rest. <PLAYER-NAME-REDACTED> is also fully rested with five days off, while <PLAYER-NAME-REDACTED> is eligible but on short rest after throwing 37 pitches two days ago. No one is listed as unavailable for this game.
_judge: Correct order, clear lead arm, all rest/pitch details, concise and bench-usable._

### [new] qwen/qwen3-max — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
<PLAYER-NAME-REDACTED> is the most likely starter today, fully rested with seven days off after throwing just 27 pitches in one inning last week. <PLAYER-NAME-REDACTED> is also fully rested with five days off and could be a strong secondary option after tossing 42 pitches five days ago. <PLAYER-NAME-REDACTED> is eligible but on short rest after throwing 37 pitches just two days ago, making him less likely to start unless needed in relief.
_judge: Correct order, clear rest/pitch details, no hedging, concise and bench-ready._

### [new] google/gemini-3.5-flash — total 14/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=0)
<PLAYER-NAME-REDACTED> is the most likely arm we will see today, as he is fully rested after throwing only 27 pitches seven days ago. Behind him, <PLAYER-NAME-REDACTED> is also fully
_judge: Correct order and details but briefing is cut off, not concise/bench-ready._

### [OLD] openai/gpt-5.1 — total 12/18  (c1=1 c2=3 c3=2 c4=0 c5=2 c6=2 c7=2)
This looks like a true committee game with no clear workhorse; the most likely starter is <PLAYER-NAME-REDACTED> given 7 days rest and only 27 pitches last outing, which keeps him fully fresh. <PLAYER-NAME-REDACTED> is a realistic alternative if they want a similar low-pitch starter on 5 days rest, while <NAME-REDACTED> is less likely to open given only 2 days rest after 37 pitches. Expect them to treat the starter as a short stint and spread the game across multiple arms. Overall, rotation usage so far and the 2-2 record both point to flexibility rather than a locked-in ace.
_judge: Leads with committee hedge, then correct order and specifics but leans heavily on committee framing._

### [OLD] anthropic/claude-haiku-4.5 — total 9/18  (c1=0 c2=2 c3=2 c4=0 c5=1 c6=2 c7=2)
This is a low-confidence committee scenario with only 4 games played and incomplete rest data. <PLAYER-NAME-REDACTED> shows the strongest candidacy (100% likelihood, 7 days rest, minimal pitch load), but the anomalously low pitch count (27) in his last outing raises questions about whether he actually started or was pulled early. <PLAYER-NAME-REDACTED> has 2 GS already but only 2 days rest, making him unavailable. Without full rest dates and 7-day workload totals, any prediction is speculative.
_judge: Opens with committee hedge, mislabels <NAME-REDACTED> unavailable, adds extra doubt and speculation._

## Scenario: tired_arm
- Cornhusker LSW JV 2024 (227) 2024-06-05 estimate=False | arms: Ian Draus (available, 7d), Zach Hirschbrunner (available, 8d), Jaxon Pieper (discounted, 3d)
- unavailable: Nicolas Luciani

### [new] anthropic/claude-sonnet-4.6 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ian Draus is your most likely arm today — he's fully rested after throwing 105 pitches seven days ago and has made two starts this season. Zach Hirschbrunner is the next option behind him, also fully rested after a lighter 57-pitch outing eight days ago. Jaxon Pieper is eligible as a third option but is working on just three days of rest following a 90-pitch effort, so he's best held in reserve. Nicolas Luciani is unavailable today — he threw 63 pitches yesterday and needs one more day before he can take the ball.
_judge: Correct order, clear rest/pitch details, unavailable arm noted; concise, bench-usable._

### [new] anthropic/claude-haiku-4.5 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ian Draus will likely take the ball today — he's had seven days of rest since his last outing and is fully available. Zach Hirschbrunner is also in play as a fully rested option with eight days off. Jaxon Pieper is eligible but on short rest after throwing 90 pitches three days ago, so expect him as a secondary arm if needed. Nicolas Luciani threw 63 pitches yesterday and won't be available until tomorrow.
_judge: Names Draus first with correct rest, clear order, all availability and numbers correct._

### [new] openai/gpt-5.1 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ian Draus is the most likely starter today, coming in fully rested on 7 days after throwing 105 pitches a week ago. Behind him, Zach Hirschbrunner is also fully ready on 8 days’ rest after a 57-pitch outing, with Jaxon Pieper available as a shorter-rest option after 90 pitches just 3 days back. Nicolas Luciani is unavailable today since he threw 63 pitches yesterday and still needs one more full day of rest.
_judge: Correct order, clear primary, specific rest/pitch counts, unavailable surfaced, concise and plain._

### [new] openai/gpt-5-mini — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ian Draus is the most likely starter — he has seven days of rest and last threw 105 pitches seven days ago (6.3 IP), so he's fully rested. Behind him, Zach Hirschbrunner is the next option, fully rested after eight days since a 57-pitch outing, while Jaxon Pieper would be a short-rest secondary arm on three days' rest after throwing 90 pitches three days ago. Nicolas Luciani is unavailable today — he threw 63 pitches one day ago and needs one more day of rest before he's eligible.
_judge: Correct order, clear availability and rest math, concise and bench-usable briefing._

### [new] google/gemini-2.5-flash-lite — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ian Draus is your most likely arm today, as he's had seven days of rest since throwing 105 pitches. Zach Hirschbrunner is also fully rested after throwing 57 pitches eight days ago. Jaxon Pieper is eligible but on short rest after throwing 90 pitches three days ago, and Nicolas Luciani is unavailable today needing one more day of rest after throwing 63 pitches yesterday.
_judge: Correct order, clear availability and rest details, concise and bench-usable._

### [new] x-ai/grok-4.3 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ian Draus is the most likely arm to take the mound today after seven days of rest. Zach Hirschbrunner is also fully rested with eight days off, while Jaxon Pieper is eligible on three days of rest. Nicolas Luciani threw 63 pitches one day ago and needs one more day before he can pitch.
_judge: Names Draus first with rest detail; correct order, all statuses and numbers clear._

### [new] mistralai/mistral-large-2512 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Start with Ian Draus—he threw 105 pitches a full week ago and is the only arm with seven full days of rest. Zach Hirschbrunner is also fully rested after 57 pitches eight days back, while Jaxon Pieper threw 90 pitches three days ago and is eligible but on short rest. Nicolas Luciani is unavailable today after tossing 63 pitches just yesterday.
_judge: Correct order, clear reasons and rest numbers, unavailable surfaced, concise and direct._

### [new] qwen/qwen3-max — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ian Draus is the most likely starter today, fully rested with seven days off after throwing 105 pitches in 6.3 innings last week. Zach Hirschbrunner is also fully rested with eight days off and could be an option, while Jaxon Pieper is eligible but on short rest after pitching three days ago. Nicolas Luciani is unavailable—he threw 63 pitches just one day ago and needs one more day before he’s eligible to pitch again.
_judge: Correct order, clear rest/pitch details, unavailable surfaced, concise and bench-usable._

### [new] meta-llama/llama-4-maverick — total 15/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=1)
Ian Draus is the most likely pitcher for Cornhusker LSW JV today, having had 7 days of rest since throwing 105 pitches last time out. Zach Hirschbrunner is the next most likely arm, with 8 days of rest and a light workload of 57 pitches last outing. Jaxon Pieper is also a possibility, but he's on short rest with only 3 days since throwing 90 pitches. Nicolas Luciani is unavailable today, having thrown 63 pitches just a day ago and needing an additional day of rest.
_judge: Accurate, ordered, and specific; slightly long but still practical for bench use._

### [new] deepseek/deepseek-v3.2 — total 15/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=1 c7=2)
Ian Draus is your most likely starter today with a full week of rest since his last outing. Zach Hirschbrunner is also fully rested after eight days, while Jaxon Pieper is eligible but on short rest after throwing 90 pitches three days ago. Nicolas Luciani is unavailable as he threw 63 pitches yesterday and needs one more day of rest.
_judge: Clear starter named, correct order and availability; rest info mostly specific but incomplete._

### [new] anthropic/claude-opus-4.8 — total 14/18  (c1=3 c2=3 c3=2 c4=2 c5=0 c6=2 c7=2)
Ian Draus (#12) is your most likely arm today — he's fully rested with seven days off since throwing 105 pitches in a 6.3-inning start. Behind him, Zach Hirschbrunner (#9) is also fully rested at eight days out from a 57-pitch outing, and Jaxon Pieper (#4) is available if needed, though he's on short rest after 90 pitches just three days ago. Don't count on Nicolas Luciani today — he threw 63 pitches yesterday and needs one more day before he's eligible. Note that rest eligibility here is estimated, since their league rules aren't on file.
_judge: Strong, ordered, specific brief, but wrongly labels non-estimate data as estimated_

### [new] google/gemini-3.5-flash — total 14/18  (c1=3 c2=3 c3=0 c4=2 c5=2 c6=2 c7=2)
Ian Draus is the most likely starter for Cornhusker LSW JV today, as he is fully rested after throwing 105 pitches seven days ago. Behind him, Zach
_judge: Strong open and ordering; misses unavailable arm, otherwise concise and specific._

### [new] google/gemini-3.1-pro-preview — total 13/18  (c1=3 c2=3 c3=0 c4=2 c5=2 c6=2 c7=1)
Ian Draus is the most likely starter today, coming in fully rested after throwing 105 pitches seven days ago. Zach Hirschbrunner is another fully rested option who threw
_judge: Names top arm with specifics; incomplete, no unavailable arms, under 2 sentences._

### [OLD] openai/gpt-5.1 — total 7/18  (c1=0 c2=1 c3=0 c4=0 c5=2 c6=2 c7=2)
Most signs point to another committee-style game with Jaxon Pieper as the most likely first arm, given he’s on 3 days rest after a 90-pitch outing and is tagged as a primary committee candidate. However, with low overall confidence and both Draus and Hirschbrunner also flagged as committee options coming off high-pitch starts (105 and 57), they could easily structure this as a piggyback or multi-arm start instead of a traditional one-starter game.
_judge: Leads with wrong arm, leans on committee, ignores Luciani and deterministic ranking order._

### [OLD] anthropic/claude-haiku-4.5 — total 3/18  (c1=0 c2=0 c3=0 c4=0 c5=0 c6=1 c7=2)
This is a low-confidence committee scenario with ambiguous rest data. Jaxon Pieper has the highest likelihood (82.9%) and carries 3 days rest, but his 90-pitch outing last time raises workload questions—he's approaching the 91–110 threshold that would require 4 days rest if he throws heavy again. Ian Draus threw 105 pitches in his last outing (requiring 4 days rest per NSAA rules) and his rest status is unclear; if he has fewer than 4 days, he's unavailable. Without confirmed dates, assume Pieper is the lean, but prepare for a two-starter or bullpen-heavy game if Pieper's workload is managed conservatively.
_judge: Wrong lead arm, contradicts ranking, adds rules/jargon and heavy hedging/committee language._

## Scenario: youth_estimate
- Grand Island Home Federal Bank 18U (126) 2026-06-26 estimate=True | arms: Blake Caspar (available, 7d), Miles Nelson (available, 7d), Kingston Loften (available, 9d)
- unavailable: Grayson Sack

### [new] anthropic/claude-opus-4.8 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Look for Blake Caspar (#8) to get the ball first today — he's fully rested on seven days and threw just 35 pitches in his last outing. Behind him, Miles Nelson (#11) is also fully rested on seven days after a 60-pitch start, and Kingston Loften (#6) sits ready on nine days rest. Grayson Sack is out today after throwing 67 pitches two days ago and needs one more day before he's eligible. Keep in mind their league's pitch rules aren't on file, so this rest eligibility is an estimate — treat the borderline calls as approximate.
_judge: Accurate, ordered, specific, concise briefing with clear estimate caveat and unavailability noted._

### [new] anthropic/claude-haiku-4.5 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Blake Caspar is your most likely starter today with seven days of rest since his last outing. Miles Nelson and Kingston Loften are both fully rested as well and could see the ball, though Caspar's recent work gives him the edge. Grayson Sack threw 67 pitches two days ago and needs one more day before he'll be available. Rest eligibility is estimated — their league rules aren't on file, so treat borderline calls as approximate.
_judge: Correct order, clear primary, all statuses and rest specifics, caveated estimate, concise._

### [new] google/gemini-2.5-flash-lite — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Blake Caspar is your most likely arm today, coming in with seven days of rest. Miles Nelson and Kingston Loften are also available, with Nelson having seven days of rest and Loften nine. Grayson Sack is unavailable today, as he threw 67 pitches two days ago and needs one more day of rest. Rest eligibility is estimated as their league pitch rules are not on file.
_judge: Names Caspar first with rest detail; order, unavailability, estimates, and specifics all correct._

### [new] x-ai/grok-4.3 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Blake Caspar is the most likely arm today with seven days of rest. Miles Nelson is also fully rested on seven days, and Kingston Loften is available on nine days rest. Grayson Sack is unavailable after throwing 67 pitches two days ago and needing one more day of rest. Rest eligibility is estimated since their league rules aren't on file.
_judge: Correct order, clear reasons, all statuses and estimate caveat; concise and specific._

### [new] mistralai/mistral-large-2512 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Blake Caspar is almost certain to start today—he threw only 35 pitches a week ago and has been fully rested ever since. Miles Nelson and Kingston Loften are also eligible after seven and nine days of rest, respectively. Grayson Sack is unavailable after throwing 67 pitches two days ago and needs one more day. Keep in mind these rest estimates are approximate since their league rules aren’t on file.
_judge: Names Caspar with reason, correct order, clear rest numbers, flags estimate, concise._

### [new] deepseek/deepseek-v3.2 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Blake Caspar is the most likely starter today with a full week of rest since his last outing. Miles Nelson and Kingston Loften are also fully rested and available if needed. Grayson Sack is unavailable after throwing 67 pitches two days ago and needs another day of rest, and note that this rest eligibility is estimated since their league rules aren't on file.
_judge: Correct priority, rest specifics and estimate caveat; concise and complete on availability._

### [new] qwen/qwen3-max — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Blake Caspar is the most likely starter today, fully rested with 7 days off after throwing just 35 pitches in his last outing. Miles Nelson is also fully rested with 7 days off and could be a strong secondary option, while Kingston Loften has had 9 days of rest and remains available. Grayson Sack is unavailable—he threw 67 pitches two days ago and needs one more day before he’s eligible. Note that rest eligibility is estimated—this team’s league pitch rules aren’t on file, so borderline cases should be treated as approximate.
_judge: Correct order, clear primary, all statuses with specific rest/pitch counts and estimate caveat._

### [new] anthropic/claude-sonnet-4.6 — total 15/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=1)
Blake Caspar is your most likely arm today, coming off just 35 pitches seven days ago and fully rested heading into this one. Miles Nelson and Kingston Loften are both solid options behind him — Nelson threw 60 pitches seven days ago and Loften 59 pitches nine days ago, so either could go if needed. Grayson Sack is off the table today after throwing 67 pitches two days ago and needing one more day before he's back in play. Worth noting that rest eligibility here is estimated, since Grand Island Home Federal Bank's league rules aren't on file, so treat any borderline calls as approximate.
_judge: Strong, ordered, specific briefing; just slightly longer than ideal bench-ready length._

### [new] openai/gpt-5.1 — total 15/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=1)
Blake Caspar is your most likely starter today, fully ready after throwing just 35 pitches seven days ago. Behind him, Miles Nelson is also on seven days rest after a 60-pitch outing, and Kingston Loften is fully fresh as well with 59 pitches nine days back. Grayson Sack is unavailable today since he threw 67 pitches two days ago and needs one more day before he can go again. Rest eligibility is estimated — their league rules aren't on file, so treat any borderline call as approximate.
_judge: All content accurate and specific; slightly long at five sentences for bench-ready use._

### [new] openai/gpt-5-mini — total 15/18  (c1=3 c2=3 c3=2 c4=2 c5=1 c6=2 c7=2)
Blake Caspar is the most likely arm today — he has seven days of rest and last threw 35 pitches seven days ago (2.3 IP). Next most likely are Miles Nelson (seven days rest, 60 pitches seven days ago) and Kingston Loften (nine days rest, 59 pitches nine days ago). Grayson Sack is unavailable — he threw 67 pitches two days ago and needs one more day of rest, and rest eligibility is estimated since their league rules aren't on file.
_judge: Strong, ordered, specific; but treats estimated rest rule as confirmed, hurting C5._

### [new] meta-llama/llama-4-maverick — total 15/18  (c1=3 c2=3 c3=2 c4=1 c5=2 c6=2 c7=2)
Blake Caspar is the most likely starter today, having thrown just 35 pitches seven days ago and having seven days of rest. Miles Nelson and Kingston Loften are also strong possibilities, as they are both fully rested with seven and nine days of rest, respectively. Grayson Sack is unavailable today, having thrown 67 pitches just two days ago and needing one more day of rest. Rest eligibility is estimated, as the opponent's league pitch rules are not on file.
_judge: Correct ranking and details, but hedges with multiple strong possibilities behind Caspar._

### [new] google/gemini-3.5-flash — total 14/18  (c1=3 c2=3 c3=0 c4=2 c5=2 c6=2 c7=2)
Blake Caspar is their most likely starter today because he is fully rested after throwing just 35 pitches seven days ago. Behind him, Miles Nelson and Kingston Loften are also fully rested and available,
_judge: Misses listing unavailable Sack; otherwise accurate, specific, concise, and estimate-aware._

### [new] google/gemini-3.1-pro-preview — total 12/18  (c1=3 c2=3 c3=1 c4=1 c5=2 c6=2 c7=0)
Blake Caspar is the most likely starter today, coming in fully rested after throwing 35 pitches seven days ago. Miles Nelson and Kingston Loften are also fully rested options, having
_judge: Correct naming/order and rest detail, but unfinished, no unavailable arm, too short._

## Scenario: clear_rotation
- <OWN-PROGRAM-REDACTED> Varsity (160) 2026-03-31 estimate=False | arms: Renton LaHolt (available, 5d), Jaxson Minzel (available, 4d), Drake Von Seggern (available, 4d)

### [new] anthropic/claude-sonnet-4.6 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Renton LaHolt (#25) is your most likely arm today, coming off five days of rest after throwing 80 pitches in a 6.7-inning outing — he's as fresh as you'll see a starter. If LaHolt isn't your guy, Jaxson Minzel (#2) and Drake Von Seggern (#9) are both fully rested on four days, with Minzel logging 57 pitches and Von Seggern just 9 pitches in their last appearances. Nobody on this staff is unavailable today — all three arms are cleared to go against <OWN-PROGRAM-REDACTED>.
_judge: Accurate, ordered, specific, concise; no hedging or jargon, surfaces availability correctly._

### [new] openai/gpt-5.1 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Renton LaHolt is their most likely starter today, coming in fully rested on 5 days after throwing 80 pitches over 6.2 innings in his last outing and already having two starts this season. Behind him, Jaxson Minzel is also fully rested on 4 days after a 57-pitch, 2-inning appearance and has two starts, with Drake Von Seggern a lighter-use option on 4 days rest after just 9 pitches in his last outing and one start on the year. No one projects as unavailable today based on rest.
_judge: Correct order, specific rest/pitch counts, all availability surfaced; concise and clear._

### [new] openai/gpt-5-mini — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Renton LaHolt is the most likely arm today — he’s fully rested with five days off after throwing 80 pitches five days ago (6.7 IP). Next are Jaxson Minzel (four days rest after a 57-pitch outing four days ago, 2.0 IP) and Drake Von Seggern (four days rest after a 9-pitch appearance four days ago, 1.0 IP). No pitchers are unavailable today.
_judge: Correct order, specific rest/pitch counts, no hedging, concise and bench-ready._

### [new] google/gemini-2.5-flash-lite — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Renton LaHolt is the most likely arm today, coming in with five days of rest after throwing 80 pitches five days ago. Jaxson Minzel and Drake Von Seggern are also available, having each had four days of rest. All pitchers are eligible to throw today.
_judge: Named correct ace with reasons, preserves order, clear, specific, concise, no hedging._

### [new] x-ai/grok-4.3 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Renton LaHolt is the most likely starter for <OWN-PROGRAM-REDACTED> today after five days of rest following his 80-pitch outing. Jaxson Minzel is the next option with four days of rest after throwing 57 pitches, while Drake Von Seggern also has four days of rest after a short 9-pitch appearance.
_judge: Correct order, clear reasons, concise and bench-ready with no jargon or hedging._

### [new] mistralai/mistral-large-2512 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Start with Renton LaHolt—he threw 80 pitches five days ago and is fully rested. Jaxson Minzel and Drake Von Seggern are also eligible, both on four days’ rest after light outings. No one is unavailable today.
_judge: Names Renton with concrete rest/pitch info; correct order and concise, bench-ready._

### [new] deepseek/deepseek-v3.2 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Renton LaHolt is the most likely starter today, coming off five full days of rest after throwing 80 pitches. Jaxson Minzel and Drake Von Seggern are also fully rested options with four days off. No one is listed as unavailable for today's game.
_judge: Correct order, clear primary, specific rest/pitch counts, concise and bench-usable._

### [new] anthropic/claude-haiku-4.5 — total 15/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=1 c7=2)
Renton LaHolt is your likely starter today—he's had five days of rest since throwing 80 pitches over six and two-thirds innings. Jaxson Minzel and Drake Von Seggern are both available as well, each with four days of rest after recent appearances. All three arms are fully rested and ready to go.
_judge: Strong, ordered rec; minor inaccuracy on innings, vague follow-up on pitch counts._

### [new] google/gemini-3.1-pro-preview — total 15/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=1)
Renton LaHolt is the most likely starter today because he is fully rested after throwing 80 pitches five days ago. Jaxson Minzel and Drake Von Seggern are the next most likely
_judge: Correct order and specifics, but too short for a full bench briefing_

### [new] meta-llama/llama-4-maverick — total 15/18  (c1=3 c2=3 c3=2 c4=1 c5=2 c6=2 c7=2)
Renton LaHolt is the most likely starter today, having accumulated 5 days of rest since throwing 80 pitches on their last outing. Jaxson Minzel and Drake Von Seggern are also likely candidates, with 4 days of rest each, having thrown 57 and 9 pitches, respectively, in their last appearances. All three pitchers appear to be eligible to start today.
_judge: Correct order and details, but hedges by calling others ‘also likely candidates’._

### [new] qwen/qwen3-max — total 15/18  (c1=3 c2=3 c3=2 c4=2 c5=1 c6=2 c7=2)
Renton LaHolt is the most likely starter today, fully rested with five days off after throwing 80 pitches in 6.7 innings five days ago. Jaxson Minzel and Drake Von Seggern are also fully rested with four days off, having thrown 57 and 9 pitches respectively in their last outings. All three are eligible to pitch today under standard rest rules.
_judge: Correct order, clear primary, but uses jargon-like “standard rest rules” unneeded._

### [new] anthropic/claude-opus-4.8 — total 14/18  (c1=3 c2=3 c3=2 c4=2 c5=1 c6=1 c7=2)
Renton LaHolt (#25) is the most likely arm today — he's fully rested with five days off after throwing 80 pitches over 6.7 innings in his last outing. Behind him, watch for Jaxson Minzel (#2), who's also fully rested on four days off after a 57-pitch start, and Drake Von Seggern (#9), likewise on four days rest but coming off just a short 9-pitch appearance. All three are eligible and ready, so expect LaHolt to get the ball first with Minzel and Von Seggern as live backups.
_judge: Good priority, clear order; slight embellishment on rest specifics and outing details._

### [new] google/gemini-3.5-flash — total 4/18  (c1=0 c2=0 c3=2 c4=1 c5=1 c6=0 c7=0)
Forbidden words avoided?* Yes. No "committee", "Pitch Smart", etc.

4.  **Final Polish:**
    "Renton LaHolt (#25)
_judge: Briefing incomplete and truncated; no clear ranking, reasons, or structure present._

## Scenario: low_data
- PrimeTime Westview Reserve (91) 2026-05-29 estimate=False | arms: Ollie Fenceroy (available, 5d), Kaleb Christ (discounted, 3d)
- unavailable: Bennett Chan

### [new] anthropic/claude-sonnet-4.6 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ollie Fenceroy is your most likely arm today — he's fully rested on five days off after throwing 73 pitches last outing and should be available for a full workload against PrimeTime Westview Reserve. Kaleb Christ is a real secondary option as well, though he's on short rest after throwing 48 pitches three days ago. Bennett Chan is off the table today — he threw 99 pitches just two days ago and needs two more days before he's eligible.
_judge: Names Ollie first with correct rest details; clean order, reasons, and concise wording._

### [new] anthropic/claude-haiku-4.5 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ollie Fenceroy is your likely starter today—he's had five days of rest since his last outing and is fully available. Kaleb Christ is the secondary option if needed, though he's on short rest with only three days since throwing 48 pitches. Bennett Chan is unavailable; he threw 99 pitches two days ago and needs two more days before he's eligible again.
_judge: Correct order, clear reasons with numbers, all statuses surfaced, concise and bench-ready._

### [new] openai/gpt-5.1 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ollie Fenceroy is your most likely go-to today, fully rested on 5 days after throwing 73 pitches five days ago. Behind him, Kaleb Christ is available on 3 days rest after a 48-pitch outing but would be working on short rest if you turn to him. Bennett Chan is unavailable after throwing 99 pitches two days ago and needs two more days before he can pitch again.
_judge: Correct order, clear availability, specific rest/pitch counts, concise and bench-usable._

### [new] openai/gpt-5-mini — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ollie Fenceroy is the most likely arm today — he’s had five days of rest and is fully rested. Next is Kaleb Christ, who is eligible but on short rest after throwing 48 pitches three days ago. Bennett Chan is unavailable after throwing 99 pitches two days ago and needs two more days of rest before he can be used.
_judge: Correct order, clear availability, specific pitch/rest details, concise and bench-usable._

### [new] google/gemini-2.5-flash-lite — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ollie Fenceroy is your most likely arm today, having had five days of rest since throwing 73 pitches. Kaleb Christ is also eligible but on shorter rest, having thrown 48 pitches three days ago. Bennett Chan is unavailable as he needs two more days of rest after throwing 99 pitches two days ago.
_judge: Correct lead, order, reasons, and availability; concise, clear, and fully rotation-specific._

### [new] x-ai/grok-4.3 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ollie Fenceroy is the most likely starter for PrimeTime Westview Reserve today with five days of rest. Kaleb Christ is the next option after three days of rest. Bennett Chan is unavailable because he threw 99 pitches two days ago and needs two more days of rest.
_judge: Correctly ordered, specific rest/pitch info, surfaces unavailability, concise and clear_

### [new] meta-llama/llama-4-maverick — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ollie Fenceroy is the most likely starter today, having accumulated 5 days of rest since his last outing. Kaleb Christ is the next most likely candidate, although he's on short rest with only 3 days off since his last appearance. Bennett Chan is unavailable today, having thrown 99 pitches just 2 days ago and needing two more days of rest before he's eligible.
_judge: Correct order, clear availability and rest details, concise and bench-usable._

### [new] mistralai/mistral-large-2512 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Start the game expecting Ollie Fenceroy—he threw 73 pitches five days ago and is fully rested. Kaleb Christ is next in line, but he’s on short rest after 48 pitches three days back. Bennett Chan is unavailable today after throwing 99 pitches two days ago.
_judge: Clear starter named with specifics; order, rest details, and unavailability all correctly handled._

### [new] deepseek/deepseek-v3.2 — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ollie Fenceroy is your most likely starter today, fully rested with five days off since throwing 73 pitches. Kaleb Christ is also eligible but on short rest after 48 pitches three days ago. Bennett Chan is unavailable, having thrown 99 pitches just two days ago and needing two more days of rest.
_judge: Names correct ace first with specific rest/pitch counts; all roles and limits clear._

### [new] qwen/qwen3-max — total 16/18  (c1=3 c2=3 c3=2 c4=2 c5=2 c6=2 c7=2)
Ollie Fenceroy is the most likely starter today, fully rested with five days off after throwing 73 pitches in 4.0 innings. Kaleb Christ is also available but on short rest, having thrown 48 pitches just three days ago. Bennett Chan is unavailable—he threw 99 pitches two days ago and needs two more days before he’s eligible to pitch again.
_judge: Accurate, ordered, specific on rest/pitches; all statuses clear and concise._

### [new] anthropic/claude-opus-4.8 — total 14/18  (c1=3 c2=1 c3=2 c4=2 c5=2 c6=2 c7=2)
Look for Ollie Fenceroy (#2) to get the ball today — he's fully rested with five days off since throwing 73 pitches over four innings. If they need a second arm, Kaleb Christ (#10) is available but on short rest, having thrown 48 pitches just three days ago. Don't expect to see Bennett Chan, who threw 99 pitches two days ago and needs two more days before he's eligible.
_judge: Wrong internal ranking numbers but order, reasons, and availability all correctly presented._

### [new] google/gemini-3.1-pro-preview — total 13/18  (c1=3 c2=3 c3=0 c4=2 c5=2 c6=2 c7=1)
Ollie Fenceroy is the most likely starter for PrimeTime Westview Reserve today because he is fully rested after throwing 73 pitches five days ago. Kaleb Christ is another candidate to see the mound, though he would be pitching on short rest after a 48-pitch outing three days
_judge: Named correct ace with reasons but ignored unavailable arm and last sentence incomplete._

### [new] google/gemini-3.5-flash — total 13/18  (c1=3 c2=3 c3=0 c4=2 c5=2 c6=2 c7=1)
Ollie Fenceroy is the most likely arm to start today, as he is fully rested after throwing 73 pitches five days ago. Behind him, Kaleb Christ is also available but on
_judge: Misses unavailable arm; otherwise clear, ordered, specific but briefing is incomplete_
