import json
from pathlib import Path

from recoverage.adapters.javascript_cov import parse_istanbul


def test_parse_istanbul_statement_and_branch_hits(tmp_path: Path):
    payload = {
        "src/pay.js": {
            "path": str(tmp_path / "src" / "pay.js"),
            "s": {"0": 1, "1": 0, "2": 4},
            "statementMap": {
                "0": {"start": {"line": 1}},
                "1": {"start": {"line": 2}},
                "2": {"start": {"line": 3}},
            },
            "b": {"0": [1, 0]},
        }
    }
    files = parse_istanbul(payload, tmp_path)
    assert len(files) == 1
    assert files[0].covered_lines == 2
    assert files[0].num_statements == 3
    assert files[0].covered_branches == 1
    assert files[0].num_branches == 2
    assert files[0].missing_lines == [2]
    assert files[0].path == "src/pay.js"
    json.dumps({"ok": True})
