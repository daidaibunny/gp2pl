# GP2PL

**GP2PL** (Generalized Planning to Plan Libraries) is a framework that constructs
reusable Belief-Desire-Intention (BDI) plan libraries from controlled
natural-language goal descriptions and planning-domain knowledge, using
generalized-planning behavior as evidence. It generates parameterized
AgentSpeak(L) plan templates with applicability contexts, primitive actions,
and subsidiary achievement-goal calls.

The domain-level library is constructed offline and retained across queries.
Achievement queries compose its reusable capabilities; temporally extended
goals (TEGs) add query-specific coordination over the same library.

## Method

### Goal Template Generation

A language model translates a controlled natural-language request into a
parameterized goal template using the domain vocabulary, declared parameter
types, and binding constraints. Deterministic validation checks the output
against these declarations. At invocation, a type-compatible binding assigns
objects from the current problem instance to the parameters.

The complete system, request, and correction-retry prompts used in the
translation study are provided in
[prompts.py](src/temporal_specification/prompts.py).

```text
controlled-language request + domain vocabulary + typed parameters
-> parameterized goal template
-> bound achievement query or TEG query
```

### Plan Template Generation

MOOSE derives reusable behavior for atomic achievement goals from training
instances. GP2PL combines this evidence with the domain action model to generate
plan candidates, including capabilities needed for subsidiary achievements.
Candidates are checked for variable binding, primitive-action executability,
and state changes on successful completion. Clingo selects a compact library
with internal-call closure: every subsidiary goal has a matching plan in the
library. Recursive calls require a decreasing progress measure and a terminating
base case. For example, a plan for `on(X,Y)` may call `!clear(Y)` before
executing `stack(X,Y)`.

```text
planning domain + training instances
-> generalized-planning evidence
-> reusable library of atomic achievement plans
```

Achievement-goal composition selects and orders capabilities so that
establishing one condition preserves the others. TEG coordination uses a
deterministic finite automaton (DFA) to track temporal progress and adds
query-specific plans without modifying the domain-level plans. The monitor
observes the initial state and every successful primitive domain action;
subgoal calls and returns add no observations. AgentSpeak(L) plans execute
with Jason.

```text
bound query + retained domain-level library
-> query-specific plan templates
-> AgentSpeak(L) execution in Jason
```

The implementation uses typed Planning Domain Definition Language (PDDL)
domains, including bounded integer resource functions with constant-integer
effects. Temporal coordination uses LTLf2DFA and MONA to construct DFAs from
finite-trace temporal specifications, with Boolean alternatives represented in
the automaton.

## Installation

Python 3.12 and [`uv`](https://docs.astral.sh/uv/) are required.

```bash
uv sync --frozen
uv run --frozen gp2pl --help
uv run --frozen ruff check src scripts
```

Install the optional language-model client with
`uv sync --extra translation --frozen`. For live translation, supply an API key
through the environment; see [`.env.example`](.env.example).

Install MONA for query compilation and VAL for trace validation:

```bash
bash scripts/setup_mona.sh
bash scripts/setup_val.sh
```

The compiler finds the installed MONA binary under `.external/mona-1.4/`.
Set `MONA_BIN` to use another installation.

Jason is resolved as Maven artifact `io.github.jason-lang:jason:3.1.2` when a
runtime validation is first requested. Java and Maven are required for Jason;
VAL builds with CMake and a C++ compiler. MOOSE is needed only when generating
new policy evidence; its pinned setup and training commands are described below.

## Reproduction

Use your own PDDL domain and instances, or fetch the optional benchmark inputs
with the pinned setup scripts. See [REPRODUCING.md](REPRODUCING.md) for training,
compilation, translation, and execution commands. A generic query generator
constructs controlled-language TEG requests from supplied instances; generated
queries, libraries, and results are not included in the repository.

## Citation and Licensing

Use [CITATION.cff](CITATION.cff) to cite the software. GP2PL source code is
licensed under Apache-2.0. External planners, PDDL benchmarks, and other
third-party materials retain their own terms; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
