# BIT International Students

Open-source tools for helping international students explore Beijing Institute of Technology resources. The first tool in this repository is **Professor Agent**, a deployable chat app that helps students find BIT professors by research topic, department, or name.

Professor Agent uses a local corpus of 22 departments and 753 professor profiles, a FastAPI backend, a DeepAgents-powered retrieval workflow, and a React + Vite frontend served behind Caddy.

## Current Tool

### Professor Agent

Students can ask about:

- Research topics, such as machine learning, robotics, materials science, or aerospace.
- BIT departments and schools.
- Individual professor profiles in the local corpus.

The app intentionally does not include the notebook's add-professor workflow, crawler, OCR path, shell execution, upload endpoints, or professor Markdown editing. The public student app is read-focused.

## Structure

```text
backend/   FastAPI API, DeepAgents factory, corpus tools, scratch workspace
frontend/  React + Vite + TypeScript UI served by Nginx
Caddyfile  Internal reverse proxy: /api/* -> backend, everything else -> frontend
```

## Local Deployment

Copy the example environment file, fill in your model credentials, then run Docker Compose:

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Open the app:

```text
http://127.0.0.1:8081
```

Health checks:

```bash
curl http://127.0.0.1:8081/healthz
curl http://127.0.0.1:8081/api/professors
```

## Environment

The main required model settings are:

```env
BIT_PROF_LLM_API_KEY=your-llm-api-key
BIT_PROF_LLM_BASE_URL=https://api.silra.cn/v1/
BIT_PROF_LLM_MODEL=deepseek-v4-flash
```

Useful optional settings:

```env
PUBLIC_PORT=8081
VITE_API_BASE_URL=/api
LAB4_ALLOWED_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
LAB4_ALLOWED_HOSTS=localhost,127.0.0.1,lab4_professor_caddy
LAB4_MAX_PROMPT_CHARS=2000
LAB4_ADMIN_USERNAME=admin
LAB4_ADMIN_PASSWORD=replace-with-a-strong-password
```

Do not commit `.env`. Use `.env.example` for shared defaults.

## Question Answer Log

The backend stores each raw student question and final agent answer in SQLite. The chat stream schedules the database write in the background after each run, so students do not wait on log I/O.

In Docker Compose, the database lives on the `lab4_professor_analytics` named volume at:

```text
/app/analytics/question_answer_log.sqlite3
```

Read recent Q&A rows with the admin credentials from `.env`:

```bash
curl -u "$LAB4_ADMIN_USERNAME:$LAB4_ADMIN_PASSWORD" \
  "http://127.0.0.1:8081/api/admin/question-answer-log?limit=50"
```

## Cloudflare Tunnel

Set `CLOUDFLARE_TUNNEL_TOKEN` in `.env`, then run:

```bash
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d
```

## Development

Backend tests:

```bash
cd backend
uv run python -m pytest -v
```

Frontend tests:

```bash
cd frontend
npm test -- --run
```

Frontend production build:

```bash
cd frontend
npm run build
```

## Contributing

Contributions are welcome. Good first contributions include:

- Improving professor profile coverage or fixing profile metadata.
- Improving bilingual UI text.
- Adding tests for existing behavior.
- Improving deployment docs for students who want to run their own instance.
- Proposing future tools for international students, such as campus FAQ, course guidance, scholarship information, or department exploration.

Before opening a pull request:

1. Keep secrets out of the repository.
2. Run the relevant backend and frontend checks.
3. Keep changes focused and explain the student-facing impact.
4. Preserve the read-only safety model for the public Professor Agent app.

## Security Defaults

- Professor Markdown is copied into the backend image and marked read-only.
- DeepAgents mounts the corpus at `/professors` for reads and a separate persistent scratch workspace at `/scratch` for working notes.
- Backend container runs as a non-root user.
- Compose sets `read_only: true`, drops Linux capabilities, enables `no-new-privileges`, mounts only a small `/tmp` tmpfs, and uses named volumes for `/app/scratch` and `/app/analytics`.
- The model receives department-aware professor tools plus safe DeepAgents filesystem tools for `/professors` reads and `/scratch` writes.
- Shell `execute` and subagent `task` tools are not exposed.
- The DeepAgent system prompt owns BIT-only scope, unrelated-request redirection, read-only corpus behavior, and scratch-only write behavior.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
