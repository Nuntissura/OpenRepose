# Adult Moodboard Prompt System

Date: 2026-05-03

Canonical status: this is the single-file adult moodboard blueprint. Keep the operating recipe, card template, diversity matrix, scoring gates, batch guidance, generated artifact schemas, and future skill instructions here instead of splitting them across separate recipe/template files.

## Changelog

Record every blueprint change here so future assistants can see what shifted between iterations without diffing the whole file. Keep the date in the filename only on structural rewrites; ordinary edits update this changelog and amend the canonical status if needed.

```text
2026-05-03  initial blueprint
2026-05-03  iter 1: added Changelog, Roles section, Tier Table, scope labels on the four sequence sections, Identity/Model-Family Adapter, Fast Triage Scoring, Abandonment Criteria, Accepted-Set Diversity Audit, Additive-Only Schema Rule, Chat-Only Output Mode, Worked Example AMB-0001
2026-05-03  iter 2: inspection cleanup; clarified production-tier package requirements as mandatory, scoped deterministic build sequence to mini/production, removed non-ASCII section markers for copy-safe skill conversion
2026-05-03  iter 3: rewrote Skill Conversion Block to mirror the Claude AMood SKILL.md — production-tier-only stance, canonical blueprint resolution order, required boot sequence, workflow per turn, boundary with the image/video pipeline, OpenRepose dual-mode operation (Mode A standalone vs Mode B in OpenRepose with dispatcher commands and I3 caveat), chat-only mode rules, update rules, hard rules (no hidden-camera / spycam / asleep / intoxicated / unconscious / juvenile-coded / school-coded / coercive framing; one kink + one archetype + one trigger per card; multi-seed acceptance), provider portability. Skill wrappers (Claude SKILL.md, GPT skill manifests, local-model system prompts) must mirror this section verbatim in intent.
```

This file is intentionally provider/model agnostic. It can be quoted into any assistant, GPT skill, Claude skill, local model prompt, or repo automation without depending on OpenAI, Anthropic, Google, or a specific local model. Model-family details belong in the active workflow or model-family note, not in this blueprint.

## Purpose

This system turns a plain explicit adult pose or exposure target into a production scene with narrative, mood, camera logic, and repeatable prompt structure.

The target remains photorealistic explicit adult pornographic output. The moodboard layer exists to make the image feel intentional instead of just technically exposed: the viewer should understand where the performer is, what moment is being staged, why the body position makes sense, and what visual details make the image memorable.

Use this system for still images, video keyframes, pose-library cards, avatar scenes, LoRA validation scenes, and small batch prompt tests.

## Blueprint Contract

This file is the source of truth. A fresh assistant uses this file plus the active workflow/model-family note to create the needed production files, matrices, prompts, run manifests, and review sheets.

The blueprint has four jobs:

1. Convert a plain explicit adult target into a full moodboard card.
2. Expand one card into diverse variants without losing the primary trigger.
3. Emit production artifacts that are easy to batch, review, score, and reuse.
4. Preserve enough structure that the file should later convert directly into a GPT skill, Claude skill, or local assistant instruction without rewriting the method.

Do not split this blueprint into separate recipe or template files unless the operator explicitly asks. Artifacts generated from it should be separate files, but this file remains the canonical instructions and template source.

## Roles: Blueprint vs Generated Artifacts

This file is a generator. The artifacts it produces live elsewhere. Do not collapse the two.

| Always inside this file | Always outside this file |
| --- | --- |
| Lenses, rules, taxonomies, fantasy modes, palettes | Filled-in moodboard cards with real content |
| Card schema and copy-this card template | Batch matrices with real rows |
| TSV headers and artifact templates | Quota plans, variant ladders, anti-repetition ledgers |
| Scoring rubric, acceptance gate, rejection reasons | Prompt manifest, run manifest, review manifest, scorecard |
| Operating recipes and sequences | Positive/negative prompt block files |
| Skill conversion block | Pose/control guides (PNG, JSON, source) |
| Examples that exist only to teach the schema (e.g. AMB-0001 worked example) | Generated images, contact sheets, accepted/rejected sets |

Rule:

```text
If a model is tempted to "just add this one card to the blueprint", stop. Cards go under references/prompts/<batch_slug>/cards/.
The blueprint only holds rules, schemas, templates, and teaching examples.
```

Provenance rule:

```text
The blueprint is the single source of truth for structure. Any generated artifact that drifts from this file's schemas should be updated to match the file, not the other way around.
If a real production batch needs a new field, add it here first (additive-only, see `Generated Artifact Schemas`), then regenerate or amend artifacts.
```

## Blueprint Outputs

When used for a production-tier batch, this blueprint must create a compact package with these artifacts.

Required package rule:

```text
Create the package folder and package index before creating stories, moodboards, prompts, matrices, manifests, or generated images.
```

Stories, moodboard cards, generated images, accepted/rejected reviews, prompt blocks, and matrices must live inside the same package folder so a future assistant can inspect one folder and understand the whole production run.

Required package layout for production batches:

```text
references/prompts/<batch_slug>/
  INDEX.md
  README.md
  stories/
    <card_id>_<slug>_story.md
  cards/
    <card_id>_<slug>.md
  moodboards/
    <card_id>_<slug>_moodboard.md
  matrices/
    <batch_slug>_batch_matrix.tsv
    <batch_slug>_variant_ladder.tsv
    <batch_slug>_quota_plan.tsv
  ledgers/
    <batch_slug>_anti_repetition_ledger.tsv
  manifests/
    <batch_slug>_prompt_manifest.tsv
    <batch_slug>_run_manifest.tsv
    <batch_slug>_review_manifest.tsv
    <batch_slug>_scorecard.tsv
  prompt_blocks/
    <card_id>_<slug>_positive.txt
    <card_id>_<slug>_negative.txt
  pose_guides/
    openpose/
      png/
      json/
      source/
      rejected/
    dwpose/
      png/
      json/
      source/
      rejected/
  generated_images/
    .gitignore
    raw/
    accepted/
    rejected/
    diagnostic/
    contact_sheets/
```

Small tests may use fewer files. For production-scale batches, generate at least:

- package folder
- package `INDEX.md`
- one batch matrix
- one moodboard card per promoted row
- one story file per promoted card when a story beat is non-trivial
- one prompt manifest
- one pose/control guide manifest when OpenPose, DWPose, or another control guide is used
- one review/scorecard file
- one anti-repetition ledger

The artifact files are generated outputs. They should be separate because they are batch data, not competing instruction sources.

Generated images must go under `generated_images/` inside the package. Keep generated image binaries out of Git unless the operator explicitly decides otherwise. Use `generated_images/.gitignore` to ignore image outputs while keeping the folder structure discoverable.

OpenPose, DWPose, and other control guide files must go under `pose_guides/` inside the same package. Store rendered guide PNGs and machine-readable JSON separately so ComfyUI workflows, scripts, and future assistants can find the exact control input used for each image.

## Minimal Input Contract

The blueprint should start from a very small input when that is all the operator provides. If the operator gives only a target, fill missing fields conservatively.

Minimum useful input:

```text
explicit target:
workflow/model family:
batch size:
intensity mode:
must include:
must avoid:
```

Optional high-value input:

```text
avatar/identity:
body emphasis:
setting preference:
wardrobe preference:
kink cue:
porn archetype:
fantasy mode:
camera family:
palette family:
output aspect ratio:
negative failure seen before:
```

If the operator gives no batch size, create 12 matrix rows for exploration. If they give no fantasy mode, spread across `casual intimate`, `raw-cam performance`, `editorial porn`, and `archetype-heavy fantasy` while keeping the explicit target first.

## Tier Table

Pick the tier from the operator's request before producing artifacts. Do not over-execute on a small ask. Do not under-execute on a production ask.

| Tier | When to use | Required artifacts | Optional artifacts |
| --- | --- | --- | --- |
| `quick` | Operator wants 1 scene, single card, ad hoc test, "give me a hotel-robe scene". Batch size 1 to 3. | One moodboard card. One positive prompt block. One negative prompt block. Acceptance gate filled. | Inline scorecard row after generation. |
| `mini` | Exploratory batch, LoRA validation set, pose stress sweep. Batch size 4 to 24. | Cards, batch matrix (categorical only), prompt blocks per card, scorecard, package `INDEX.md`, `generated_images/` folder. | Variant ladder, story files, pose/control guide manifest. |
| `production` | Reusable scene branch, gallery batch, video keyframe set, LoRA training scene set. Batch size 25 or more. | Full package per `Blueprint Outputs`: INDEX, README, stories, cards, moodboards, batch matrix, quota plan, variant ladder, anti-repetition ledger, prompt manifest, pose/control guide manifest, run manifest, review manifest, scorecard, prompt blocks, pose guide folders, generated image folders. | Series plan when shots become a sequence. |

Decision rule:

```text
operator request mentions "one image / one card / quick test"     -> quick
operator request mentions "small batch / try a few / explore"     -> mini
operator request mentions "scene branch / gallery / 25+ / batch"  -> production
ambiguous: pick mini and ask the operator to confirm the tier before scaling
```

Tiers are not gates. A `quick` card that proves promising can be promoted into a `mini` package without throwing away the original card; the card moves into `cards/` inside the new package folder.

## Deterministic Build Sequence (mini/production, model-agnostic)

Use this exact sequence for mini and production work when generating files from the blueprint. For quick one-card work, use `Card-To-Prompt Method (one card, any tier)` and do not create quota plans, ledgers, or run manifests unless the card is promoted.

```text
operator input
-> normalize target
-> choose explicit family
-> choose quotas
-> fill batch matrix
-> run compatibility check
-> create moodboard cards
-> create variant ladder
-> assemble prompt blocks
-> create prompt manifest
-> run small seed batch
-> inspect outputs
-> score outputs
-> update anti-repetition ledger
-> promote / revise / reject
-> update workflow or scene note
```

Do not skip directly from operator input to final prompt prose for large batches. The matrix and compatibility pass are what create diversity at scale.

## Core Rule

Build from the explicit target outward.

```text
explicit adult target -> body mechanics -> camera/framing -> scene logic -> mood -> texture/details -> negative gates
```

Do not start with a pretty setting and hope the adult target appears. The act, exposure, pose, contact point, or anatomy visibility requirement is the anchor. The story supports it.

## Lens Stack

Build every card by moving through production lenses in order. This is stricter than brainstorming a scene.

```text
sexual trigger lens
-> fantasy/story lens
-> viewer intensification lens
-> arousal/engagement lens
-> pose/body mechanics lens
-> wardrobe/exposure lens
-> set designer lens
-> composition/color lens
-> cinematography/light lens
-> continuity/review lens
```

### Sexual Trigger Lens

Answer this first:

```text
What is the viewer supposed to react to sexually in this image?
```

Examples:

- visible vulva/pussy exposure
- exposed breasts, underboob, cleavage, sideboob, or nipples
- ass/rear exposure
- penetration contact point
- masturbation or toy contact
- cumplay/fluid placement
- mouth/tongue/gaze expression
- body scale/fetish emphasis, such as top-heavy glamour proportions, long legs, narrow waist, or oil-slick skin

This lens decides the primary acceptance gate. If the trigger does not read clearly, the image fails even if the story and setting are attractive.

### Fantasy / Story Lens

Answer:

```text
What staged moment makes this sexual trigger feel intentional?
```

Keep it to one sentence. The story should create a reason for the exposure or act:

- a robe slips open in a hotel doorway
- a skirt is lifted while leaning on a counter
- a performer looks back over her shoulder while bracing on a bed edge
- a shower scene uses steam, wet hair, and a towel opened toward camera
- a mirror setup makes direct self-display plausible

The story should never become longer than the anatomy and pose instructions. If the model starts prioritizing scenery over the target, shorten the story.

### Viewer Intensification Lens

Answer:

```text
How is the adult subject made more sexually legible to the viewer?
```

Use this to hypersexualize the adult subject without losing realism:

- direct camera awareness or deliberate over-shoulder gaze
- parted lips, open mouth, tongue cue, or heavy breathing expression
- opened, lifted, displaced, wet, sheer, or tensioned wardrobe
- skin shine, sweat, oil sheen, pressure marks, damp hair, makeup smudge
- body-led pose line: arched back, hip presentation, chest lift, leg spread, shoulder roll
- tactile cue: hand on fabric, fingers holding a robe belt, hand moving clothing aside, toy or support object placement
- camera proximity, crop, and focus that prioritize the trigger

Do not use juvenile styling, school-coded framing, intoxication, unconsciousness, hidden-camera logic, or coercive setup as an intensifier. Use adult performance, adult styling, body mechanics, and camera intent.

### Arousal / Engagement Lens

Answer:

```text
Why would this image hold attention and create a stronger urge to keep looking?
```

Explicit anatomy is not enough. Strong porn usually combines trigger clarity with beauty, performer intent, tactile realism, and a small tension loop.

Use this lens to define the arousal strategy:

- `trigger clarity`: the sexual target is immediately readable
- `tease/reveal`: wardrobe, hand placement, pose, or camera creates a reveal moment
- `performer connection`: direct gaze, over-shoulder look, mouth cue, or mirror gaze feels aimed at the viewer
- `body invitation`: hips, chest, legs, back arch, shoulder roll, or hand placement guides the eye
- `tactile realism`: skin texture, pressure marks, sweat, oil, wet hair, fabric pull, bed wrinkles, or condensation
- `beauty/polish`: attractive face, coherent anatomy, flattering light, strong palette, clean composition
- `fantasy readability`: kink cue and porn archetype are legible in one glance
- `replay value`: the scene has enough pose, gaze, story, and detail to stay interesting after the first explicit read

For each serious card, write one arousal hook in plain language:

```text
The viewer first notices <sexual trigger>, then <gaze/body/wardrobe detail> pulls attention back, while <set/palette/detail> makes the scene feel specific.
```

Reject cards that are explicit but dead: no gaze, no body intent, flat lighting, muddy palette, generic set, target visible but unflattering, or no tactile detail.

### Pose / Body Mechanics Lens

Answer:

```text
What body position makes the trigger visible and physically plausible?
```

Specify stance, hip angle, torso lean, head direction, leg placement, hand placement, and support point. If hands or props are not needed, keep them away from the target anatomy.

### Wardrobe / Exposure Lens

Answer:

```text
What clothing state reveals the trigger and adds story texture?
```

Wardrobe is a mechanism, not decoration. A robe, shirt, skirt, bra, towel, thong, bikini, stockings, or heels must either reveal the target, explain hand placement, or add texture. If it covers the primary trigger, reject the card.

### Set Designer Lens

Answer:

```text
What set, furniture, and background objects make the pose believable without blocking the target?
```

The set designer chooses:

- physical support: bed edge, sink, counter, chair, doorframe, balcony rail, shower wall, stool, sofa arm, studio cube
- background depth: room corner, mirror, window, city lights, bathroom tile, rumpled bed, wardrobe rack, steam, curtains
- object placement: towels, sheets, robe belt, lube, toy, phone, camera remote, makeup mirror, lamp
- sightline protection: no furniture, prop, fabric, signage, or clutter in front of the target anatomy

The set should make the sexual trigger feel staged and inevitable. It should not compete with the performer.

### Composition / Color Lens

Answer:

```text
What composition and palette make the sexual trigger read first?
```

Composition controls visual hierarchy. Color palette controls mood and separates skin, wardrobe, target anatomy, background, and props.

Good composition controls:

- trigger-first visual hierarchy: the eye lands on the sexual trigger, face/gaze, then set
- clear silhouette around the body and target anatomy
- foreground used as framing only, not coverage
- support furniture angled away from the target sightline
- negative space placed behind the body or gaze direction, not over the target
- leading lines from bed edge, counter, doorway, mirror, rail, or shower glass toward the performer
- crop choice matches target: chest-level for cleavage/underboob, rear three-quarter for ass, lower-body protected for vulva, contact-point protected for penetration

Useful palette families:

| Palette | Use when | Visual effect |
| --- | --- | --- |
| `warm hotel amber` | hotel robe, bedroom, luxury private-room | skin warmth, intimacy, soft glamour |
| `cool bathroom tile` | shower, mirror, towel, wet/oil | clean wet skin contrast |
| `neon magenta/cyan` | raw-cam, nightlife, balcony, club-adjacent sets | heightened fantasy and edge light |
| `soft daylight cream` | casual intimate, bedroom, couch, morning scenes | natural realism and skin detail |
| `black/red latex` | wardrobe fetish, studio glamour, power-exchange styling | high contrast, bold kink signal |
| `white studio clean` | body showcase, avatar validation, catalog-like explicit tests | clean anatomy read and low background noise |
| `moody green/gold` | luxury, lounge, spa, cinematic private-room | adult premium mood without flat beige |
| `flash-photo neutral` | raw-cam performance, phone camera | direct, immediate, amateur-style clarity |

Palette must not erase anatomy. Avoid palettes where skin, wardrobe, and background collapse into the same color mass, or where saturated light hides target detail.

### Cinematography / Light Lens

Answer:

```text
What camera and light make the trigger readable and the scene attractive?
```

Specify camera height, lens feel, crop rule, focus priority, and lighting family. Use light to reveal skin texture and shape, not to hide target anatomy.

### Continuity / Review Lens

Answer:

```text
Did every lens support the same primary trigger?
```

Reject the card if the lenses fight each other: sideboob target with frontal-only pose, penetration target with hidden contact point, rear exposure with a full-frontal camera, mouth/tongue cue with a face too small to inspect, or elaborate furniture blocking the anatomy.

## Fantasy Mode Dial

Choose the fantasy mode before writing the final story beat. This controls whether the card leans into heightened porn fantasy, casual intimacy, staged voyeurism, or polished editorial production.

Do not confuse useful genre archetypes with demographic stereotypes. The repo can use strong adult fantasy coding, but avoid reducing the scene to protected-class caricatures, juvenile-coded roles, school-coded framing, coercion, intoxication, unconsciousness, hidden-camera violation, or threat. Use adult performer styling, wardrobe, set, gaze, camera, and body mechanics as the levers.

| Mode | Use when | Maximize by | Avoid |
| --- | --- | --- | --- |
| `archetype-heavy fantasy` | The image should read instantly as a porn fantasy setup. | Clear role signal, iconic wardrobe state, high-contrast set, direct performance gaze, exaggerated adult body emphasis, obvious sexual trigger. | Protected-class caricatures, school/teen coding, coercive or intoxicated setup, too many props. |
| `casual intimate` | The image should feel private, natural, and less staged. | Softer light, believable room mess, relaxed body line, robe/towel/sheet mechanics, close camera, natural expression, skin texture. | Overdesigned sets, glossy studio light, theatrical roleplay, heavy makeup that fights intimacy. |
| `staged voyeur` | The image should feel observed from a doorway, mirror, phone, or room corner while still being adult-performed. | Partial foreground frame, mirror/reflection, over-shoulder gaze, performer-aware glance, imperfect crop that still protects the target, natural practical light. | Hidden camera, spycam, peeping, non-consensual framing, asleep/unconscious/intoxicated subject, target hidden by the voyeur angle. |
| `raw-cam performance` | The image should feel direct, immediate, and amateur-style. | Phone-flash look, direct camera address, simple room, close crop, fewer props, clear trigger, mouth/gaze cue. | Fake UI, timestamps, platform branding, messy text artifacts, target cropped out. |
| `editorial porn` | The image should feel premium, deliberate, and cover-worthy. | Clean pose line, polished wardrobe reveal, designed furniture, controlled lighting, glossy but realistic skin, readable target. | Fashion styling that covers the trigger, too much negative space, generic glamour without explicit clarity. |

### Maximizing Archetype / Fantasy Coding

When using `archetype-heavy fantasy`, stack signals across different lenses instead of repeating adjectives.

Good signal stack:

```text
sexual trigger: <specific target>
fantasy archetype: <adult role or genre-coded setup>
wardrobe signal: <opened/lifted/displaced item>
set signal: <place that instantly supports the role>
object signal: <one prop that explains hands or action>
viewer signal: <gaze, mouth, body line, camera proximity>
```

Use one strong archetype and one strong trigger. Do not pile five fantasies into one card. A clear hotel robe reveal, shower towel opening, backstage mirror scene, studio audition set, luxury balcony tease, or private-bedroom self-display will usually outperform a cluttered prompt that mixes unrelated role signals.

### Making It Casual / Intimate

Reduce the obvious roleplay and increase ordinary physical detail:

- simple bed, bathroom, couch, shower, mirror, towel, robe, sheet, nightstand, lamp
- relaxed direct gaze or shy glance
- imperfect but intentional framing
- natural skin texture, pressure marks, damp hair, fabric wrinkles
- lower prop count
- one small story beat, not a theatrical scenario

The trigger still comes first. Casual does not mean vague.

### Making It Staged-Voyeuristic

Use camera grammar that feels observed, but keep the scene adult-performed and camera-aware:

- doorway frame, mirror angle, phone held at chest height, room-corner perspective, shower glass, balcony doorway, reflected gaze
- performer notices the camera or knowingly glances back
- foreground can frame the body but must not cover the sexual trigger
- practical light, slight motion tension, less polished set dressing

Reject hidden-camera, spycam, asleep/unconscious, intoxicated, peeping, or unaware-subject framing. For production prompting, staged voyeurism should mean "performed being watched," not non-consent.

## Kink And Porn Archetype Lens

Use kinks and porn archetypes as production signals. They should clarify the sexual trigger, wardrobe, object choice, set design, and camera language.

Rule:

```text
one primary kink cue + one porn archetype + one explicit trigger
```

Do not stack many kinks in one card. Too many kink cues make the prompt muddy and increase anatomy, prop, and consent/framing failures.

### Kink Cues

Useful adult-production kink cues:

- body-focus: breasts, underboob, cleavage, sideboob, ass, legs, feet, waist, hips
- wardrobe fetish: lingerie, stockings, heels, open robe, lifted shirt, displaced panties, wet clothing, sheer fabric
- tactile/material: oil sheen, sweat, wet skin, shower steam, fabric tension, pressure marks
- gaze/mouth: direct stare, shy gaze, over-shoulder gaze, parted lips, open mouth, tongue cue
- self-display: mirror posing, phone self-recording, deliberate camera address
- staged exhibition: performer knowingly presenting to camera, doorway reveal, balcony doorway, studio pose
- staged voyeur: observed camera language with performer awareness
- solo/toy: vibrator, dildo, lube, hand placement, toy contact
- cumplay/after-action: intentional fluid placement and realistic wet texture
- power-exchange styling: dominant/submissive body language, collar/strap/rope styling, kneeling/standing contrast

For power-exchange or restraint-coded cards, keep the framing clearly adult, performed, coherent, non-injurious, and not fear/distress-driven. The visual trigger should be the erotic pose and styling, not harm.

Reject kink cues that depend on juvenile coding, school/teen coding, coercion, unconsciousness, intoxication, hidden-camera violation, injury, degradation as harm, or illegal/non-consensual framing.

### Porn Archetypes

Use porn archetypes as shorthand for scene logic.

Good archetype families:

| Archetype | Scene logic | Good pairings |
| --- | --- | --- |
| `amateur bedroom` | private, casual, close camera, simple room | raw-cam, casual intimate, mirror, bed-edge, robe/sheet |
| `cam performer` | direct address to viewer, performer-aware, clean trigger | phone/camera remote, ring light, bed/couch/studio corner |
| `hotel robe reveal` | adult luxury/private-room fantasy | robe open, warm lamp, balcony doorway, bed edge |
| `bathroom mirror` | self-display and reflection logic | towel open, wet hair, sink, mirror gaze |
| `shower glass` | wet texture and partial framing | towel, shower wall, steam light, wet skin |
| `backstage/dressing room` | wardrobe transition and mirror set | lifted clothing, stockings, heels, makeup mirror |
| `studio glamour` | clean body showcase and controlled pose | softbox, heels, oil sheen, seamless backdrop, chair/cube |
| `luxury balcony` | high-status fantasy and doorway framing | robe, city lights, over-shoulder gaze, warm/cool mixed light |
| `couch amateur` | relaxed private-room sexuality | casual wardrobe, phone camera, close/medium framing |
| `kitchen/counter lean` | support object explains hip/ass/body angle | counter edge, shirt/skirt displacement, practical light |

Archetype strength should match the fantasy mode. `archetype-heavy fantasy` can use obvious shorthand. `casual intimate` should use lighter signals. `staged voyeur` should use camera position and performer-aware glance instead of hidden-camera cues.

## Moodboard Card Schema

Each reusable scene should be written as a card with these fields.

| Field | Purpose |
| --- | --- |
| `slug` | Stable lowercase scene id for filenames, manifests, and output tags. |
| `production role` | Why this scene exists: pose test, avatar production, LoRA stress, background pass, video keyframe, etc. |
| `explicit anchor` | Exact adult action, pose, or exposure requirement. Keep this direct and visible. |
| `sexual trigger` | The viewer-facing sexual hook that must read first. |
| `fantasy/story lens` | The one-sentence staged reason the trigger is visible. |
| `viewer intensification` | How adult gaze, mouth, body line, wardrobe state, skin, and camera height make the subject more sexually legible. |
| `arousal strategy` | The trigger, tease/reveal, gaze/body invitation, tactile realism, and replay hook. |
| `beauty strategy` | What makes the image visually attractive to an artist: composition, palette, light, face, silhouette, material contrast. |
| `body mechanics` | How the body plausibly creates the target view: stance, lean, hip angle, hand placement, head direction, weight shift. |
| `story beat` | One sentence describing the staged moment. |
| `setting` | Location and set dressing that naturally supports the pose. |
| `performer state` | Expression, confidence/shyness, eye contact, motion, sweat, hair, makeup, wardrobe state. |
| `composition` | Visual hierarchy, crop logic, silhouette, leading lines, foreground/background separation. |
| `color palette` | Palette family and accent color that support skin, wardrobe, and set separation. |
| `camera` | Lens, angle, crop rule, distance, focus priority, full-body vs close-up. |
| `lighting` | Main light, practical lights, contrast, skin highlights, shadow behavior. |
| `texture details` | Real materials, skin texture, fabric behavior, set mess, fingerprints, condensation, bed wrinkles, etc. |
| `style family` | Photoreal glamour, raw cam, editorial porn, luxury hotel, gritty backstage, studio catalog, etc. |
| `fantasy mode` | Archetype-heavy fantasy, casual intimate, staged voyeur, raw-cam performance, or editorial porn. |
| `archetype signal` | The adult genre/role shorthand, if any, that makes the fantasy read quickly. |
| `kink cue` | The primary kink or fetish signal the card is serving. |
| `porn archetype` | The porn-scene shorthand: amateur bedroom, cam performer, hotel robe reveal, bathroom mirror, shower glass, etc. |
| `positive prompt blocks` | Modular phrases assembled in priority order. |
| `negative prompt blocks` | Anatomy, age, framing, censorship, clothing, text/logos, artifact, and model-family negatives. |
| `acceptance gate` | What must be visible/coherent before any output is accepted. |
| `failure levers` | First prompt/control changes if the output fails. |

For high-volume prompt batches, use the `Batch Matrix TSV Header` section in this file. The card template controls quality; the matrix controls coverage.

## High-Volume Diversity Layer

For 100+ or 1000+ prompt batches, do not ask a model to "write many creative porn scenes" from scratch. Make it fill a matrix first, then assemble prompts from compatible rows.

Minimum diversity axes:

```text
explicit_family
exposure_detail
pose_family
orientation
wardrobe_state
held_object
support_object
setting_family
lighting_family
camera_family
gaze
mouth_tongue
mood
texture_details
negative_focus
```

This prevents repetitive outputs and keeps every creative detail tied to production function. The explicit family decides what must be visible. Wardrobe and objects explain why it is visible. Camera/framing protects it. Setting and texture make the image feel specific.

Useful explicit families:

- vulva/pussy exposure
- breast exposure: underboob, cleavage, sideboob, nipple/full breast
- ass/rear exposure
- penetration
- masturbation/toy use
- cumplay/after-action fluid detail
- gaze/mouth/tongue-led variants

Every row should have one primary explicit family. Secondary details can be added, but should not compete with the primary visibility gate.

## Quota Planning

Before writing rows, decide quotas. Quotas prevent a batch from collapsing into the same room, pose, camera, palette, or fantasy mode.

For a 100-row batch, a balanced starting point is:

| Axis | Minimum coverage |
| --- | --- |
| `explicit_family` | 5 to 7 families, unless the operator requested one family only. |
| `fantasy_mode` | At least 4 modes. |
| `porn_archetype` | At least 8 archetypes. |
| `setting_family` | At least 8 settings. |
| `pose_family` | At least 10 pose families. |
| `camera_family` | At least 6 camera families. |
| `palette_family` | At least 6 palettes. |
| `wardrobe_state` | At least 8 mechanisms. |
| `held_object` | At least 8 useful object choices plus `none`. |
| `support_object` | At least 8 support objects. |
| `gaze` | At least 5 gaze modes. |
| `mouth_tongue` | At least 4 mouth/tongue modes. |
| `texture_details` | At least 12 rotating texture cues. |

For a single-target batch, keep the `explicit_family` fixed and diversify the other axes more aggressively:

```text
1 explicit family
3 to 5 exposure details
8 to 12 pose families
8 settings
6 camera families
6 palettes
6 wardrobe mechanisms
4 fantasy modes
```

Use quotas as production controls, not mathematical theater. If a row is incompatible, replace it instead of forcing quota balance.

## Compatibility Check

Every matrix row must pass compatibility before becoming a card.

Hard rejects:

- The camera angle cannot see the explicit target.
- The wardrobe state covers the explicit target.
- The held object or support object blocks the target.
- The fantasy mode conflicts with the setting or camera grammar.
- The pose family makes the body mechanics implausible.
- The palette makes skin, wardrobe, target anatomy, and background collapse into one unreadable mass.
- The archetype depends on juvenile, school-coded, coercive, intoxicated, unconscious, hidden-camera, or non-consensual framing.
- The row has more than one primary trigger fighting for the same crop.

Compatibility signature:

```text
explicit_family + exposure_detail + pose_family + orientation + camera_family + wardrobe_state + support_object
```

If two rows share the same compatibility signature, they are near-duplicates. Keep one, or change at least two axes.

## Variant Ladder

A strong row should become a controlled set of variants. Variants should change intensity, styling, camera, or story pressure while preserving the target.

Default ladder:

| Variant | Purpose | Change rule |
| --- | --- | --- |
| `baseline` | Clean read of the target and pose. | Use the simplest compatible setting, camera, and wardrobe mechanism. |
| `intimate` | Softer, closer, more private version. | Reduce set complexity, increase skin/fabric texture, soften light. |
| `explicit_plus` | Stronger visibility and body presentation. | Move trigger earlier, protect crop, strengthen pose/body mechanics. |
| `editorial` | Prettier hero/cover version. | Improve palette, silhouette, lighting, and set design while preserving target visibility. |
| `raw_cam` | More immediate amateur-style version. | Simplify set, add direct camera address, use practical/flash light, keep target clear. |
| `story_plus` | More memorable scene version. | Add one stronger object, set, or story beat without adding a second trigger. |

Do not create variants by adding unrelated kinks. Variant quality comes from changing one or two controlled levers, not piling on new concepts.

## Anti-Repetition Ledger

Maintain a ledger for any batch larger than 24 rows. The ledger stops the assistant from rediscovering the same scene shape under different adjectives.

Track these fields:

```text
card_id
slug
explicit_family
exposure_detail
pose_family
orientation
fantasy_mode
kink_cue
porn_archetype
setting_family
specific_setting
wardrobe_state
held_object
support_object
composition_rule
palette_family
lighting_family
camera_family
gaze
mouth_tongue
arousal_strategy
dedupe_signature
status
notes
```

Dedupe signature:

```text
explicit_family|pose_family|orientation|wardrobe_state|support_object|setting_family|camera_family|palette_family
```

Replacement rule:

```text
If a new row matches 6 or more dedupe fields with a recent accepted row, revise it before generation.
```

Good revisions change physical reality, not just adjectives:

- change support object
- change camera height
- change wardrobe mechanism
- change setting family
- change palette family
- change pose family
- change gaze/mouth cue
- change scene engine

## Accepted-Set Diversity Audit

The quota plan sets target coverage per axis at the start of a batch. The anti-repetition ledger prevents near-duplicates at row time. Neither measures whether the *accepted* outputs (not the planned rows) actually cover the planned axes after rejection winnows the batch.

Run this audit after every promotion pass. It closes the loop between quota planning and what the operator actually keeps.

Steps:

1. Filter the scorecard to rows where `promotion_decision = promote`.
2. For each diversity axis used in the quota plan, count distinct values in the accepted set.
3. Compute realized coverage as `accepted_distinct_values / quota_target_distinct_values`.
4. Flag any axis with realized coverage below 0.5 as `next-batch priority`.
5. Record the audit as a TSV row per axis so the next batch's quota plan can read it.

Diversity audit TSV header:

```text
batch_slug	axis	quota_target_distinct	planned_distinct	accepted_distinct	realized_coverage	priority_flag	notes
```

Example:

```text
hotel-reveal-100	fantasy_mode	4	4	2	0.50	priority	editorial and staged voyeur did not survive promotion
hotel-reveal-100	porn_archetype	8	8	3	0.38	priority	cam performer and backstage failed anatomy gate; revisit with guide
hotel-reveal-100	palette_family	6	6	5	0.83	ok	soft daylight cream not promoted; one card in next batch
```

Priority rule:

```text
realized_coverage >= 0.75   -> ok
0.5  to 0.74                 -> watch (acceptable but reseed once before next batch closes)
below 0.5                    -> priority (next batch must add cards using under-served values, not just retry rejected ones)
```

The audit feeds the next quota plan. It does not cancel the current batch.

## Shot Taxonomy

For a gallery or video keyframe batch, mix shot purposes instead of making every image a center-framed explicit still.

Useful shot purposes:

| Shot purpose | Job |
| --- | --- |
| `establishing explicit` | Shows body, setting, and primary trigger clearly. |
| `body-led` | Uses pose line, hips/chest/back/legs, and silhouette as the main draw. |
| `face-gaze-led` | Makes eye contact, mouth cue, and expression the secondary hook. |
| `detail-led` | Crops around target anatomy, wardrobe tension, hand placement, or texture. |
| `mirror/reflection` | Creates self-display logic and doubles gaze/body angles. |
| `pov/performance` | Makes the performer address the camera directly. |
| `environment-pressure` | Uses counter, bed edge, shower wall, chair, doorway, or rail to explain pose. |
| `aftermath/detail` | Uses texture, mess, wardrobe displacement, and relaxed body state after action. |

One concept can become a mini-set by using 3 shots:

```text
setup/arrival -> primary explicit still -> aftermath/detail
```

The primary explicit still must remain the strongest acceptance target.

## Prompt Assembly Order

Use this order when converting a card into a prompt. Earlier blocks carry more intent.

1. Adult gate and subject anchor.
2. Sexual trigger and explicit anchor.
3. Viewer intensification.
4. Arousal and beauty strategy.
5. Body mechanics and pose lock.
6. Wardrobe/exposure mechanism.
7. Composition and color palette.
8. Camera/framing.
9. Setting, furniture, and story beat.
10. Lighting and mood.
11. Texture and realism details.
12. Identity/body/model-specific anchors.
13. Quality terms.

Example structure:

```text
adult 18+ performer, mature adult face and body,
<explicit anchor>,
<sexual trigger and viewer intensification>,
<arousal hook and beauty strategy>,
<body mechanics>,
<wardrobe/exposure mechanism>,
<composition and color palette>,
<camera and framing>,
<set designer details and story beat>,
<lighting and mood>,
<texture and realism details>,
<identity/body/model anchors>,
photorealistic, realistic skin texture, coherent anatomy
```

Keep the explicit anchor direct. Keep the story short enough that the model does not ignore the anatomy target.

## Identity / Model-Family Adapter

The blueprint is provider/model agnostic, but real prompts run against a specific checkpoint, LoRA stack, control guide, and sampler. This adapter is the slot where model-family and identity details get spliced into the generic prompt blocks. Keep the model-family details out of this file; keep this adapter inside it so a fresh assistant knows where to put them.

Adapter slots:

```text
identity anchor:
  identity token, trigger word, or LoRA-trained name (e.g. "h4er1nface")
  identity LoRA file and strength range
  identity reference image path when used (face crop, body crop, contact sheet)

model-family adapter:
  checkpoint family (Pony/PDXL, SDXL, Illustrious, Flux, Z-Image, ERNIE, LTX video, etc.)
  required model-family positives (e.g. "score_9, score_8_up" for Pony, "masterpiece" for Illustrious)
  required model-family negatives (e.g. "score_4, score_5, score_6" for Pony, ERNIE quality terms, etc.)
  CLIP skip and known-good sampler/scheduler defaults for this family

control guide adapter:
  guide type (OpenPose, DWPose, depth, canny, segmentation, mask)
  pose guide PNG and JSON path inside the package pose_guides/ folder
  control weight, control_start, control_end
  target visibility rule: which body parts must remain visible despite the guide

style/LoRA stack adapter:
  style/concept LoRAs and their strengths
  conflict notes: which LoRAs fight identity, which fight anatomy, which fight pose

avatar/scene linkage:
  link to the avatar/scene playbook in references/ (e.g. AVATAR1_CYBERREALISTIC_PONY_V170_OPENPOSE_2026-05-01.md)
  link to the recipe in recipes/
  link to the WORKFLOW_INDEX.md entry slug
```

Splice rule:

```text
Adapter content gets spliced into the generic prompt blocks at fixed slots:
  identity anchor       -> "identity/body/model anchors" block in `Positive Prompt Blocks`
  model-family positives -> append to "quality" block
  model-family negatives -> append to "model-family blockers" in `Negative Prompt Blocks`
  control guide         -> recorded in pose/control guide manifest, not in prompt prose
  style/LoRA stack      -> recorded in run manifest, not in prompt prose
The blueprint stays generic. The adapter file (or the active workflow note) stays specific. Generated prompt blocks combine both.
```

Worked adapter example (Avatar1 + CyberRealistic Pony v17, repo state as of 2026-05-03):

```text
identity anchor:
  token: h4er1nface
  identity LoRA: Haerin_raw_identity_v3_strict28_facegeo_lowvram_cyberrealisticpony_v170_face_lora_2026-05-02.safetensors
  identity LoRA strength: 0.7 to 1.0 face-only test range

model-family adapter:
  checkpoint family: Pony / PDXL (CyberRealistic Pony v17)
  required positives: score_9, score_8_up, score_7_up, source_anime off, real photo
  required negatives: score_4, score_5, score_6, source_cartoon, source_3d, anime
  CLIP skip: -2
  sampler/scheduler defaults: dpmpp_2m_sde_gpu / karras

control guide adapter:
  guide type: OpenPose (body) + optional DWPose (face)
  guide path: package pose_guides/openpose/png/<guide_id>.png and json/<guide_id>.json
  control weight: 0.6 to 0.9 starting range
  target visibility rule: hands kept off the trigger crop unless the pose explicitly uses contact

style/LoRA stack adapter:
  body LoRA: PerfectBreastsPonyV2 at 0.4 to 0.6 (per Avatar1 baseline)
  conflict notes: do not stack body sliders with identity LoRA above 0.7 combined identity weight; check face crop after every change

avatar/scene linkage:
  avatar playbook: references/AVATAR1_CYBERREALISTIC_PONY_V170_OPENPOSE_2026-05-01.md
  recipe: recipes/cyberrealistic_pony_v170_avatar1_openpose.md
  workflow index slug: avatar1-cyberrealistic-pony-v170-openpose
```

The adapter example is a teaching artifact, not a model-family rule. Real adapter content for a new batch goes into the package or workflow note, not into this blueprint.

## Scene Engines

Use a scene engine when starting from a plain pose/exposure card.

### Performance Lens

The performer knowingly plays to the camera. Best for direct eye contact, frontal exposure, POV, studio sets, or avatar showcase outputs.

Useful details:

- Confident or shy direct gaze.
- Hands deliberately placed away from the target anatomy unless the pose requires contact.
- Clean camera path with no occluding props.
- Studio light, ring light, phone camera, tripod, mirror, bed-edge, hotel-room, or white-backdrop variants.

### Private-Room Lens

The set feels intimate and real, but still staged for the camera. Best for bedroom, bathroom, dressing-room, hotel, shower, or domestic scenes.

Useful details:

- Practical lamps, bathroom mirror light, window light, phone flash, rumpled sheets, towel, robe, scattered clothes.
- Skin texture, pressure marks, damp hair, uneven fabric, real room clutter.
- Strong crop rules so furniture does not hide the explicit target.

### Editorial Porn Lens

The image has adult-magazine composition: polished, readable, and intentionally lit. Best for hero stills, thumbnails, and premium set covers.

Useful details:

- Controlled pose line, clean silhouette, deliberate negative space.
- Glossy skin highlights, styled hair, makeup, luxe bedding, marble bathroom, leather chair, satin robe, glass wall, city light.
- Keep the target anatomy clear; do not let fashion styling become coverage.

### Raw Cam Lens

The image feels immediate and less polished, but the anatomy and pose still need to be readable. Best for phone POV, amateur-style, mirror, or casual set variants.

Useful details:

- Slight motion tension, flash highlights, natural skin imperfections, messy bed, imperfect framing that still preserves the target.
- Direct performer awareness of camera.
- Avoid fake UI, timestamps, watermarks, readable text, or platform branding.

### Environment-Pressure Lens

The setting explains the pose: doorway, counter, bed edge, sink, stool, shower wall, window, sofa arm, balcony rail, stage platform, studio cube.

Useful details:

- A physical support point for hips, knees, hands, back, or shoulders.
- One clear reason the camera sees the target anatomy.
- No busy objects in front of the target area.

## Card-To-Prompt Method (one card, any tier)

1. Write the explicit anchor in one line.
2. Pick one scene engine.
3. Add only the minimum setting details needed to make the pose believable.
4. Add camera/framing instructions that protect the target.
5. Add two to four texture details.
6. Add negative gates for the exact failure expected from the model family.
7. Generate a small seed batch.
8. Inspect full frame, face crop, hands/feet, and target anatomy.
9. Accept only outputs where the story and explicit target both read clearly.
10. Record accepted/rejected filenames and prompt deltas.

For batch generation, insert a matrix pass before step 1:

```text
matrix row -> compatibility check -> moodboard card -> final prompt -> small seed test -> review -> promote/reject
```

## Positive Prompt Blocks

Use these as categories, not as one giant prompt.

```text
adult subject:
adult 18+ performer, mature adult woman, adult facial structure, adult body proportions

explicit target:
<exact adult pose, exposure, anatomy, or sexual act target>

body mechanics:
<stance>, <hip angle>, <torso lean>, <hand placement>, <head direction>, <eye contact>, <weight shift>

camera:
<lens>, <camera height>, <distance>, <crop rule>, <focus priority>, <full body / half body / close-up>

scene:
<location>, <surface/support>, <set dressing>, <wardrobe state>, <prop if useful>

mood:
<confident / shy / teasing / intense / playful / raw / polished>, direct camera awareness

lighting:
<window light / softbox / phone flash / mirror bulbs / neon practical / warm lamp>, realistic skin highlights

texture:
skin pores, natural skin texture, pressure marks, stray hair, fabric wrinkles, rumpled sheets, fingerprints, condensation

quality:
photorealistic, coherent anatomy, realistic hands, realistic feet, natural joints, sharp face, clean target visibility
```

## Negative Prompt Blocks

Keep a reusable base and add scene-specific negatives.

```text
age gate:
underage, minor, child, teen, school, school uniform, youthful face, childlike proportions, age ambiguous

target blockers:
censored, mosaic, blur, covered target anatomy, hidden target anatomy, clothing blocking target, hand blocking target, prop blocking target

composition blockers:
cropped head, accidental foot crop, target out of frame, profile when direct gaze required, looking away when eye contact required

anatomy blockers:
extra limbs, fused fingers, broken hands, distorted feet, malformed anatomy, impossible joints, duplicated body parts

scene blockers:
watermark, logo, readable text, fake UI, social media overlay, random signage, clutter covering body

style blockers:
cartoon, anime, plastic skin, waxy skin, doll face, over-smoothed face, CGI, low detail, bad lighting
```

## Acceptance Gate

An output is not accepted unless all required gates pass.

| Gate | Pass condition |
| --- | --- |
| Adult gate | Subject reads clearly adult, not age-ambiguous or youth-coded. |
| Explicit gate | The exact adult target is visible and unambiguous. |
| Arousal gate | The image has a clear hook beyond visibility: gaze, tease/reveal, body invitation, tactile realism, or fantasy readability. |
| Beauty gate | Composition, palette, light, face, silhouette, and material contrast make the image attractive, not merely explicit. |
| Story gate | The scene explains the pose in one glance. |
| Composition gate | Visual hierarchy leads to the sexual trigger, with no prop/furniture/foreground coverage. |
| Palette gate | Skin, wardrobe, target anatomy, and background remain separated and readable. |
| Camera gate | Framing is intentional; no accidental crop hides important anatomy. |
| Anatomy gate | Face, hands, feet, limbs, joints, and target anatomy are coherent enough for production use. |
| Identity gate | For avatar/LoRA work, the face/body identity target is preserved. |
| Style gate | Output matches the chosen scene engine and model-family look. |
| Artifact gate | No text/logos/watermarks/UI junk, no pasted-looking repairs, no obvious generation artifacts. |

If the explicit target passes but the story is dead, reject or rework. If the story is strong but the target is hidden, reject. Production outputs need both.

## Scoring Rubric

Every reviewed output should receive numeric scores so batch selection is repeatable.

### Fast Triage (tier 1)

The full rubric has 16 fields. For 100-row batches at 4 seeds, that is 6400 score entries; nobody fills it in practice and selection collapses into vibes. Use fast triage first; only run the full rubric on outputs that survive.

Fast triage uses 4 fields with a hard fail-fast rule. Any single failure rejects the output before the full rubric runs.

| Field | Pass | Reject if |
| --- | --- | --- |
| `adult_gate_score` | 5 | < 5: subject reads age-ambiguous or youth-coded |
| `trigger_clarity_score` | 4 or 5 | < 4: primary sexual trigger not immediately readable |
| `anatomy_score` | 3 or higher | < 3: face/hands/feet/joints/target anatomy broken enough to disqualify |
| `artifact_score` | 4 or 5 | < 4: text/logos/UI/watermarks/pasted-repair damage visible |

Triage flow:

```text
inspect output
-> fast triage 4 fields
-> if any field fails the bar, mark rejected and record primary_rejection_reason; stop scoring
-> if all four pass, run the full rubric below for promotion decision
```

This keeps total scoring effort proportional to actual candidate output: most rejections are decided in 4 fields, full rubric only runs on the survivors.

### Full Rubric (tier 2)

Scale:

| Score | Meaning |
| --- | --- |
| `0` | Complete failure or unusable. |
| `1` | Severe failure; only useful as a diagnostic. |
| `2` | Partial read; not production usable. |
| `3` | Usable test output; needs improvement before promotion. |
| `4` | Strong output; candidate for accepted set. |
| `5` | Excellent output; promote and mine for future prompt rules. |

Core scores:

| Score field | What to judge |
| --- | --- |
| `adult_gate_score` | Subject reads clearly adult and not youth-coded. |
| `trigger_clarity_score` | Primary sexual trigger reads immediately. |
| `explicit_target_score` | Exact requested exposure/action/contact point is visible and unambiguous. |
| `arousal_score` | Gaze, body invitation, reveal tension, tactile realism, or fantasy readability creates a strong hook. |
| `beauty_score` | Face, pose line, composition, palette, light, and materials are attractive. |
| `story_readability_score` | Viewer understands the staged moment in one glance. |
| `pose_mechanics_score` | Body position feels physically plausible and supports visibility. |
| `wardrobe_mechanism_score` | Wardrobe explains the reveal instead of blocking it. |
| `set_design_score` | Furniture, props, and background support the pose without clutter. |
| `composition_score` | Visual hierarchy leads to trigger, face/gaze, and set in that order. |
| `palette_score` | Skin, wardrobe, target, and background separate clearly. |
| `camera_score` | Crop, distance, and angle protect the target and flatter the performer. |
| `anatomy_score` | Face, hands, feet, limbs, joints, and target anatomy are coherent. |
| `artifact_score` | Output is free of text, logos, watermarks, UI junk, and obvious generation damage. |
| `novelty_score` | The row contributes meaningful diversity to the batch. |
| `commercial_usability_score` | The image is strong enough for the intended production use. |

Promotion rule:

```text
Reject if adult_gate_score < 5.
Reject if trigger_clarity_score < 4.
Reject if explicit_target_score < 4.
Reject if anatomy_score < 3.
Reject if artifact_score < 4.
Promote only if arousal_score >= 4 and beauty_score >= 4.
Mark as diagnostic if the output teaches a useful fix but fails promotion.
```

Batch success rule:

```text
A card is stable only after multiple seeds score 4+ on trigger clarity, explicit target, arousal, beauty, composition, and artifact control.
```

### Abandonment Criteria

Promotion tells the assistant when to stop iterating because the card succeeded. Abandonment tells the assistant when to stop iterating because the card or path will not succeed without a structural change. Without an abandonment rule the loop runs forever on dead cards.

Trigger an abandonment decision when any of these is true:

| Signal | Meaning | Required action |
| --- | --- | --- |
| 12 seeds, no row reaches `trigger_clarity_score >= 4` | The trigger is fighting the model family or the prompt structure. | Stop tuning prompt prose. Switch model family or rewrite the trigger anchor. |
| 8 seeds, repeated `bad_anatomy` or `pose_impossible` rejection | Model family cannot render this pose without a control guide. | Add OpenPose/DWPose/depth guide, or simplify the pose family. |
| 8 seeds, repeated `target_hidden` rejection after wardrobe and crop changes | Wardrobe or set is structurally incompatible with the target. | Replace the wardrobe state or support object. Do not keep tuning negatives. |
| 8 seeds, repeated `identity_drift` for avatar/LoRA work | Identity weight, LoRA stack, or base checkpoint is incompatible. | Adjust identity adapter (token, LoRA strength, base model) before more prompt edits. |
| 8 seeds, all promote but `novelty_score <= 2` | Card is too close to an existing accepted row in the ledger. | Mark as duplicate; redirect seeds to underrepresented axes. |
| Any seed produces juvenile-coded, school-coded, coercive, intoxicated, unconscious, or hidden-camera output | Hard safety boundary hit. | Reject the card, not just the seed. Rewrite the prompt and/or set without those signals. Document the trigger that caused it. |

Abandonment is not failure logging. Record the decision plainly:

```text
card_id: <id>
abandoned_after: <n> seeds
abandonment_reason: <one of the signals above>
structural_change_attempted: <model family swap / control guide added / wardrobe replaced / identity adapter changed / card rewritten / card killed>
follow_up_card_id: <new card id when the path is rebuilt, or none>
```

Abandonment of one card does not abandon the batch. Move the seed budget to other cards in the matrix.

## Rejection Diagnosis

Every rejected output should receive one primary rejection reason. Do not write vague notes like "bad" or "meh."

Useful rejection reasons:

| Rejection reason | Meaning | First correction |
| --- | --- | --- |
| `target_hidden` | The primary target is covered, cropped, turned away, or obscured. | Move explicit target earlier; adjust camera/crop; add blocker negatives. |
| `dead_gaze` | Expression does not connect with viewer or story. | Add performer-aware gaze, mouth cue, or mirror gaze. |
| `explicit_but_flat` | Target is visible but not engaging. | Strengthen arousal hook, body invitation, tactile detail, or camera proximity. |
| `pretty_but_not_explicit` | Image is attractive but fails the production target. | Re-anchor explicit target and reduce scenic/fashion language. |
| `pose_impossible` | Body mechanics do not make sense. | Simplify pose; add support object; use pose guide. |
| `wardrobe_blocks` | Clothing fights the reveal. | Change wardrobe state or remove conflicting clothing. |
| `set_blocks` | Furniture, props, foreground, or clutter hides the target. | Move support object; simplify background; add sightline rule. |
| `palette_muddy` | Skin/wardrobe/background merge visually. | Change palette, accent color, or light contrast. |
| `bad_anatomy` | Hands, feet, face, joints, or target anatomy fail. | Use control/pose/inpaint path or reduce conflicting prompt details. |
| `identity_drift` | Avatar/LoRA identity fails. | Strengthen identity anchors or lower conflicting style/LoRA pressure. |
| `artifact_noise` | Text/logos/UI/watermarks/pasted repairs appear. | Add scene blockers and remove sign/screen/brand cues. |
| `duplicate_scene` | Output repeats an existing accepted row. | Change at least two dedupe axes before regenerating. |

## Failure Levers

| Failure | First lever | Second lever |
| --- | --- | --- |
| Target hidden by clothing | Move wardrobe state earlier; add target-blocker negatives. | Use mask/inpaint or pose/control guide. |
| Pose correct but scene generic | Add one scene engine and two texture details. | Add physical support point: bed edge, sink, counter, chair, rail. |
| Explicit but not arousing | Add a clear arousal hook: gaze, reveal tension, body invitation, tactile detail, or stronger kink/archetype signal. | Change camera distance or expression. |
| Explicit but not pretty | Improve palette, silhouette, face light, body line, and background separation. | Switch to a cleaner composition rule. |
| Story strong but anatomy wrong | Shorten story block; put body mechanics before setting. | Lower CFG or reduce conflicting LoRAs depending on model family. |
| Face looks too young | Strengthen adult gate; reject youth-coded styling. | Change face prompt, lighting, hairstyle, and makeup away from juvenile cues. |
| Cropping hides target | Put crop rule in camera block. | Change aspect ratio or guide image. |
| Composition feels flat | Add a leading line, support-object angle, foreground frame, or negative-space rule. | Change camera family or aspect ratio. |
| Palette muddies anatomy | Choose clearer skin/background separation and a controlled accent color. | Change wardrobe or lighting color. |
| Hands block target | Add explicit hand placement. | Use OpenPose/DWPose or pose reference. |
| Plastic/glossy AI look | Add skin texture and realistic light detail. | Reduce over-polished style terms and face restore strength. |
| Text/logos appear | Add no readable text/logos/signage. | Change setting away from signs/packaging/screens. |

## Batch Discipline

For a new moodboard card:

- Run 4 seeds first.
- Reject obviously failed mechanisms before scaling.
- For any promising card, run at least 8 to 12 total seeds before calling it stable.
- Review full frames plus crops of face, hands, feet, and target anatomy.
- Record accepted/rejected outputs in the relevant recipe, scene note, or `references/WORKFLOW_INDEX.md`.

One good image means the card is promising, not stable.

## File Naming

Recommended output tag:

```text
<slug>_<model-family>_<mechanism>_<variant>_s<seed>
```

Examples:

```text
hotel-mirror-front-exposure_pony_openpose_v1_s9410102
balcony-doorway-rear-exposure_sdxl_prompt_v2_s9761004
studio-cube-pov_exp120_openpose_v1_s1033007
```

## Generated Artifact Schemas

The blueprint should generate these artifact types for production batches. Keep headers stable so sheets, scripts, and future skills can parse them.

### Additive-Only Schema Rule

Once a TSV header has been used by a real batch, it is locked for backwards compatibility with already-generated packages and any consumer scripts that read them.

Rules:

```text
1. Never reorder existing columns. Column position is part of the contract.
2. Never rename existing columns. Consumers grep by name.
3. Never delete existing columns. Leave the column and write empty strings if no longer used.
4. New columns are appended on the right only.
5. New columns must have a sensible empty/default value so older rows remain parseable.
6. Document every header change in the `Changelog` section, with the affected schema name.
```

A header change is a structural change. Bump the `Changelog` with a new dated entry naming the affected schema (e.g. "added column `identity_drift_seen` to scorecard"). If the change cannot be additive (semantic redefinition of an existing column, type change, etc.), treat it as a new schema with a new name (e.g. `scorecard_v2.tsv`) instead of mutating the original.

### Batch Package INDEX Template

Every package must have an `INDEX.md` at its root. This is the first file a future assistant should read inside the package.

```text
# <batch_slug> Index

Date:
Status: draft / testing / active / stable / rejected
Blueprint source: references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md
Workflow / model family:
Operator request:
Primary production goal:
Primary explicit family:
Batch size:
Output aspect ratio:
Generated image policy: local assets under generated_images/; do not commit binaries unless explicitly approved.

Folder map:
- stories/:
- cards/:
- moodboards/:
- matrices/:
- ledgers/:
- manifests/:
- prompt_blocks/:
- pose_guides/openpose/png/:
- pose_guides/openpose/json/:
- pose_guides/openpose/source/:
- pose_guides/openpose/rejected/:
- pose_guides/dwpose/png/:
- pose_guides/dwpose/json/:
- pose_guides/dwpose/source/:
- pose_guides/dwpose/rejected/:
- generated_images/raw/:
- generated_images/accepted/:
- generated_images/rejected/:
- generated_images/diagnostic/:
- generated_images/contact_sheets/:

Core files:
- batch matrix:
- quota plan:
- variant ladder:
- anti-repetition ledger:
- prompt manifest:
- pose/control guide manifest:
- run manifest:
- review manifest:
- scorecard:

Current counts:
- matrix rows:
- cards:
- variants:
- pose guides:
- generated images:
- accepted:
- rejected:
- diagnostic:

Accepted cards:

Rejected cards:

Known blockers:

Next action:
```

### Batch Package README Template

```text
# <batch_slug>

Date:
Status: draft / testing / active / stable / rejected
Operator request:
Workflow / model family:
Primary explicit target:
Batch size:
Aspect ratio:
Output folder:

Generated from:
references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md

Artifacts:
- index:
- cards:
- stories:
- moodboards:
- batch matrix:
- variant ladder:
- quota plan:
- anti-repetition ledger:
- prompt manifest:
- pose/control guide manifest:
- run manifest:
- review manifest:
- scorecard:
- pose guides:
- generated images:

Current decision:
- promoted:
- needs revision:
- rejected:

Notes:
```

### Quota Plan TSV Header

Use this before writing the batch matrix.

```text
batch_slug	axis	value	target_count	current_count	status	notes
```

Example:

```text
hotel-reveal-100	fantasy_mode	casual intimate	25	0	open	quota seed
hotel-reveal-100	camera_family	mirror medium	15	0	open	quota seed
hotel-reveal-100	palette_family	warm hotel amber	20	0	open	quota seed
```

### Prompt Manifest TSV Header

The prompt manifest records final prompt blocks before generation.

```text
card_id	slug	status	workflow_model_family	variant	explicit_family	sexual_trigger	kink_cue	porn_archetype	fantasy_mode	scene_engine	positive_prompt_path	negative_prompt_path	positive_prompt_inline	negative_prompt_inline	aspect_ratio	seed_plan	steps_cfg_sampler_notes	control_guidance_notes	output_tag	notes
```

### Pose / Control Guide Manifest TSV Header

Use this when a card uses OpenPose, DWPose, depth, canny, segmentation, masks, or any other control input. OpenPose and DWPose PNG and JSON files should be stored under `pose_guides/<guide_type>/png/` and `pose_guides/<guide_type>/json/`.

```text
guide_id	card_id	slug	variant	guide_type	pose_family	orientation	source_path	png_path	json_path	workflow_node	control_weight	control_start	control_end	target_visibility_rule	status	primary_failure	linked_run_ids	notes
```

### Run Manifest TSV Header

The run manifest records what was actually generated.

```text
run_id	card_id	slug	variant	workflow_model_family	workflow_file	prompt_manifest_row	seed	width	height	steps	cfg	sampler	scheduler	checkpoint	lora_stack	control_stack	output_file	status	error_or_blocker	notes
```

### Review Manifest TSV Header

The review manifest records visual inspection and promotion decisions.

```text
review_id	run_id	card_id	slug	variant	output_file	review_status	primary_rejection_reason	adult_gate_pass	explicit_gate_pass	arousal_gate_pass	beauty_gate_pass	story_gate_pass	composition_gate_pass	palette_gate_pass	camera_gate_pass	anatomy_gate_pass	artifact_gate_pass	identity_gate_pass	accepted_output_tag	next_change	notes
```

### Scorecard TSV Header

Use this with the scoring rubric.

```text
review_id	run_id	card_id	slug	variant	output_file	adult_gate_score	trigger_clarity_score	explicit_target_score	arousal_score	beauty_score	story_readability_score	pose_mechanics_score	wardrobe_mechanism_score	set_design_score	composition_score	palette_score	camera_score	anatomy_score	artifact_score	novelty_score	commercial_usability_score	total_score	promotion_decision	primary_rejection_reason	notes
```

### Variant Ladder TSV Header

Use this to turn one card into controlled variants.

```text
card_id	slug	variant	preserved_trigger	change_lever	intensity_delta	story_delta	camera_delta	wardrobe_delta	set_delta	palette_delta	negative_delta	expected_risk	status	notes
```

### Anti-Repetition Ledger TSV Header

Use this for batches larger than 24 rows.

```text
card_id	slug	explicit_family	exposure_detail	pose_family	orientation	fantasy_mode	kink_cue	porn_archetype	setting_family	specific_setting	wardrobe_state	held_object	support_object	composition_rule	palette_family	lighting_family	camera_family	gaze	mouth_tongue	arousal_strategy	dedupe_signature	status	notes
```

### Series Plan TSV Header

Use this when one concept should produce a mini-gallery or video keyframe sequence.

```text
series_id	shot_id	card_id	slug	shot_order	shot_purpose	preserved_trigger	story_phase	camera_family	framing	pose_delta	wardrobe_delta	set_delta	palette_delta	texture_delta	acceptance_gate	notes
```

### Prompt Block File Template

Positive prompt block files should preserve category order.

```text
adult gate:

sexual trigger + explicit anchor:

arousal hook + viewer intensification:

body mechanics:

wardrobe/exposure:

composition/color:

camera/framing:

set/furniture/story:

lighting/mood:

texture/realism:

identity/body/model anchors:

quality:
```

Negative prompt block files should preserve blocker categories.

```text
age gate:

target blockers:

composition blockers:

anatomy blockers:

scene blockers:

style blockers:

model-family blockers:
```

## Operating Recipe (single scene and high-volume tracks)

Use this order for a single scene:

1. Fill the sexual trigger first.
2. Pick one primary kink cue.
3. Pick one porn archetype.
4. Pick one fantasy mode.
5. Write the explicit anchor.
6. Write the one-sentence fantasy/story reason.
7. Add viewer intensification and arousal hook.
8. Add body mechanics and wardrobe/exposure mechanism.
9. Add set designer details.
10. Add composition/color.
11. Add camera/light.
12. Add negatives and acceptance gates.
13. Generate 4 seeds, inspect, then iterate.

Use this order for high-volume batches:

1. Create the batch package folder under `references/prompts/<batch_slug>/`.
2. Create the required subfolders: `stories/`, `cards/`, `moodboards/`, `matrices/`, `ledgers/`, `manifests/`, `prompt_blocks/`, `pose_guides/`, and `generated_images/`.
3. Create `INDEX.md` from the `Batch Package INDEX Template`.
4. Create the package README from the `Batch Package README Template`.
5. Create the quota plan before writing prose prompts.
6. Fill the batch matrix columns.
7. Enforce quotas across explicit family, kink cue, porn archetype, fantasy mode, setting, composition, palette, and camera.
8. Reject incompatible rows.
9. De-duplicate rows before generation.
10. Create one moodboard card per promoted row.
11. Create one story file per promoted card when story is part of the concept.
12. Create variant ladder rows for the strongest cards.
13. Convert only compatible rows into final prompt blocks.
14. Create the prompt manifest.
15. Create a pose/control guide manifest when OpenPose, DWPose, or other control inputs are used.
16. Store OpenPose/DWPose PNG and JSON files inside `pose_guides/<guide_type>/`.
17. Test small batches per family before scaling.
18. Create the run manifest from actual generations.
19. Store generated images inside `generated_images/raw/`, then move reviewed outputs into `accepted/`, `rejected/`, or `diagnostic/`.
20. Inspect outputs visually and fill the review manifest.
21. Score outputs with the scorecard.
22. Update the anti-repetition ledger.
23. Update `INDEX.md` with current counts, accepted cards, rejected cards, blockers, and next action.
24. Promote, revise, or reject cards based on the acceptance gate and score thresholds.
25. Update the relevant workflow/scene note or `references/WORKFLOW_INDEX.md` when a reusable branch changes status.

## Chat-Only Output Mode

Some assistants run with no filesystem access (chat product, web sandbox, mobile app, voice assistant, restricted skill). They cannot create the package folder or write the TSV files. The blueprint must still be usable in that environment so the operator can paste the output into a real package later.

When the assistant has no file write capability:

1. Do not pretend to create files. Do not say "I have created `cards/AMB-0001.md`" when no file was written.
2. Produce the same artifact content inline as fenced blocks, named so the operator can drop them on disk verbatim.
3. Use the on-disk path the artifact would have had as the fence label or as a one-line comment above the fence.
4. Preserve the schema headers and field order from this blueprint. Do not abbreviate columns.
5. Tell the operator the on-disk paths and the order to write them in.

Inline equivalents per artifact:

| On-disk artifact | Chat-only equivalent |
| --- | --- |
| `references/prompts/<batch_slug>/INDEX.md` | Fenced markdown block labelled with that path. |
| `cards/<card_id>_<slug>.md` | Fenced markdown block per card. |
| `prompt_blocks/<card_id>_<slug>_positive.txt` | Fenced text block, one per card. |
| `prompt_blocks/<card_id>_<slug>_negative.txt` | Fenced text block, one per card. |
| `matrices/<batch_slug>_batch_matrix.tsv` | Fenced TSV block with the full header row and rows below. |
| `manifests/<batch_slug>_scorecard.tsv` | Fenced TSV block. |
| Pose guide PNG/JSON | Cannot be produced inline. State the path the operator should generate the guide into; describe the pose so the operator or a tooled assistant can render it. |
| Generated images | Cannot be produced inline. Same rule: state the target path under `generated_images/raw/` and the file naming pattern from `File Naming`. |

Tier interaction:

```text
chat-only + quick     -> always feasible: one card + two prompt blocks inline
chat-only + mini      -> feasible: cards + matrix + prompt blocks + scorecard inline; pose guides and images deferred to operator's tooled environment
chat-only + production -> partial: produce schemas and a starter set inline, mark which artifacts require a tooled environment, hand back to operator with explicit next-step list
```

Handback line at the end of every chat-only response:

```text
on-disk paths to create (in order):
1. references/prompts/<batch_slug>/INDEX.md
2. references/prompts/<batch_slug>/cards/<card_id>_<slug>.md
3. references/prompts/<batch_slug>/prompt_blocks/<card_id>_<slug>_positive.txt
4. references/prompts/<batch_slug>/prompt_blocks/<card_id>_<slug>_negative.txt
... etc, in dependency order ...
```

This keeps non-tooled models honest: they produce the same content shapes as tooled models, the operator does the file mechanics, and nothing pretends to have happened that did not.

## Moodboard Card Template

Copy this section when creating a new card.

```text
Date:
Slug:
Status: draft / testing / active / stable / rejected
Workflow / model family:
Output tag:

Sexual trigger:
Primary kink cue:
Porn archetype:
Explicit family:
Exposure detail:
Fantasy mode:
Archetype signal:

Fantasy/story lens:
Viewer intensification:
Arousal hook:
Beauty strategy:

Body mechanics:
- Stance/base:
- Hip angle:
- Torso angle:
- Head direction:
- Eye contact:
- Hand placement:
- Leg placement:
- Support point:
- Body-led sexual emphasis:

Wardrobe/exposure:
- Wardrobe state:
- Exposure mechanism:
- Held object:
- Held object purpose:
- What must not block the target:

Set designer:
- Location:
- Surface/support:
- Furniture:
- Background depth:
- Foreground hazards:
- Sightline to target:

Composition/color:
- Composition rule:
- Visual hierarchy:
- Leading lines:
- Negative space:
- Palette family:
- Accent color:
- Skin/background separation:

Camera/light:
- Camera family:
- Framing:
- Camera height:
- Lens feel:
- Focus priority:
- Lighting family:
- Skin highlights:

Texture details:
- texture_1:
- texture_2:
- texture_3:

Positive prompt blocks:
- adult gate:
- sexual trigger + explicit anchor:
- arousal hook + viewer intensification:
- body mechanics:
- wardrobe/exposure:
- composition/color:
- camera/framing:
- set/furniture/story:
- lighting/mood:
- texture/realism:
- identity/body/model anchors:
- quality:

Negative prompt blocks:
- age gate:
- target blockers:
- composition blockers:
- anatomy blockers:
- scene blockers:
- style blockers:

Acceptance gate:
- adult subject reads clearly 18+:
- sexual trigger reads first:
- arousal hook is clear:
- image is beautiful enough to keep:
- explicit target is visible:
- kink cue supports the trigger:
- porn archetype reads quickly:
- fantasy mode is consistent:
- wardrobe reveals rather than covers:
- set/furniture does not block:
- composition points first to the trigger:
- palette separates skin/wardrobe/target/background:
- face/hands/feet/anatomy pass:
- no text/logos/UI/watermarks:

Variant ladder:
- baseline:
- intimate:
- explicit_plus:
- editorial:
- raw_cam:
- story_plus:

Anti-repetition signature:
- compatibility_signature:
- dedupe_signature:
- repeated axes to avoid:

Scoring plan:
- required minimums:
- likely failure risks:
- primary rejection reason if failed:

Test log:
- seeds:
- accepted:
- rejected:
- next change:
```

## Batch Matrix TSV Header

Use this header for spreadsheet or TSV batch planning:

```text
batch_slug	row_id	card_id	status	sexual_trigger	kink_cue	porn_archetype	explicit_family	exposure_detail	fantasy_mode	archetype_signal	fantasy_story	viewer_intensifier	arousal_hook	beauty_strategy	pose_family	orientation	wardrobe_state	held_object	support_object	setting_family	specific_setting	set_designer_notes	composition_rule	palette_family	accent_color	lighting_family	camera_family	gaze	mouth_tongue	mood	texture_1	texture_2	negative_focus	story_beat	acceptance_gate	scene_engine	shot_purpose	compatibility_signature	dedupe_signature	variant_plan	generation_priority	notes
```

Example rows:

```text
example-batch	1	AMB-0001	draft	visible vulva/pussy exposure	self-display	hotel robe reveal	vulva/pussy exposure	full target visible	casual intimate	hotel robe reveal	hotel robe reveal	shy direct gaze and robe tension	clear reveal plus direct gaze	warm skin, robe contrast, clean sightline	bed-edge lean	three-quarter front	robe open	robe belt	bed edge	luxury hotel	hotel room	rumpled bed behind performer, lamp behind shoulder, clear lower-body sightline	trigger-first hierarchy	warm hotel amber	red robe belt	warm lamp	eye-level full-body	direct eye contact	parted lips	shy	rumpled sheets	skin pores	no clothing blocking target	robe reveal at bed edge	adult gate plus explicit target visible	private-room	primary explicit still	vulva/pussy exposure+full target visible+bed-edge lean+three-quarter front+eye-level full-body+robe open+bed edge	vulva/pussy exposure|bed-edge lean|three-quarter front|robe open|bed edge|luxury hotel|eye-level full-body|warm hotel amber	baseline,intimate,editorial	high	example
example-batch	2	AMB-0002	draft	underboob reveal	wardrobe fetish	amateur bedroom	breast exposure	underboob	raw-cam performance	private bedroom shirt lift	private bedroom shirt lift	lifted chest and fabric tension	fabric lift creates tease/reveal	soft daylight, clean torso silhouette	standing frontal	front-facing	crop top lifted	crop top hem	doorframe	private bedroom	bedroom	open doorframe support, clean wall behind torso, no foreground clutter	rule-of-thirds face/target diagonal	soft daylight cream	pink crop top	window light	chest-level medium	direct eye contact	subtle smile	teasing	fabric wrinkles	skin highlights	no hands covering target	shirt lift in doorway	adult gate plus target breast exposure visible	raw-cam	face-gaze-led	breast exposure+underboob+standing frontal+front-facing+chest-level medium+crop top lifted+doorframe	breast exposure|standing frontal|front-facing|crop top lifted|doorframe|private bedroom|chest-level medium|soft daylight cream	baseline,raw_cam,story_plus	medium	example
example-batch	3	AMB-0003	draft	rear/ass presentation	staged voyeur	kitchen/counter lean	ass/rear exposure	rear target visible	staged voyeur	counter lean	counter lean	over-shoulder gaze and hip presentation	over-shoulder glance pulls viewer back	strong hip line, uncluttered counter, dark accent	counter lean	three-quarter rear	thong displaced	phone	counter edge	kitchen/counter	loft counter	counter edge supports hands, chair angled away from target, uncluttered floor	over-shoulder triangle	flash-photo neutral	black thong	softbox	over-shoulder	glancing back	parted lips	confident	pressure marks	fabric tension	no fabric blocking target	counter lean with aware glance	adult gate plus rear target visible	environment-pressure	body-led	ass/rear exposure+rear target visible+counter lean+three-quarter rear+over-shoulder+thong displaced+counter edge	ass/rear exposure|counter lean|three-quarter rear|thong displaced|counter edge|kitchen/counter|over-shoulder|flash-photo neutral	baseline,explicit_plus,raw_cam	high	example
```

## Worked Example: AMB-0001 (hotel robe reveal, vulva exposure)

This example exists only to teach the schemas. It is a teaching artifact inside the blueprint, not a real production card. Real cards live under `references/prompts/<batch_slug>/cards/`. See `Roles: Blueprint vs Generated Artifacts`.

The example walks one row from the `Batch Matrix TSV Header` through to a filled card, positive and negative prompt blocks, a matrix row, and a scorecard row.

Scenario: operator asked for one hotel-robe reveal scene with visible vulva exposure, casual intimate fantasy mode, on the Avatar1 + CyberRealistic Pony v17 stack. Tier: `quick`.

### Filled moodboard card (cards/AMB-0001_hotel-robe-bed-edge.md)

```text
Date: 2026-05-03
Slug: hotel-robe-bed-edge
Status: testing
Workflow / model family: Avatar1 + CyberRealistic Pony v17 (Pony / PDXL)
Output tag: hotel-robe-bed-edge_pony_openpose_v1

Sexual trigger: visible vulva exposure
Primary kink cue: self-display (robe opened to camera)
Porn archetype: hotel robe reveal
Explicit family: vulva/pussy exposure
Exposure detail: full target visible, lower body unobstructed
Fantasy mode: casual intimate
Archetype signal: hotel robe reveal

Fantasy/story lens: Performer sits at the edge of a hotel bed and lets the robe fall open toward the camera in a private moment.
Viewer intensification: shy direct gaze, parted lips, robe belt held loosely, lamp-side warm skin highlight, knees parted just enough to clear sightline
Arousal hook: Viewer first notices the open robe and lower-body exposure, then the shy direct gaze pulls attention back, while the rumpled bed and warm lamp make the moment feel specific.
Beauty strategy: warm hotel amber palette, clean lower-body silhouette against rumpled white sheets, robe contrast for skin separation

Body mechanics:
- Stance/base: seated at the edge of the bed, weight on hands behind hips
- Hip angle: hips squared to camera, slight forward tilt
- Torso angle: relaxed back lean, shoulders down
- Head direction: face to camera
- Eye contact: shy direct gaze
- Hand placement: one hand resting on robe belt, other hand on bed beside hip; hands kept clear of the lower-body crop
- Leg placement: knees parted to clear sightline, feet flat on floor
- Support point: bed edge under hips and hands behind hips
- Body-led sexual emphasis: open robe framing the lower body and chest; hip line readable

Wardrobe/exposure:
- Wardrobe state: white hotel robe, fully open down the front
- Exposure mechanism: robe gravity falls open from belt loosened
- Held object: robe belt
- Held object purpose: explains why the robe is open and keeps the hand off the trigger
- What must not block the target: hands, robe panel, sheet, prop

Set designer:
- Location: hotel bedroom, edge of bed
- Surface/support: bed edge
- Furniture: bed with rumpled white sheets, nightstand with warm lamp behind shoulder
- Background depth: dim hotel room, curtain edge in soft focus
- Foreground hazards: no foreground objects in lower-body sightline
- Sightline to target: clear from camera to lower body

Composition/color:
- Composition rule: trigger-first hierarchy, lower body in central thirds
- Visual hierarchy: lower-body trigger -> face/gaze -> rumpled bed
- Leading lines: bed edge line into the body, robe lapel lines into the chest and lower body
- Negative space: behind the body and above the head
- Palette family: warm hotel amber
- Accent color: red robe belt
- Skin/background separation: warm lamp on skin against cool dim room

Camera/light:
- Camera family: eye-level full-body
- Framing: full body, vertical 4:5
- Camera height: eye-level seated, slightly below performer's eye line
- Lens feel: 35mm, mild compression
- Focus priority: lower body and face both in focus, soft falloff to bed and lamp
- Lighting family: warm lamp practical, soft ambient fill
- Skin highlights: warm rim from lamp on shoulder and thigh, soft fill on torso

Texture details:
- texture_1: rumpled white sheets behind hips
- texture_2: natural skin texture, no plastic gloss
- texture_3: robe terrycloth weave catching the lamp

Positive prompt blocks: see prompt_blocks/AMB-0001_hotel-robe-bed-edge_positive.txt
Negative prompt blocks: see prompt_blocks/AMB-0001_hotel-robe-bed-edge_negative.txt

Acceptance gate:
- adult subject reads clearly 18+: required
- sexual trigger reads first (vulva exposure): required
- arousal hook is clear (shy gaze + open robe tension): required
- image is beautiful enough to keep (palette, light, silhouette): required
- explicit target is visible (lower body unobstructed): required
- kink cue supports the trigger (self-display via opened robe): required
- porn archetype reads quickly (hotel robe reveal): required
- fantasy mode is consistent (casual intimate, not staged glamour): required
- wardrobe reveals rather than covers: required
- set/furniture does not block: required
- composition points first to the trigger: required
- palette separates skin/wardrobe/target/background: required
- face/hands/feet/anatomy pass: required
- no text/logos/UI/watermarks: required

Variant ladder:
- baseline: as written above
- intimate: closer crop, dimmer lamp, softer gaze, more skin texture
- explicit_plus: stronger hip angle, lower camera height, robe pulled wider
- editorial: cleaner sheet styling, controlled key light, glossier skin
- raw_cam: phone-flash neutral palette, direct camera address, simpler background
- story_plus: add room-service tray on the nightstand to fix the moment in time

Anti-repetition signature:
- compatibility_signature: vulva/pussy exposure+full target visible+seated bed-edge+three-quarter front+eye-level full-body+robe open+bed edge
- dedupe_signature: vulva/pussy exposure|seated bed-edge|three-quarter front|robe open|bed edge|luxury hotel|eye-level full-body|warm hotel amber
- repeated axes to avoid in next batch: hotel + robe + bed edge if accepted; rotate to bathroom mirror, balcony doorway, or shower glass

Scoring plan:
- required minimums: trigger_clarity 4+, explicit_target 4+, anatomy 3+, artifact 4+
- likely failure risks: hands drifting onto target; robe overlap covering trigger; identity drift on face crop
- primary rejection reason if failed: target_hidden or identity_drift

Test log:
- seeds: 9410101, 9410102, 9410103, 9410104
- accepted: (fill after generation and review)
- rejected: (fill after generation and review)
- next change: (fill after generation and review)
```

### Filled positive prompt block (prompt_blocks/AMB-0001_hotel-robe-bed-edge_positive.txt)

```text
adult gate:
adult 18+ performer, mature adult woman, adult facial structure, adult body proportions

sexual trigger + explicit anchor:
visible vulva exposure, lower body unobstructed, robe fully open down the front

arousal hook + viewer intensification:
shy direct gaze to camera, parted lips, robe belt held loosely, warm lamp on skin

body mechanics:
seated at the edge of a hotel bed, weight on hands behind hips, hips squared to camera, slight forward tilt, knees parted to clear sightline, feet flat on floor, hands clear of lower-body crop

wardrobe/exposure:
white hotel robe fully open, robe panels framing torso and lower body, robe belt held in one hand

composition/color:
trigger-first hierarchy with lower body in central thirds, warm hotel amber palette, red robe belt as accent, warm lamp skin highlight against cool dim room

camera/framing:
eye-level full-body, 35mm lens feel, vertical 4:5 framing, focus on lower body and face, soft falloff to bed and lamp

set/furniture/story:
hotel bedroom, edge of bed, rumpled white sheets, nightstand with warm lamp behind shoulder, dim curtain edge in soft focus, robe just fallen open in a private moment

lighting/mood:
warm practical lamp key, soft ambient fill, warm rim on shoulder and thigh, intimate hotel room mood

texture/realism:
natural skin texture, fine pores, robe terrycloth weave catching the lamp, rumpled sheet folds, warm lamp glow

identity/body/model anchors:
h4er1nface, Haerin face structure preserved

quality:
photorealistic, coherent anatomy, realistic hands, realistic feet, sharp face, clean target visibility, score_9, score_8_up, score_7_up, real photo
```

### Filled negative prompt block (prompt_blocks/AMB-0001_hotel-robe-bed-edge_negative.txt)

```text
age gate:
underage, minor, child, teen, school, school uniform, youthful face, childlike proportions, age ambiguous

target blockers:
censored, mosaic, blur, robe panel covering target, hand on lower body, sheet over lower body, prop in front of target, crossed legs hiding target

composition blockers:
cropped head, accidental foot crop, target out of frame, profile when direct gaze required, looking away when eye contact required

anatomy blockers:
extra limbs, fused fingers, broken hands, distorted feet, malformed anatomy, impossible joints, duplicated body parts

scene blockers:
watermark, logo, readable text, fake UI, social media overlay, random signage, hotel brand text, tv screen text, clutter covering body

style blockers:
cartoon, anime, plastic skin, waxy skin, doll face, over-smoothed face, CGI, low detail, bad lighting

model-family blockers:
score_4, score_5, score_6, source_cartoon, source_3d, anime, illustration
```

### Matching batch matrix row (matrices/<batch_slug>_batch_matrix.tsv)

```text
hotel-reveal-quick	1	AMB-0001	testing	visible vulva exposure	self-display	hotel robe reveal	vulva/pussy exposure	full target visible	casual intimate	hotel robe reveal	performer lets the robe fall open toward the camera in a private moment at the bed edge	shy direct gaze with open robe tension	open robe + shy gaze pulls viewer back	warm skin against rumpled white sheets, red belt accent	seated bed-edge	three-quarter front	robe open	robe belt	bed edge	luxury hotel	hotel bedroom	rumpled bed behind performer, lamp behind shoulder, clear lower-body sightline	trigger-first hierarchy	warm hotel amber	red robe belt	warm lamp	eye-level full-body	shy direct gaze	parted lips	intimate	rumpled sheets	skin pores	no clothing blocking target	robe just fallen open at bed edge	adult gate plus vulva target visible	private-room	primary explicit still	vulva/pussy exposure+full target visible+seated bed-edge+three-quarter front+eye-level full-body+robe open+bed edge	vulva/pussy exposure|seated bed-edge|three-quarter front|robe open|bed edge|luxury hotel|eye-level full-body|warm hotel amber	baseline,intimate,explicit_plus	high	teaching example - quick tier
```

### Matching scorecard row template (manifests/<batch_slug>_scorecard.tsv)

The scorecard row is filled after visual inspection. Header and an example pre-promotion row:

```text
review_id	run_id	card_id	slug	variant	output_file	adult_gate_score	trigger_clarity_score	explicit_target_score	arousal_score	beauty_score	story_readability_score	pose_mechanics_score	wardrobe_mechanism_score	set_design_score	composition_score	palette_score	camera_score	anatomy_score	artifact_score	novelty_score	commercial_usability_score	total_score	promotion_decision	primary_rejection_reason	notes
RV-0001	RUN-0001	AMB-0001	hotel-robe-bed-edge	baseline	hotel-robe-bed-edge_pony_openpose_v1_s9410102.png	5	4	4	4	4	4	4	4	3	4	4	4	3	5	3	4	63	promote		fast triage passed; full rubric promoted; minor set clutter behind nightstand to clean on next pass
```

This single row pattern repeats for every reviewed seed.

### Adapter content used by AMB-0001

The model-family and identity values above came from the `Identity / Model-Family Adapter` worked example. The blueprint stays generic; the adapter and this card are where Pony / Avatar1 specifics enter.

## Skill Conversion Block

This section is the quotable wrapper for turning the blueprint into a GPT skill, Claude skill, local assistant system prompt, or repo agent instruction. It is the canonical MD form of the wrapper — providers that load skills (Claude `SKILL.md`, GPT skill manifests, etc.) must mirror this section verbatim in intent and stay in sync with it.

The wrapper is production-tier only. There is no quick mode and no mini mode in any skill or assistant invocation built from this section. The blueprint itself still documents quick/mini tiers because they are valid for direct manual use, but a skill, assistant, or agent invoking this wrapper must refuse to deliver a quick or mini package and stop instead — let the operator either commit to a production package or invoke a separate quick/mini skill if one exists.

Skill name:

```text
adult-moodboard-blueprint
```

Skill purpose:

```text
Plan and produce full production-tier moodboard packages for batch adult image and video production. Convert explicit adult production targets into the full package — folder, INDEX, moodboard cards, batch matrices, prompt blocks, manifests, scorecards, and anti-repetition ledgers — by reading this single-file blueprint and applying its production-tier rules. Planning-only: does not queue image/video runs and does not wrap project-specific runner pipelines.
```

Provider-agnostic rule:

```text
Do not assume a specific LLM provider, image model, sampler, checkpoint, LoRA, node pack, or hosted service. Use this blueprint for concept, prompt, matrix, and review structure. Pull model-family settings from the active workflow or repo note.
```

Scope:

```text
In scope:
- Plan a full production-tier moodboard batch for explicit adult image or video work.
- Produce the full package: folder, INDEX, README, cards, moodboards, stories, batch matrices, quota plans, variant ladders, anti-repetition ledgers, prompt blocks, prompt/run/review manifests, scorecards, pose-guide folders, generated-image folders.
- Apply the Identity / Model-Family Adapter to splice model-family and identity values into generic prompt blocks.
- Run fast triage and the full rubric over inspected outputs the operator points at.
- Run the accepted-set diversity audit after a promotion pass.
- Apply abandonment criteria to dead cards.
- Update the operator's workflow index when a card or scene branch changes status.

Out of scope:
- Quick-tier or mini-tier output. Do not deliver a single card, a 4-card sketch, or any reduced package as a wrapper result. If the operator's request would naturally be a quick or mini batch, name that explicitly and stop.
- Queuing image/video runs. The operator runs the queue command themselves; the wrapper does not call repo runner scripts or hosted generation services.
- Wrapping or interacting with project-specific runner pipelines (for example, repo-internal exposure or training pipelines). They have their own dedicated workflows.
- LoRA training orchestration.
- Inventing model-family settings. Pull those from the active workflow note or the Identity / Model-Family Adapter slot.
- Claiming acceptance from a single seed. Acceptance requires multiple inspected seeds per Batch Discipline.
```

Canonical blueprint resolution:

```text
This file (ADULT_MOODBOARD_SYSTEM_2026-05-03.md) is the single source of truth. No hardcoded absolute path lives in the wrapper — resolve it on every invocation in this order, stopping at the first hit:

1. OpenRepose mode — if the OpenRepose detection in the OpenRepose dual-mode operation block matches, the blueprint is `<OPENREPOSE_ROOT>/.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md`. Do not fall back further when in this mode.
2. Operator-supplied path for the current turn.
3. Environment variable `AMOOD_BLUEPRINT` if set.
4. Walk up from cwd looking for `comfyui-workbench/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md`; use it if found.
5. Ask the operator for the path. Do not proceed from memory — the operator may have iterated the blueprint since the wrapper was written.

The blueprint has a Changelog section near the top. Read it on every invocation so the wrapper catches structural changes between iterations. When reading tier-related sections, treat any `quick` or `mini` guidance as out of scope for the wrapper; only the production-tier sequence, package contract, matrices, scorecards, ledgers, and audits apply.
```

Required boot sequence:

```text
Every invocation:

1. Load the blueprint from the path above. If absent, ask the operator.
2. Read the Changelog so structural changes are caught.
3. Read Roles, Identity / Model-Family Adapter, and the production-tier portion of the Operating Recipe. Skip the quick and mini rows of the Tier Table — they do not apply to the wrapper.
4. Restate the operator's input contract (explicit target, workflow/model family, must-include, must-avoid). If the operator's framing implies a quick or mini batch, surface that conflict before producing anything.
5. Confirm the Identity / Model-Family Adapter values. Propose values from the closest avatar/scene playbook in the active repo if the operator did not specify, then ask to confirm before producing prompt blocks.

Do not skip the boot sequence. The blueprint is long and changes often; producing artifacts from memory is the most likely failure mode.
```

Workflow per turn:

```text
Turn 1 — intake and adapter confirmation:
  Load the blueprint, confirm production package, propose the Identity / Model-Family Adapter from the closest playbook, ask the operator to confirm adapter and any must-include / must-avoid.

Turn 2 — produce the full production package:
  Create `references/prompts/<batch_slug>/` (or the OpenRepose path under Mode B) containing INDEX.md, README.md, cards/, moodboards/, stories/, matrices/ (batch_matrix.tsv, quota_plan.tsv, variant_ladder.tsv, anti_repetition_ledger.tsv), prompt_blocks/, manifests/ (prompt_manifest.tsv, run_manifest.tsv, review_manifest.tsv, scorecard.tsv skeleton), generated_images/ (.gitignore, raw/, accepted/, rejected/, diagnostic/), and pose-guide folders when the workflow needs them.
  Every section is required. Do not skip moodboards, stories, quota plan, variant ladder, anti-repetition ledger, or any manifest because the batch is "small". A small production batch is still a production package.
  Hand back to the operator: package path, axis coverage summary, what each card is testing, and the queue command they should run themselves (just the path to the API JSON or runner script — the wrapper does not queue).

Turn 3 — operator runs the queue and points the wrapper at `generated_images/raw/`.

Turn 4 — review and score:
  1. Run fast triage (4 fields, fail-fast) on every output.
  2. Run the full rubric only on triage survivors.
  3. Sort files into accepted/, rejected/, diagnostic/.
  4. Populate `manifests/<batch_slug>_scorecard.tsv` with one row per output.
  5. Update the anti-repetition ledger.
  6. Run the accepted-set diversity audit; record TSV per axis.
  7. Apply abandonment criteria — flag cards meeting any Abandonment signal with the structural change required.
  8. Update INDEX.md with current counts, accepted cards, rejected cards, blockers, next action.

Turn 5 — promotion and next-batch planning:
  1. Promote stable cards into the right scene/workflow branch.
  2. Update the active repo's workflow index for any branch that changed status.
  3. Propose the next batch focused on the priority axes from the diversity audit.
```

Boundary with the image/video pipeline:

```text
The wrapper plans, produces artifacts, scores, and audits. It does not generate pixels.

- Pixel generation: the operator runs ComfyUI (or any equivalent image/video stack) and queues runs themselves — by loading the produced API JSON, by running their own runner script, or by any workflow they prefer. The wrapper stays planning-only.
- Visual review: the operator opens images and may invoke a separate visual-QA assistant or skill. The wrapper consumes the resulting accepted/rejected sorting and writes the scorecard.
- Acceptance: the operator owns acceptance. The wrapper records it.

Do not couple the wrapper to repo-internal runner scripts or pipelines (for example, exposure or training pipelines). Those have their own owners.
```

OpenRepose dual-mode operation:

```text
The wrapper always writes the canonical TSV package. Where the package lands and whether it is also pushed into Postgres depends on whether the wrapper was invoked inside an OpenRepose repo.

Detection:
  On boot, walk up from the current working directory looking for `.gov/topology.yaml`. If found and the file contains `name: OpenRepose` under the `project:` block, set `OPENREPOSE_ROOT` to the directory holding `.gov/`. Otherwise the wrapper is in standalone mode.

Mode A — Standalone (no OpenRepose detected):
  - Blueprint path resolved via the Canonical blueprint resolution order (operator / env / workbench walk-up / ask).
  - Package output at `references/prompts/<batch_slug>/`.
  - No DB persistence; the TSV package is the artifact.

Mode B — Inside OpenRepose:
  Five changes apply for the invocation:

  1. Blueprint path is `<OPENREPOSE_ROOT>/.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md`. The in-repo copy is the version the I3 spec lock pins. Do not fall back to a workbench path even if one exists.

  2. Package output is `<OPENREPOSE_ROOT>/outputs/library/<project_slug>/<batch_slug>/` per `openrepose_amood_v0_1.md`. Resolve `project_slug` via `project_list` (or create with `project_create` first); use the batch_slug the operator names. Sanitize both for the OpenRepose Naming Convention (no spaces, kebab-case) before sending.

  3. Postgres ingest — after the TSV package is on disk, push it through the OpenRepose dispatcher so it lands in the AMood tables. Send on whichever channel responds first:
     - Preferred: POST http://127.0.0.1:8765/command with
       {"command":"init_batch_package","args":{"project_slug":"...","batch_slug":"...","package_path":"<abs>"}}
       then
       {"command":"amood_import_tsv","args":{"package_path":"<abs>"}}
     - Fallback: drop both payloads as JSON files into `<OPENREPOSE_ROOT>/outputs/.runtime/inbox/` named `<UTC-ms>_init_batch_package.json` and `<UTC-ms+1>_amood_import_tsv.json`. The inbox processes mtime-ascending, one at a time.
     If both channels fail, do not pretend the import happened. Hand back the package path and the two payloads verbatim.

  4. Adult Production Boundary acknowledgement — before issuing any dispatcher command, read `<OPENREPOSE_ROOT>/outputs/.runtime/state.json` and honor the `adult_production_boundary` object (RUL-000). Reading it is the acknowledgement step.

  5. Triage / scoring (turn 4) — when the operator points at outputs, prefer dispatcher commands (`intake_register_output`, `intake_soft_accept`, `intake_reject`, `accepted_set_audit`) over local TSV manipulation. The local `scorecard.tsv` stays as the operator-readable mirror; the DB is the system of record.

Caveats:
  - The I3 implementation iteration may not have shipped yet. Until it has, the dispatcher will reject `init_batch_package`, `amood_import_tsv`, `intake_register_output`, `accepted_set_audit`, etc. as unknown commands. Run Mode B for the file layout, skip the dispatcher calls, and tell the operator the import is queued in the inbox for when the implementation ships.
  - The wrapper never edits `.gov/`, `.product/`, or any tracked file in OpenRepose — those are operator / workpacket territory. Mode B writes only under `outputs/library/<project>/<batch>/` and `outputs/.runtime/inbox/`.
```

Chat-only mode:

```text
When invoked in an environment without filesystem access:

1. Do not pretend files were created.
2. Produce all artifacts inline as fenced blocks, labelled with the on-disk path they would have used.
3. End with the Chat-Only Output Mode "on-disk paths to create (in order)" handback line so the operator can drop them on disk verbatim.

The blueprint's Chat-Only Output Mode covers the full equivalence table. Apply only the production-tier portion of that table.
```

Update rules:

```text
After every batch handoff:

1. Update the package INDEX.md with current counts, accepted, rejected, blockers, next action.
2. Update the active repo's workflow index for any reusable branch that changed status (a card promoted into a scene branch, a card abandoned with a documented reason, a new package created).
3. If the operator iterates on the blueprint itself, append a Changelog entry inside ADULT_MOODBOARD_SYSTEM_2026-05-03.md and bump the entry in the workflow index.

Do not update the blueprint silently. Structural changes go in the changelog with a date and a one-line reason.
```

Hard rules:

```text
- Production package only. No quick, no mini, no abbreviated handoff. If the operator wants something lighter, name it and stop; do not improvise a smaller wrapper result.
- Build from the explicit target outward. The trigger is the anchor; the story supports it.
- Reject hidden-camera, spycam, asleep, intoxicated, unconscious, juvenile-coded, school-coded, or coercive framing at the row level — not at the seed level. A card that produces those outputs gets killed, not just reseeded.
- One primary kink cue + one porn archetype + one explicit trigger per card. Do not stack.
- A passing API call, saved file, or single lucky seed is not a pass. Acceptance requires multiple inspected seeds per Batch Discipline.
- Do not split the blueprint into separate files unless the operator explicitly asks. Generated artifacts go in the package folder; the blueprint stays single-file.
```

Required assistant behavior:

```text
1. Identify the explicit target and explicit family.
2. Choose or request the active workflow/model family.
3. Create quotas before writing high-volume rows.
4. Fill the matrix before writing final prompt prose.
5. Reject incompatible rows before generation.
6. Create moodboard cards only from compatible rows.
7. Create variants with controlled levers, not random extra concepts.
8. Create prompt blocks in the required assembly order.
9. Store OpenPose/DWPose PNG and JSON files inside the package pose-guide folders.
10. Store generated images inside the package generated-image folders.
11. Create manifests and scorecards for actual generation runs.
12. Review visually and score outputs before accepting.
13. Update ledgers and package INDEX so future batches avoid repetition.
14. Keep provider/model-specific settings outside this blueprint unless they are copied into a generated artifact for the active workflow.
```

Provider portability:

```text
This wrapper is provider-agnostic. A Claude skill, GPT skill, local-model system prompt, or chat-only assistant follows the same blueprint by reading this canonical file and applying this Skill Conversion Block. Changes to behavior land in the blueprint first, then propagate to whichever skill wrappers exist.
```

Skill input schema:

```text
explicit_target:
workflow_model_family:
batch_size:
production_goal:
must_include:
must_avoid:
preferred_fantasy_modes:
preferred_settings:
preferred_wardrobe:
preferred_camera:
preferred_palette:
identity_or_avatar:
known_model_failures:
output_package_slug:
```

Skill output schema:

```text
summary:
package_path:
package_index:
created_artifacts:
matrix_rows:
cards_created:
variants_created:
pose_guides_created:
generation_ready_prompts:
review_requirements:
known_risks:
next_action:
```

## Fresh Assistant Checklist (production tier)

1. Run `.\CUIstart`.
2. Read this note.
3. Identify the exact workflow/model family before writing final prompts.
4. For small work, create a moodboard card, prompt blocks, and scoring plan.
5. For production work, create the batch package folder, required subfolders, and `INDEX.md` before creating content.
6. Put stories, moodboards, prompt blocks, matrices, manifests, pose guides, and generated images inside that package.
7. Store OpenPose/DWPose PNG and JSON files under `pose_guides/<guide_type>/`.
8. Fill the quota plan and batch matrix before writing prose prompts.
9. Run compatibility and dedupe checks.
10. Choose or create moodboard cards from compatible rows only.
11. Put the sexual trigger and explicit anchor before story details.
12. Create prompt manifest, pose/control manifest when needed, and run manifest entries before generation.
13. Generate a small batch.
14. Store generated images inside `generated_images/raw/`, then sort reviewed files into `accepted/`, `rejected/`, or `diagnostic/`.
15. Inspect visually before accepting.
16. Fill the review manifest and scorecard.
17. Update the anti-repetition ledger and package `INDEX.md`.
18. Document prompt deltas, accepted outputs, rejected outputs, and blockers.
