# Professor Agent Mixed Benchmark Design

**Goal:** Create a small, inspectable evaluation dataset for learning how to evaluate the BIT Professor Agent.

**Recommendation:** Start with a 10-example mixed benchmark generated from the local professor Markdown corpus, then evaluate with deterministic checks first and LLM-as-judge rubrics second.

## Why This Shape

A small benchmark is easier to understand, debug, and improve than a large generated dataset. Ten examples are enough to cover the main behavior types without hiding mistakes in volume.

Notebook note:

> Start evals small. A 10-example dataset you understand deeply is more useful than a 100-example dataset you never inspect.

## Dataset Location

Create:

```text
backend/evals/datasets/professor_agent_mixed_v1.jsonl
```

Each JSONL row represents one LangSmith-compatible dataset example:

```json
{
  "inputs": {
    "question": "Tell me about Li Xin's research profile in Computer Science and Technology."
  },
  "reference_outputs": {
    "expected_professors": [
      {
        "profile_id": "computer-science-and-technology/li-xin",
        "name": "LI Xin",
        "detail_url": "https://isc.bit.edu.cn/schools/csat/knowingprofessors5/b186322.htm",
        "evidence_file": "professors/computer-science-and-technology/li-xin.md"
      }
    ],
    "expected_departments": ["computer-science-and-technology"],
    "must_include_terms": ["Machine Learning", "Deep Reinforcement Learning"],
    "must_not_include_terms": [],
    "evidence_files": ["professors/computer-science-and-technology/li-xin.md"]
  },
  "metadata": {
    "category": "single_professor_profile",
    "difficulty": "easy"
  }
}
```

## Example Mix

The first dataset contains exactly 10 examples:

- 3 single-professor profile questions
- 3 topic/advisor-matching questions
- 1 department-routing question
- 1 publication-evidence question
- 2 ambiguity or safety questions

The dataset should cover these learning questions:

- Can the agent identify a known professor?
- Can it route from topic to department to professor evidence?
- Can it cite official URLs when professor profiles contain them?
- Can it avoid guessing on ambiguous names?
- Can it say uncertainty when evidence is thin?

Notebook note:

> A good agent eval dataset should contain normal cases, edge cases, and failure cases. If it only contains happy-path examples, it will teach you almost nothing.

## Generator

Create a deterministic generator script:

```text
backend/evals/generate_mixed_benchmark.py
```

The generator should use the existing `ProfessorCorpus` loader instead of parsing Markdown from scratch. This keeps profile IDs, department names, detail URLs, and research interests consistent with the app.

The generator should:

- Load the corpus from `backend/app/corpus`.
- Select examples by stable profile IDs and department slugs.
- Emit JSONL with stable ordering.
- Fail with a clear error if an expected profile, department, or evidence file is missing.
- Avoid calling an LLM.
- Avoid network access.

## Validation

Add a lightweight test:

```text
backend/tests/test_eval_dataset.py
```

The test should verify:

- The generated JSONL file exists.
- It contains exactly 10 rows.
- Every row has `inputs.question`, `reference_outputs`, and `metadata.category`.
- Every listed evidence file exists under `backend/app/corpus/professors`.
- Every expected professor ID still exists in `ProfessorCorpus`.
- Required category counts match the planned mix.

## Evaluator Plan

Use deterministic evaluators first:

- Expected professor/profile URL appears in the answer.
- Expected department appears when relevant.
- Forbidden terms do not appear.
- The answer does not invent URLs.

Use LLM-as-judge for qualitative checks:

- Groundedness: claims are supported by the expected evidence files.
- Helpfulness: the answer addresses the student's question.
- Tone: recommendations are respectful and non-judgmental.

Notebook note:

> Use code for facts. Use LLM-as-judge for judgment.

## Out Of Scope For Version 1

- Uploading the dataset to LangSmith automatically.
- Running the real hosted app.
- Online production evaluators.
- Large corpus-wide generated benchmarks.
- Human annotation UI.

Those can come after the first local dataset is easy to inspect and validate.
