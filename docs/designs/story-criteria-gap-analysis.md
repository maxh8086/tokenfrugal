# Story prompts vs platform criteria: gap analysis

* **Status:** analysis only. No prompt or runner change has been made, and nothing has been re-run.
* **Date:** 2026-11-04
* **Related:** [story-model-test-plan.md](story-model-test-plan.md) (section 4 rubric), `Benchmark/story-test/run_stories.py` (prompts)

## 1. Question

Were the story prompts designed to meet the platform criteria (YouTube Shorts, Instagram and FB Reels, LinkedIn, long-form), and if not, what must change?

## 1a. Platform criteria (source, pasted 2026-11-04)

| Platform | Story (script and narrative) | Video (editing and execution) |
|---|---|---|
| **YouTube Shorts** | The "impossible" hook: open at the climax with a bizarre or high-stakes paradox. Hyper-niche mashups: surreal, highly specific crossovers (e.g. Cyberpunk Rome). Aggressive pacing: short sentences that demand constant visual progression. Infinite loop: the final sentence connects back to the opening line. | High sensory impact: change the visual every 2 to 3 s, zero static dead air. Extreme audio: high-emotion TTS (panicked, whispering) and heavy SFX on every cut. Kinetic typography: centre-screen, word-by-word bouncing captions. |
| **Instagram and FB Reels** | Shareability first (IG): end by prompting a direct share ("Send this to the friend who..."). Relatable tropes (FB): nostalgia, mythical sightings, "what-if" for an older audience. Pacing: slightly more breathing room than YouTube. | The text hook: massive curiosity-inducing overlay in the first 0 to 1 s for muted scrollers. Trending audio (IG): trending platform audio at 1 to 5% volume under the TTS. Slightly slower cuts (FB): hold AI motion clips 3 to 4 s. |
| **LinkedIn** | B2B pivot: a professional parable, future-of-work simulation, or AI capability showcase. Value-driven insight: a clear business lesson or thought-leadership view. Debate engine: end with a specific professional question that drives comments. | Documentary polish: high-end commercial look, no generic "AI slop". Accessibility first: 85% watch on mute, so clean block captions (not bouncing words). Authoritative tone: calm, confident, documentary TTS, not extreme emotion. |
| **Long-form (5 to 20+ min)** | True three-act structure (setup, conflict, resolution), not just a punchy loop. Deep world-building: lore, character motivation, atmosphere. Tension and release: dialogue valleys and action peaks to prevent fatigue. | Cinematic pacing: hold establishing shots and reactions 5 to 15 s with subtle ambient motion. Strict visual consistency: character and style references so the look does not drift. Thematic audio: continuous emotional score and ambient soundscape instead of constant impact SFX. |

## 2. Answer

No. The prompts were not designed for these criteria. The 180 ratings measure each model's default behaviour under prompts that never ask for a hook, a loop, or short pacing. They are a valid comparison of defaults, but not a test of the criteria. The ranking in [story-ranking-2026-11-04.csv](../../Benchmark/results/story-ranking-2026-11-04.csv) should be treated as provisional until the prompts are updated and the stories re-generated.

## 3. Measured facts

| Item | Value | Source |
|---|---|---|
| Draft length | 232 to 268 words (mean about 250) | `Benchmark/story-test/drafts/topic-*.md` |
| Story pass length | mean 770 words (45 stories) | `outputs/*/topic-*/story.md` |
| Story prompt length ask | 600 to 900 words | `run_stories.py` PROMPTS["story"] |
| Shorts length target | about 150 to 200 words for a 60 s short (inferred, see section 6) | not in the criteria table |

Stories are about 4 to 5 times longer than a Shorts script. The 4-item rubric (hook, concept, pacing, loop) is written for short scripts, so long stories are scored under a rubric they were never asked to meet.

## 4. Cross-check: each pass vs the criteria

Criteria column = the script-side criteria in the pasted table (YouTube Shorts; FB/IG; LinkedIn; long-form).

| Pass | What the prompt asks | Criteria it touches | Gap |
|---|---|---|---|
| **story** | "600 to 900 words. Keep every event in the draft. Output only the story." | None directly | No hook rule. No loop rule. No pacing rule. Length is 4 to 5 times too long for Shorts. "Keep every event" stops the model cutting scope. |
| **critic** | "List the weakest points: plot gaps, choices with no reason, vague detail." | None | Checks plot logic, not the four criteria. Its output feeds anti-ai, so the weak points that matter for the platform are never named. |
| **anti-ai** | Remove the stock-phrase list, "vary sentence length". | Pacing (partly) | "Vary sentence length" pulls against "short, punchy sentences". No cap on length. |
| **humanizer** | "Keep the plot. Output only the final story." | None | Preserves whatever the earlier passes produced, including a long, non-hooky opening. |

## 5. Cross-check: ai-short-style skill vs the criteria

The skill (`.claude/skills/ai-short-style`) describes a cliffhanger narration style. Where it agrees and disagrees with the criteria:

| Topic | ai-short-style | Criteria | Verdict |
|---|---|---|---|
| Hook | Ordinary action, then the surprise ("While cleaning rust... a man discovered...") | Open at the climax with a bizarre or high-stakes paradox | **Conflict.** The skill starts ordinary; the criteria start extreme. |
| Ending | Withhold the payoff, end on a turn or "Part 1" cliffhanger | Final sentence loops back to the opening line; or prompts a share (IG) | **Conflict.** Cliffhanger is not a loop. No loop in the skill. |
| Sentences | Short declarative, one beat per sentence | Short, punchy, one visual every 2 to 3 s | Agrees. |
| Voice | Calm, curious, never shouting | Shorts: high-emotion TTS. LinkedIn: calm, documentary. | Agrees with LinkedIn and long-form; **conflicts with Shorts and FB/IG**. |
| Cuts | Every 2 to 4 s | Shorts 2 to 3 s; FB slower, 3 to 4 s | Agrees with FB; a bit slow for Shorts. |
| Captions | One bold word at a time | Shorts: bouncing word captions. LinkedIn: block captions. | Agrees with Shorts; conflicts with LinkedIn. |
| Concept | Storyteller, realistic setting, a named character | Hyper-niche mashups, surreal crossovers (Shorts); relatable tropes (FB); professional parable (LinkedIn) | Partly. The skill is a single style; the criteria vary by platform. |

Conclusion: the skill is a good fit for one platform (calm narration, short cuts, word captions) but does not carry the hook and loop items. It cannot be used as-is to meet the Shorts criteria.

## 6. Differences to resolve before updating

1. **Target platform.** The rubric in the plan is the YouTube Shorts script rubric (section 4). The table covers four platforms. Recommend: **YouTube Shorts is the primary target** for this test, since the rubric already assumes it. Other platforms become later variants. Needs your confirmation.
2. **Length.** Shorts wants about 150 to 200 words. Recommend 120 to 180 words for the story pass, and drop "keep every event" in favour of "keep the core events". This is a judgement; a 60 s limit is assumed, not in the table.
3. **Hook: skill vs criteria.** The skill opens on an ordinary action. The Shorts criteria open on a paradox at the climax. Recommend the criteria for this test, and keep the skill's style only for the calm-narration variant.
4. **Ending: cliffhanger vs loop.** The rubric rewards a loop (last line echoes the first). The skill rewards a cliffhanger. These can coexist: the last line can be a turn that also echoes the opening. Needs your decision.
5. **Anti-AI vs pacing.** "Vary sentence length" should become "vary rhythm, keep every sentence under about 15 words".

## 7. Proposed prompt changes (draft, not applied)

These are drafts for review. They are not in `run_stories.py`.

**story (v2)**
> Rewrite the draft below as a YouTube Shorts script of 120 to 180 words. Open the first line on the climax or on a bizarre, impossible, or high-stakes paradox. Keep the premise unusual and specific. Use short sentences, one new visual beat per sentence, no sentence over 15 words. End with a final line that echoes the opening line so the video loops. Keep the core events of the draft. Output only the script.

**critic (v2)**
> Score the script below against four items: (1) the first line is a paradox or climax, (2) the premise is unusual and specific, (3) sentences are short and each adds a visual beat, (4) the last line echoes the first. For each item that fails, name it and the line that fails it. Output a numbered list and no rewrite.

**anti-ai (v2)**
> Revise the script using the critique. Remove every phrase in the list below. Keep every sentence under 15 words. Keep the first line and the final line word for word. Output only the revised script.

**humanizer (v2)**
> Make a final pass for natural voice. Keep the first line and the final line word for word. Keep sentences under 15 words. Output only the final script.

The phrase list and the one-phrase-per-line format stay as they are.

## 8. Video-side items (not for this test)

The table's video criteria (visual change every 2 to 3 s, emotional TTS, kinetic captions, music and SFX) belong to the Part 2 rubric in section 4 of the plan, scored on the films. They are noted here only because the ai-short-style skill's calm voice conflicts with the Shorts emotional-TTS item. That conflict is for the film step.

## 9. Next steps (need approval)

1. Confirm the target platform (recommend YouTube Shorts).
2. Confirm the length target (recommend 120 to 180 words) and whether "keep every event" is replaced.
3. Confirm the hook and ending choices in section 6.
4. Approve the v2 prompts (section 7). Then update `run_stories.py` and re-run all 9 models x 5 topics x 4 passes. This is a GPU run and needs your approval under the plan's run rules.
5. Keep the current 180 results as "v1 default prompts", so the two runs can be compared.
