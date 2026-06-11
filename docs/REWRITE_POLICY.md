# Rewrite Policy

`flatten-polymorph` rewrites only when the planner has positive closure
evidence. Unknown and unsupported cases are rejected.
Observation is evidence, not proof; missing open signals never imply CLOSED.

| Reason code | Meaning |
| --- | --- |
| `ALLOWED_CLOSED` | Positive closure evidence allows rewrite. |
| `OPEN_CLOSURE_INCOMPLETE` | Closure is incomplete or unobserved subclasses may exist. |
| `UNSAFE_NO_RECEIVER_TYPES` | No observed receiver types are available. |
| `UNSAFE_DYNAMIC_GETATTR` | `__getattr__` or dynamic `getattr(obj, name)()` can alter dispatch. |
| `UNSAFE_DYNAMIC_ATTRIBUTE_CALL` | Call target is not statically clear. |
| `UNSAFE_MONKEY_PATCH` | Runtime method replacement or monkey patch evidence exists. |
| `UNSAFE_MULTIPLE_INHERITANCE` | Multiple or diamond inheritance makes MRO unsafe to flatten. |
| `UNSAFE_UNRESOLVABLE_CLASS_REFERENCE` | Receiver class cannot be referenced safely from rewrite scope. |
| `UNSAFE_ALIAS_IMPORT` | Alias import prevents a safe class reference. |
| `UNSAFE_LOCAL_OR_NESTED_CLASS` | Local, nested, or dynamically created class is unsupported. |
| `UNSAFE_DESCRIPTOR_OR_BINDING` | Descriptor, property, staticmethod, or classmethod binding is unsafe. |
| `UNSAFE_CUSTOM_METACLASS` | Custom metaclass can change lookup or construction semantics. |
| `UNSAFE_SUPER_DEPENDENCY` | Method behavior depends on `super()` resolution. |
| `UNSAFE_ARGUMENT_SIDE_EFFECTS` | Receiver or argument evaluation order may change side effects. |
| `UNSAFE_ASYNC_OR_GENERATOR` | Async and generator methods are unsupported. |
| `UNSAFE_EXCEPTION_BEHAVIOR` | Exception behavior may diverge after rewrite. |
| `UNKNOWN_UNSUPPORTED` | Safety status is unknown or unsupported. |

Dispatch order is deterministic: MRO depth first, then static hierarchy
relationship, then source location. If that order cannot be established, the
rewrite is rejected.
