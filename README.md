# CodePilot AI — Autonomous Coding Agent

Natural-language coding requests → AutoGen generates Python → runs in a **Docker sandbox** → fixes errors and re-runs → returns the result in a Streamlit UI.

```
User → Streamlit UI → AutoGen Agent → Python Code
     → PythonCodeExecutionTool → Docker Sandbox
     → Validate → Fix & Re-execute if needed → Final Response
```

## Features

- Natural-language coding tasks (Fibonacci, primes, sorting, …)
- AutoGen `AssistantAgent` generates Python code
- Execution via `PythonCodeExecutionTool`
- Sandboxed runs with `DockerCommandLineCodeExecutor`
- Auto error detection & correction (generate → execute → fix → re-execute)
- Streamlit UI: task input, generated code, execution output, explanation
- Optional conversation memory

## Prerequisites

1. **Python 3.10+**
2. **Docker Desktop** installed and running
3. An **OpenRouter API key** ([openrouter.ai/keys](https://openrouter.ai/keys))

## Setup

```bash
cd AutoGen_Code_Agent
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # then edit .env and set OPENROUTER_API_KEY
```

Edit `.env`:

```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Other model examples: `anthropic/claude-3.5-sonnet`, `google/gemini-2.0-flash-001`, `meta-llama/llama-3.3-70b-instruct`.

## Run

```bash
streamlit run app.py
```

Open the browser URL Streamlit prints (usually http://localhost:8501).

## Example tasks

- Calculate the first 15 Fibonacci numbers
- Find all prime numbers below 50
- Create a bubble sort and sort `[5, 2, 9, 1]`
- Write a function that checks if a string is a palindrome

## Project layout

```
AutoGen_Code_Agent/
├── app.py                 # Streamlit UI
├── agent/
│   ├── __init__.py
│   └── code_agent.py      # AutoGen agent + Docker execution
├── requirements.txt
├── .env.example
└── README.md
```

## How it works

1. You enter a coding task in Streamlit.
2. `AssistantAgent` writes Python code.
3. `PythonCodeExecutionTool` runs that code inside a Docker container (`python:3-slim`).
4. If the run fails, the agent reads the error, fixes the code, and tries again (up to 5 tool iterations).
5. The UI shows the final code, Docker execution output, and a short explanation.

## Notes

- Docker must be running before you click **Run CodePilot**.
- Generated code uses the Python standard library only (no `pip install` inside the sandbox).
- Toggle **Conversation memory** in the sidebar to let follow-up questions use recent chat context.
