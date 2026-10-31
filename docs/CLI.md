# CLI

`python -m flatten` and the `flatten` console script expose the same commands.

Commands:

- `analyze [path] [--json] [--strict]`
- `trace path --entry module:function [--out obs.json] [--json] [--strict]`
- `plan path --observations obs.json [--out plan.json] [--closed-world] [--json] [--strict]`
- `rewrite path (--observations obs.json | --plan plan.json) --out output.py [--dry-run | --apply] [--entry module:function] [--skip-verify] [--json] [--strict]`
- `verify original.py rewritten.py --entry module:function [--cases cases.json] [--json] [--strict]`
- `report plan.json [--json] [--strict]`

`rewrite` defaults to dry-run unless `--apply` is supplied. Applied rewrites
require `--entry` for verification unless `--skip-verify` is explicit.

`--strict` turns unsafe or unbound evidence into a non-zero exit where the
command can detect it. JSON output is intended for automation; text output is
for review.
