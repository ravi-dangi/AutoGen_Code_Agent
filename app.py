"""CodePilot AI — Streamlit UI for the AutoGen coding agent."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on the path when run via `streamlit run app.py`
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.code_agent import run_coding_task

st.set_page_config(
    page_title="CodePilot AI",
    page_icon="🛠️",
    layout="wide",
)

st.title("CodePilot AI")
st.caption("Autonomous coding agent — generate → execute in Docker → fix → respond")

# ---- Session state ----
if "history" not in st.session_state:
    st.session_state.history = []  # conversation memory
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ---- Sidebar ----
with st.sidebar:
    st.header("Settings")
    use_memory = st.toggle("Conversation memory", value=True)
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.history = []
        st.session_state.last_result = None
        st.rerun()

    st.divider()
    st.markdown(
        """
**Examples**
- Calculate the first 15 Fibonacci numbers
- Find all prime numbers below 50
- Create a bubble sort and sort `[5, 2, 9, 1]`
- Write a function that checks if a string is a palindrome
        """
    )
    st.divider()
    st.markdown(
        "Requires **Docker Desktop** running and a valid `OPENROUTER_API_KEY` in `.env`."
    )

# ---- Input ----
task = st.text_area(
    "Coding task",
    placeholder="e.g. Calculate Fibonacci numbers up to n=20",
    height=100,
)
run = st.button("Run CodePilot", type="primary", use_container_width=True)

# ---- Run agent ----
if run:
    if not task.strip():
        st.warning("Please enter a coding task.")
    else:
        with st.spinner("Agent is generating and executing code in Docker..."):
            try:
                history = st.session_state.history if use_memory else None
                result = asyncio.run(run_coding_task(task.strip(), history))
                st.session_state.last_result = result
                st.session_state.history.append({"role": "user", "content": task.strip()})
                st.session_state.history.append(
                    {"role": "assistant", "content": result.final_response}
                )
            except Exception as exc:
                st.error(f"Failed to run agent: {exc}")
                st.stop()

# ---- Display result ----
result = st.session_state.last_result
if result is not None:
    status = "Success" if result.success else "Completed with errors"
    st.subheader(f"Result — {status}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Generated code")
        if result.generated_code:
            st.code(result.generated_code, language="python")
        else:
            st.info("No code block was captured from the agent.")

        if len(result.attempts) > 1:
            with st.expander(f"Fix attempts ({len(result.attempts)})"):
                for i, attempt in enumerate(result.attempts, start=1):
                    st.markdown(f"**Attempt {i}**")
                    st.code(attempt.get("code", ""), language="python")
                    st.text(attempt.get("output", ""))

    with col2:
        st.markdown("#### Execution output")
        st.code(result.execution_output or "(no output)", language="text")

        st.markdown("#### Final explanation")
        st.write(result.final_response)

# ---- Conversation history ----
if st.session_state.history:
    with st.expander("Conversation memory", expanded=False):
        for turn in st.session_state.history:
            role = "You" if turn["role"] == "user" else "CodePilot"
            st.markdown(f"**{role}:** {turn['content']}")
