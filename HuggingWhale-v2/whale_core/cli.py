"""python -m whale_core.cli setup|indexes|worker|evaluate"""
import argparse
import json
import time
from pathlib import Path

from whale_core.config import Identity
from whale_core.runtime import build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["setup", "indexes", "worker", "evaluate"])
    parser.add_argument("--config", default="config.local.json")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--cases", default="examples/eval.json")
    parser.add_argument("--tenant", default="demo")
    parser.add_argument("--principal", default="jeffery")
    args = parser.parse_args()
    svc = build(args.config)
    if args.command == "setup":
        svc.atlas.setup()
        print("Regular indexes created. Run indexes to create Atlas Search indexes.")
    elif args.command == "indexes":
        for index in svc.atlas.ensure_search_indexes():
            print(index["name"], index.get("status"), "queryable:", index.get("queryable"))
        print("Wait until both indexes are READY and queryable before searching.")
    elif args.command == "evaluate":
        cases = json.loads(Path(args.cases).read_text())
        if not cases:
            raise SystemExit("Add evaluation cases before running")
        scores = []
        for case in cases:
            response = svc.search(Identity(args.tenant, args.principal), case["query"])
            ids = [s["document_id"] for s in response["sources"]]
            rank = next((i for i, doc in enumerate(ids, 1) if doc in case["expected_document_ids"]), None)
            scores.append(1 / rank if rank else 0)
            print(json.dumps({"query": case["query"], "rank": rank, "latency_ms": response["latency_ms"]}))
        print(json.dumps({"cases": len(scores), "hit_rate_at_6": sum(s > 0 for s in scores) / len(scores),
                          "mrr_at_6": sum(scores) / len(scores)}))
    else:
        print("Worker started. Ctrl-C to stop.")
        while True:
            worked = svc.work_one()
            if args.once:
                break
            if not worked:
                time.sleep(1)


if __name__ == "__main__":
    main()
