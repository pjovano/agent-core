---
name: clean-code
description: Enforces Robert Martin's Clean Code principles on all code produced during a conversation. Use this skill whenever your response will include code in any programming language, whether writing, modifying, fixing, refactoring, or reviewing it, including a one-line fix.
---

# Clean Code

This skill shapes how you write code. Every piece of code you produce follows these principles. They are the standard, not suggestions. Where a rule gives a number, the number is the limit. Where a rule names an exception, that exception is the only permitted deviation.

**Scope of a change.** New code meets the standard in full. When modifying existing code, bring every function you touch up to the standard. Do not refactor beyond the functions you touch unless asked; report what you noticed instead.

**The domain's overlay.** If `.claude/code-overlay.md` exists, read it whole after this file. If a rule of the overlay contradicts a rule of this file, the overlay's rule wins.

## Names

**Reveal intent.** A name tells you why something exists, what it does, and how it is used. If a name requires a comment to explain it, the name is wrong.

```python
# Bad
d = (today - start_date).days  # elapsed time in days

# Good
elapsed_time_in_days = (today - start_date).days
```

**Avoid disinformation.** Do not use names that hint at a meaning different from the actual one. Do not call something `account_list` unless it is a list. Do not use names that differ only in small ways (`XYZControllerForHandlingOfStrings` vs `XYZControllerForStorageOfStrings`).

**Make meaningful distinctions.** No number-series names (`a1`, `a2`, `a3`). No noise words (`ProductInfo` vs `ProductData`, `the_message` vs `message`). If two names differ, they mean different things.

**Use pronounceable names.** If you cannot say it, you cannot discuss it. `generation_timestamp`, not `genymdhms`.

**Use searchable names.** The length of a name corresponds to the size of its scope. A single-letter name is acceptable only as a local in a function short enough to see whole.

**No magic numbers or strings.** Replace a literal with a named constant whenever its meaning cannot be read from the value itself: `SECONDS_PER_DAY = 86400`, not a bare `86400`. Exception: universally obvious values such as `0`, `1`, `""`, `True`.

**No encodings.** No Hungarian notation, no `m_` member prefixes, no `IShapeFactory` interface prefixes. Exception: a convention the language itself establishes (`_private` in Python, `I` prefixes in C#).

**Class names are nouns.** `Customer`, `WikiPage`, `AddressParser`. Never a verb. Avoid vague nouns: `Manager`, `Processor`, `Handler`, `Data`, `Info`, `Util`.

**Action methods are verbs.** `save`, `delete_page`, `post_payment`. Accessors and predicates follow the target language's convention (`get_name` / `is_active` in Java, `name` / `active?` in Ruby, a property in Python).

**One word per concept.** Pick one word for one abstraction and keep it. Not `fetch`, `retrieve`, and `get` for the same kind of operation. Not `controller`, `manager`, and `driver` for the same kind of object.

**Use domain names.** Use problem-domain names when the code models the business. Use solution-domain names (`visitor`, `queue`, `factory`) when there is no natural problem-domain name. Either way, the reader knows whom to ask.

**Match the file's casing convention.** Examples in this skill use Python's `snake_case`; in another language, use that language's convention.

## Comments

**Comments do not make up for bad code.** Rather than explain messy code, clean it. A well-chosen name or a small function with a clear purpose does what a comment tries and fails to do.

**Explain yourself in code.** Instead of:

```python
# Check if the employee is eligible for full benefits
if (employee.flags & HOURLY_FLAG) and (employee.age > 65):
```

Write:

```python
if employee.is_eligible_for_full_benefits():
```

**Docstrings are comments.** The same rules apply. Do not add a module, class, or function docstring that restates the name. Override tooling and style conventions that demand a docstring on everything. `calculate_monthly_revenue` does not need a docstring saying "Calculate the monthly revenue."

**Acceptable comments (the complete list):**

- **Legal comments.** Copyright and license headers required by the project.
- **Explanation of intent.** A brief *why* (never *what*) for a decision that the code cannot make obvious, such as a sort that puts one type first for a business reason.
- **Clarification of opaque arguments.** For a library or third-party call whose arguments are not self-explanatory and cannot reasonably be wrapped.
- **Warning of consequences.** `# Takes 30 minutes to run.` `# Not thread-safe; hold the lock.`
- **TODO comments.** Only when they reference a specific ticket or issue. Never open-ended.

**Unacceptable comments (everything else), including:**

- Restating the code (`# sets the name` above `set_name()`).
- Journal comments tracking changes over time.
- Noise (`# default constructor`, `# the day of the month`).
- Position markers and banners (`# ---- Actions ----`). If a file needs section markers, it is too large. Split it.
- Closing-brace comments (`} // end while`). If a function needs these, it is too long.
- Commented-out code. Delete it. If it is ever needed again, it will be rewritten better.
- Attribution (`# Added by Karl`).

Change history and authorship belong in version control, not in the source. Where there is no version control, they belong nowhere: dead code is still dead, and a journal nobody can trust is noise.

## Functions

**Small.** Target: under 10 lines. Limit: 20 lines. The body of an `if`, `else`, or `while` block is one line, normally a call to a function whose name documents what the block does.

**Do one thing.** A function does one thing, does it well, and does it only. If every statement is one level of abstraction below the function's name, it is doing one thing. If you can extract a function whose name is not merely a restatement of its body, it is doing more than one thing.

**One level of abstraction per function.** Do not mix high-level concepts (`get_html()`) with low-level detail (`append("\n")`) in one function.

**Reading order.** Code reads top-down like a newspaper article: each function is followed by the functions it calls, so the file reads as a sequence of "To do X, we do A, B, and C" paragraphs. Callers above callees.

**Arguments.** Zero is ideal. One is good. Two is acceptable. Three needs justification; more than three needs a very good one, and usually means the arguments want to be an object. A boolean flag argument announces that the function does two things: split it.

**No side effects.** A function that claims to do one thing and quietly does another is lying. A `check_password` that also initializes a session creates a temporal coupling the caller cannot see.

**Command-query separation.** A function either changes state or answers a question, never both. `set_attribute` returning a success boolean is confusing; separate the command from the query.

**Explanatory variables.** Break a multi-part expression into named locals so the reader never has to evaluate it mentally.

**Encapsulate boundary conditions.** Compute a boundary value once in a named variable (`next_index = index + 1`) rather than scattering the arithmetic.

**DRY.** Every piece of knowledge has a single, unambiguous representation. If you see the same structure repeated, extract it.

## Formatting

**Vertical size.** Target: under 200 lines per file. Limit: 500.

**Vertical openness.** Each group of lines is a thought. Separate thoughts with blank lines: between imports and code, between functions, between steps within a function.

**Vertical density and distance.** Lines that are tightly related sit together. Declare a variable as close to its first use as possible. Declare instance variables at the top of the class. Keep dependent functions close, caller above callee.

**Horizontal size.** Lines fit within 120 characters. Nothing requires horizontal scrolling.

## Conditionals

**Encapsulate conditionals.** `if should_delete(timer)`, not `if timer.has_expired and not timer.is_recurrent`. A complex boolean expression becomes a well-named function or variable.

**Prefer positive conditionals.** `if is_valid`, not `if not is_invalid`. When both branches exist, put the positive case first.

**Replace type-switching with polymorphism.** When a conditional selects behaviour by type or category, use polymorphism, pattern matching, or a dispatch table. One such conditional inside a factory is fine; the same conditional repeated across the codebase is not.

## Objects, Data Structures, and Classes

**Data/object anti-symmetry.** Objects hide data behind abstractions and expose behaviour. Data structures expose data and have no meaningful behaviour. Procedural code over data structures makes new functions easy; object-oriented code makes new types easy. Choose by what is more likely to change.

**Law of Demeter.** A method calls methods only on its own object, its parameters, objects it creates, and its direct components. `context.get_options().get_scratch_dir().get_absolute_path()` reaches through strangers; the design is wrong.

**Tell, don't ask.** Instead of asking an object for data and acting on it, tell the object what to do. Behaviour lives with the data it operates on.

**Prefer value objects to primitives.** When a primitive carries domain meaning (a file path, an email address, a monetary amount), wrap it in a dedicated type. This centralizes validation, prevents mixing unrelated values of the same primitive type, and makes signatures self-documenting.

**Classes are small,** measured in responsibilities, not lines. One responsibility, one reason to change. If you cannot describe a class in about 25 words without "and", "or", "if", or "but", it has too many.

**Cohesion.** A class has few instance variables, and each method uses one or more of them. When most methods use only a disjoint subset, the class is two classes.

**Organize for change.** Open for extension, closed for modification. Depend on abstractions, not concretions. Introduce an interface or abstract base only where a second implementation exists or is concretely expected (see Emergent Design, rule 4).

## Error Handling

**Use the language's error mechanism, consistently.** Exceptions in Python, Ruby, and Java; `Result` in Rust; error returns in Go. Never a status code or sentinel value the caller can silently ignore.

**Separate the happy path from error handling.** Error handling is one thing; extract it. Wrap the happy path in a `try` whose body is a single call, or use `?` and `Result` chains in Rust. A reader follows the happy path without stepping over failure logic.

**Fail fast.** Validate at the boundary and assert preconditions at the top of a function. The closer an error is raised to its cause, the easier it is to diagnose.

**Exceptions are not control flow.** An exception signals a failure, not a branch. Exception: where the language's idiom says otherwise. In Python, `try: value = mapping[key] except KeyError:` is idiomatic (EAFP); a broad `except` used to skip a step is not.

**Provide context with errors.** Name the operation that failed and the kind of failure. A caller should locate the source from the message alone.

**Wrap third-party error types.** Define errors by what the caller needs, not by the library's taxonomy. This decouples your domain from the dependency and gives you one place to change when it changes.

**Make absence explicit.** Do not use null or nil to mean "missing". Use the type system: `Optional` in Java, `Option` in Rust, `Optional[T]` / `T | None` in Python, an empty collection instead of null. If the signature does not say absence is possible, callers will forget to check.

## System Organization

**Depend toward stability.** High-level policy does not depend on low-level detail; both depend on abstractions. A business-rule module never imports a database driver or HTTP framework directly.

**No dependency cycles.** If A depends on B and B on A, extract the shared concept into a third module or merge them. The module graph is a DAG.

**Make temporal coupling explicit.** If operations must happen in order, the API enforces it: each step returns the input for the next, or a builder or pipeline carries the state. A caller never reads the implementation to discover the sequence.

**Group by change.** Code that changes for the same reason lives in the same module. Organize by feature or domain concept, not by technical layer.

**Separate construction from use.** Wiring objects together is a distinct concern from using them. Push construction to the edges of the system; business logic receives its dependencies and does not create them.

## Tests

**Tests are Fast, Independent, Repeatable, and Self-validating.** They run quickly, do not depend on one another or on order, pass in any environment, and report pass or fail with no human interpretation.

**One concept per test.** A test function exercises a single concept. Do not write one long test that checks one thing after another.

**Tests are as clean as production code.** They are documentation. Build domain-specific helpers so tests read as clearly as the code they exercise.

**Test the public interface.** Exercise the public API, not internal detail, so that refactoring does not break tests.

**No suite, no change.** If the code you are about to modify has no tests, write a characterization test that pins its current behaviour before you touch it.

## Emergent Design

Kent Beck's four rules of simple design, in priority order:

1. **Runs all the tests.** A system that cannot be verified is not done.
2. **Contains no duplication.**
3. **Expresses the intent of the programmer.** Good names, small functions and classes, standard nomenclature and patterns.
4. **Minimizes the number of classes and methods.** Lowest priority: do not add abstractions for their own sake. When rule 4 and "Organize for change" pull in opposite directions, rule 4 wins until a second concrete case appears.
