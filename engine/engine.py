#!/usr/bin/env python3
"""engine.py — the cap-set record engine: symmetry-restricted exact search + large-neighbourhood search.

    python3 engine.py                # run forever (resumes: finished tasks are skipped)
    python3 engine.py --status       # print a one-screen summary and exit
    python3 engine.py --tasks        # list the task queue and exit

What it does, in plain terms
    A cap set is a set of points in F_3^n with no three on a line. The largest known ones are:
        n=7: 236   n=8: 512 (DeepMind 2023)   n=9: 1082   n=10: 2432   n=11: 5488   (n=9..11 from Edel's projective caps, doubled)
    Anything larger, verified, is a new result. Two engines look for one:
      1. EXACT, with symmetry: pick a symmetry group G of the space (Singer subgroups of the field F_{3^n}, products of
         them across coordinate splits, coordinate permutations, negation). A G-invariant cap is a union of G-orbits,
         so "largest G-invariant cap" is a small exact problem that CP-SAT solves — often to proven optimality.
         Every task ends in a theorem: either a cap bigger than the record (a record) or "no cap with symmetry G beats X".
      2. LNS (large-neighbourhood search) from the best known caps: remove a structured chunk, let CP-SAT refill it
         optimally. Never leaves valid caps; any strict growth is a record.
    Every claimed record is re-verified by an independent checker (verify_record.py, pure Python) before it is saved.

Files: state/results/*.json (one per finished exact task), state/lns_*.json (live LNS stats), records/ (any records),
       state/status.json and status.html (the dashboard, served on PORT).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import math
import multiprocessing as mp
import os
import pathlib
import random
import socketserver
import subprocess
import sys
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler
from typing import Dict, List, Optional, Tuple

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capset as C          # noqa: E402
import lns as L             # noqa: E402
import orbit_solver as O    # noqa: E402
import symmetry as S        # noqa: E402

STATE = HERE / "state"
RESULTS = STATE / "results"
RECORDS = HERE / "records"
DATA = HERE / "edel"
for d in (STATE, RESULTS, RECORDS):
    d.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "dims": [7, 8, 9, 10, 11],
    "records": {"7": 236, "8": 512, "9": 1082, "10": 2432, "11": 5504, "12": 12928},
    "record_sources": {"7": "Edel 2004", "8": "Romera-Paredes et al. (FunSearch) 2023", "9": "Edel's 541-cap in PG(8,3), doubled; FunSearch notebook: largest known",
                       "10": "Edel's 1216-cap in PG(9,3), doubled", "11": "Karapetyan & Karapetyan 2024 (5504); Edel's 2744-cap doubled gives 5488",
                       "12": "Edel's 6464-cap in PG(11,3), doubled"},
    "solver_workers": None,         # processes running exact tasks; None = (cores - 4) // 2, at least 1
    "threads_per_solve": 2,
    "lns_workers": 2,               # processes running LNS on the best known caps (n=8 and n=10 by default)
    "lns_dims": [8, 10],
    "max_orbits": {"7": 2500, "8": 2500, "9": 2500, "10": 1600, "11": 900},
    "min_orbit_size": 4,
    "time_limit": {"small": 300, "medium": 900, "large": 2400},   # by orbit count: <=300 / <=1000 / more
    "second_pass_factor": 4,        # unresolved tasks whose bound still allows a record get this much more time, later
    "port": 8170,
    "host": "0.0.0.0",
    "status_every": 20,
    "machine": None,                # this machine's name on the dashboard; None = hostname
    "shard": {"index": 0, "count": 1},   # split the exact task queue across machines: this machine takes tasks with hash % count == index
    "remotes": [],                  # other machines running the engine, e.g. [{"name": "xai4", "ssh": "tt@xai4", "path": "capset_project/v2"}]
}


def load_config() -> Dict:
    cfg = dict(DEFAULT_CONFIG)
    p = HERE / "config.json"
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text()))
        except json.JSONDecodeError as e:
            print(f"config.json ignored: {e}")
    if cfg["solver_workers"] is None:
        cfg["solver_workers"] = max(1, ((os.cpu_count() or 4) - 4) // max(1, cfg["threads_per_solve"]))
    return cfg


def log(msg: str):
    line = f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with (STATE / "engine.log").open("a") as f:
        f.write(line + "\n")


# ------------------------------------------------------------------------------------------------- known caps

_SPACES: Dict[int, C.Space] = {}


def space(n: int) -> C.Space:
    if n not in _SPACES:
        _SPACES[n] = C.Space(n)
    return _SPACES[n]


def known_caps(n: int) -> List[Tuple[str, List[int]]]:
    """Named best-known / seed caps for n as index lists (verified)."""
    sp = space(n)
    out = []
    if n == 8:
        out.append(("published-512", sp.indices(C.build_512_cap_n8()).tolist()))
    for f in sorted(DATA.glob(f"affine_n{n}_*.json")):
        vecs = json.loads(f.read_text())
        out.append((f.stem, sp.indices(vecs).tolist()))
    if n == 7:
        c6 = DATA / "cap6_112.json"
        if c6.exists():
            v112 = json.loads(c6.read_text())
            out.append(("product-112x2", sp.indices([list(v) + [b] for v in v112 for b in (0, 1)]).tolist()))
    good = [(name, pts) for name, pts in out if C.verify(sp, pts)]
    good.sort(key=lambda t: -len(t[1]))
    return good


# ------------------------------------------------------------------------------------------------- tasks

def my_tasks(cfg: Dict, tasks: List[Dict]) -> List[Dict]:
    """The slice of the queue this machine owns (stable hash of the task name)."""
    sh = cfg.get("shard") or {"index": 0, "count": 1}
    cnt, idx = max(1, int(sh.get("count", 1))), int(sh.get("index", 0))
    if cnt == 1:
        return tasks
    return [t for t in tasks if int(hashlib.md5(t["name"].encode()).hexdigest(), 16) % cnt == idx]


def task_list(cfg: Dict) -> List[Dict]:
    """Every symmetry group we try, as a JSON-able spec. Sorted cheap-first."""
    tasks = []
    for n in cfg["dims"]:
        size = 3 ** n
        maxo = cfg["max_orbits"].get(str(n), 1500)
        order = size - 1
        # Singer subgroups
        for k in S.divisors(order):
            if k < cfg["min_orbit_size"]:
                continue
            n_orb = order // k + 1
            if n_orb > maxo:
                continue
            tasks.append({"n": n, "kind": "singer", "k": k, "orbits_est": n_orb, "name": f"n{n}-singer{k}"})
            if k % 2 == 1:   # add negation (caps closed under -1 <-> projective caps): orbits roughly halve
                tasks.append({"n": n, "kind": "singer+neg", "k": k, "orbits_est": order // (2 * k) + 1, "name": f"n{n}-singer{k}-neg"})
        # product Singer groups across a coordinate split a + b = n
        for a in range(2, n // 2 + 1):
            b = n - a
            oa, ob = 3 ** a - 1, 3 ** b - 1
            for k1 in S.divisors(oa):
                for k2 in S.divisors(ob):
                    if k1 * k2 < cfg["min_orbit_size"] * 2 or (k1 == 1 and k2 == 1):
                        continue
                    # generic orbit size is lcm-ish; estimate orbit count conservatively as size / (k1*k2/gcd)
                    g = math.gcd(k1, k2)
                    est = int(size / (k1 * k2 / g)) + 2
                    if est > maxo or est < 8:
                        continue
                    tasks.append({"n": n, "kind": "product", "a": a, "k1": k1, "k2": k2, "orbits_est": est, "name": f"n{n}-prod{a}+{b}-{k1}x{k2}"})
        # coordinate symmetries
        for nm, spec in (("shift", {"kind": "coord", "gens": ["shift"]}), ("shift+neg", {"kind": "coord", "gens": ["shift", "neg"]}),
                         ("dihedral", {"kind": "coord", "gens": ["shift", "rev"]}), ("dihedral+neg", {"kind": "coord", "gens": ["shift", "rev", "neg"]})):
            est = int(size / (n if "rev" not in spec["gens"] else 2 * n) / (2 if "neg" in spec["gens"] else 1)) + 2
            if est <= maxo:
                tasks.append({"n": n, "orbits_est": est, "name": f"n{n}-{nm}", **spec})
        if n == 8:
            # the symmetry visible in the published 512-cap: the three reflections i <-> -i, and negation
            tasks.append({"n": 8, "kind": "coord", "gens": ["refl"], "orbits_est": 3 ** 8 // 2, "name": "n8-reflection"})
            tasks.append({"n": 8, "kind": "coord", "gens": ["refl", "neg"], "orbits_est": 3 ** 8 // 4, "name": "n8-reflection-neg"})
            tasks.append({"n": 8, "kind": "coord", "gens": ["refl", "neg", "swap17_26"], "orbits_est": 3 ** 8 // 8, "name": "n8-refl-neg-pairswap"})
    # de-duplicate by name, sort by estimated cost
    seen, out = set(), []
    for t in sorted(tasks, key=lambda t: (t["orbits_est"], t["n"])):
        if t["name"] in seen:
            continue
        seen.add(t["name"])
        out.append(t)
    return out


def build_group(task: Dict) -> List[np.ndarray]:
    sp = space(task["n"])
    kind = task["kind"]
    if kind == "singer":
        return [S.singer_subgroup_generator(sp, task["k"])]
    if kind == "singer+neg":
        return [S.singer_subgroup_generator(sp, task["k"]), S.negation(sp)]
    if kind == "product":
        return S.product_singer(sp, task["a"], task["k1"], task["k2"])
    if kind == "coord":
        gens = []
        for g in task["gens"]:
            if g == "shift":
                gens.append(S.cyclic_shift(sp))
            elif g == "rev":
                gens.append(S.reversal(sp))
            elif g == "neg":
                gens.append(S.negation(sp))
            elif g == "refl":
                n = sp.n
                gens.append(S.coordinate_permutation(sp, [0] + [n - i for i in range(1, n)]))
            elif g == "swap17_26":
                n = sp.n
                perm = list(range(n))
                perm[1], perm[2] = 2, 1
                perm[n - 1], perm[n - 2] = n - 2, n - 1
                gens.append(S.coordinate_permutation(sp, perm))
        return gens
    raise ValueError(kind)


def time_limit_for(cfg: Dict, n_orbits: int, pass_no: int) -> float:
    tl = cfg["time_limit"]
    base = tl["small"] if n_orbits <= 300 else tl["medium"] if n_orbits <= 1000 else tl["large"]
    return base * (cfg["second_pass_factor"] ** (pass_no - 1))


def run_task(args) -> Dict:
    """Worker: one exact task. Writes its own result file; returns a summary."""
    task, cfg, pass_no = args
    n = task["n"]
    sp = space(n)
    out_path = RESULTS / f"{task['name']}.json"
    t0 = time.time()
    try:
        gens = build_group(task)
        ids, orbs = S.orbits(sp.size, gens)
        record = int(cfg["records"].get(str(n), 0))
        maxo = int(cfg["max_orbits"].get(str(n), 1500))
        if len(orbs) > maxo:
            result = {"task": task, "pass": pass_no, "n": n, "n_orbits": len(orbs), "status": "SKIPPED", "size": 0, "bound": None,
                      "record_to_beat": record, "note": f"{len(orbs)} orbits > max_orbits {maxo}",
                      "finished": dt.datetime.now().isoformat(timespec="seconds"), "wall_seconds": round(time.time() - t0, 1)}
            out_path.write_text(json.dumps(result, indent=1))
            return result
        # hint: a known cap that happens to be invariant
        hint = None
        for name, pts in known_caps(n):
            if S.invariant(pts, gens):
                hint = pts
                break
        tl = time_limit_for(cfg, len(orbs), pass_no)
        res = O.solve(sp, ids, orbs, time_limit=tl, workers=cfg["threads_per_solve"], hint_pts=hint)
        pts = res.pop("points")
        result = {"task": task, "pass": pass_no, "n": n, "n_orbits": len(orbs), "orbit_sizes": sorted(set(len(o) for o in orbs)),
                  "record_to_beat": record, "hint": bool(hint), "time_limit": tl, **res,
                  "finished": dt.datetime.now().isoformat(timespec="seconds"), "wall_seconds": round(time.time() - t0, 1)}
        result["beats_record"] = bool(res.get("valid")) and res["size"] > record
        result["could_still_beat"] = (res["status"] not in ("OPTIMAL", "INFEASIBLE")) and (res.get("bound") is None or res["bound"] > record)
        if result["beats_record"]:
            save_record(n, pts, f"exact:{task['name']}", result)
        elif res.get("valid") and res["size"] >= record and hint is None:
            save_cap(n, pts, f"tie:{task['name']}")
        out_path.write_text(json.dumps(result, indent=1))
        return result
    except Exception as e:  # noqa: BLE001
        result = {"task": task, "pass": pass_no, "n": n, "status": "ERROR", "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-2000:],
                  "finished": dt.datetime.now().isoformat(timespec="seconds"), "wall_seconds": round(time.time() - t0, 1)}
        out_path.write_text(json.dumps(result, indent=1))
        return result


# ------------------------------------------------------------------------------------------------- records

def save_cap(n: int, pts: List[int], how: str) -> pathlib.Path:
    sp = space(n)
    dg = C.cap_digest(sp, pts)
    p = STATE / "caps" / f"cap_n{n}_{len(pts)}_{dg}.txt"
    p.parent.mkdir(exist_ok=True)
    if not p.exists():
        p.write_text("\n".join(" ".join(map(str, v)) for v in sp.vectors_of(sorted(pts)).tolist()) + "\n")
        (p.with_suffix(".json")).write_text(json.dumps({"n": n, "size": len(pts), "how": how, "digest": dg,
                                                         "when": dt.datetime.now().isoformat(timespec="seconds")}, indent=1))
    return p


def save_record(n: int, pts: List[int], how: str, extra: Optional[Dict] = None) -> Optional[pathlib.Path]:
    """A claimed record is re-verified by the independent pure-Python checker before it is accepted."""
    sp = space(n)
    if not C.verify(sp, pts):
        log(f"RECORD CLAIM REJECTED by capset.verify (n={n}, {len(pts)} pts, {how})")
        return None
    dg = C.cap_digest(sp, pts)
    p = RECORDS / f"cap_n{n}_{len(pts)}_{dg}.txt"
    p.write_text("# cap set in F_3^%d, %d points, found by %s on %s\n" % (n, len(pts), how, dt.datetime.now().isoformat(timespec="seconds"))
                 + "\n".join(" ".join(map(str, v)) for v in sp.vectors_of(sorted(pts)).tolist()) + "\n")
    chk = subprocess.run([sys.executable, str(HERE / "verify_record.py"), str(p)], capture_output=True, text=True, timeout=3600)
    ok = chk.returncode == 0
    meta = {"n": n, "size": len(pts), "how": how, "digest": dg, "independent_check": chk.stdout.strip(), "verified": ok,
            "sha256_of_file": hashlib.sha256(p.read_bytes()).hexdigest(), "when": dt.datetime.now().isoformat(timespec="seconds"), "extra": extra or {}}
    p.with_suffix(".json").write_text(json.dumps(meta, indent=1))
    if ok:
        log(f"*** RECORD: cap of size {len(pts)} in F_3^{n} ({how}) — independently verified — {p}")
    else:
        log(f"RECORD CLAIM FAILED INDEPENDENT CHECK: {p} :: {chk.stdout[-300:]}")
    return p if ok else None


# ------------------------------------------------------------------------------------------------- LNS workers

def best_cap_on_disk(n: int) -> Optional[Tuple[str, List[int]]]:
    """The largest cap for dimension n saved by any worker on any machine (state/caps here, records here and synced)."""
    best = None
    for d in [STATE / "caps", RECORDS] + [p / "records" for p in (STATE / "remote").glob("*")]:
        for j in d.glob(f"cap_n{n}_*.json"):
            try:
                meta = json.loads(j.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if best is None or int(meta.get("size", 0)) > best[0]:
                best = (int(meta["size"]), j.with_suffix(".txt"), meta.get("how", j.stem))
    if best is None:
        return None
    sp = space(n)
    vecs = [[int(c) for c in line.split()] for line in best[1].read_text().splitlines() if line.strip() and not line.startswith("#")]
    pts = sp.indices(vecs).tolist()
    return (f"disk:{best[2]}", pts) if C.verify(sp, pts) else None


def lns_worker(n: int, cfg: Dict, idx: int):
    sp = space(n)
    rng = random.Random(1000 * n + idx + int(time.time()))
    seeds = known_caps(n)
    if not seeds:
        log(f"lns n={n}: no seed cap; worker exits")
        return
    name, pts = seeds[0]
    disk = best_cap_on_disk(n)
    if disk and len(disk[1]) > len(pts):
        name, pts = disk
    record = int(cfg["records"].get(str(n), 0))
    st = C.CapState(sp, pts)
    last_adopt = time.time()
    status_path = STATE / f"lns_n{n}_{idx}.json"
    stats = {"n": n, "worker": idx, "seed": name, "start": len(pts), "current": len(pts), "best": len(pts), "steps": 0,
             "by_kind": {}, "started": dt.datetime.now().isoformat(timespec="seconds"), "last": None, "record_to_beat": record}
    kinds = ["coord", "coords2", "affine", "affine2", "random", "random", "coord"]
    while True:
        kind = rng.choice(kinds)
        # neighbourhood size budget: aim for a free set the solver can handle
        tl = rng.choice((20, 60, 180)) if n <= 9 else rng.choice((60, 180, 600)) if n <= 11 else rng.choice((180, 600, 1200))
        try:
            rec = L.lns_step(st, rng, kind, time_limit=tl, workers=cfg["threads_per_solve"])
        except Exception as e:  # noqa: BLE001
            log(f"lns n={n}#{idx}: step error {type(e).__name__}: {e}; restarting from seed")
            st = C.CapState(sp, pts)
            continue
        stats["steps"] += 1
        stats["current"] = len(st.pts)
        # every ten minutes, adopt a better cap if another worker (or machine) has found one
        if time.time() - last_adopt > 600:
            last_adopt = time.time()
            disk = best_cap_on_disk(n)
            if disk and len(disk[1]) > len(st.pts):
                st = C.CapState(sp, disk[1])
                stats["adopted"] = {"from": disk[0], "size": len(disk[1]), "at": dt.datetime.now().isoformat(timespec="seconds")}
                stats["best"] = max(stats["best"], len(disk[1]))
        k = stats["by_kind"].setdefault(kind, {"steps": 0, "free_max": 0, "optimal": 0})
        k["steps"] += 1
        k["free_max"] = max(k["free_max"], rec.get("free", 0))
        if str(rec.get("status", "")).startswith("OPTIMAL"):
            k["optimal"] += 1
        stats["last"] = {**rec, "at": dt.datetime.now().isoformat(timespec="seconds")}
        if len(st.pts) > stats["best"]:
            stats["best"] = len(st.pts)
            save_cap(n, list(st.pts), f"lns:{name}:{kind}")
            if len(st.pts) > record:
                save_record(n, list(st.pts), f"lns from {name} ({kind})", {"stats": stats})
        status_path.write_text(json.dumps(stats, indent=1))


# ------------------------------------------------------------------------------------------------- status page

def _load_json_dir(d: pathlib.Path, pattern: str, tag: Optional[str] = None) -> List[Dict]:
    out = []
    for p in d.glob(pattern):
        try:
            r = json.loads(p.read_text())
            if tag:
                r["machine"] = tag
            out.append(r)
        except (json.JSONDecodeError, OSError):
            pass
    return out


def collect_status(cfg: Dict, tasks: List[Dict]) -> Dict:
    me = cfg.get("machine") or os.uname().nodename
    results = _load_json_dir(RESULTS, "*.json", me)
    lns = _load_json_dir(STATE, "lns_n*.json", me)
    records = _load_json_dir(RECORDS, "*.json", me)
    machines = [{"name": me, "tasks_done": len(results), "synced": "local"}]
    for rem in cfg.get("remotes") or []:
        rd = STATE / "remote" / rem["name"]
        rr = _load_json_dir(rd / "results", "*.json", rem["name"])
        results += rr
        lns += _load_json_dir(rd / "lns", "lns_n*.json", rem["name"])
        records += [r for r in _load_json_dir(rd / "records", "*.json", rem["name"])
                    if r.get("verified") and (rd / "verified_here" / f"cap_n{r['n']}_{r['size']}_{r['digest']}.ok").exists()]
        stamp = rd / "synced.txt"
        machines.append({"name": rem["name"], "tasks_done": len(rr), "synced": stamp.read_text().strip() if stamp.exists() else "never"})
    # a task may appear from two machines (overlap after resharding): keep the stronger result
    best_by_name: Dict[str, Dict] = {}
    for r in results:
        nm = r.get("task", {}).get("name")
        if not nm:
            continue
        cur = best_by_name.get(nm)
        if cur is None or (r.get("size", 0), r.get("status") == "OPTIMAL") > (cur.get("size", 0), cur.get("status") == "OPTIMAL"):
            best_by_name[nm] = r
    results = list(best_by_name.values())
    by_name = best_by_name
    per_dim = {}
    for n in cfg["dims"]:
        rs = [r for r in results if r.get("n") == n and r.get("status") not in (None, "ERROR")]
        done = len(rs)
        total = sum(1 for t in tasks if t["n"] == n)
        best = max([r.get("size", 0) for r in rs] + [0])
        proven = sum(1 for r in rs if r.get("status") == "OPTIMAL")
        open_ = sum(1 for r in rs if r.get("could_still_beat"))
        per_dim[n] = {"record": cfg["records"].get(str(n)), "source": cfg["record_sources"].get(str(n), ""), "tasks_total": total,
                      "tasks_done": done, "best_exact": best, "proven": proven, "still_open": open_,
                      "errors": sum(1 for r in results if r.get("n") == n and r.get("status") == "ERROR"),
                      "lns": [x for x in lns if x.get("n") == n]}
    recent = sorted(rs_all := [r for r in results if r.get("status") != "ERROR"], key=lambda r: r.get("finished", ""), reverse=True)[:12]
    return {"when": dt.datetime.now().isoformat(timespec="seconds"), "per_dim": per_dim, "records": sorted(records, key=lambda r: r.get("when", ""), reverse=True), "machines": machines,
            "recent": [{k: r.get(k) for k in ("n", "status", "size", "bound", "record_to_beat", "n_orbits", "solve_seconds", "finished", "beats_record")} | {"name": r["task"]["name"]} for r in recent],
            "queue_total": len(tasks), "done_total": len(by_name), "cpu": os.cpu_count(), "load": os.getloadavg()[0] if hasattr(os, "getloadavg") else None,
            "errors": [{"name": r["task"]["name"], "error": r.get("error")} for r in results if r.get("status") == "ERROR"][:10]}


def render_html(st: Dict, cfg: Dict) -> str:
    E = html.escape
    rec_banner = ""
    if st["records"]:
        best = {}
        for r in st["records"]:
            if r["n"] not in best or r["size"] > best[r["n"]]["size"]:
                best[r["n"]] = r
        rows = ""
        for n in sorted(best):
            r0 = best[n]
            rec = cfg["records"].get(str(n), "?")
            rows += (f'<p class="big">F<sub>3</sub><sup>{n}</sup>: a cap of <strong>{r0["size"]}</strong> points — previous best known {rec} '
                     f'({E(cfg["record_sources"].get(str(n), ""))}) · found by {E(str(r0["how"]))} on {E(str(r0.get("machine", "")))}, verified on every machine.</p>'
                     f'<p class="mono">cap_n{n}_{r0["size"]}_{E(r0["digest"])}.txt · sha256 {E(r0["sha256_of_file"][:16])}… · {E(r0["when"])}</p>')
        rec_banner = (f'<section class="banner"><h2>New records — {len(best)} dimension{"s" if len(best) != 1 else ""}, {len(st["records"])} verified caps above the known bound</h2>{rows}'
                      '<p>Files live in <code>records/</code> on the machine that found them (and under <code>state/remote/&lt;machine&gt;/records/</code> here). '
                      'Verify any of them: <code>python3 verify_record.py &lt;file&gt;</code>. Before calling it a record in public, check the literature for a larger cap in that dimension.</p></section>')
    dims = ""
    for n, d in st["per_dim"].items():
        frac = (d["tasks_done"] / d["tasks_total"]) if d["tasks_total"] else 0
        lns_rows = "".join(f'<li>LNS worker {x["worker"]} on {E(str(x.get("machine", "")))}: from {E(x["seed"])} ({x["start"]}) · now {x["current"]} · best {x["best"]} · {x["steps"]} moves'
                           + (f' · last: {E(x["last"]["kind"])} removed {x["last"]["removed"]}, free {x["last"]["free"]}, {E(str(x["last"]["status"]))} in {x["last"]["secs"]}s' if x.get("last") else "") + "</li>"
                           for x in d["lns"])
        dims += f'''<div class="dim"><div class="dimhead"><span class="n">n = {n}</span><span class="rec">record to beat <strong>{d["record"]}</strong> <small>({E(d["source"])})</small></span></div>
<div class="bar"><div class="fill" style="width:{frac*100:.1f}%"></div><span>{d["tasks_done"]} of {d["tasks_total"]} symmetry groups searched</span></div>
<div class="facts"><span>best exact cap so far <strong>{d["best_exact"]}</strong></span><span>proven optimal (for its symmetry) <strong>{d["proven"]}</strong></span><span>still open <strong>{d["still_open"]}</strong></span>{f'<span class="err">errors {d["errors"]}</span>' if d["errors"] else ""}</div>
{f'<ul class="lns">{lns_rows}</ul>' if lns_rows else ""}</div>'''
    recent = "".join(f'<tr class="{"hit" if r["beats_record"] else ""}"><td>{E(r["name"])}</td><td>{r["n_orbits"]}</td><td>{E(str(r["status"]))}</td><td>{r["size"]}</td><td>{r["bound"] if r["bound"] is not None else "—"}</td><td>{r["record_to_beat"]}</td><td>{r["solve_seconds"]}s</td><td>{E(str(r["finished"]))[11:19]}</td></tr>' for r in st["recent"])
    errs = "".join(f"<li>{E(e['name'])}: {E(str(e['error']))}</li>" for e in st["errors"])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30">
<title>Cap set engine</title><style>
:root{{color-scheme:dark;--ink:#0e1320;--surface:#151c2c;--line:#263048;--paper:#ece6d8;--paper-2:#b9b3a6;--slate:#7f8aa3;--gold:#e8c56a;--live:#4fbf8c;--red:#d96565}}
body{{margin:0;background:var(--ink);color:var(--paper);font:16px/1.5 system-ui,sans-serif;padding:0 16px 48px}}.wrap{{max-width:980px;margin:0 auto}}
h1{{font:600 26px/1.2 Georgia,serif;letter-spacing:.04em;margin:28px 0 4px}}.sub{{color:var(--slate);margin:0 0 24px;font-size:14px}}
.banner{{background:color-mix(in srgb,var(--gold) 18%,var(--surface));border:1px solid var(--gold);border-radius:14px;padding:18px 22px;margin:0 0 24px}}.banner h2{{margin:0 0 6px;color:var(--gold);font-size:15px}}
.big{{font:300 28px/1.25 Georgia,serif;margin:0 0 8px}}.mono{{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:var(--paper-2)}}
.dim{{border-top:1px solid var(--line);padding:18px 0}}.dimhead{{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}}.n{{font:600 22px Georgia,serif}}.rec{{color:var(--paper-2)}}.rec strong{{color:var(--paper);font-size:20px}}
.bar{{position:relative;height:26px;border-radius:13px;background:var(--surface);border:1px solid var(--line);overflow:hidden;margin:10px 0}}.fill{{height:100%;background:var(--live)}}.bar span{{position:absolute;inset:0;display:flex;align-items:center;padding-left:12px;font-size:13px;color:var(--paper)}}
.facts{{display:flex;gap:22px;flex-wrap:wrap;color:var(--paper-2);font-size:14px}}.facts strong{{color:var(--paper)}}.err{{color:var(--red)}}
ul.lns{{margin:10px 0 0;padding-left:18px;color:var(--paper-2);font-size:14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}}th{{color:var(--slate);font-weight:400}}tr.hit td{{color:var(--gold);font-weight:600}}
h2{{font:400 15px system-ui;color:var(--slate);margin:26px 0 8px}}.explain{{color:var(--paper-2);font-size:15px;max-width:70ch}}
footer{{color:var(--slate);font-size:13px;margin-top:30px}}
</style></head><body><div class="wrap">
<h1>CAP SET ENGINE</h1><p class="sub">Looking for a cap set larger than any known, in dimensions {", ".join(str(n) for n in cfg["dims"])}. {E(st["when"])} · {st["done_total"]} of {st["queue_total"]} exact tasks done · machines: {", ".join(f'{E(m["name"])} ({m["tasks_done"]} done, sync {E(str(m["synced"]))[:19]})' for m in st["machines"])} · this box: {st["cpu"]} cores, load {st["load"]:.1f}</p>
{rec_banner}
<p class="explain">A cap set is a set of points in F<sub>3</sub><sup>n</sup> with no three on a line. Each exact task picks a symmetry of the space and finds the largest cap with that symmetry — a small enough problem to solve to proven optimality. Beating the record in any row would be a new mathematical result; a proven "no" is a theorem too. LNS workers meanwhile try to grow the best known caps by removing chunks and refilling them optimally.</p>
{dims}
<h2>Recently finished exact tasks</h2>
<table><tr><th>task</th><th>orbits</th><th>status</th><th>size</th><th>bound</th><th>record</th><th>solve</th><th>when</th></tr>{recent}</table>
{f'<h2>Errors</h2><ul>{errs}</ul>' if errs else ""}
<footer>Everything on this page is derived from state/ and records/. A record is only shown after verify_record.py (pure Python, no numpy) re-checked the file.</footer>
</div></body></html>'''


def sync_loop(cfg: Dict):
    """Pull results, LNS status and verified records from the other machines (rsync over ssh), once a minute."""
    rems = cfg.get("remotes") or []
    if not rems:
        return
    while True:
        for rem in rems:
            rd = STATE / "remote" / rem["name"]
            ok = True
            for sub, pat in (("results", "state/results/"), ("lns", "state/"), ("records", "records/")):
                (rd / sub).mkdir(parents=True, exist_ok=True)
                src = f'{rem["ssh"]}:{rem["path"].rstrip("/")}/{pat}'
                cmd = ["rsync", "-az", "--timeout=60", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=15", src, str(rd / sub) + "/"]
                if sub == "lns":
                    cmd[1:1] = ["--include=lns_n*.json", "--include=*/", "--exclude=*"]
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                    if r.returncode != 0:
                        ok = False
                        log(f"sync {rem['name']}/{sub}: rsync rc {r.returncode}: {r.stderr.strip()[-200:]}")
                except (OSError, subprocess.SubprocessError) as e:
                    ok = False
                    log(f"sync {rem['name']}/{sub}: {type(e).__name__}: {e}")
            if ok:
                (rd / "synced.txt").write_text(dt.datetime.now().isoformat(timespec="seconds"))
                # re-verify any remote record here before it can reach the banner
                for j in (rd / "records").glob("*.json"):
                    try:
                        meta = json.loads(j.read_text())
                    except json.JSONDecodeError:
                        continue
                    mark = rd / "verified_here" / (j.stem + ".ok")
                    bad = rd / "verified_here" / (j.stem + ".bad")
                    if meta.get("verified") and not mark.exists() and not bad.exists():
                        mark.parent.mkdir(exist_ok=True)
                        txt = j.with_suffix(".txt")
                        chk = subprocess.run([sys.executable, str(HERE / "verify_record.py"), str(txt)], capture_output=True, text=True, timeout=3600)
                        (mark if chk.returncode == 0 else bad).write_text(chk.stdout.strip() + "\n")
                        log(f"remote record {txt.name} from {rem['name']}: {'VERIFIED here' if chk.returncode == 0 else 'FAILED verification here'}")
        time.sleep(60)


def status_loop(cfg: Dict, tasks: List[Dict]):
    while True:
        try:
            st = collect_status(cfg, tasks)
            (STATE / "status.json").write_text(json.dumps(st, indent=1))
            (HERE / "status.html").write_text(render_html(st, cfg))
        except Exception as e:  # noqa: BLE001
            log(f"status error: {type(e).__name__}: {e}")
        time.sleep(cfg["status_every"])


class Quiet(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path in ("/", ""):
            self.path = "/status.html"
        return super().do_GET()


def serve(cfg: Dict):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((cfg["host"], int(cfg["port"])), Quiet) as httpd:
        httpd.serve_forever()


# ------------------------------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--tasks", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    tasks = task_list(cfg)
    if args.tasks:
        mine = {t["name"] for t in my_tasks(cfg, tasks)}
        for t in tasks:
            print(f"{t['name']:36s} ~{t['orbits_est']:6d} orbits {'(mine)' if t['name'] in mine else ''}")
        print(len(tasks), "tasks,", len(mine), "on this machine")
        return
    if args.status:
        print(json.dumps(collect_status(cfg, tasks), indent=1)[:4000])
        return
    log(f"engine start: {len(tasks)} exact tasks, {cfg['solver_workers']} solver workers x {cfg['threads_per_solve']} threads, "
        f"{cfg['lns_workers']} LNS workers on dims {cfg['lns_dims']}, dashboard on {cfg['host']}:{cfg['port']}")
    threading.Thread(target=serve, args=(cfg,), daemon=True).start()
    threading.Thread(target=status_loop, args=(cfg, tasks), daemon=True).start()
    threading.Thread(target=sync_loop, args=(cfg,), daemon=True).start()
    mine = my_tasks(cfg, tasks)
    log(f"this machine owns {len(mine)} of {len(tasks)} tasks (shard {cfg.get('shard')})")
    procs = []
    for i in range(int(cfg["lns_workers"])):
        n = cfg["lns_dims"][i % len(cfg["lns_dims"])]
        p = mp.Process(target=lns_worker, args=(n, cfg, i), daemon=True, name=f"lns-n{n}-{i}")
        p.start()
        procs.append(p)
    done = {p.stem for p in RESULTS.glob("*.json")}
    while True:
        pending = [(t, cfg, 1) for t in mine if t["name"] not in done]
        # second pass: unresolved tasks that could still beat the record
        for p in RESULTS.glob("*.json"):
            try:
                r = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            if r.get("could_still_beat") and r.get("pass", 1) < 3:
                pending.append((r["task"], cfg, r["pass"] + 1))
        if not pending:
            log("all tasks done (including second passes); LNS keeps running. Sleeping 1h.")
            time.sleep(3600)
            continue
        log(f"{len(pending)} tasks pending")
        with mp.Pool(processes=int(cfg["solver_workers"]), maxtasksperchild=4) as pool:
            for r in pool.imap_unordered(run_task, pending):
                nm = r["task"]["name"]
                done.add(nm)
                log(f"task {nm}: {r.get('status')} size={r.get('size')} bound={r.get('bound')} orbits={r.get('n_orbits')} "
                    f"record={r.get('record_to_beat')} {('*** BEATS RECORD ***' if r.get('beats_record') else '')} {r.get('error', '')}")
        for p in procs:
            if not p.is_alive():
                log(f"{p.name} died; restarting")
                i = int(p.name.split("-")[-1]); n = int(p.name.split("-")[1][1:])
                q = mp.Process(target=lns_worker, args=(n, cfg, i), daemon=True, name=p.name)
                q.start()
                procs[procs.index(p)] = q


if __name__ == "__main__":
    mp.set_start_method("fork")
    main()
