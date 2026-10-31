# Unsupported Cases

Unsupported or unsafe inputs are safe rejects. Observation is evidence, not
proof, so unsupported cases must remain OPEN, UNSAFE, UNKNOWN, or UNSUPPORTED.

- Dynamic `getattr(obj, name)()` dispatch.
- Monkey patching or runtime method replacement.
- Multiple or diamond inheritance where MRO safety cannot be proven.
- Receiver classes not safely referenceable from the rewrite target file.
- Alias imports when a safe class reference cannot be generated.
- Nested, local, or dynamically created classes.
- Descriptor, property, staticmethod, and classmethod binding ambiguity.
- `__getattribute__`, `__getattr__`, custom metaclasses, and subclass hooks.
- `super()`-dependent behavior.
- Receiver or argument side effects that could be reordered.
- Async methods and generator methods.
- Exception behavior that could diverge after rewrite.
