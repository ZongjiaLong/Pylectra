"""Top-level convenience script — re-exports pylectra.run.run.

Usage::

    from run import run
    out = run("examples/single_case39.yaml")

    # Or run directly as a script with a single YAML:
    #   python run.py examples/single_case39.yaml
"""
from pylectra.run import run  # noqa: F401

if __name__ == "__main__":
    import sys
    import pprint

    if len(sys.argv) < 2:
        print("Usage: python run.py <config.yaml> [key=value ...]")
        sys.exit(1)

    yaml_path = sys.argv[1]

    # Parse optional KEY=VALUE overrides from the command line.
    # Values are JSON-decoded where possible (so numbers stay numeric).
    import json
    extra: dict = {}
    for token in sys.argv[2:]:
        if "=" not in token:
            print(f"Warning: ignoring malformed override {token!r} (expected KEY=VALUE)")
            continue
        k, _, v_raw = token.partition("=")
        try:
            extra[k] = json.loads(v_raw)
        except (json.JSONDecodeError, ValueError):
            extra[k] = v_raw  # keep as string

    result = run(yaml_path, **extra)
    pprint.pprint(result)
