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
        llm_mode = _llm_mode(args)
        if args.command == "run":
            if args.dynamic:
                print("recoverage: dynamic mode executes project code as you. There is no OS sandbox.", file=sys.stderr)
            analysis, code = execute_run(
                project,
                output,
                llm_mode=llm_mode,
                threshold=args.threshold,
                dynamic=args.dynamic,
                deep=args.deep,
            )
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
                dynamic=args.dynamic,
                deep=args.deep,
            )
            _print_summary(analysis, output)
            return code
        analysis, planned = execute_generate(
            project,
            output,
            llm_mode=llm_mode,
            dry_run=args.dry_run,
            dynamic=args.dynamic,
            deep=args.deep,
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
        command.add_argument(
            "--llm",
            action="store_true",
            help=(
                "Opt in to an OpenAI-compatible call. Sends gap id, title, why, file, symbol, and suggestion, "
                "plus SBST symbol and parameter names on a coverage stall. Requires RECOVERAGE_LLM_API_KEY."
            ),
        )
        command.add_argument("--no-llm", action="store_true", help="Stay offline. This is the default.")
        command.add_argument("--dynamic", action="store_true", help="Opt in to running the project's tests. Trusted code only. No OS sandbox.")
        command.add_argument("--deep", action="store_true", help="With --dynamic, also run property, mutation, timing, and search probes out of process.")
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


def _llm_mode(args: argparse.Namespace) -> str:
    """Network is opt-in. A key in the environment does not turn it on."""
    if args.llm and args.no_llm:
        raise ValueError("pass only one of --llm and --no-llm")
    if args.llm:
        return "on"
    return "off"


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
    written = [output / "report.md", output / "report.html"]
    pdf = output / "report.pdf"
    if pdf.is_file():
        written.append(pdf)
    print("Reports: " + " ".join(str(path) for path in written))
    mutation_note = next((note for note in analysis.score.notes if "mutant" in note.lower() or "mutation" in note.lower()), "")
    print(mutation_note or "Mutation testing did not run.")


def _fmt(value: float | None) -> str:
    return "not measured" if value is None else f"{value:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
