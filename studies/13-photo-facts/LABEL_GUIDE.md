# Photo label guide (agent labeller, public replica)

This is the production label guide with two changes: the `offer` field is dropped (it needs the
listing's own text, which public photos do not have), and contact sheets come from
`run.py sheets` instead of the production photo folder. Field names, options and definitions are
otherwise production's, word for word.

**Provenance:** the agent labels in `data/agent_labels/` were written by a Claude agent session
(Claude Opus 5.5, model id `claude-opus-5-5`) viewing each contact sheet with its file-reading tool,
on 2026-11-15. They are agent labels, not human labels. The human labels are Open Images V7's
human-verified image-level labels and the Places365 scene categories.

Contact sheets: `work/sheets/sNNN.jpg` (9 photos each, yellow 4-digit number in the corner).
`work/sheets/index.txt` gives each photo's sheet, number and photo id. Full-size photos:
`work/img/<id>.jpg`. Open the full-size photo whenever a field below is unclear at sheet size, and
ALWAYS for bathrooms, entrances, stairs, pools and anything where an accessibility cue could be
present. Label only what is visible.

One line per photo, space-separated, in this exact order:

    NNNN subject setting people equip=a,b access=x,y

- subject (pick the single best): bedroom, bathroom, exterior (outside of a building), pool, dining
  (food, drinks, restaurant, bar, breakfast), interior (lobby, lounge, reception, corridor, other
  common indoor space), meeting (meeting/conference room), gym, spa (sauna, massage, hot tub), scenery
  (landscape, city view, landmark, street, beach with no activity), activity (people taking part in a
  tour or activity, or a guide), boat, vehicle (bus, car, tuk tuk, bicycles, train), animal, graphic
  (painting, drawing, render, logo, map, text, screenshot), other (close-up object, decoration, amenity).
- setting: indoor, outdoor, on_water (photo taken on a boat or in the water), underwater, unclear.
- people: none, few (1-2 people), group (3 or more). Statues and paintings are not people.
- equip (visible things, comma-separated, or none): boat, kayak, bicycle, helmet, bus, car, tuk_tuk,
  train, paraglider, ski, snorkel, surfboard, horse, camel, backpack, gym_machine, bed, bathtub, desk.
- access (visible cues, comma-separated, or none): stairs, ramp, handrail, grab_bar, walk_in_shower
  (no step or curb into the shower), step_free_entrance, elevator, wheelchair, wide_doorway.

Example: `0412 bathroom indoor none equip=bathtub access=grab_bar,handrail`

Write your lines to `data/agent_labels/labels_<sheet range>.txt`, sorted by number. Be consistent;
when two subjects fit, pick the one the photo is mainly about.

## How the agent fields map to the human labels

| Agent field | Human label it is compared with |
|---|---|
| subject, setting | Places365 photos only: the scene category, mapped in `run.py` (`PLACES`) |
| people (none vs few or group) | Open Images `Person`, `Man`, `Woman`, `Boy`, `Girl` |
| equip:* | Open Images class of the same name; `paraglider` is `Paragliding`, `gym_machine` is `Exercise machine` |
| access: stairs, handrail, wheelchair, ramp, elevator | Open Images `Stairs`, `Handrail`, `Wheelchair`, `Ramp`, `Elevator` |
| tuk_tuk, snorkel, grab_bar, walk_in_shower, step_free_entrance, wide_doorway | no human label; labelled for parity, not scored |

A comparison counts only where a person verified the label (present or absent). Open Images labels
are not exhaustive: a class nobody verified for a photo is unknown, not absent.
