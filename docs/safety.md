# Safety Model

## CLOSED

A call site may be rewritten when the observed call-site id matches static discovery, all observed implementations are in the closed set, and closure has concrete evidence such as `typing.final`, sealed config, or closed-world package analysis.

## OPEN

The planner refuses rewrite when unobserved subclasses, external subclass risk, stale or missing observations, or imprecise call-site identity leave the hierarchy open.

## UNSAFE

The planner refuses rewrite for monkey patching, dynamic `setattr`, `__getattr__`, `__getattribute__`, custom metaclasses, descriptors/properties, complex MRO, dynamic imports, or receiver expressions that cannot be single-evaluated for guarded dispatch.

## UNKNOWN

Parsing failures, unsupported syntax, and import resolution failures are reported as analysis failures and result in no rewrite.
