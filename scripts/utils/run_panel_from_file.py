"""Wrapper to run the agentic panel with a prompt read from a file (avoids shell-escaping the multi-line prompt)."""
import argparse
import sys
from scripts.utils.agentic_panel import run_panel_pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True, help="Path to a text file containing the prompt.")
    parser.add_argument("--out", default=None, help="Write final code to this file.")
    parser.add_argument("--report", default=None, help="Write panel report JSON to this path.")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--threshold", type=float, default=7.0)
    args = parser.parse_args()

    with open(args.prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read()

    report = run_panel_pipeline(
        prompt,
        max_retries=args.max_retries,
        threshold=args.threshold,
    )

    if args.out and report.final_code:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report.final_code)
        print(f"\nFinal code written to: {args.out}")

    if args.report:
        import json
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Full report written to: {args.report}")


if __name__ == "__main__":
    main()