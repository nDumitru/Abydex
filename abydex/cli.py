"""Abydex command line."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, advisor, catalog, generate, workflow
from .memory import Memory


def _out(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:  # old Windows consoles
        print(text.encode("ascii", "replace").decode())


def cmd_printers(a):
    for pid, p in catalog.printers().items():
        extra = "inchisa" if p.get("enclosed") else ("deschisa" if p["technology"] == "fdm" else "")
        _out(f"  {pid:24} {p['name']:36} {p['technology']:5} {extra}")


def cmd_materials(a):
    techs = [a.tech] if a.tech else ["fdm", "resin", "sls"]
    for t in techs:
        _out(f"[{t}]")
        for mid, m in catalog.materials().items():
            if m["technology"] == t:
                _out(f"  {mid:24} {m['name']}")


def _print_result(r: dict):
    rec = r["recommendation"]
    a = r["analysis"]
    _out(f"\n== {r['name']}  (job #{r['job_id']}) ==")
    _out(f"Dimensiuni: {' x '.join(map(str, a['dims_mm']))} mm | volum: {a['volume_cm3']} cm3 | "
         f"console: {a['overhang_frac']*100:.1f}% | watertight: {'da' if a['watertight'] else 'nu'}")
    rep = r["repair"]
    if rep["removed_fragments"] or rep["holes_filled"] or rep["scaled_by"] != 1.0:
        _out(f"Reparat: {rep['removed_fragments']} fragmente sterse, gauri umplute: "
             f"{'da' if rep['holes_filled'] else 'nu'}, scalat x{rep['scaled_by']:.3f}")
    _out("\nSetari:")
    for k, v in rec["settings"].items():
        if k == "nozzle":
            continue
        name, unit = advisor.LABELS.get(k, (k, ""))
        if isinstance(v, bool):
            v, unit = ("da" if v else "nu"), ""
        _out(f"  {name:28} {v} {unit}")
    for w in rec["warnings"] + rep.get("notes", []):
        _out(f"  ! {w}")
    for x in rec["reasons"]:
        _out(f"  - {x}")
    _out("\nFisiere:")
    for f in r["files"]:
        _out(f"  {f}")
    _out(f"\nDupa print spune-mi cum a iesit:  abydex feedback {r['job_id']} --ok   "
         f"sau  --fail --issues warping,stringing")


def cmd_prepare(a):
    r = workflow.prepare_job(a.model, a.printer, a.material, a.layer, a.nozzle, a.size, a.name,
                             a.out, orient=not a.no_orient)
    if a.json:
        _out(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        _print_result(r)


def cmd_feedback(a):
    mem = Memory()
    job = mem.get_job(a.job_id)
    if not job:
        sys.exit(f"Nu exista job-ul #{a.job_id}")
    tech = catalog.get_material(job["material_id"])["technology"]
    issues = [i.strip() for i in (a.issues or "").split(",") if i.strip()]
    valid = advisor.describe_issues(tech)
    bad = [i for i in issues if i not in valid]
    if bad:
        sys.exit(f"Probleme necunoscute: {bad}. Valide: {', '.join(valid)}")
    outcome = "fail" if a.fail else "partial" if (a.partial or issues) and not a.ok else "ok"
    actual = {}
    for kv in a.set or []:
        k, _, v = kv.partition("=")
        actual[k.strip()] = float(v)
    mem.add_feedback(a.job_id, outcome, a.rating, issues, a.notes or "", actual or None)
    _out(f"Multumesc! Am salvat: job #{a.job_id} -> {outcome}" + (f" ({', '.join(issues)})" if issues else ""))
    _out("Data viitoare recomandarile pentru piese similare vor tine cont de asta.")


def cmd_issues(a):
    for t in ("fdm", "resin"):
        _out(f"[{t}]")
        for k, v in advisor.describe_issues(t).items():
            _out(f"  {k:18} {v}")


def cmd_history(a):
    mem = Memory()
    s = mem.stats()
    _out(f"Proiecte: {s['projects']} | joburi: {s['jobs']} | cu feedback: {s['with_feedback']} "
         f"(reusite {s['ok']}, esuate {s['fail']})\n")
    for j in mem.recent_jobs(a.limit):
        res = j["outcome"] or "fara feedback"
        iss = f" [{', '.join(j['issues'])}]" if j["issues"] else ""
        _out(f"  #{j['id']:<4} {j['project_name'][:28]:28} {j['printer_id']:16} {j['material_id']:10} {res}{iss}")


def cmd_recommend(a):
    r = advisor.recommend(a.printer, a.material, None, a.layer, a.nozzle, memory=Memory())
    _out(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))


def cmd_engine(a):
    if a.action == "list":
        for k, e in generate.ENGINES.items():
            st = "instalat" if generate.is_installed(k) else "neinstalat"
            _out(f"  {k:10} {e['name']} ({e['license']}) - {st}. {e['info']}")
    else:
        generate.install(a.name, log=_out)


def cmd_generate(a):
    out = Path(a.out or Path(a.image).with_suffix(".obj"))
    _out("Generez modelul 3D (pe procesor poate dura cateva minute)...")
    mesh_path = generate.generate(a.image, out, a.engine, a.resolution)
    _out(f"Model generat: {mesh_path}")
    if a.printer and a.material:
        r = workflow.prepare_job(mesh_path, a.printer, a.material, a.layer, a.nozzle,
                                 a.size or 50.0, a.name or Path(a.image).stem)
        _print_result(r)


def cmd_text(a):
    from . import textcad
    from .memory import Memory
    if a.show or not (a.printer and a.material):
        mem = Memory()
        d = textcad.understand(a.text, a.mode, use_llm=not a.no_llm, past=mem.good_text_designs())
        mem.close()
        _out(json.dumps(d, indent=2, ensure_ascii=False))
        if not (a.printer and a.material):
            _out("\nAdauga -p IMPRIMANTA -m MATERIAL ca sa generez si piesa pentru print.")
        return
    r = workflow.text_to_3d(a.text, a.printer, a.material, a.layer, a.nozzle, a.name, a.mode,
                            size_mm=a.size, use_llm=not a.no_llm, log=_out)
    d = r["design"]
    _out(f"Interpretare ({d.get('source')}): " + (d.get("template") or ("CSG" if "csg" in d else "obiect decorativ")))
    if d.get("params"):
        _out("  " + ", ".join(f"{k}={v}" for k, v in d["params"].items()))
    for n in d.get("notes", []):
        _out(f"  - {n}")
    _print_result(r)


def cmd_templates(a):
    from . import templates
    for n, t in templates.describe().items():
        _out(f"{n:10} {t['label']} - {t['description']}")
        _out("           " + ", ".join(f"{k}={v['default']}" for k, v in t["params"].items()))


def cmd_doctor(a):
    from . import doctor, logs
    ok, lines = doctor.run()
    for line in lines:
        _out(line)
    _out(f"\nLog: {logs.log_path()}")
    _out("Totul e in regula." if ok else "Sunt probleme - copiaza textul de mai sus intr-un issue pe GitHub.")
    if not ok:
        raise SystemExit(1)


def cmd_update(a):
    from . import updates
    r = updates.check(force=True)
    if r.get("disabled"):
        _out("Verificarea de update e dezactivata (ABYDEX_NO_UPDATE_CHECK).")
    elif r.get("error"):
        _out(f"Nu am putut verifica: {r['error']}")
    elif not r.get("latest"):
        _out(f"Ai versiunea {r['current']}. Inca nu exista niciun release publicat.")
    elif r["update_available"]:
        _out(f"Versiune noua: {r['latest']} (ai {r['current']}). Descarca: {r['url']}")
    else:
        _out(f"Ai ultima versiune ({r['current']}).")


def cmd_ui(a):
    from .webui.server import serve
    serve(a.port, open_browser=not a.no_browser)


def cmd_info(a):
    _out(f"Abydex {__version__}")
    _out(f"Folder date: {catalog.user_dir()}")
    _out("Poti adauga imprimante/materiale proprii in printers.json / materials.json din acel folder.")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="abydex", description="Abydex - AI local pentru printare 3D")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("printers", help="lista imprimante").set_defaults(fn=cmd_printers)
    p = sub.add_parser("materials", help="lista materiale")
    p.add_argument("--tech", choices=["fdm", "resin", "sls"])
    p.set_defaults(fn=cmd_materials)
    sub.add_parser("issues", help="lista problemelor posibile pentru feedback").set_defaults(fn=cmd_issues)
    sub.add_parser("info", help="unde sunt datele").set_defaults(fn=cmd_info)

    def common(p):
        p.add_argument("-p", "--printer", required=True)
        p.add_argument("-m", "--material", required=True)
        p.add_argument("-l", "--layer", type=float, help="inaltime strat (mm)")
        p.add_argument("--nozzle", type=float, default=0.4)

    p = sub.add_parser("prepare", help="repara + orienteaza + recomanda setari pentru un model")
    p.add_argument("model")
    common(p)
    p.add_argument("--size", type=float, help="scaleaza la aceasta dimensiune maxima (mm)")
    p.add_argument("--name")
    p.add_argument("-o", "--out", help="folder pentru fisierele exportate")
    p.add_argument("--no-orient", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_prepare)

    p = sub.add_parser("recommend", help="doar setari (fara model)")
    common(p)
    p.set_defaults(fn=cmd_recommend)

    p = sub.add_parser("feedback", help="spune cum a iesit printul, ca aplicatia sa invete")
    p.add_argument("job_id", type=int)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--ok", action="store_true")
    g.add_argument("--partial", action="store_true")
    g.add_argument("--fail", action="store_true")
    p.add_argument("--issues", help="ex: warping,stringing (vezi: abydex issues)")
    p.add_argument("--rating", type=int, choices=range(1, 6))
    p.add_argument("--notes")
    p.add_argument("--set", action="append", metavar="CHEIE=VALOARE",
                   help="valori schimbate de tine in slicer, ex: --set nozzle_temp=255")
    p.set_defaults(fn=cmd_feedback)

    p = sub.add_parser("history", help="istoric proiecte si printuri")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_history)

    p = sub.add_parser("engine", help="motoare AI (list / install)")
    p.add_argument("action", choices=["list", "install"])
    p.add_argument("name", nargs="?", default="triposr")
    p.set_defaults(fn=cmd_engine)

    p = sub.add_parser("generate", help="poza -> model 3D (AI), optional si pregatire pentru print")
    p.add_argument("image")
    p.add_argument("-o", "--out")
    p.add_argument("--engine", default="triposr")
    p.add_argument("--resolution", type=int, default=256)
    p.add_argument("-p", "--printer")
    p.add_argument("-m", "--material")
    p.add_argument("-l", "--layer", type=float)
    p.add_argument("--nozzle", type=float, default=0.4)
    p.add_argument("--size", type=float, help="dimensiunea maxima dorita (mm), implicit 50")
    p.add_argument("--name")
    p.set_defaults(fn=cmd_generate)

    p = sub.add_parser("text", help="descriere text -> piesa 3D pregatita pentru print")
    p.add_argument("text")
    p.add_argument("-p", "--printer")
    p.add_argument("-m", "--material")
    p.add_argument("-l", "--layer", type=float)
    p.add_argument("--nozzle", type=float, default=0.4)
    p.add_argument("--mode", choices=["auto", "technical", "organic"], default="auto")
    p.add_argument("--size", type=float, help="dimensiunea maxima (mm)")
    p.add_argument("--name")
    p.add_argument("--no-llm", action="store_true", help="nu folosi Ollama chiar daca ruleaza")
    p.add_argument("--show", action="store_true", help="arata doar cum a inteles cererea")
    p.set_defaults(fn=cmd_text)

    sub.add_parser("templates", help="sabloanele de piese tehnice").set_defaults(fn=cmd_templates)
    sub.add_parser("doctor", help="verifica instalarea (pentru raportare probleme)").set_defaults(fn=cmd_doctor)
    sub.add_parser("update", help="verifica daca exista o versiune noua").set_defaults(fn=cmd_update)

    p = sub.add_parser("ui", help="porneste interfata grafica in browser")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(fn=cmd_ui)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        a = ap.parse_args(["ui"])
    from . import logs
    log = logs.setup()
    try:
        a.fn(a)
    except (KeyError, ValueError, RuntimeError, FileNotFoundError) as e:
        msg = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
        log.warning("%s: %s", a.cmd, msg)
        _out(f"Eroare: {msg}")
        return 1
    except SystemExit:
        raise
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # unexpected: keep the full traceback in the log
        log.exception("comanda %s a esuat", a.cmd)
        _out(f"Eroare neasteptata: {type(e).__name__}: {e}\nDetalii in {logs.log_path()} "
             f"- ruleaza 'abydex doctor' si trimite rezultatul pe GitHub.")
        return 1
    return 0
