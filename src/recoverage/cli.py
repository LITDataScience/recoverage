"""CLI: recoverage run | generate | report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from recoverage.version import __version__
from recoverage.display import locate_html, serve_html
from recoverage.pipeline import execute_generate, execute_report, execute_run


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "show":
        return _show(args)
    try:
        project = Path(args.path).resolve()
        output = Path(args.output).resolve() if args.output else (project / "recoverage-out")
        llm_mode = "off" if args.no_llm else "on" if args.llm else "auto"
        if args.command == "run":
            analysis, code = execute_run(project, output, llm_mode=llm_mode, threshold=args.threshold)
            _print_summary(analysis, output)
            return code
        if args.command == "report":
            analysis_path = Path(args.input).resolve() if args.input else None
            analysis, code = execute_report(
                project,
                output,
                llm_mode=llm_mode,
                threshold=args.threshold,
                analysis_path=analysis_path,
            )
            _print_summary(analysis, output)
            return code
        analysis, planned = execute_generate(
            project,
            output,
            llm_mode=llm_mode,
            dry_run=args.dry_run,
        )
        _print_summary(analysis, output)
        mode = "dry-run" if args.dry_run else "wrote"
        print(f"Generate {mode}: {len(planned)} file(s)")
        for item in planned:
            print(f"  {item.action}  {item.path}")
        if args.dry_run:
            print(f"Preview: {output / 'generation-preview.md'}")
        return 0
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"recoverage: {exc}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recoverage", description="Agentic code coverage for any project.")
    parser.add_argument("--version", action="version", version=f"recoverage {__version__}")
    sub = parser.add_subparsers(dest="command")

    def add_common(command: argparse.ArgumentParser, *, generate: bool = False) -> None:
        command.add_argument("path", nargs="?", default=".", help="Project root. Default: current directory.")
        command.add_argument("--output", help="Report directory. Default: <project>/recoverage-out")
        command.add_argument("--llm", action="store_true", help="Require RECOVERAGE_LLM_API_KEY and enrich gaps.")
        command.add_argument("--no-llm", action="store_true", help="Force the offline heuristic path.")
        if generate:
            command.add_argument(
                "--dry-run",
                action="store_true",
                help="Preview drafted tests. Default is to write new files.",
            )
        else:
            command.add_argument(
                "--threshold",
                help="Gate name (blocked, needs-review, merge-ready, production-ready) or a minimum score. Exit 1 when missed.",
            )

    run = sub.add_parser("run", help="Analyze, measure coverage, score, and write Markdown, HTML, and PDF reports.")
    add_common(run)
    report = sub.add_parser("report", help="Render reports from analysis.json, or analyze if it is missing.")
    add_common(report)
    report.add_argument("--input", help="Path to an existing analysis.json.")
    generate = sub.add_parser("generate", help="Write missing tests in the project's framework. Will not overwrite.")
    add_common(generate, generate=True)
    show = sub.add_parser("show", help="Serve the HTML report already written by run or report.")
    show.add_argument("path", nargs="?", default=".", help="Project root, report directory, or report.html.")
    show.add_argument("--output", help="Report directory, if it is not <path>/recoverage-out or <path> itself.")
    show.add_argument("--port", type=int, default=0, help="Local port. 0 picks a free port.")
    show.add_argument("--no-open", action="store_true", help="Serve without launching a browser.")
    return parser


def _show(args: argparse.Namespace) -> int:
    try:
        html_path = locate_html(Path(args.path).resolve(), Path(args.output).resolve() if args.output else None)
    except FileNotFoundError as exc:
        print(f"recoverage: {exc}", file=sys.stderr)
        return 2
    serve_html(html_path, port=args.port, open_browser=not args.no_open)
    return 0


def _print_summary(analysis, output: Path) -> None:
    coverage = analysis.coverage
    print(f"Recoverage score: {analysis.score.score:.1f}/100")
    print(f"Gate: {analysis.score.gate}")
    print(f"Line coverage: {_fmt(coverage.line_percent)} ({coverage.tool}, measured={coverage.measured})")
    print(f"Branch coverage: {_fmt(coverage.branch_percent)} (tool_only={coverage.branch_is_tool})")
    counts: dict[str, int] = {}
    for gap in analysis.gaps:
        counts[gap.severity] = counts.get(gap.severity, 0) + 1
    summary = ", ".join(f"{name} {counts[name]}" for name in ("critical", "high", "medium", "low") if name in counts)
    print(f"Gaps: {len(analysis.gaps)}" + (f" ({summary})" if summary else ""))
    print(f"Reports: {output / 'report.md'} {output / 'report.html'} {output / 'report.pdf'}")
    mutation_note = next((note for note in analysis.score.notes if "mutant" in note.lower() or "mutation" in note.lower()), "")
    print(mutation_note or "Mutation testing did not run.")


def _fmt(value: float | None) -> str:
    return "not measured" if value is None else f"{value:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
