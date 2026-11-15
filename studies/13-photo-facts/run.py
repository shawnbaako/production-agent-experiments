"""Study 13: reading facts from photos with the embedding you already have.

    python3 run.py select        # choose the photos and both splits from the downloaded label files
    python3 run.py qwenitems     # item and key files for qwen_modal.py, and the mining pool
    uv run --frozen python run.py fetch     # download Open Images photos, extract Places365 photos
    uv run --frozen python run.py sheets    # contact sheets for the agent labeller
    uv run --frozen python run.py embed     # EmbeddingGemma 2 image and option-text vectors (CUDA)
    OPENROUTER_API_KEY=... python3 run.py apilabel   # second agent labeller, Gemini 3.8 Flash
    uv run --frozen python run.py minesheets  # contact sheets of mined candidates nobody verified
    uv run --frozen python run.py report    # every number in the README, no network

Human labels: Open Images V7 human-verified image-level labels (present, absent or unknown per
class) and the Places365 scene category. Agent labels: data/agent_labels/ (see LABEL_GUIDE.md).
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import random
import sys
import tarfile
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA, RESULTS, WORK = HERE / "data", HERE / "results", HERE / "work"
RAW, IMG = WORK / "raw", WORK / "img"
UA = "production-agent-experiments/1.0 (research script)"
SPEND_CAP = 10.0
SEED = 20261115

# Production's option lists (LABEL_GUIDE.md). Only the ones with a human counterpart are scored.
EQUIP = {  # replica field -> Open Images class id
    "boat": "/m/019jd", "kayak": "/m/04fdw", "bicycle": "/m/0199g", "helmet": "/m/0zvk5",
    "bus": "/m/01bjv", "car": "/m/0k4j", "train": "/m/07jdr", "paraglider": "/m/0h1j7",
    "ski": "/m/071p9", "surfboard": "/m/019w40", "horse": "/m/03k3r", "camel": "/m/01x_v",
    "backpack": "/m/01940j", "gym_machine": "/m/097wsh", "bed": "/m/03ssj5",
    "bathtub": "/m/03dnzn", "desk": "/m/01y9k5",
}  # fmt: skip
ACCESS = {"stairs": "/m/01lynh", "handrail": "/m/07p_zw", "wheelchair": "/m/0qmmr",
          "ramp": "/m/02xf10", "elevator": "/m/02r60"}  # fmt: skip
PERSON = {
    "/m/01g317",
    "/m/04yx4",
    "/m/03bt1vf",
    "/m/01bl7v",
    "/m/05r655",
}  # person, man, woman, boy, girl
AGENT_ONLY = {"equip:tuk_tuk", "equip:snorkel", "access:grab_bar", "access:walk_in_shower",
              "access:step_free_entrance", "access:wide_doorway"}  # fmt: skip
# Places365 category -> production subject. Setting comes from Places365's indoor/outdoor file,
# except a boat deck (on_water) and the deep ocean (underwater).
PLACES = {
    "bedroom": "bedroom", "hotel_room": "bedroom", "bathroom": "bathroom", "shower": "bathroom",
    "hotel/outdoor": "exterior", "building_facade": "exterior", "inn/outdoor": "exterior",
    "swimming_pool/outdoor": "pool", "swimming_pool/indoor": "pool", "restaurant": "dining",
    "dining_room": "dining", "bar": "dining", "coffee_shop": "dining", "lobby": "interior",
    "corridor": "interior", "reception": "interior", "conference_room": "meeting",
    "gymnasium/indoor": "gym", "sauna": "spa", "jacuzzi/indoor": "spa", "beach": "scenery",
    "mountain": "scenery", "coast": "scenery", "boat_deck": "boat",
    "underwater/ocean_deep": "other",
}  # fmt: skip
PLACES_PER_SUBJECT = 30
# Open Images photos per field: (verified positives, verified negatives).
OI_TAKE = {"access": (70, 30), "equip": (30, 12), "people": (40, 40)}
AGENT_SAMPLE = 324  # 36 contact sheets of 9


def fields_human() -> list[str]:
    return ["subject", "setting", "people", *[f"equip:{k}" for k in EQUIP],
            *[f"access:{k}" for k in ACCESS]]  # fmt: skip


def sha12(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def jl(path: Path) -> list[dict]:
    return [json.loads(x) for x in open(path)] if path.exists() else []


def photos() -> list[dict]:
    return jl(DATA / "photos.jsonl")


# --------------------------------------------------------------------------- selection


def _oi_labels(ids: set[str]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for name in ("oidv7-val-annotations-human-imagelabels.csv",
                 "oidv7-test-annotations-human-imagelabels.csv"):  # fmt: skip
        for r in csv.DictReader(open(RAW / name)):
            if r["LabelName"] in ids:
                out[r["ImageID"]][r["LabelName"]] = int(float(r["Confidence"]))
    return out


def _oi_human(lab: dict[str, int]) -> dict:
    h: dict = {}
    if any(lab.get(c) == 1 for c in PERSON):
        h["people"] = 1
    elif lab.get("/m/01g317") == 0:
        h["people"] = 0
    for kind, table in (("equip", EQUIP), ("access", ACCESS)):
        for k, c in table.items():
            if c in lab:
                h[f"{kind}:{k}"] = lab[c]
    return h


def _oi_meta() -> dict[str, dict]:
    meta = {}
    for name in ("validation-images-with-rotation.csv", "test-images-with-rotation.csv"):
        for r in csv.DictReader(open(RAW / name)):
            if r["Rotation"] == "0.0" and "/by/2.0" in r["License"]:
                meta[r["ImageID"]] = r
    return meta


def _places() -> list[dict]:
    cats = {}
    for line in open(RAW / "categories_places365.txt"):
        name, idx = line.split()
        cats[int(idx)] = name[3:]  # "/a/airfield" -> "airfield"
    io_ = {line.split()[0][3:]: int(line.split()[1]) for line in open(RAW / "IO_places365.txt")}
    by_subject: dict[str, list] = defaultdict(list)
    for line in open(RAW / "places365_val.txt"):
        fname, idx = line.split()
        cat = cats[int(idx)]
        if cat in PLACES:
            by_subject[PLACES[cat]].append((fname, cat))
    rng = random.Random(SEED)
    out = []
    for subject, rows in sorted(by_subject.items()):
        rows.sort()
        for fname, cat in rng.sample(rows, min(PLACES_PER_SUBJECT, len(rows))):
            setting = {"boat_deck": "on_water", "underwater/ocean_deep": "underwater"}.get(
                cat, "indoor" if io_[cat] == 1 else "outdoor"
            )
            out.append({
                "id": "pl_" + fname.removesuffix(".jpg").split("_")[-1],
                "source": "places365", "group": "pl_" + fname, "file": fname,
                "category": cat,
                "human": {"subject": subject, "setting": setting},
            })  # fmt: skip
    return out


def _split(rows: list[dict], seeds: range) -> set[str]:
    """Group-held-out split, production's split.py rule: about a quarter of the photos and of
    each field's positives (and each subject or setting value) on the test side, no group on both."""
    by_group: dict[str, list] = defaultdict(list)
    for r in rows:
        by_group[r["group"]].append(r)
    groups = sorted(by_group)

    def keys(r):
        h = r["human"]
        return [f for f in h if h[f] == 1] + [
            f"{f}={h[f]}" for f in ("subject", "setting") if f in h
        ]

    tot = Counter(k for r in rows for k in keys(r))

    def badness(pick):
        ps = [r for g in pick for r in by_group[g]]
        c = Counter(k for r in ps for k in keys(r))
        cue = sum(abs(c[k] / tot[k] - 0.25) for k in tot if tot[k] >= 4)
        return cue + 2 * abs(len(ps) / len(rows) - 0.25)

    best = min((random.Random(s).sample(groups, len(groups) // 4) for s in seeds), key=badness)
    return set(best)


def select() -> None:
    meta = _oi_meta()
    want = {c for t in (EQUIP, ACCESS) for c in t.values()} | PERSON
    lab = _oi_labels(want)
    human = {i: _oi_human(v) for i, v in lab.items() if i in meta}
    rng = random.Random(SEED)
    chosen: set[str] = set()
    for f in fields_human()[2:]:
        kind = f.split(":")[0]
        npos, nneg = OI_TAKE[kind]
        for value, n in ((1, npos), (0, nneg)):
            pool = sorted(i for i, h in human.items() if h.get(f) == value)
            chosen |= set(rng.sample(pool, min(n, len(pool))))
    rows = [
        {
            "id": "oi_" + i,
            "source": "openimages",
            "subset": meta[i]["Subset"],
            "group": "oi_" + sha12(meta[i]["Author"] or i),
            "human": human[i],
        }  # fmt: skip
        for i in sorted(chosen)
    ] + _places()
    test_a = _split(rows, range(4000))
    test_b = _split(rows, range(4000, 8000))
    for r in rows:
        r["test_a"], r["test_b"] = r["group"] in test_a, r["group"] in test_b
    train_a = sorted(r["id"] for r in rows if not r["test_a"])
    agent = sorted(random.Random(SEED + 1).sample(train_a, AGENT_SAMPLE))
    for r in rows:
        r["agent_sample"] = r["id"] in agent
    DATA.mkdir(exist_ok=True)
    with open(DATA / "photos.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{len(rows)} photos, {len({r['group'] for r in rows})} groups; "
          f"test a {sum(r['test_a'] for r in rows)}, test b {sum(r['test_b'] for r in rows)}")  # fmt: skip
    for fld in fields_human():
        vals = Counter(r["human"].get(fld) for r in rows if fld in r["human"])
        print(f"  {fld}: {dict(vals)}")


# --------------------------------------------------------------------------- photos


def fetch() -> None:
    from PIL import Image

    IMG.mkdir(parents=True, exist_ok=True)
    rows = photos() + jl(DATA / "mine_pool.jsonl")
    todo = [r for r in rows if not (IMG / f"{r['id']}.jpg").exists()]
    places = {r["file"]: r for r in todo if r["source"] == "places365"}
    if places:
        with tarfile.open(RAW / "val_large.tar") as tar:
            for m in tar:
                name = Path(m.name).name
                if name in places:
                    im = Image.open(tar.extractfile(m)).convert("RGB")
                    im.save(IMG / f"{places[name]['id']}.jpg", quality=90)

    def one(r):
        url = f"https://open-images-dataset.s3.amazonaws.com/{r['subset']}/{r['id'][3:]}.jpg"
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                          timeout=60).read()  # fmt: skip
        except OSError as e:
            return r["id"], str(e)
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((1024, 1024))
        im.save(IMG / f"{r['id']}.jpg", quality=90)
        return None

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(8) as ex:
        dead = [d for d in ex.map(one, [t for t in todo if t["source"] == "openimages"]) if d]
    print(f"fetched; {len(dead)} failed", dead[:5])


def sheets(sample: list[dict] | None = None, name: str = "agent_sheet_index.txt",
           out: Path = WORK / "sheets") -> None:
    from PIL import Image, ImageDraw

    out.mkdir(parents=True, exist_ok=True)
    if sample is None:
        sample = [r for r in photos() if r["agent_sample"]]
        random.Random(SEED + 2).shuffle(sample)  # sources and splits mixed on every sheet
    index = []
    cell = 320
    for s in range(0, len(sample), 9):
        sheet = Image.new("RGB", (3 * cell, 3 * cell), "black")
        draw = ImageDraw.Draw(sheet)
        for j, r in enumerate(sample[s : s + 9]):
            num = s + j
            im = Image.open(IMG / f"{r['id']}.jpg")
            im.thumbnail((cell - 4, cell - 4))
            x, y = (j % 3) * cell, (j // 3) * cell
            sheet.paste(im, (x + 2, y + 2))
            draw.rectangle((x + 2, y + 2, x + 50, y + 22), fill="black")
            draw.text((x + 6, y + 5), f"{num:04d}", fill="yellow")
            index.append(f"s{s // 9:03d} {num:04d} {r['id']}")
        sheet.save(out / f"s{s // 9:03d}.jpg", quality=88)
    (out / "index.txt").write_text("\n".join(index) + "\n")
    (DATA / name).write_text("\n".join(index) + "\n")
    print(f"{len(index)} photos on {len(index) // 9} sheets")


# --------------------------------------------------------------------------- EG2

EG2 = "google/embeddinggemma-2"
EG2_REVISION = "f9972ac22e696a105c482202646979e33e4b5a1e"
OPTION_TEXT = {
    "subject": {
        "bedroom": "a hotel bedroom", "bathroom": "a bathroom",
        "exterior": "the outside of a building", "pool": "a swimming pool",
        "dining": "a restaurant, bar, food or drinks", "interior": "a lobby, corridor or reception",
        "meeting": "a meeting room", "gym": "a gym", "spa": "a sauna or hot tub",
        "scenery": "a landscape, beach or mountain view", "boat": "the deck of a boat",
        "other": "something else",
    },
    "setting": {"indoor": "a photo taken indoors", "outdoor": "a photo taken outdoors",
                "on_water": "a photo taken on a boat", "underwater": "a photo taken underwater"},
    "people": {1: "a photo with people in it"},
    **{f"equip:{k}": {1: f"a photo of a {k.replace('_', ' ').replace('gym machine', 'gym exercise machine')}"} for k in EQUIP},
    "access:stairs": {1: "a photo of stairs or steps"},
    "access:handrail": {1: "a photo of a handrail"},
    "access:wheelchair": {1: "a photo of a wheelchair"},
    "access:ramp": {1: "a photo of a wheelchair ramp"},
    "access:elevator": {1: "a photo of an elevator or lift"},
}  # fmt: skip


def embed() -> None:
    import numpy as np
    import torch
    from PIL import Image
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EG2, revision=EG2_REVISION, device="cuda",
                                config_kwargs={"audio_config": None},
                                model_kwargs={"dtype": torch.float32})  # fmt: skip
    model.eval()
    model[0].processor.image_processor.max_soft_tokens = 140  # production's image budget
    rows = photos()
    t0 = time.time()
    vec = {}
    for s in range(0, len(rows), 16):
        chunk = rows[s : s + 16]
        ims = [Image.open(IMG / f"{r['id']}.jpg").convert("RGB") for r in chunk]
        v = model.encode([{"image": im} for im in ims], normalize_embeddings=True,
                         convert_to_numpy=True)  # fmt: skip
        vec.update({r["id"]: x.astype(np.float32) for r, x in zip(chunk, v, strict=True)})
    dt = time.time() - t0
    np.savez_compressed(RESULTS / "eg2_vectors.npz", **vec)
    print(f"{len(vec)} photos in {dt:.0f} s ({dt / len(vec):.3f} s/photo)")
    texts = {f"{f}={k}": t for f, opts in OPTION_TEXT.items() for k, t in opts.items()}
    tv = model.encode([f"task: search result | query: {t}" for t in texts.values()],
                      normalize_embeddings=True, convert_to_numpy=True)  # fmt: skip
    np.savez_compressed(RESULTS / "eg2_option_text.npz", **dict(zip(texts, tv, strict=True)))


# --------------------------------------------------------------------------- agent labels


def _parse_agent(lines) -> dict[int, dict]:
    """Production's labels.py parser, without the offer column."""
    out = {}
    for line in lines:
        p = line.split()
        if len(p) < 4 or not p[0].isdigit():
            continue
        kv = {x.split("=")[0]: {y for y in x.split("=")[1].split(",") if y and y != "none"}
              for x in p[4:] if "=" in x}  # fmt: skip
        out[int(p[0])] = {"subject": p[1], "setting": p[2], "people": p[3],
                          "equip": kv.get("equip", set()), "access": kv.get("access", set())}  # fmt: skip
    return out


def as_fields(lab: dict) -> dict:
    """An agent label line in replica fields; every field is answered (agent labels are exhaustive)."""
    out = {
        "subject": lab["subject"],
        "setting": lab["setting"],
        "people": int(lab["people"] != "none"),
    }
    for k in [*EQUIP, "tuk_tuk", "snorkel"]:
        out[f"equip:{k}"] = int(k in lab["equip"])
    for k in [*ACCESS, "grab_bar", "walk_in_shower", "step_free_entrance", "wide_doorway"]:
        out[f"access:{k}"] = int(k in lab["access"])
    return out


def agent_labels(source: str = "claude") -> dict[str, dict]:
    num_to_id = {int(x.split()[1]): x.split()[2] for x in open(DATA / "agent_sheet_index.txt")}
    if source == "claude":
        lines = [x for p in sorted((DATA / "agent_labels").glob("labels_*.txt")) for x in open(p)]
        return {num_to_id[n]: as_fields(v) for n, v in _parse_agent(lines).items()}
    rows = jl(RESULTS / "api_labels.jsonl")
    return {r["id"]: as_fields(v) for r in rows for v in _parse_agent([r["line"]]).values()}


# --------------------------------------------------------------------------- second labeller

API_MODEL = "google/gemini-3.8-flash"


def spend(step: str, usd: float) -> None:
    with open(RESULTS / "spend.jsonl", "a") as f:
        f.write(json.dumps({"step": step, "usd": round(usd, 6)}) + "\n")


def spent() -> float:
    return sum(r["usd"] for r in jl(RESULTS / "spend.jsonl"))


def apilabel() -> None:
    """The same guide and photos, one photo per call, through OpenRouter."""
    guide = (
        (HERE / "LABEL_GUIDE.md").read_text().split("One line per photo")[1].split("Write your")[0]
    )
    done = {r["id"] for r in jl(RESULTS / "api_labels.jsonl")}
    index = [x.split() for x in open(DATA / "agent_sheet_index.txt")]
    key = os.environ["OPENROUTER_API_KEY"]
    import threading
    from concurrent.futures import ThreadPoolExecutor

    lock = threading.Lock()

    def one(row):
        _, num, pid = row
        if spent() > SPEND_CAP - 0.05:
            return f"spend cap reached: {spent():.3f}"
        b64 = base64.b64encode((IMG / f"{pid}.jpg").read_bytes()).decode()
        text = (f"Label this photo for a travel catalogue. Photo number: {num}.\nOne line per "
                f"photo{guide}\nReply with the one line only.")  # fmt: skip
        body = {
            "model": API_MODEL, "temperature": 0, "max_tokens": 4000,
            # The endpoint refuses {"enabled": false}: "Reasoning is mandatory for this endpoint".
            "reasoning": {"effort": "low"}, "usage": {"include": True},
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": text}]}],
        }  # fmt: skip
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "User-Agent": UA},
        )  # fmt: skip
        try:
            d = json.load(urllib.request.urlopen(req, timeout=180))
        except (urllib.error.HTTPError, TimeoutError) as e:
            return f"{pid} {e}"
        line = d["choices"][0]["message"]["content"].strip().splitlines()[0].strip("` ")
        with lock:
            spend("apilabel", d.get("usage", {}).get("cost", 0.0))
            with open(RESULTS / "api_labels.jsonl", "a") as f:
                f.write(json.dumps({"id": pid, "line": line, "model": d.get("model")}) + "\n")
        return None

    with ThreadPoolExecutor(8) as ex:
        for err in ex.map(one, [r for r in index if r[2] not in done]):
            if err:
                print(err)
    print(f"labelled; total spend {spent():.4f}")


# --------------------------------------------------------------------------- Qwen inputs

QWEN_CUES = [*ACCESS]
QWEN_EQUIP = [*EQUIP]
MINE_POOL = 1000
MINE_CLASSES = {  # listing-like photos: building, house, room, interior design, bathroom, bedroom,
    # kitchen, living room, lobby, swimming pool, restaurant, street, boat, beach
    "/m/0cgh4", "/m/03jm5", "/m/06ht1", "/m/02rfdq", "/m/01j2bj", "/m/02_58j", "/m/0d4wf",
    "/m/03f6tq", "/m/027dwg0", "/m/0b_rs", "/m/06l8d", "/m/01c8br", "/m/019jd", "/m/0b3yr",
}  # fmt: skip


def qwenitems() -> None:
    """Items for qwen_modal.py. Unverified items are absent in training targets (Open Images is
    not exhaustive); scoring uses verified labels only."""
    rows = photos()
    with open(DATA / "qwen_items.jsonl", "w") as f:
        for r in rows:
            h = r["human"]
            f.write(json.dumps({"key": r["id"],
                                "visible": [k for k in QWEN_CUES if h.get(f"access:{k}") == 1]
                                + [k for k in QWEN_EQUIP if h.get(f"equip:{k}") == 1]}) + "\n")  # fmt: skip
    for s in "ab":
        (DATA / f"test_keys_{s}.txt").write_text(
            "\n".join(r["id"] for r in rows if r[f"test_{s}"]) + "\n")  # fmt: skip
        (DATA / f"train_keys_{s}.txt").write_text(
            "\n".join(r["id"] for r in rows if not r[f"test_{s}"]) + "\n")  # fmt: skip
    if not (DATA / "mine_pool.jsonl").exists():
        meta = _oi_meta()
        want = {*ACCESS.values(), *EQUIP.values(), *PERSON, *MINE_CLASSES}
        lab = _oi_labels(want)
        taken = {r["id"][3:] for r in rows if r["source"] == "openimages"}
        pool = sorted(i for i, v in lab.items() if i in meta and i not in taken
                      and any(v.get(c) == 1 for c in MINE_CLASSES))  # fmt: skip
        pick = random.Random(SEED + 3).sample(pool, MINE_POOL)
        with open(DATA / "mine_pool.jsonl", "w") as f:
            for i in sorted(pick):
                f.write(json.dumps({"id": "oi_" + i, "source": "openimages",
                                    "subset": meta[i]["Subset"], "human": _oi_human(lab[i])}) + "\n")  # fmt: skip
    with open(DATA / "mine_items.jsonl", "w") as f:
        for r in jl(DATA / "mine_pool.jsonl"):
            f.write(json.dumps({"key": r["id"], "visible": []}) + "\n")
    print("wrote qwen items, key files and mine items")


def minesheets() -> None:
    """Contact sheets of the mined candidates no person verified, for the agent check.
    Candidates a person verified are scored against that label instead."""
    pool = {r["id"]: r for r in jl(DATA / "mine_pool.jsonl")}
    todo = []
    for p in jl(RESULTS / "qwen/mine_a.jsonl"):
        h = pool[p["key"]]["human"]
        cues = [c for c in ACCESS if p["ans"] and c in p["ans"]["visible"]]
        if any(f"access:{c}" not in h for c in cues):
            todo.append(pool[p["key"]])
    sheets(todo, "mine_sheet_index.txt", WORK / "mine_sheets")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "report":
        import report

        report.main()
    else:
        {"select": select, "fetch": fetch, "sheets": sheets, "embed": embed,
         "apilabel": apilabel, "qwenitems": qwenitems, "minesheets": minesheets}[cmd]()  # fmt: skip
