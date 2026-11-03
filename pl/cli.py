import argparse
import json
import sys


def main(argv=None):
    p = argparse.ArgumentParser(prog="pl", description="PaperLane sales assistant")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("ingest", help="crawl the catalog site into a new snapshot")
    pi.add_argument("--base-url", required=True)
    pi.add_argument("--delay", type=float, default=1.0, help="min seconds between requests (robots.txt may raise it)")
    pi.add_argument("--accept", action="store_true", help="promote even if the run has warnings (dead links, SKU count swing)")
    pp = sub.add_parser("promote", help="promote a held snapshot after reviewing its report")
    pp.add_argument("run_id")
    pq = sub.add_parser("quote", help="price lines against the current snapshot, e.g. pl quote PL-CP-A4-70:10")
    pq.add_argument("lines", nargs="+")
    sub.add_parser("chat", help="interactive chat REPL")
    ps = sub.add_parser("serve", help="run the API + UI")
    ps.add_argument("--port", type=int, default=8080)
    pe = sub.add_parser("eval", help="run the evaluation set")
    pe.add_argument("--runs", type=int, default=3)
    pe.add_argument("--only", nargs="*")
    a = p.parse_args(argv)

    if a.cmd == "ingest":
        from .ingest import run_ingest
        res = run_ingest(a.base_url, min_delay=a.delay, accept=a.accept)
        sys.exit({"promoted": 0, "held": 3}.get(res.status, 2))
    if a.cmd == "promote":
        from . import db
        con = db.connect()
        if db.run_status(con, a.run_id) not in ("held", "promoted"):
            sys.exit(f"run {a.run_id} is not a held snapshot")
        db.promote(con, a.run_id)
        print(f"promoted {a.run_id}")
    if a.cmd == "quote":
        from . import db
        from .pricing import quote
        _, items = db.load_current()
        lines = [(s.split(":")[0], int(s.split(":")[1])) for s in a.lines]
        print(json.dumps(quote(lines, items).to_dict(), indent=2, ensure_ascii=False))
    if a.cmd == "chat":
        from .agent import Agent
        agent = Agent()
        print("PaperLane assistant. Ctrl-D to exit.")
        while True:
            try:
                msg = input("you> ")
            except EOFError:
                break
            if msg.strip():
                print("assistant>", agent.chat("cli", msg)["reply"], "\n")
    if a.cmd == "serve":
        import uvicorn
        uvicorn.run("pl.api:app", host="127.0.0.1", port=a.port)
    if a.cmd == "eval":
        from .evaluate import main as eval_main
        sys.exit(eval_main(runs=a.runs, only=a.only))
