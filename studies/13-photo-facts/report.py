"""Every replica number in the README, from committed files only (no network, no GPU).

    uv run --frozen python run.py report

The head trainer, threshold rule, Wilson bound and grouped folds are production's
(train_heads.py), unchanged apart from the field list. Every score is against human labels on
held-out photos, and a field counts only where a person verified it.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict

import numpy as np
from run import (
    ACCESS,
    AGENT_ONLY,
    DATA,
    EQUIP,
    OPTION_TEXT,
    RESULTS,
    _parse_agent,
    _split,
    as_fields,
    agent_labels,
    fields_human,
    jl,
    photos,
)

TARGET = 0.90
LOWER_BOUND = 0.80  # 95% Wilson lower bound an answer's held-out precision must clear
MIN_HITS = 5
SCALE = 10.0
SETTINGS = ["indoor", "outdoor", "on_water", "underwater"]
QWEN_ITEMS = [*ACCESS, *EQUIP]


# --------------------------------------------------------------- production's trainer, verbatim


def fit(X: np.ndarray, y: np.ndarray, k: int, wd: float = 1e-3, epochs: int = 300):
    """Weight-decayed softmax regression by full-batch Adam; returns (W, b)."""
    Y = np.eye(k, dtype=np.float32)[y]
    W = np.zeros((X.shape[1], k), np.float32)
    b = np.zeros(k, np.float32)
    m = [np.zeros_like(W), np.zeros_like(b)]
    v = [np.zeros_like(W), np.zeros_like(b)]
    for t in range(1, epochs + 1):
        P = softmax(SCALE * X @ W + b)
        G = (P - Y) / len(X)
        grads = [SCALE * X.T @ G + 2 * wd * W, G.sum(0)]
        for i, (p, g) in enumerate(zip((W, b), grads, strict=True)):
            m[i] = 0.9 * m[i] + 0.1 * g
            v[i] = 0.999 * v[i] + 0.001 * g * g
            p -= 0.05 * (m[i] / (1 - 0.9**t)) / (np.sqrt(v[i] / (1 - 0.999**t)) + 1e-8)
    return W, b


def softmax(Z: np.ndarray) -> np.ndarray:
    Z = Z - Z.max(1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(1, keepdims=True)


def predict(W, b, X):
    return softmax(SCALE * X @ W + b)


def threshold(prob: np.ndarray, truth: np.ndarray, binary: bool) -> float | None:
    """Lowest confidence at which predictions are right >= TARGET (binary: of 'yes' calls)."""
    guess = prob.argmax(1)
    conf = prob[:, 1] if binary else prob.max(1)
    for t in np.arange(0.5, 0.991, 0.01):
        said = conf >= t
        right = said & ((truth == 1) if binary else (guess == truth))
        if right.sum() >= MIN_HITS and right.sum() / max(said.sum(), 1) >= TARGET:
            return round(float(t), 2)
    return None


def wilson(right: int, calls: int, z: float = 1.96) -> float:
    if not calls:
        return 0.0
    p = right / calls
    centre = p + z * z / (2 * calls)
    margin = z * np.sqrt(p * (1 - p) / calls + z * z / (4 * calls * calls))
    return float((centre - margin) / (1 + z * z / calls))


def grouped_folds(cids: list[str], k: int = 5) -> np.ndarray:
    uniq = sorted(set(cids))
    order = np.random.default_rng(0).permutation(len(uniq))
    fold = {c: int(order[i]) % k for i, c in enumerate(uniq)}
    return np.array([fold[c] for c in cids])


# --------------------------------------------------------------- heads


def classes_of(field: str, labels: dict[str, dict]) -> list:
    if field == "subject":
        return sorted({v["subject"] for v in labels.values() if "subject" in v} - {"unclear"})
    if field == "setting":
        return SETTINGS
    return [0, 1]


def gate(right: int, calls: int) -> bool:
    return (
        right >= MIN_HITS
        and right / max(calls, 1) >= TARGET
        and wilson(right, calls) >= LOWER_BOUND
    )


def heads(vec, train_ids, train_labels, test_ids, human, fields=None, keep_probs=False):
    """Train every field's head on (train_ids, train_labels), measure on test_ids' human labels."""
    out = {}
    for f in fields or fields_human():
        classes = classes_of(f, train_labels)
        binary = classes == [0, 1]
        tr = [(i, classes.index(train_labels[i][f])) for i in train_ids
              if f in train_labels.get(i, {}) and train_labels[i][f] in classes]  # fmt: skip
        te = [(i, classes.index(human[i][f])) for i in test_ids
              if f in human[i] and human[i][f] in classes]  # fmt: skip
        res = {"train": len(tr), "train_pos": sum(y for _, y in tr) if binary else None,
               "test": len(te), "test_pos": sum(y for _, y in te) if binary else None}  # fmt: skip
        out[f] = res
        if not te or (binary and res["train_pos"] < MIN_HITS) or len({y for _, y in tr}) < 2:
            res["verdict"] = "too few to train"
            continue
        X = np.stack([vec[i] for i, _ in tr])
        y = np.array([y for _, y in tr])
        folds = grouped_folds([GROUP[i] for i, _ in tr])
        cv = np.zeros((len(tr), len(classes)), np.float32)
        for k in range(5):
            if (folds != k).sum() and len(set(y[folds != k])) == len(set(y)):
                W, b = fit(X[folds != k], y[folds != k], len(classes))
                cv[folds == k] = predict(W, b, X[folds == k])
        t = threshold(cv, y, binary)
        W, b = fit(X, y, len(classes))
        prob = predict(W, b, np.stack([vec[i] for i, _ in te]))
        truth = np.array([y for _, y in te])
        if keep_probs:
            res["probs"] = {
                i: [round(float(p), 4) for p in row] for (i, _), row in zip(te, prob, strict=True)
            }
        if binary:
            from_scores = auc(prob[:, 1], truth)
            res["auc"] = from_scores
        else:
            res["accuracy_all"] = float((prob.argmax(1) == truth).mean())
        res["threshold"] = t
        if t is None:
            res["verdict"] = "never 90% in cross-validation"
            continue
        conf = prob[:, 1] if binary else prob.max(1)
        said = conf >= t
        guess = np.ones_like(truth) if binary else prob.argmax(1)
        answers = {}
        for c in [1] if binary else range(len(classes)):
            calls = int((said & (guess == c)).sum())
            right = int((said & (guess == c) & (truth == c)).sum())
            answers[str(classes[c])] = {"right": right, "calls": calls,
                                        "lower_bound": round(wilson(right, calls), 3),
                                        "passes": gate(right, calls)}  # fmt: skip
        res["answers"] = answers
        if binary:
            tp = answers["1"]["right"]
            res["recall"] = tp / max(int(truth.sum()), 1)
        else:
            res["answers_share"] = float(said.mean())
            res["right_when_answering"] = float(
                (said & (guess == truth)).sum() / max(said.sum(), 1)
            )
        res["verdict"] = "passes" if any(a["passes"] for a in answers.values()) else "fails gate"
    return out


def auc(score: np.ndarray, truth: np.ndarray) -> float | None:
    pos, neg = score[truth == 1], score[truth == 0]
    if not len(pos) or not len(neg):
        return None
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


# --------------------------------------------------------------- EG2 zero-shot


def zero_shot(vec, text, train_ids, test_ids, human):
    """Photo against option text. Multi-class: nearest option. Binary: similarity to the option
    text, with a threshold set on the training photos by the production rule (lowest similarity
    at which >= 90% of calls are right, >= 5 right). Nothing is trained."""
    out = {}
    for f in fields_human():
        opts = OPTION_TEXT[f]
        tr = [i for i in train_ids if f in human[i]]
        te = [i for i in test_ids if f in human[i]]
        if f in ("subject", "setting"):
            keys = list(opts)
            T = np.stack([text[f"{f}={k}"] for k in keys])
            pick = lambda ids: [keys[j] for j in (np.stack([vec[i] for i in ids]) @ T.T).argmax(1)]  # noqa: E731
            guess = pick(te)
            out[f] = {
                "test": len(te),
                "accuracy_all": float(
                    np.mean([g == human[i][f] for g, i in zip(guess, te, strict=True)])
                ),
            }
            continue
        T = text[f"{f}=1"]
        s_tr = np.array([vec[i] @ T for i in tr])
        y_tr = np.array([human[i][f] for i in tr])
        s_te = np.array([vec[i] @ T for i in te])
        y_te = np.array([human[i][f] for i in te])
        t = None
        for cand in np.sort(s_tr):
            said = s_tr >= cand
            right = (said & (y_tr == 1)).sum()
            if right >= MIN_HITS and right / max(said.sum(), 1) >= TARGET:
                t = float(cand)
                break
        res = {"test": len(te), "test_pos": int(y_te.sum()), "auc": auc(s_te, y_te), "threshold": t}
        if t is not None:
            said = s_te >= t
            right, calls = int((said & (y_te == 1)).sum()), int(said.sum())
            res.update(right=right, calls=calls, lower_bound=round(wilson(right, calls), 3),
                       recall=right / max(int(y_te.sum()), 1), passes=gate(right, calls))  # fmt: skip
        out[f] = res
    return out


# --------------------------------------------------------------- agreement


def kappa(a: list, b: list) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def agreement(labels: dict[str, dict], human: dict[str, dict]) -> dict:
    out = {}
    for f in fields_human():
        ids = [i for i in labels if f in human[i]]
        a = [labels[i][f] for i in ids]
        h = [human[i][f] for i in ids]
        res = {"n": len(ids), "agree": sum(x == y for x, y in zip(a, h, strict=True)),
               "kappa": kappa(a, h)}  # fmt: skip
        if f not in ("subject", "setting"):
            tp = sum(x == 1 and y == 1 for x, y in zip(a, h, strict=True))
            res.update(agent_yes=sum(a), human_yes=sum(h), both_yes=tp,
                       agent_precision=tp / max(sum(a), 1), agent_recall=tp / max(sum(h), 1))  # fmt: skip
        else:
            res["confusions"] = Counter(
                f"{y}->{x}" for x, y in zip(a, h, strict=True) if x != y
            ).most_common(6)
        out[f] = res
    return out


def agent_vs_agent(a: dict, b: dict) -> dict:
    ids = sorted(set(a) & set(b))
    out = {}
    for f in [*fields_human(), *sorted(AGENT_ONLY)]:
        x = [a[i][f] for i in ids]
        y = [b[i][f] for i in ids]
        out[f] = {"n": len(ids), "agree": sum(p == q for p, q in zip(x, y, strict=True)), "kappa": kappa(x, y),
                  "yes_a": sum(x) if f not in ("subject", "setting") else None,
                  "yes_b": sum(y) if f not in ("subject", "setting") else None}  # fmt: skip
    return out


# --------------------------------------------------------------- Qwen


def qwen_score(path, human, items=QWEN_ITEMS):
    preds = jl(path)
    out = {"photos": len(preds), "unparsed": sum(p["ans"] is None for p in preds)}
    for it in items:
        f = f"access:{it}" if it in ACCESS else f"equip:{it}"
        rows = [(p, human[p["key"]][f]) for p in preds if f in human[p["key"]]]
        said = [p["ans"] is not None and it in p["ans"]["visible"] for p, _ in rows]
        truth = [y for _, y in rows]
        tp = sum(s and t for s, t in zip(said, truth, strict=True))
        calls = sum(said)
        unverified_calls = sum(p["ans"] is not None and it in p["ans"]["visible"]
                               for p in preds if f not in human[p["key"]])  # fmt: skip
        out[it] = {"verified": len(rows), "positives": sum(truth), "calls": calls, "right": tp,
                   "calls_on_unverified_photos": unverified_calls,
                   "precision": tp / max(calls, 1), "recall": tp / max(sum(truth), 1),
                   "lower_bound": round(wilson(tp, calls), 3), "passes": gate(tp, calls)}  # fmt: skip
    return out


def subsample(path, human, size: int, draws: int = 2000):
    """How often a random held-out set of `size` photos makes each cue look ready by point
    precision (>= 90%, >= 5 right) and how often by the full gate (lower bound >= 80% too)."""
    preds = jl(path)
    rng = random.Random(7)
    out = {}
    for it in ACCESS:
        f = f"access:{it}"
        rows = [(p["ans"] is not None and it in p["ans"]["visible"], human[p["key"]][f])
                for p in preds if f in human[p["key"]]]  # fmt: skip
        if not rows:
            continue
        point = full = 0
        prec = []
        for _ in range(draws):
            s = rng.sample(range(len(preds)), min(size, len(preds)))
            keys = {preds[j]["key"] for j in s}
            sub = [
                (a, y)
                for (a, y), p in zip(rows, [p for p in preds if f in human[p["key"]]], strict=True)
                if p["key"] in keys
            ]
            tp = sum(a and y for a, y in sub)
            calls = sum(a for a, _ in sub)
            if calls:
                prec.append(tp / calls)
            point += tp >= MIN_HITS and tp / max(calls, 1) >= TARGET
            full += gate(tp, calls)
        out[it] = {"looks_ready": point / draws, "passes_gate": full / draws,
                   "precision_p5_p95": [float(np.percentile(prec, 5)), float(np.percentile(prec, 95))] if prec else None}  # fmt: skip
    return out


def mining(path, pool):
    human = {r["id"]: r["human"] for r in pool}
    preds = {p["key"]: p for p in jl(path)}
    n = len(preds)
    out = {"screened": n}
    for it in ACCESS:
        f = f"access:{it}"
        flagged = [k for k, p in preds.items() if p["ans"] and it in p["ans"]["visible"]]
        pos = [k for k in preds if human[k].get(f) == 1]
        tp = [k for k in flagged if human[k].get(f) == 1]
        fp = [k for k in flagged if human[k].get(f) == 0]
        unv = [k for k in flagged if f not in human[k]]
        out[it] = {"flagged": len(flagged), "flagged_verified_present": len(tp),
                   "flagged_verified_absent": len(fp),
                   "flagged_unverified": len(unv),
                   "unverified_agent_present": sum(AGENT_MINE.get(k, {}).get(f) == 1 for k in unv),
                   "unverified_agent_absent": sum(AGENT_MINE.get(k, {}).get(f) == 0 for k in unv),
                   "verified_present_in_pool": len(pos),
                   "true_per_1000_screened": round(1000 * len(tp) / max(n, 1), 1),
                   "recall_of_verified": len(tp) / max(len(pos), 1),
                   "precision_where_verified": len(tp) / max(len(tp) + len(fp), 1)}  # fmt: skip
    return out


# --------------------------------------------------------------- production records

PROD_CUES = "stairs ramp handrail grab_bar walk_in_shower step_free_entrance elevator wheelchair wide_doorway".split()


def production() -> dict:
    """Production's Qwen and access-head figures recomputed from production/records.jsonl.
    Every figure is agreement with agent labels; no person labelled these photos."""
    recs = jl(DATA.parent / "production/records.jsonl")
    meta = json.loads((DATA.parent / "production/heads_meta.json").read_text())
    out: dict = {"photos": len(recs), "groups": len({r["group"] for r in recs}),
                 "held_out": sum(r["held_out"] for r in recs),
                 "positives_all": {c: sum(c in r["agent_label"]["access"] for r in recs) for c in PROD_CUES},
                 "offer_generic_all": sum(r["agent_label"]["offer"] == "generic" for r in recs)}  # fmt: skip
    for run in ("qwen_zs_v2", "qwen_ft_v2", "qwen_ft_v3"):
        rs = [r for r in recs if run in r]
        tab = {"photos": len(rs)}
        for c in PROD_CUES:
            truth = [c in r["agent_label"]["access"] for r in rs]
            said = [r[run] is not None and c in r[run]["visible"] for r in rs]
            tp = sum(a and b for a, b in zip(said, truth, strict=True))
            tab[c] = {"positives": sum(truth), "calls": sum(said), "right": tp,
                      "precision": tp / max(sum(said), 1), "recall": tp / max(sum(truth), 1),
                      "lower_bound": round(wilson(tp, sum(said)), 3), "passes": gate(tp, sum(said))}  # fmt: skip
        out[run] = tab
    heads_out = {}
    held = [r for r in recs if r["held_out"] and "heads" in r]
    for name, m in meta.items():
        if m["classes"] != ["no", "yes"] or m["threshold"] is None:
            continue
        kind, item = name.split(":")
        rs = [r for r in held if name in r["heads"]]
        truth = [item in r["agent_label"][kind] for r in rs]
        said = [r["heads"][name] >= m["threshold"] for r in rs]
        tp = sum(a and b for a, b in zip(said, truth, strict=True))
        heads_out[name] = {"positives": sum(truth), "calls": sum(said), "right": tp,
                           "lower_bound": round(wilson(tp, sum(said)), 3), "passes": gate(tp, sum(said))}  # fmt: skip
    out["eg2_heads_held_out"] = heads_out
    return out


# --------------------------------------------------------------- main

GROUP: dict[str, str] = {}
AGENT_MINE: dict[str, dict] = {}  # the agent's check of mined candidates no person verified


def main() -> None:
    rows = photos()
    GROUP.update({r["id"]: r["group"] for r in rows})
    human = {r["id"]: r["human"] for r in rows}
    vec = dict(np.load(RESULTS / "eg2_vectors.npz"))
    text = dict(np.load(RESULTS / "eg2_option_text.npz"))
    train_a = [r["id"] for r in rows if not r["test_a"]]
    test_a = [r["id"] for r in rows if r["test_a"]]
    S: dict = {"photos": len(rows), "groups": len(set(GROUP.values())),
               "test_a": len(test_a), "test_b": sum(r["test_b"] for r in rows)}  # fmt: skip
    S["human_counts"] = {
        f: dict(Counter(str(human[i][f]) for i in human if f in human[i])) for f in fields_human()
    }

    claude = agent_labels("claude")
    api = agent_labels("api") if (RESULTS / "api_labels.jsonl").exists() else {}
    sample = sorted(claude)
    S["agent_sample"] = len(sample)
    S["agreement_claude"] = agreement(claude, human)
    if api:
        S["agreement_api"] = agreement(api, human)
        S["claude_vs_api"] = agent_vs_agent(claude, api)

    S["zero_shot"] = zero_shot(vec, text, train_a, test_a, human)
    full = heads(vec, train_a, human, test_a, human, keep_probs=True)
    (RESULTS / "heads_test_probs.json").write_text(
        json.dumps({f: r.pop("probs", {}) for f, r in full.items()})
    )
    S["heads_human_full"] = full
    S["heads_agent_claude"] = heads(vec, sample, claude, test_a, human)
    S["heads_human_same_photos"] = heads(vec, sample, human, test_a, human)
    if api:
        S["heads_agent_api"] = heads(vec, sorted(api), api, test_a, human)

    # The re-drawn split and 20 more: the same trainer, data and gate; only the held-out groups move.
    test_b = [r["id"] for r in rows if r["test_b"]]
    S["heads_split_b"] = heads(
        vec, [r["id"] for r in rows if not r["test_b"]], human, test_b, human
    )
    redraw = defaultdict(list)
    for d in range(20):
        held = _split(rows, range(10000 + 300 * d, 10000 + 300 * (d + 1)))
        tr = [r["id"] for r in rows if r["group"] not in held]
        te = [r["id"] for r in rows if r["group"] in held]
        for f, res in heads(vec, tr, human, te, human).items():
            for ans, a in res.get("answers", {}).items():
                redraw[f"{f}={ans}"].append([a["right"], a["calls"], a["passes"]])
            if "answers" not in res:
                redraw[f"{f}:{res['verdict']}"].append(1)
    S["redraws"] = dict(redraw)

    q = RESULTS / "qwen"
    for name, split in (("zs_a", "a"), ("ft_a", "a"), ("ft_b", "b")):
        if (q / f"{name}.jsonl").exists():
            S[f"qwen_{name}"] = qwen_score(q / f"{name}.jsonl", human)
    if (q / "ft_a.jsonl").exists():
        S["qwen_ft_a_subsample_100"] = subsample(q / "ft_a.jsonl", human, 100)
        S["qwen_ft_a_subsample_200"] = subsample(q / "ft_a.jsonl", human, 200)
    if (q / "mine_a.jsonl").exists():
        if (DATA / "mine_sheet_index.txt").exists():
            num_to_id = {
                int(x.split()[1]): x.split()[2] for x in open(DATA / "mine_sheet_index.txt")
            }
            lines = [x for p in sorted((DATA / "agent_labels_mine").glob("*.txt")) for x in open(p)]
            AGENT_MINE.update({num_to_id[n]: as_fields(v) for n, v in _parse_agent(lines).items()})
        S["mining"] = mining(q / "mine_a.jsonl", jl(DATA / "mine_pool.jsonl"))
    S["production"] = production()
    S["spend"] = {"total_usd": round(sum(r["usd"] for r in jl(RESULTS / "spend.jsonl")), 4),
                  "by_step": dict(Counter({r["step"]: 0 for r in jl(RESULTS / "spend.jsonl")}))}  # fmt: skip
    by = defaultdict(float)
    for r in jl(RESULTS / "spend.jsonl"):
        by[r["step"]] += r["usd"]
    S["spend"]["by_step"] = {k: round(v, 4) for k, v in by.items()}
    (RESULTS / "summary.json").write_text(json.dumps(S, indent=1, default=str))
    print(
        json.dumps(
            {k: S[k] for k in ("photos", "groups", "test_a", "test_b", "agent_sample", "spend")},
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
