import argparse
import json
import platform
import sys
import time

from .config import ROOT, Settings
from .ingest import build_index, download
from .retrieval import Retriever


def main():
    parser = argparse.ArgumentParser(description="Handbook ingestion and diagnostics")
    parser.add_argument("command", choices=["doctor", "download", "index", "search", "evaluate"])
    parser.add_argument("question", nargs="?")
    args = parser.parse_args()
    settings = Settings()
    if args.command == "doctor":
        print(f"Python: {platform.python_version()} | executable: {sys.executable}")
        print(f"Project: {ROOT}\nData: {settings.data_dir.resolve()}")
        print(f"LLM key configured: {bool(settings.groq_api_key.get_secret_value())} (key never printed)")
        pointer = settings.data_dir / "indexes/CURRENT"
        print(f"Index pointer present: {pointer.exists()}")
        if pointer.exists():
            retriever = Retriever(settings.data_dir)
            print(f"Index valid: {retriever.manifest['version']}; chunks: {len(retriever.chunks)}")
    elif args.command == "download":
        print(download(settings))
    elif args.command == "index":
        print(json.dumps(build_index(settings), indent=2))
    elif args.command == "search":
        if not args.question:
            parser.error('Supply a question: python -m handbook search "How do I update firmware?"')
        print(
            json.dumps(
                Retriever(settings.data_dir).search(args.question, settings.top_k),
                indent=2,
                ensure_ascii=False,
            )
        )
    elif args.command == "evaluate":
        retriever = Retriever(settings.data_dir)
        cases = json.loads((ROOT / "eval/retrieval_cases.json").read_text(encoding="utf-8"))
        results = []
        for case in cases:
            start = time.perf_counter()
            hits = retriever.search(case["question"], settings.top_k)
            pages = sorted({h["page"] for h in hits})
            results.append(
                {
                    **case,
                    "retrieved_pages": pages,
                    "hit": bool(set(pages) & set(case["expected_pages"])),
                    "retrieval_ms": round((time.perf_counter() - start) * 1000),
                }
            )
        score = sum(r["hit"] for r in results) / len(results)
        report = {
            "metric": f"page_hit_rate@{settings.top_k}",
            "score": score,
            "note": "Small development set; not held-out answer quality or factuality.",
            "index_version": retriever.manifest["version"],
            "results": results,
        }
        target = ROOT / "reports/retrieval.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        print(f"Report saved: {target}")
        return 0 if score >= 0.8 else 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
