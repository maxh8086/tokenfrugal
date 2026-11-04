# Story model test: five sample stories

* **Status:** draft for approval. Nothing here has been run. No GPU run starts without your approval.
* **Date:** 2026-11-03
* **Scope:** test whether a model can tell a story that holds up, and whether critic, anti-AI, and humanizer passes improve it. This comes before any story-model code is built.

## 1. Goal

Test the story hypothesis before implementation: a story model drafts, critics and humanizer passes revise, and raters judge the result. The test answers which models are worth building on.

## 2. Inputs

| Item | Value |
|---|---|
| Topics | Five fictional topics, listed in section 2a. |
| Draft | One fixed, AI-sounding draft per topic, written by me. Every model gets the same draft, so the only variable is the model. |
| Models | Nine models: gemma-4-E4B, Qwen3.8-9B-Distill, Qwen3.5-4B Q6_K, nemotron-3-nano-4b, llama3-1-8b, granite4-tiny-h, qwen2.5-7b, ministral-3-8b, granite4-micro. Chosen 2026-11-03. |
| Raters | Haiku and Sonnet, scored separately. Each rater sees the story and the rubric, never the model name. |

## 2a. Topics (fictional, drafted 2026-11-03)

Each topic is invented. No real brand, person, or place is used.

1. **Shared water tank:** during a drought, a rooftop-garden co-op in a coastal city learns a developer has bought the rights to the building's shared water tank.
2. **Seed route:** a freight-drone pilot notices her delivery route is carrying sealed boxes that she was never told about, and the boxes are not on the manifest.
3. **Forecast caller:** a late-night radio host in a small inland town takes calls from a listener who describes tomorrow's weather before it happens.
4. **Inference chain:** a logistics firm's AI planner reasons through three linked steps to reroute a fleet. One assumption in step one is false, and the only person who can see it is the analyst who wrote the original rule.
5. **Unproven lemma:** a retired topologist writes a proof of a knot-invariant result on the back of an envelope. Her former student finds that the whole argument rests on one lemma that was never proved, and the two race to close the gap before a conference talk.

## 3. Passes per story

1. **Story:** the model rewrites the fixed draft as a story.
2. **Critic:** the model lists weak points in its own story.
3. **Anti-AI:** the model removes AI-sounding patterns (stock phrases, even rhythm, hedging).
4. **Humanizer:** the model makes a final pass for natural voice.

Each pass is recorded separately, so the rater can score the draft, the story, and the final output against each other.

## 4. Rubric

The ranking uses the script rubric (Part 1 of the Viral Retention framework, 100 points), scored on the story text only. It was chosen on 2026-11-04 and replaces the earlier five-criterion 1-to-5 rubric. Each rater scores every row out of 100 on four items.

1. **3-second hook (30):** the opening line introduces a bizarre, impossible, or high-stakes paradox, or starts at the climax.
2. **Concept and what-if factor (25):** the premise is a hyper-niche mashup or unusual crossover that forces curiosity.
3. **Narrative pacing (25):** short, punchy sentences that would need a new visual every 2 to 3 seconds, with no dead air.
4. **Loop and call to action (20):** the ending loops back into the opening hook, or it prompts a share.

Destination item 4 (decided 2026-11-04): LinkedIn uses 'Closing question (20): the last line is one specific professional question a reader can answer in a comment, tied to the business lesson.' Long-form uses 'Resolution (20): the ending resolves the central conflict set up in act one.' Shorts, Instagram and Facebook keep the loop/share item above.

Row score = sum of the four items (out of 100). Raters score independently, blind to model name and pass.

Stock-phrase count from the fixed list is recorded beside each score and is not part of it.

Part 2 (video, 100 points) is scored on the rendered films in a later step. Its AI-motion and emotional-TTS items are adapted to the HyperFrames render, because that pipeline has no Runway or Luma motion.

## 5. Output

* One row per (topic, model, pass, rater) in a CSV under `Benchmark/results/`, with columns for the four item scores, the total out of 100, and the stock-phrase count.
* Summary: mean total per model and per pass, with the spread between raters.
* The ranking itself is the mean of the two raters' totals per model, highest first.

## 6. Run rules

* Run one model at a time. Record each run's wall-clock time and whether the GPU was used.
* Stop after the first failed run and report it. Do not skip silently.
* No GPU run starts until you approve the model list and the topic list.
* Destination gate (added 2026-11-04): a full run needs `--destination` to name where the story will be placed (`youtube-shorts`, `instagram-reels`, `facebook-reels`, `linkedin`, `long-form`). The runner refuses to start without it. Each destination has its own story, critic, anti-AI and humanizer prompts, and its own output folder, CSV and failure file. Criteria per destination: [story-criteria-gap-analysis.md](story-criteria-gap-analysis.md) section 10.
* Test length (decided 2026-11-04): each destination targets one minute of narration, 130 to 180 words (2.70 words per second). Real runs take minutes from the user, and words = minutes x 162.

## 7. Done when

* All nine models have finished all five topics across all four passes.
* Both raters have scored every row, and the CSV is committed.
* The summary says which models to build on, and which were rejected and why.

## 8. Open items

1. The five topics: approved 2026-11-03.
2. The nine models: chosen 2026-11-03 (listed in section 2). Dropped from the earlier proposal: Qwen3.5-9B IQ4_XS, qwable-9b, Qwable-9B-Claude-Fable-5. Added: nemotron-3-nano-4b, llama3-1-8b, granite4-tiny-h. Four Gemma/Qwen models remain, so the family rule is not applied to this test.
3. The rubric: section 4, decided 2026-11-03 and changed to the script rubric (100 points) on 2026-11-04. The stock-phrase list is written before the run.
4. Approval to start the GPU run. **Open.**
