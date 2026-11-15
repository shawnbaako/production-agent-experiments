"""Zero-shot and LoRA fine-tune of Qwen3.5-2B for visible cues and equipment, on Modal.

Production's script with the fields swapped: no listing text (public photos have none) and no
offer field; equipment items are asked alongside the accessibility cues. Training setup unchanged:
LoRA r16 on the language-model projections only, vision tower frozen, 2 epochs, lr 1e-4, photos
with any cue shown three times, greedy decoding, photos at 768 px max side.

    modal run qwen_modal.py --stage upload                  # photos + items to the volume
    modal run qwen_modal.py --stage zs                      # base model on split a's test photos
    modal run qwen_modal.py --stage ft --split a            # LoRA on split a's train photos, then test
    modal run qwen_modal.py --stage ft --split b            # the re-drawn split
    modal run qwen_modal.py --stage mine --split a          # fine-tuned model over the mining pool

Every run appends its GPU time and an estimated cost to results/spend.jsonl and refuses to start
if the recorded spend plus the run's estimate would pass the cap.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CUES = ["stairs", "handrail", "wheelchair", "ramp", "elevator"]
EQUIP = ["boat", "kayak", "bicycle", "helmet", "bus", "car", "train", "paraglider", "ski",
         "surfboard", "horse", "camel", "backpack", "gym_machine", "bed", "bathtub", "desk"]  # fmt: skip
ITEMS = CUES + EQUIP
REPO = "Qwen/Qwen3.5-2B"
MAX_SIDE = 768
CAP = 10.0
A10G_PER_S = (
    1.10 / 3600
)  # Modal list price for an A10G, USD per second (CPU and memory extra, small)
ESTIMATE = {"zs": 1.0, "ft": 2.0, "mine": 2.6}


def prompt() -> str:
    return (
        "This photo could appear in a hotel or activity listing.\n\n"
        "Look only at what is visible in the photo. Accessibility cues:\n"
        "- stairs: steps or a staircase\n- ramp: a sloped ramp for wheels\n"
        "- handrail: a rail to hold along stairs, a ramp or a walkway\n"
        "- elevator: a lift or its doors\n- wheelchair: a wheelchair or wheelchair symbol\n\n"
        "Equipment: boat, kayak, bicycle, helmet, bus, car, train, paraglider, ski, surfboard, "
        "horse, camel, backpack, gym_machine (a gym exercise machine), bed, bathtub, desk.\n\n"
        'Reply with one line of JSON only: {"visible": [cues and equipment clearly visible]}. '
        "Leave the list empty when nothing applies."
    )


def target(item: dict) -> str:
    return json.dumps({"visible": [c for c in ITEMS if c in item["visible"]]})


def parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or not isinstance(d.get("visible"), list):
        return None
    return {"visible": [c for c in d["visible"] if c in ITEMS]}


def _spent() -> float:
    path = HERE / "results/spend.jsonl"
    return sum(json.loads(x)["usd"] for x in open(path)) if path.exists() else 0.0


import modal  # noqa: E402

app = modal.App("pae-photo-facts-qwen")
vol = modal.Volume.from_name("pae-photo-facts-qwen", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "torch==2.15.0",
    "torchvision",
    "transformers==5.22.2",
    "peft==0.21.2",
    "accelerate==1.15.0",
    "pillow",
)
V = Path("/vol")


def _load(adapter: str | None = None):
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    proc = AutoProcessor.from_pretrained(REPO, cache_dir=str(V / "hf"))
    model = AutoModelForImageTextToText.from_pretrained(
        REPO, dtype=torch.bfloat16, device_map="cuda:0", cache_dir=str(V / "hf")
    )
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(V / adapter))
    return proc, model


def _inputs(proc, item: dict):
    from PIL import Image

    im = Image.open(V / "img" / f"{item['key']}.jpg").convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    msgs = [{"role": "user", "content": [{"type": "image", "image": im},
                                         {"type": "text", "text": prompt()}]}]  # fmt: skip
    return proc.apply_chat_template(
        msgs,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        enable_thinking=False,
    )


def _items(split: str) -> list[dict]:
    """``test_a``/``train_b``...: photos by key file; ``mine``: the mining pool."""
    if split == "mine":
        return list(map(json.loads, open(V / "mine_items.jsonl")))
    keys = set((V / f"{split.split('_')[0]}_keys_{split.split('_')[1]}.txt").read_text().split())
    return [i for i in map(json.loads, open(V / "qwen_items.jsonl")) if i["key"] in keys]


@app.function(image=image, gpu="A10G", volumes={"/vol": vol}, timeout=3 * 3600)
def predict(adapter: str | None, out: str, split: str) -> tuple[str, float]:
    import torch

    t0 = time.time()
    proc, model = _load(adapter)
    model.eval()
    lines = []
    for n, item in enumerate(_items(split)):
        inp = _inputs(proc, item).to(model.device)
        with torch.no_grad():
            gen = model.generate(**inp, max_new_tokens=80, do_sample=False)
        text = proc.decode(gen[0, inp["input_ids"].shape[1] :], skip_special_tokens=True)
        lines.append(json.dumps({"key": item["key"], "raw": text, "ans": parse(text)}))
        if n % 50 == 0:
            print(n, text[:160].replace("\n", " "), flush=True)
    (V / out).write_text("\n".join(lines) + "\n")
    vol.commit()
    return "\n".join(lines) + "\n", time.time() - t0


@app.function(image=image, gpu="A10G", volumes={"/vol": vol}, timeout=3 * 3600)
def train(epochs: int, lr: float, out: str, split: str) -> float:
    import random

    import torch
    from peft import LoraConfig, get_peft_model

    t0 = time.time()
    proc, model = _load()
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    # Language-model projections only; the vision tower stays frozen.
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)",
        ),
    )
    eos = proc.tokenizer.convert_tokens_to_ids("<|im_end|>")
    rows = _items(f"train_{split}")
    # Production's 3x oversampling of photos with a cue.
    rows += [r for r in rows if set(r["visible"]) & set(CUES)] * 2
    accum = 8
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    total = epochs * len(rows) // accum
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1, (s + 1) / 20) * max(0.0, 1 - s / total)
    )
    model.train()
    step, running = 0, 0.0
    for ep in range(epochs):
        random.Random(ep).shuffle(rows)
        for n, item in enumerate(rows):
            inp = _inputs(proc, item)
            ans = proc.tokenizer(target(item), add_special_tokens=False, return_tensors="pt")[
                "input_ids"
            ]
            ans = torch.cat([ans, torch.tensor([[eos]])], 1)
            L = inp["input_ids"].shape[1]
            inp["input_ids"] = torch.cat([inp["input_ids"], ans], 1)
            inp["attention_mask"] = torch.ones_like(inp["input_ids"])
            if "mm_token_type_ids" in inp:
                inp["mm_token_type_ids"] = torch.cat(
                    [inp["mm_token_type_ids"], torch.zeros_like(ans)], 1
                )
            labels = inp["input_ids"].clone()
            labels[:, :L] = -100
            loss = model(**inp.to(model.device), labels=labels.to(model.device)).loss / accum
            loss.backward()
            running += loss.item()
            if (n + 1) % accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                sched.step()
                opt.zero_grad()
                step += 1
                if step % 20 == 0:
                    print(f"ep {ep} step {step}/{total} loss {running / 20:.4f} "
                          f"{(time.time() - t0) / 60:.1f} min", flush=True)  # fmt: skip
                    running = 0.0
    model.save_pretrained(str(V / out))
    vol.commit()
    print(f"saved {out} in {(time.time() - t0) / 60:.1f} min")
    return time.time() - t0


def _record(step: str, seconds: float) -> None:
    with open(HERE / "results/spend.jsonl", "a") as f:
        f.write(json.dumps({"step": step, "usd": round(seconds * A10G_PER_S, 4),
                            "gpu_seconds": round(seconds)}) + "\n")  # fmt: skip


@app.local_entrypoint()
def main(stage: str, split: str = "a", epochs: int = 2, lr: float = 1e-4):
    runs = HERE / "results/qwen"
    runs.mkdir(parents=True, exist_ok=True)
    if stage == "upload":
        with vol.batch_upload(force=True) as b:
            for name in ("qwen_items.jsonl", "mine_items.jsonl", "train_keys_a.txt",
                         "test_keys_a.txt", "train_keys_b.txt", "test_keys_b.txt"):  # fmt: skip
                b.put_file(str(HERE / "data" / name), f"/{name}")
            keys = [json.loads(x)["key"] for f in ("qwen_items.jsonl", "mine_items.jsonl")
                    for x in open(HERE / "data" / f)]  # fmt: skip
            for k in keys:
                b.put_file(str(HERE / "work/img" / f"{k}.jpg"), f"/img/{k}.jpg")
        print(f"uploaded {len(keys)} photos")
        return
    if _spent() + ESTIMATE[stage] > CAP:
        raise SystemExit(f"spend cap: {_spent():.2f} recorded + {ESTIMATE[stage]} estimate > {CAP}")
    if stage == "zs":
        text, s = predict.remote(None, "qwen_zs_a.jsonl", "test_a")
        (runs / "zs_a.jsonl").write_text(text)
        _record("qwen zero-shot, split a test", s)
    elif stage == "ft":
        s = train.remote(epochs, lr, f"lora_{split}", split)
        _record(f"qwen LoRA train, split {split}", s)
        text, s = predict.remote(f"lora_{split}", f"qwen_ft_{split}.jsonl", f"test_{split}")
        (runs / f"ft_{split}.jsonl").write_text(text)
        _record(f"qwen LoRA predict, split {split} test", s)
    elif stage == "mine":
        text, s = predict.remote(f"lora_{split}", f"qwen_mine_{split}.jsonl", "mine")
        (runs / f"mine_{split}.jsonl").write_text(text)
        _record(f"qwen mining pool, LoRA {split}", s)
