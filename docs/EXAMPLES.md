# Examples

Examples are executable scripts under `examples/`.

- `simple_dispatch_success`: final method evidence allows a direct rewrite.
- `multi_subclass_success`: multiple observed subclasses inherit a final method.
- `dynamic_getattr_rejected`: dynamic attribute lookup is rejected.
- `monkey_patch_rejected`: runtime method replacement is rejected.
- `multiple_inheritance_rejected`: multiple inheritance is rejected.

Observation is evidence, not proof. Rejected examples are successful outcomes
when the policy cannot prove safety.
