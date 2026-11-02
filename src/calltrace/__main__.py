"""Command-line entry point.

    python -m calltrace sample             draw the seeded sample and write its manifest
    python -m calltrace run --smoke        run one call end to end into results/smoke
    python -m calltrace run --full         run the selected sample into results/
    python -m calltrace run --full --asr-only   transcripts only, no LLM server needed
    python -m calltrace run --pilot        run the held-out pilot call into results/pilot
    python -m calltrace export             write CSV/JSONL outputs from finished calls
    python -m calltrace evaluate           compute metrics and write review sheets
"""

from __future__ import annotations

import argparse
import shutil

from .config import load_config
from .data import AppTekDataset
from .pipeline import CallPipeline

SMOKE_CALL = "005"  # the shortest call in the sample


def main() -> None:
    parser = argparse.ArgumentParser(prog="calltrace", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sample")
    run = subparsers.add_parser("run")
    mode = run.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--full", action="store_true")
    mode.add_argument("--pilot", action="store_true")
    run.add_argument("--asr-only", action="store_true")
    run.add_argument("--fresh", action="store_true", help="clear earlier smoke output first")
    subparsers.add_parser("export")
    subparsers.add_parser("evaluate")
    args = parser.parse_args()

    config = load_config()
    dataset = AppTekDataset(config)

    if args.command == "sample":
        manifest = dataset.sample()
        print(f"Selected {len(manifest['selected'])} of {manifest['eligible_calls']} eligible calls.")
    elif args.command == "run":
        manifest = dataset.load_manifest()
        if args.smoke:
            output = config.path("results") / "smoke"
            if args.fresh and output.exists():
                shutil.rmtree(output)
            records = [r for r in manifest["selected"] if r["call_id"] == SMOKE_CALL]
        elif args.pilot:
            output = config.path("results") / "pilot"
            records = [manifest["pilot"]]
        else:
            output = config.path("results")
            records = manifest["selected"]
        summary = CallPipeline(config, output, use_llm=not args.asr_only).run(records)
        print(summary)
        if summary["failed"]:
            raise SystemExit(f"{len(summary['failed'])} call(s) failed; see failures.jsonl")
    elif args.command == "export":
        from .export import export_all

        export_all(config)
    elif args.command == "evaluate":
        from .run_evaluation import run_evaluation

        run_evaluation(config)


if __name__ == "__main__":
    main()
