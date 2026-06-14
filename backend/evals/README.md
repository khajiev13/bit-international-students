# Professor Agent Evals

This folder contains the first local evaluation layer for the BIT Professor Agent.

## What Is Here

- `datasets/professor_agent_mixed_v1.jsonl`: 10 curated benchmark examples.
- `generate_mixed_benchmark.py`: deterministic dataset generator backed by `ProfessorCorpus`.
- `evaluators.py`: LangSmith-compatible deterministic code evaluators.

The dataset follows the LangSmith shape:

```json
{
  "inputs": {"question": "..."},
  "reference_outputs": {"expected_professors": [], "must_include_terms": []},
  "metadata": {"id": "...", "category": "..."}
}
```

Notebook note:

> Dataset = the questions and expected evidence. Target = the app answer. Evaluators = the scoring rules.

## Regenerate The Dataset

From `backend/`:

```bash
uv run python evals/generate_mixed_benchmark.py
```

The generator should always produce the same JSONL. If a professor profile or evidence file disappears, it fails with a clear error.

## Run Local Validation

From `backend/`:

```bash
uv run --extra test pytest tests/test_eval_dataset.py tests/test_eval_evaluators.py
```

The dataset test checks the 10-example contract and corpus references. The evaluator test checks the deterministic scoring rules.

## LangSmith Usage

LangSmith's SDK evaluation pattern is:

```python
from langsmith import Client
from evals.evaluators import (
    expected_professors_mentioned,
    expected_departments_mentioned,
    required_terms_present,
    forbidden_terms_absent,
    invented_urls_absent,
)

client = Client()

def target(inputs: dict) -> dict:
    answer = run_professor_agent(inputs["question"])
    return {"answer": answer}

results = client.evaluate(
    target,
    data="Professor Agent Mixed v1",
    evaluators=[
        expected_professors_mentioned,
        expected_departments_mentioned,
        required_terms_present,
        forbidden_terms_absent,
        invented_urls_absent,
    ],
    experiment_prefix="professor-agent-mixed-v1",
    upload_results=False,
)
```

Use `upload_results=False` while learning or debugging locally. Remove it when you want the experiment and feedback visible in LangSmith.

## How To Think About The Layers

Use code evaluators for objective facts:

- Did the answer mention the expected professor?
- Did it mention the expected department?
- Did it include required terms from the corpus?
- Did it avoid forbidden phrases?
- Did it avoid invented URLs?

Use LLM-as-judge after those pass, for judgment-heavy qualities:

- Is the answer grounded in the supplied evidence?
- Is it helpful for the student's actual intent?
- Is the tone respectful and appropriately uncertain?

Notebook note:

> Use code for facts. Use LLM-as-judge for judgment. Use humans to calibrate the judge.
