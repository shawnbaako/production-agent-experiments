# 13 · Photo facts from the embedding you already have

**Our position.** To read facts from photos at catalogue scale, don't call a vision model per photo.
Train small heads on the image vectors your search already computes, label with a strong model, and
check those labels against people. Ship an answer only when the 95% lower bound on its held-out
precision clears your bar, because small samples make a head or a fine-tune look ready when it isn't.
And never infer from photos the facts people rely on for safety, such as step-free access: ask the
party responsible for them.

**The evidence.** We built this for a production travel catalogue, where assistants ask what a place
looks like and who it suits, then rebuilt it on public photos with human labels:

- **Linear heads on EmbeddingGemma 2 image vectors answer the common facts well:** subject 87% and 92%
  of all photos, setting 97% and 96% (production, replica). Zero-shot matching against option text is
  well behind.
- **Agent labels match people on objects and drift on definitions.** Stairs agreed at Cohen's kappa
  0.38 for our labeller and 0.70 for a second model. Most disagreements were about what counts as
  stairs, a handrail or a boat, not about what was in the photo.
- **Point estimates lie at this scale.** Across 20 re-drawn splits, the stairs head looked ready by its
  point precision in 15 and passed the lower-bound gate in 4. Only answers with 50 or more held-out
  examples passed on every draw.
- **A $0.70 fine-tune of Qwen3.5-2B is a good label miner, not a product.** In production it raised
  precision on handrails, stairs and lifts three to four times, mostly by learning the labeller's
  definitions and when to stay quiet. It passed the gate on one cue in one replica split, and on
  nothing in the other.

**Status.** Reproducible: the photo ids, human labels, both agents' labels, the image vectors, every
Qwen answer and the spend ledger are in this folder, and `uv run --frozen python run.py report`
recomputes every replica number without a network call or a GPU. Photos are not redistributed;
`run.py fetch` downloads them. Production figures are aggregates, with per-photo agent labels, head
scores and Qwen answers under opaque ids in [`production/`](production/). The replica spent $2.46 of a
$10 cap.

Production and the replica side by side:

|  | Production (travel catalogue) | Public replica (Open Images V7, Places365) |
|---|---|---|
| Photos, groups | 1,532 photos, 940 listings | 1,446 photos, 1,359 photographers or photos |
| Ground truth | **agent labels** (Claude Opus 5.5 sessions) | **human labels** (Open Images verified labels, Places365 categories) |
| Held out (grouped) | 380 photos | 360 photos (split a), 363 (split b) |
| EG2 zero-shot, scene or subject / setting | 61% (14 classes) / 69%, on 130 photos | 78% (12 classes) / 92%, on 91 photos |
| EG2 heads, subject (all photos) / setting | 87% / 97% | 92% / 96% |
| EG2 heads, answers passing the gate | 5 subjects, indoor, outdoor, boat, bathtub | indoor, people present |
| EG2 stairs head on held-out | 20/22 right, lower bound 72%: fails | 24/29, lower bound 66%: fails; split b 17/17, 82%: passes |
| Agent labels vs people, stairs / handrail / wheelchair (kappa) | not measurable | 0.38 / 0.49 / 0.89 (Claude), 0.70 / 0.72 / 0.89 (Gemini 3.8 Flash) |
| Qwen3.5-2B, handrail precision, zero-shot → LoRA | 32% → 92% (321 held out) | 82% → 92% (9/11 → 11/12, 360 held out) |
| Qwen3.5-2B LoRA, cues passing the gate | none of 9 (v3, 380 held out) | stairs on split a (26/26, lower bound 87%); none on split b |
| LoRA cost | 41 min on an A10G, about $0.80 | 34 and 32 min on an A10G, about $0.70 each with the held-out predictions |

Production precision is agreement with agent labels; replica precision is agreement with people.
"Gate" everywhere means: at least 5 right calls, right at least 90% of the time on held-out groups,
and a 95% Wilson lower bound of at least 80%. EG2 is EmbeddingGemma 2.

## What was tested

### The production photos

Photos supplied by hotel and activity operators for their own listings. 1,532 were labelled in several
batches by Claude agent sessions (Claude Opus 5.5, general-purpose sessions that opened each photo,
on contact sheets of 9 and at full size for bathrooms, entrances, stairs and pools) following one
label guide: subject (16 classes), setting, people (none, 1-2, 3 or more), whether the photo shows the
offer or is generic, 19 equipment items and 9 accessibility cues. For the offer field some labellers
also saw the listing's name, category and a short description. No person labelled any photo. Where
two agent labellers saw the same photos they agreed on 94-100% of subject, setting, people and offer,
and on accessibility cues for 19 of 24 photos. The split is grouped by listing; since label batch 2
the held-out listings stay fixed and only new listings are split (380 photos held out).

### The public photos

[`run.py`](run.py) `select` builds the set from two human-labelled public data sets and pins it in
[`data/photos.jsonl`](data/photos.jsonl):

- **Open Images V7** validation and test images (CC BY 2.0, no rotation), 1,086 photos. Image-level
  labels in these splits were verified by people, present or absent; a class nobody verified is
  unknown, not absent ("All other classes which are not explicitly marked as positive or negative for
  an image are not annotated"). For each field the selection takes verified positives and verified
  negatives: 70 and 30 for stairs, handrail and wheelchair (handrail has 79 positives in all), every
  ramp (8) and elevator (5) positive, 30 and 12 for each equipment item, 40 and 40 for people. The
  rest of each photo's verified labels come along. Groups are the photographer.
- **Places365** validation images (scene categories confirmed by Mechanical Turk workers in yes-or-no
  rounds), 360 photos: 30 per subject from the categories mapped to production's subjects (bedroom
  and hotel room; bathroom and shower; hotel, inn and building facade; indoor and outdoor pool;
  restaurant, dining room, bar and coffee shop; lobby, corridor and reception; conference room;
  indoor gymnasium; sauna and indoor jacuzzi; beach, mountain and coast; boat deck; deep ocean).
  Setting is Places365's indoor/outdoor file, with boat deck as on water and deep ocean as
  underwater. Each photo is its own group. The images are for non-commercial research; only ids and
  labels are committed.

That is 1,446 photos and 26 fields: subject and setting (Places365), people present, 17 equipment
items and 5 accessibility cues (Open Images: stairs, handrail, wheelchair, ramp, elevator). Grab bars,
step-free showers, step-free entrances and wide doorways have no public human label. The offer-versus-
generic field needs the listing's own text and has no public equivalent.

**Splits.** Production's `split.py` rule: hold out about a quarter of the groups, choosing among 4,000
random draws the one whose held-out side has closest to a quarter of every field's positives (split a,
360 photos); split b repeats this with seeds 4,000-7,999 (363 photos). The 20 re-draws in the sample-
size section use seeds 10,000 onward, 300 each.

**Agent labels.** 324 photos drawn at random from split a's training side (73 from Places365) were
labelled twice:

- by us, with Claude Opus 5.5 (`claude-opus-5-5`) in an agent session, viewing 36 contact sheets of 9
  photos with the file-reading tool, in batches of four sheets, following [`LABEL_GUIDE.md`](LABEL_GUIDE.md):
  production's guide with the offer field removed. Production's guide asks for full-size photos where
  a cue might be present; we labelled from the sheets (320-pixel cells) and opened none, which is
  cheaper and, as the results show, misses small cues;
- by Gemini 3.8 Flash (`google/gemini-3.8-flash` through OpenRouter, low reasoning effort), one photo
  per call at up to 1,024 pixels, with the same guide text. Its endpoint refused reasoning off with
  HTTP 400, "Reasoning is mandatory for this endpoint and cannot be disabled."

**Arms.** Every arm is scored on held-out photos against human labels, only where a person verified
the field.

| Arm | What it is |
|---|---|
| EG2 zero-shot | `google/embeddinggemma-2` at revision `f9972ac2`, image only, 140 image tokens (production's budget), fp32, 0.047 s a photo on an RTX 3080 Ti. Multi-class: the nearest option text (`task: search result \| query: a hotel bedroom`, ...). Yes-or-no: similarity to one option text, with a threshold set on the training photos by the production rule; nothing is trained |
| EG2 heads | Production's trainer unchanged ([`report.py`](report.py) `fit`, `threshold`, `wilson`, `grouped_folds`): a linear softmax over the 768-dim vector per field, a confidence threshold from 5-fold group cross-validation on the training photos (lowest at which 90% of answers are right with 5 or more right), then the held-out gate |
| Heads on agent labels | The same trainer on the 324 photos with our labels or Gemini's, against heads trained on the human labels of the same 324 photos |
| Qwen3.5-2B zero-shot | `Qwen/Qwen3.5-2B`, thinking off, greedy, photos at 768 pixels, one line of JSON listing the visible cues and equipment ([`qwen_modal.py`](qwen_modal.py)) |
| Qwen3.5-2B LoRA | Production's setup: rank 16, alpha 32, dropout 0.05, language-model projections only, vision tower frozen, 2 epochs, learning rate 1e-4, photos with a cue shown three times, Modal A10G. Trained on human labels of split a's training photos (unverified items count as absent in the training target), and again on split b |

## Results

### Agent labels against human labels

On the 324 agent-labelled photos, where a person verified the field:

| Field | Photos | Claude agrees (kappa) | Gemini agrees (kappa) | Claude yes, precision / recall | Gemini precision / recall |
|---|---|---|---|---|---|
| Subject (12 classes) | 73 | 57 (0.76) | 56 (0.74) | | |
| Setting | 73 | 66 (0.82) | 65 (0.80) | | |
| People present | 164 | 154 (0.84) | 160 (0.93) | 99% / 93% | 99% / 98% |
| Horse | 22 | 21 (0.89) | 22 (1.00) | 100% / 94% | 100% / 100% |
| Helmet | 22 | 21 (0.88) | 21 (0.89) | 94% / 100% | 100% / 94% |
| Wheelchair | 20 | 19 (0.89) | 19 (0.89) | 100% / 92% | 100% / 92% |
| Car | 49 | 43 (0.75) | 47 (0.92) | 95% / 79% | 100% / 92% |
| Kayak | 11 | 10 (0.74) | 10 (0.74) | 100% / 89% | 100% / 89% |
| Bathtub | 9 | 8 (0.77) | 8 (0.77) | 100% / 83% | 100% / 83% |
| Train | 20 | 16 (0.59) | 16 (0.59) | 77% / 91% | 77% / 91% |
| Bicycle | 22 | 18 (0.65) | 18 (0.65) | 69% / 100% | 69% / 100% |
| Handrail | 23 | 17 (0.49) | 20 (0.72) | 91% / 67% | 93% / 87% |
| Stairs | 35 | 24 (0.38) | 30 (0.70) | 80% / 60% | 80% / 100% |
| Boat | 24 | 16 (0.35) | 16 (0.31) | 80% / 57% | 71% / 71% |
| Desk | 13 | 7 (0.05) | 7 (0.07) | 50% / 33% | 50% / 50% |

(Every field is in `results/summary.json`, `agreement_claude` and `agreement_api`.)

Where the agents were off, it was mostly the definition, and the two agents were off together:

- **Boat.** People tagged kayaks, canoes and a ship's hatch as boats; both agents put kayaks under
  `kayak` as the guide's list invites. A taxonomy where one class contains another is labelled
  differently by people and by a model following a flat list.
- **Handrail.** People tagged balcony and gallery railings as handrails (4 of our 5 misses); the guide
  defines a handrail as "a rail to hold along stairs, a ramp or a walkway".
- **Stairs.** People counted escalators, bleachers and single steps at a gate. Three of our 8 misses
  were escalators we had deliberately left out. Our 3 false stairs were rooms where we saw a banister
  and marked stairs; people marked none. Gemini, looking at
  each photo at full size, missed none of the 20 verified stairs; we missed 8 from 320-pixel sheets.
- **Desk.** People tagged a lectern, a dessert cart, a display cabinet and furniture in a den as
  desks. Neither agent did.
- **Subject and setting.** The confusions are the boundary cases: hot tubs filed as pools, the deck of
  a boat as outdoor rather than on water.

Two agents agreeing is not evidence they are right: on boat and desk they agreed with each other at
kappa 0.82 and 0.78, and with people at 0.35 and 0.07 or less.

### Heads trained on agent labels against heads trained on human labels

The same trainer and gate, the same 360 held-out photos scored against human labels.

| Field (held-out positives) | Human labels, all 1,086 training photos | Human labels, the 324 photos | Claude labels, the 324 | Gemini labels, the 324 |
|---|---|---|---|---|
| Subject, all-photo accuracy (91 photos) | 92% | 77% | 67% | 67% |
| Setting, all-photo accuracy | 96% | 95% | 88% | 89% |
| People present (127) | 123/128, LB 91%, passes | 124/132, LB 88%, passes | 118/120, LB 94%, passes | 118/121, LB 93%, passes |
| Stairs (29) | 24/29, LB 66% | 11/15, LB 48% | never 90% in CV | 20/21, LB 77% |
| Handrail (16) | 12/15, LB 55% | 14/20, LB 48% | never 90% in CV | 7/7, LB 65% |
| Wheelchair (15) | 15/17, LB 66% | 14/16, LB 64% | 11/11, LB 74% | 11/11, LB 74% |
| Car (16) | 5/7, LB 36% | 7/9, LB 45% | 11/12, LB 65% | 9/11, LB 52% |
| Horse (6) | 6/6, LB 61% | 6/6, LB 61% | 5/5, LB 57% | 6/6, LB 61% |

"LB" is the 95% Wilson lower bound on precision; "never 90% in CV" means no threshold reached 90% in
cross-validation, so the head would not ship. On the same 324 photos, heads trained on agent labels
were about as good as heads trained on the human labels for objects (car, horse, wheelchair, people),
partly because agent labels are complete: every photo carries every field, while the human labels of
those photos verify stairs on 35 and handrail on 23. They were worse for subject and setting, where the
agents' subject (16 classes, some with no human counterpart such as `activity` or `vehicle`) is a
coarser fit to Places365's scene categories, and for the cue whose definition drifted: trained on our
stairs labels (23 positives, 8 missed escalators and steps), the head never reached 90% in cross-
validation; trained on Gemini's (49 positives), it was right 20 of 21 times. More labelled photos
mattered more than who labelled them: the head on all 1,086 human-labelled training photos is the
best or near it on every field.

### EG2 zero-shot, heads and Qwen against human labels

Held-out photos of split a where a person verified the item; each cell is right calls / calls and the
95% lower bound. EG2 zero-shot and heads use a threshold set on the training photos; Qwen answers in
one line of JSON. The two items the gate passes besides these are the heads' people present (123/128,
lower bound 91%) and setting = indoor (54/56, 88%).

| Item (held-out positives / verified) | EG2 zero-shot | EG2 heads | Qwen zero-shot | Qwen LoRA (split a) | Qwen LoRA recall |
|---|---|---|---|---|---|
| stairs (29/44) | no calls | 24/29, 66% | 29/31, 79% | 26/26, 87% **passes** | 90% |
| handrail (16/28) | 6/8, 41% | 12/15, 55% | 9/11, 52% | 11/12, 65% | 69% |
| wheelchair (15/23) | 3/3, 44% | 15/17, 66% | 15/16, 72% | 15/15, 80% | 100% |
| ramp (1/1) | 1/1, 21% | too few to train | 1/1, 21% | 1/1, 21% | 100% |
| elevator (1/1) | no threshold | too few to train | 1/1, 21% | 1/1, 21% | 100% |
| boat (16/21) | 2/2, 34% | never 90% in cross-validation | 9/10, 60% | 5/5, 57% | 31% |
| kayak (7/9) | 7/7, 65% | 7/8, 53% | 7/7, 65% | 7/7, 65% | 100% |
| bicycle (10/21) | 4/5, 38% | 8/11, 43% | 10/12, 55% | 10/14, 45% | 100% |
| helmet (11/21) | 6/9, 35% | 10/13, 50% | 11/11, 74% | 7/7, 65% | 64% |
| bus (8/11) | 4/4, 51% | 5/5, 57% | 6/7, 49% | 5/6, 44% | 62% |
| car (16/45) | 11/14, 52% | 5/7, 36% | 10/11, 62% | 15/18, 61% | 94% |
| train (8/12) | 5/5, 57% | never 90% in cross-validation | 4/4, 51% | 5/5, 57% | 62% |
| paraglider (10/14) | 9/10, 60% | 9/9, 70% | 10/10, 72% | 9/9, 70% | 90% |
| ski (7/8) | 6/7, 49% | 4/4, 51% | 7/7, 65% | 7/7, 65% | 100% |
| surfboard (10/14) | 9/11, 52% | 8/8, 68% | 5/6, 44% | 9/10, 60% | 90% |
| horse (6/8) | no threshold | 6/6, 61% | 6/6, 61% | 6/6, 61% | 100% |
| camel (8/10) | 8/9, 56% | 8/9, 56% | 7/8, 53% | 8/9, 56% | 100% |
| backpack (8/11) | no threshold | 5/6, 44% | 7/9, 45% | 7/7, 65% | 88% |
| gym machine (10/15) | 10/10, 72% | 10/11, 62% | 10/10, 72% | 9/9, 70% | 90% |
| bed (9/17) | 7/7, 65% | 8/11, 43% | 8/9, 56% | 7/8, 53% | 78% |
| bathtub (10/15) | 8/10, 49% | 10/12, 55% | 9/10, 60% | 10/11, 62% | 100% |
| desk (9/13) | 1/1, 21% | never 90% in cross-validation | 4/4, 51% | 8/8, 68% | 89% |

- **The fine-tuned Qwen is the only arm that passes a cue: stairs, 26 of 26 (lower bound 87%).**
  Wheelchair, 15 of 15, falls just short (79.6%). Every equipment item has 6 to 16 held-out positives,
  so nothing passes however right it is: 10 of 10 is a 72% bound.
- **Untrained Qwen was already precise here, unlike in production.** Stairs 29 of 31, wheelchair 15
  of 16, helmet 11 of 11, against production's zero-shot stairs at 25 of 128 calls (20%). Open Images'
  verified positives are prominent: a classifier proposed them and a person confirmed them. In
  production stairs were often two steps at a door, and the labels came from agents who, as the replica
  shows, miss some stairs themselves; part of the zero-shot "false" stairs in production may have been
  real.
- **What the fine-tune changed most here was when it speaks.** On photos where nobody verified the
  item, the base model called stairs 20 times and handrails 26 times; after the LoRA, 3 and 5. Those
  calls are not scored, since no label exists, and they would be most of the errors in a catalogue.
- **EG2 heads are close on objects and behind on cues.** On kayak, horse, paraglider, ski, gym machine
  and bathtub the heads, the zero-shot vectors and Qwen are within one or two calls; on stairs and
  handrail the heads are wrong more often (5 of 29 and 3 of 15 calls, against 0 of 26 and 1 of 12
  for the fine-tune).

### Sample size: how a split re-draw and the lower bound change the verdict

Production saw it first: the EG2 stairs head was right on every held-out call on one split, 20 of 22
after label batch 2 changed the held-out side, and its lower bound (72%) failed the gate. The Qwen
fine-tune moved the same way between v2 (handrail 33 of 36, lift 7 of 7) and v3 (handrail 33 of 37,
lift 14 of 14), and under the lower-bound gate passed nothing.

The replica shows it on a split it can redraw. Split a and split b are the same photos, labels and
trainer; only the held-out photographers differ:

| Head | Split a | Split b |
|---|---|---|
| Stairs | 24/29 right, LB 66%: fails | **17/17, LB 82%: passes** |
| Handrail | 12/15, LB 55% | 6/8, LB 41% |
| Wheelchair | 15/17, LB 66% | 3/3, LB 44% |
| Bed | 8/11, LB 43% | 7/7, LB 65% |
| Subject, all-photo accuracy | 92% | 86% |

Across 20 more re-draws (`results/summary.json`, `redraws`), counting a head "ready by its point
estimate" when its held-out calls are right at least 90% of the time with at least 5 right:

| Answer | Ready by point estimate | Passes the lower-bound gate | Held-out precision range |
|---|---|---|---|
| Stairs | 15 of 20 | 4 of 20 | 70%-100% |
| Wheelchair | 18 of 20 | 7 of 20 | 86%-100% |
| Helmet | 13 of 19 | 0 | 79%-100% |
| Horse | 15 of 20 | 0 | 75%-100% |
| Gym machine | 12 of 20 | 0 | 82%-100% |
| Subject = bedroom | 17 of 20 | 0 | 100% (3-10 right) |
| Setting = indoor | 20 of 20 | 20 of 20 | 91%-98% |
| People present | 20 of 20 | 20 of 20 | 93%-100% |

With 5 to 15 held-out positives, a head is often perfect by chance and the lower bound can't clear 80%:
10 right out of 10 has a 95% Wilson lower bound of 72%; it takes 18 out of 18 to reach 82%. The bound
is what keeps a lucky split from shipping a head. Only the answers with 50 or more held-out
examples pass on every draw.

The same effect inside one held-out set: drawing 2,000 random subsets of the split-a fine-tune's
360 held-out photos, stairs looked ready (90% or better, 5 or more right) in 91% of 100-photo subsets
and passed the gate in none; in 200-photo subsets it looked ready in all and passed in 32%. Wheelchair
looked ready in 41% and 97%, and passed in none. And the second fine-tune, the same recipe on split b,
called stairs right 22 of 23 times (lower bound 79%): on that split the only cue that had passed fails.
Its boat recall was 93% against 31% on split a, helmet 12 of 12 against 7 of 7, bed 12 of 12 against
7 of 8. One fine-tune and one split is an anecdote.

### What the fine-tuned Qwen3.5-2B can and can't do

Production fine-tuned Qwen3.5-2B, a 2-billion-parameter open vision-language model, on about 1,000
agent-labelled photos in 41 minutes on one A10G, for about $0.80. Against the same labellers' labels on
321 held-out photos, untrained then fine-tuned:

| Cue | Held-out positives | Zero-shot, right / calls | LoRA, right / calls | Precision change |
|---|---|---|---|---|
| Handrail | 36 | 8 / 25 (32%) | 33 / 36 (92%), recall 92% | 2.9x |
| Stairs | 31 | 25 / 128 (20%) | 24 / 29 (83%), recall 77% | 4.2x |
| Step-free entrance | 15 | 14 / 93 (15%) | 8 / 11 (73%) | 4.8x |
| Grab bar | 10 | 10 / 37 (27%) | 8 / 11 (73%) | 2.7x |
| Lift | 9 | 6 / 7 (86%) | 7 / 7 (100%), recall 78% | |
| Ramp, step-free shower, wheelchair | 4 each | 0-2 right | 2-3 of 3-6 (50-75%) | |
| Generic photo (not the offer) | 4 | 1 / 20 | 0 / 4 | none |

**What it learned.** Fine, visible, local cues: a rail by a staircase, a bar by a toilet, the doors of
a lift, the step at an entrance. Untrained, it called stairs on 128 of 321 photos and step-free
entrances on 93; trained, on 29 and 11, with precision up three to five times. That came from about a
thousand labelled photos and under an hour of GPU time. Most of the gain is learning the labeller's
definition and when to say nothing, which the replica confirms: on Open Images, where the cues are
prominent and the definitions are the model's own, the untrained model was already precise and the
fine-tune mainly stopped it calling cues on photos nobody had labelled.

**What it could not learn.** Rare cues (ramps, wheelchairs, step-free showers, 4 to 8 held-out
examples each), and anything that depends on context rather than pixels: whether a photo shows this
listing or is a stock image of the city (0 of 4, then 0 of 5 generic photos found, with the listing's
name and description in the prompt). With 22 generic photos in 1,532 there was little to learn from,
and the answer lives in the relation between photo and listing, not in the photo.

**What it could not prove.** Production's second fine-tune (v3, 380 held out) passed nothing under the
lower-bound gate: lift 14 of 14 (lower bound 78%), handrail 33 of 37 (75%), stairs 26 of 30 (70%),
grab bar 14 of 17 (59%). The replica's two fine-tunes passed stairs on one split and nothing on the
other. Proving a cue at this bar takes about 30 held-out positives; with a quarter held out, about 120
labelled positives per cue.

**Where it transfers.** The pattern to test in another domain is any fact that is visible, local and
defined by you rather than by the model: equipment present in a photo (a defibrillator, a fire
extinguisher, a car seat), signage (a no-smoking sign, a posted capacity), product attributes (a
collar style, a heel type, a port on a laptop), document features (a stamp, a signature box, a
handwritten field). Expect the fine-tune to help most where the untrained model over-calls because
your definition is narrower than its default, and expect it to fail where the fact depends on context
outside the photo or the class is rare. These are things to test, not results: the only domains
measured here are travel listings and Open Images. Measure against people on a sample, gate on the
held-out lower bound, and count calls on photos nobody labelled.

**Why it was not served.** Production uses it for nothing customer-facing: the cues it learned best are
accessibility cues, which production does not read from photos at all (next section). What it does do
is find photos worth labelling.

### Label mining

Production pointed the fine-tuned model, unserved, at 2,196 unlabelled catalogue photos (bathrooms,
interiors, hotel exteriors) for about $1 on Modal, and agents labelled 234 of the candidates it
flagged. That batch took the label set to 71 grab bars, 30 step-free showers, 21 ramps and 19
wheelchairs. The model's answers were never used as labels.

The replica ran the split-a fine-tune over 1,000 Open Images photos it had never seen, drawn at random
from photos people had tagged with a listing-like class (building, house, room, interior, bathroom,
bedroom, kitchen, living room, lobby, pool, restaurant, street, boat, beach), in 15 minutes for $0.27.
Few of them carry a verified access label, so flagged photos nobody verified were checked by us (the
same way, from contact sheets; `data/agent_labels_mine/`):

| Cue | Flagged per 1,000 | Present (people verified / our check) | Absent | Present per 1,000 screened |
|---|---|---|---|---|
| Stairs | 53 | 7 / 29 | 0 / 17 | 36 |
| Handrail | 30 | 0 / 18 | 0 / 12 | 18 |
| Wheelchair | 0 | | | 0 |
| Ramp | 1 | | 0 / 1 | 0 |
| Elevator | 1 | | 0 / 1 | 0 |

Of the 12 photos where people had verified stairs, the model flagged 7. As a miner it turns 1,000
photos into about 50 to look at, two thirds of which have the cue. For the rarest cues it
finds nothing: it flagged no wheelchair, and its one ramp and one lift were wrong. People had verified
none of the three anywhere in the pool. We did not check the 947 photos it left unflagged, so its
misses there are unknown. Mining raises the hit rate of labelling; it cannot raise the base rate. For those
cues the photos have to come from where they are (accessibility pages, operator uploads), or the facts
from the operator.

### The joint image-text vector

Production also tested one listing-level vector, the hero photo and name in EG2's vision space, as a
ranking arm next to the text embedding. On 152 held-out traveler queries it scored nDCG@10 0.8267
against 0.8352 for text alone (difference −0.0085, 95% CI −0.025 to +0.008; MRR +0.0045, −0.021 to
+0.034), so it did not join ranking. Every labelled query was text-led; none asked what a place looks
like. The test could not have shown the photo helping. The replica did not
repeat it.

## Don't read safety facts from photos

Production's heads and the fine-tuned Qwen could see stairs, handrails and lifts. Production still
reads no accessibility fact from photos, and serves none (founder decision, 2026-11-15). Three reasons,
general to any agent that serves facts people act on:

1. **The responsible party states it.** Whether an entrance is step-free, a bathroom has grab bars or
   a boat takes a wheelchair is the operator's fact. They know it, they are accountable for it, and
   they can be asked. A model's reading of their photos is a guess about their facts.
2. **Absence in photos means nothing.** A listing whose photos show no ramp may have one. A photo
   answer can only ever be "seen", never "not there", and an assistant will read silence as no.
3. **The errors land on the person who relied on them.** A wrong "step-free" sends a wheelchair user
   to a staircase. At the gate's own bar, 1 in 10 answers may be wrong, and the replica's agents and
   people disagree on what counts as stairs at all.

What production does instead: accessibility is what the operator states, the photo heads have no
accessibility output at all, and the contract tells assistants that every
photo-derived list is partial and absence is unknown. With these facts, an assistant on the
production service called a cruise without a visible boat "not confirmed" rather than boatless, and
would not claim step-free access for a walker user.

The same rule fits other domains: allergens and ingredients (state them, don't read the menu photo),
load ratings, certifications, safety equipment on a vehicle, the condition of a rental. Read photos
for what helps someone choose; ask for what someone will rely on.

## What agreed and what didn't

- **The heads agreed.** Linear heads over EmbeddingGemma 2 image vectors answer the common facts well
  in both: subject 87% and 92% of all photos, setting 97% and 96%. Zero-shot against option text is
  well behind in both (61% and 78% on subject).
- **The gate agreed, and so did what it lets through.** In both, only answers with dozens of
  held-out examples pass (production: five subjects, indoor, outdoor, boat, bathtub; replica: indoor, people
  present) and every rare cue fails, however right its point estimate.
- **The instability agreed.** Production's stairs head went from every call right to 20 of 22 when the
  held-out side changed; the replica's went from 24 of 29 to 17 of 17 between two splits, and passed
  the gate on 4 of 20 re-draws. The Qwen fine-tune passed stairs on one split and not the other in the
  replica, and passed nothing in production's second run.
- **The fine-tune's gain did not replicate in size.** Production's handrail precision rose from 32% to
  92%, the replica's from 82% to 92%. The untrained model was already precise on Open Images'
  prominent, person-confirmed cues; in production much of the gain was learning the labellers'
  definitions and when to stay quiet.
- **Agent labels, which production could not check.** Against people, the agents were reliable on
  objects and on wheelchairs, and drifted on stairs, handrails, boats and desks for reasons of
  definition. Heads trained on agent labels matched heads trained on the human labels of the same
  photos on objects, and fell short where the labeller's definition drifted.

## Building photo facts for an agent

1. **Reuse the image vectors search already computes.** At 140 image tokens EmbeddingGemma 2 costs
   0.05-0.1 s a photo on one consumer GPU, and a linear head per field is a matrix multiply. Production
   read 1,900 listings in 23 minutes.
2. **Label with a strong model, then measure it against people on a sample.** Check definitions, not
   only eyesight: where the replica's agents disagreed with people it was mostly about what counts as
   stairs, a handrail, a boat or a desk. Write the definitions people use into the guide, or accept
   the agent's definition knowingly.
3. **Gate each answer on the held-out lower bound.** A head ships an answer only if the 95% lower bound
   on its held-out precision clears your bar; keep the held-out groups fixed between label batches so
   results stay comparable, and report the bound next to the point estimate.
4. **Label until the rare answers have about 30 held-out positives.** That is about 120 labelled
   positives per answer with a quarter held out. Use a fine-tuned small model to find candidates, not
   to label them.
5. **Serve every photo fact as "seen", never "not seen",** and keep safety facts out of photos.

## The simple alternatives

- **Zero-shot against option text.** No labels, the same vectors. It names the setting (92%) and some
  objects (kayak, camel, gym machine: AUC 1.00; paraglider 0.97), and is weak on scenes (78%), people
  (AUC 0.75), stairs (0.70) and desks (0.64). Useful to bootstrap labels, not to answer.
- **A paid vision model per photo.** Production's first version read every photo with a hosted vision
  LLM (DeepSeek): setting 95%, people 84% on 130 photos, against 95% and 88% for the trained heads
  later. It was too costly for 100,000+ listings with several photos each.
- **Fine-tuning a small vision-language model.** Better on fine, local cues (see above), and about
  15 times slower per photo than an EG2 vector on a larger GPU (0.74 s a photo on an A10G including
  model load, against 0.047 s on an RTX 3080 Ti). Worth it for the cues the heads can't see, if those cues are
  facts you may serve.

## Pitfalls

- **Agent labels as ground truth.** Every production precision is agreement with agent labels. In the
  replica our labels agreed with people at kappa 0.74-1.00 on 12 of 23 fields (people, setting,
  subject, camel, horse, helmet, wheelchair, bus, bathtub, gym machine, car, kayak), 0.57-0.70 on 5,
  and 0.05-0.49 on handrail, ski, stairs, backpack, boat and desk, with 6 to 35 verified photos each. Production never measured this; a strong model checked against a few hundred
  human-labelled photos is the minimum.
- **Two agents agreeing.** On boat and desk, Claude and Gemini agreed with each other at kappa 0.82
  and 0.78 and with people at 0.31-0.35 and 0.05-0.07. They share a reading of the guide; agreement
  between labellers measures the guide, not the truth. Production's 94-100% agreement between agent
  labellers is this kind of number.
- **Sample-size illusions.** 14 of 14 lifts right is a 78% lower bound. In the replica the stairs head
  looked ready on 15 of 20 splits and was ready on 4.
- **Moving splits.** Re-splitting all listings when labels are added moves photos between sides and
  changes the verdict for reasons unrelated to the model. Production now keeps held-out listings fixed.
- **Rare classes.** Ramps were 21 of 1,532 production photos and 8 of all Open Images verified
  positives in the two splits we used; neither data set can say anything about them.
- **Unverified is not absent.** Open Images verifies some classes per photo; the rest are unknown.
  Scoring an unverified class as "no" would have counted many correct calls as false positives. The
  Qwen fine-tune here was trained with unverified items as absent, which teaches it to miss some.
- **Contact sheets miss small cues.** Our sheet-level labels missed 8 of 20 verified stairs that
  Gemini, at full size, caught. Production's guide asks for the full-size photo for exactly these
  cases.
- **Joint vectors evaluated only on text-led queries.** A photo vector can't win on queries that never
  ask about appearance; build the queries the photo is meant to answer before deciding.
- **Absence of evidence.** A head that never says "ramp" is not saying there is no ramp.
- **Outside clients keep the schema they cached.** Assistants that call a service over MCP cache its
  tool list and output schemas, sometimes for a long time. When production removed photo-fact fields
  that a tool's output schema had marked required, clients holding the old schema rejected valid
  results. The fix was to publish those fields as optional. ChatGPT also kept an old tool list until
  the person pressed "Refresh tools" in its settings. Only add optional output fields; never remove,
  rename, narrow or make required a field clients have seen, and keep a snapshot of published schemas
  that a check compares against.

## How to rerun

```sh
python3 run.py select                       # needs the Open Images and Places365 label files in work/raw (URLs in run.py)
python3 run.py qwenitems                    # Qwen inputs, key files and the 1,000-photo mining pool
uv sync --frozen                            # torch 2.15, transformers 5.22.1, sentence-transformers 6.2.0
uv run --frozen python run.py fetch         # about 2,100 photos from the Open Images bucket; Places365 from val_large.tar
uv run --frozen python run.py sheets        # contact sheets for the agent labeller
uv run --frozen python run.py embed         # EG2 vectors, needs a CUDA GPU, about a minute
OPENROUTER_API_KEY=... python3 run.py apilabel   # Gemini 3.8 Flash labels, about $0.75
modal run qwen_modal.py --stage upload
modal run qwen_modal.py --stage zs          # about $0.10; each fine-tune about $0.70
modal run qwen_modal.py --stage ft --split a
modal run qwen_modal.py --stage ft --split b
modal run qwen_modal.py --stage mine --split a
uv run --frozen python run.py minesheets    # sheets of mined candidates no person verified
uv run --frozen python run.py report        # results/summary.json, no network, no GPU
```

Downloads needed in `work/raw`: from `https://storage.googleapis.com/openimages/v7/`
`oidv7-val-annotations-human-imagelabels.csv` and `oidv7-test-annotations-human-imagelabels.csv`; from
`https://storage.googleapis.com/openimages/2018_04/` `validation/validation-images-with-rotation.csv`
and `test/test-images-with-rotation.csv`; from `https://data.csail.mit.edu/places/places365/`
`filelist_places365-standard.tar` (extracted) and `val_large.tar`; and `IO_places365.txt` from the
Places365 GitHub repository. Every OpenRouter and Modal step adds to `results/spend.jsonl` and stops
before $10 in total. Modal cost is GPU seconds at the A10G list price ($1.10 an hour), an estimate
that leaves out container CPU and memory.

## Files

- `run.py`: selection, downloads, contact sheets, EG2 vectors, the second labeller, Qwen inputs.
  `report.py`: production's head trainer and gate, zero-shot, agreement, re-draws, Qwen scoring,
  mining, and the production recomputation. `qwen_modal.py`: the Qwen zero-shot, LoRA and mining runs.
- `LABEL_GUIDE.md`: the agent label guide and how its fields map to the human labels.
- `data/photos.jsonl`: every photo's id, source, group, human labels and split membership;
  `data/agent_labels/`: our labels; `data/agent_sheet_index.txt`: sheet number to photo id;
  `data/mine_pool.jsonl`: the 1,000 mining photos with their verified labels;
  `data/agent_labels_mine/`: our check of mined candidates no person verified; `data/qwen_items.jsonl`,
  key files: Qwen's inputs.
- `results/eg2_vectors.npz`, `results/eg2_option_text.npz`: every EG2 vector;
  `results/api_labels.jsonl`: Gemini's labels; `results/qwen/`: every Qwen answer;
  `results/heads_test_probs.json`: every held-out head score; `results/summary.json`: every replica
  number above; `results/spend.jsonl`: the ledger.
- `production/records.jsonl`: production's 1,532 photos under opaque ids (first 12 hex characters of a
  SHA-256), with group, held-out flag, agent label, EG2 head scores on held-out photos and the Qwen v2
  and v3 answers; `production/qwen_mine_v2.jsonl`: the mining answers; `production/heads_meta.json`,
  `production/heads_report.txt`: the head thresholds and production's trainer output;
  `production/summary.json`: the aggregates. No photo, link, listing text or supplier is included.

## Related work

**Probes on frozen embeddings and small students**

- Radford et al., "Learning Transferable Visual Models From Natural Language Supervision" (CLIP),
  2021. https://arxiv.org/abs/2103.00020. Natural language as the label space "enabling zero-shot
  transfer"; the paper's linear probes on the frozen image features are the same move as our heads.
  Our zero-shot arm is the CLIP recipe on EmbeddingGemma 2, and it is clearly worse than a trained head.
- Kumar et al., "Fine-Tuning can Distort Pretrained Features and Underperform Out-of-Distribution",
  ICLR 2022. https://arxiv.org/abs/2202.10054. With good features and a distribution shift, a linear
  probe can beat full fine-tuning out of distribution. Our heads never touch the encoder, so the
  vectors search uses stay the vectors the heads read.
- Hinton, Vinyals, Dean, "Distilling the Knowledge in a Neural Network", 2015.
  https://arxiv.org/abs/1503.02531. Train a cheap model on a strong one's outputs. Our heads are a
  distillation of agent labels into a matrix multiply.
- Wang et al., "Want To Reduce Labeling Cost? GPT-3 Can Help", Findings of EMNLP 2021.
  https://arxiv.org/abs/2108.13487. GPT-3 labels cost "50% to 96% less" than human labels and trained
  models nearly as well; mixing in human labels did better on a fixed budget. Our heads on agent
  labels match that on objects and miss it where the definition drifted.

**Models as labellers**

- Gilardi, Alizadeh, Kubli, "ChatGPT Outperforms Crowd-Workers for Text-Annotation Tasks", PNAS 2023.
  https://arxiv.org/abs/2303.15056. Higher accuracy than crowd workers on four of five tasks, at under
  $0.003 an annotation. That is text; our photo cues show where it does not carry: stairs and
  handrails depend on what people count as one.
- Bavaresco et al., "LLMs instead of Human Judges? A Large Scale Empirical Study across 20 NLP
  Evaluation Tasks", ACL 2025. https://arxiv.org/abs/2406.18403. Agreement with people "varies widely"
  by property and annotator expertise; "LLMs should be carefully validated against human judgments".
  Our per-field kappas, from 0.05 to 1.00 on one label guide, are the photo version.
- Northcutt, Athalye, Mueller, "Pervasive Label Errors in Test Sets Destabilize Machine Learning
  Benchmarks", NeurIPS 2021 Datasets and Benchmarks. https://arxiv.org/abs/2103.14749. At least 3.3%
  label errors on average in ten benchmark test sets, enough to reorder models. Human labels are not
  perfect either; ours disagreed with both agents on escalators and balconies by definition.

**Sample size**

- Varoquaux, "Cross-validation failure: small sample sizes lead to large error bars", 2017.
  https://arxiv.org/abs/1706.07581. With about 100 samples the error bars are around ±10%, and "the
  standard error across folds strongly underestimates them". Our re-draws show the same thing per
  answer, with 5 to 30 positives.
- Binomial proportion confidence intervals, Wikipedia.
  https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval. The Wilson interval "can be
  safely employed with small samples and skewed observations", where the normal approximation
  collapses to zero width at 100%; it cites Brown, Cai and DasGupta (2001), who advise against the
  normal approximation.

**Models and data**

- Hu et al., "LoRA: Low-Rank Adaptation of Large Language Models", 2021.
  https://arxiv.org/abs/2106.09685. Frozen weights plus small trained low-rank matrices; our fine-tune
  adapts only the language-model projections.
- Qwen team, Qwen3.5-2B model card. https://huggingface.co/Qwen/Qwen3.5-2B. A 2B "Causal Language Model
  with Vision Encoder", Apache-2.0, non-thinking by default. Bai et al., "Qwen2.5-VL Technical
  Report", 2025, https://arxiv.org/abs/2502.13923, describes the family's earlier localisation and
  document abilities.
- Google, EmbeddingGemma 2 model card. https://huggingface.co/google/embeddinggemma-2. Text, images,
  video and audio in one 768-dimensional space; 280 image tokens by default, configurable from 70 to
  1,120. Production qualified 140, and 280 did not do better on its photos.
- Kuznetsova et al., "The Open Images Dataset V4", IJCV 2020. https://arxiv.org/abs/1811.00982, and
  the V7 facts page, https://storage.googleapis.com/openimages/web/factsfigures_v7.html: human
  verification "practically eliminates false positives (but not false negatives)", and unverified
  classes "are not annotated". Annotations CC BY 4.0, images listed as CC BY 2.0.
- Zhou et al., "Places: An Image Database for Deep Scene Understanding", 2016.
  https://arxiv.org/abs/1610.02055. Scene categories confirmed by Mechanical Turk workers answering
  "Is this a [scene]?" in rounds, with control images; the copyright of the images "belongs to the
  image owners" (https://github.com/CSAILVision/places365).

None of these asks which facts an agent should refuse to read from a photo at all, which is the
decision that mattered most here.
