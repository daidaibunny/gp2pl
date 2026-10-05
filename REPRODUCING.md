# Running GP2PL

GP2PL accepts a PDDL domain, training problems, and goal descriptions.
The domain library is compiled once and retained for subsequent queries.

## Install

Use Python 3.12 and `uv`:

```bash
uv sync --frozen
bash scripts/setup_mona.sh
bash scripts/setup_val.sh
export VAL_VALIDATE_BIN="$PWD/.external/val-build/bin/Validate"
```

Jason execution requires Java and Maven; VAL requires CMake and a C++ compiler.
MONA is discovered automatically under `.external/mona-1.4/`. For a separate
installation, set `MONA_BIN` to the executable path.

## Prepare Inputs and Evidence

Use your own PDDL domain and training instances. To obtain the optional
published benchmark inputs:

```bash
bash scripts/setup_benchmark_sources.sh
uv run --frozen python scripts/materialize_achievement_benchmarks.py --domains ferry
```

This writes the domain and train/test splits under `src/domains/ferry/`.
Existing domain directories are not overwritten.

MOOSE provides singleton-goal policy evidence. Fetch its pinned source and
build its runtime following the upstream instructions:

```bash
bash scripts/setup_moose.sh
```

The upstream Apptainer runtime runs on Linux. Once built, train and dump
a readable policy under a process-tree memory limit:

```bash
uv run --frozen python scripts/train_moose.py \
  --moose-command "apptainer run .external/moose/moose.sif" \
  --domain-file src/domains/ferry/domain.pddl \
  --training-dir src/domains/ferry/train \
  --model-file artifacts/moose/ferry.model \
  --seed 0 --max-rss-gb 16
```

An existing MOOSE readable policy can be used directly without training.

## Compile a Domain Library

```bash
uv run --frozen gp2pl compile-moose-atomic-library \
  --policy-file artifacts/moose/ferry.model.readable \
  --domain-file src/domains/ferry/domain.pddl \
  --domain-name ferry
```

The compiler writes `plan_library.json` and `plan_library.asl` under
`artifacts/domain_libraries/ferry/`.

## Translate and Bind a Goal

The prompts used in the translation study are implemented in
[prompts.py](src/temporal_specification/prompts.py).
`build_lifted_ltlf_system_prompt`, `build_lifted_ltlf_user_prompt`, and
`build_retry_user_message` render the system, request, and correction messages,
respectively. The system prompt specifies the typed domain vocabulary, external
parameter-binding semantics, supported temporal operators, and output schema.

A controlled-language request supplies a request identifier, declared typed
parameters, and binding constraints:

```json
{
  "sample_id": "query_1",
  "source_text": "Eventually at(X, Y).",
  "declared_parameters": [
    {"name": "X", "pddl_type": "car"},
    {"name": "Y", "pddl_type": "location"}
  ],
  "constraints": [],
  "parameter_semantics": "externally_bound"
}
```

Use the exact predicate and type names declared by your domain.
Install the optional client with `uv sync --extra translation --frozen`,
configure the environment as shown in `.env.example`, and translate:

```bash
uv run --frozen python scripts/translate_goal.py \
  --domain-file src/domains/ferry/domain.pddl \
  --request-file artifacts/input/request.json \
  --output artifacts/input/template.json
```

Bind that template to problem objects using a JSON assignment such as
`{"X": "car0", "Y": "l0"}`:

```bash
uv run --frozen python scripts/translate_goal.py \
  --domain-file src/domains/ferry/domain.pddl \
  --template-file artifacts/input/template.json \
  --problem-file src/domains/ferry/test/p0_01.pddl \
  --bindings-file artifacts/input/bindings.json \
  --output artifacts/input/query.json
```

The binding step validates objects, types, and constraints. Manually specified
templates use the same validated eight-key schema implemented in
`src/temporal_specification/prediction_validation.py` and need no model call.

## Generate Temporal Requests

For a supplied problem, the optional generator explores short legal action
traces and produces up to one request per supported temporal profile:

```bash
uv run --frozen python scripts/generate_temporal_queries.py \
  --domain-file src/domains/ferry/domain.pddl \
  --problem-file src/domains/ferry/test/p0_01.pddl \
  --output-dir artifacts/requests
```

Each output contains a request, object bindings, a reference template, and
the action sequence used to construct it. Only the request and domain
vocabulary are passed to the translation model:

```bash
uv run --frozen python scripts/translate_goal.py \
  --domain-file src/domains/ferry/domain.pddl \
  --request-file artifacts/requests/query_1.json \
  --problem-file src/domains/ferry/test/p0_01.pddl \
  --output artifacts/input/query.json
```

## Compose and Execute

```bash
uv run --frozen gp2pl append-lifted-temporal-goal \
  --domain-file src/domains/ferry/domain.pddl \
  --ltlf-goal-json artifacts/input/query.json \
  --query-id query_1

uv run --frozen gp2pl validate-jason-plan-library \
  --domain-file src/domains/ferry/domain.pddl \
  --problem-file src/domains/ferry/test/p0_01.pddl \
  --goal-name g_query_1 \
  --require-plan-verifier \
  --plan-verifier-command "$VAL_VALIDATE_BIN"
```

Query-specific plans are appended to the same domain library. Achievement
queries and TEGs share this compiler path; the runtime monitor observes the
initial state and every primitive action.

Execution validation replays the action trace and checks the query DFA.
VAL checks action legality with an empty goal rather than the instance's
original achievement goal. When a reference template is available, include
`--reference-template-file artifacts/requests/query_1.json` in the execution
command to also check its DFA. This accepts either a template directly or the
generator's output containing `reference`; the reference is used only for
evaluation, not for query compilation or execution.

Python dependencies are locked in `uv.lock`; external versions are pinned in
the setup scripts. Third-party inputs retain their upstream terms, as listed
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
