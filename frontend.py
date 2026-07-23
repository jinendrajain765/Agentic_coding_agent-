import streamlit as st
from backend import app
from langgraph.types import Command
import os
import uuid

st.set_page_config(page_title="Forge — AI Build Agent", page_icon="⚙️", layout="wide")

#Design system 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --ink: #0B1220;
    --ink-panel: #101A2E;
    --grid: #1C2B45;
    --cyan: #5EEAD4;
    --amber: #F5A524;
    --text: #E6EDF7;
    --text-dim: #8593AD;
}

.stApp {
    background:
        linear-gradient(var(--grid) 1px, transparent 1px) 0 0 / 32px 32px,
        linear-gradient(90deg, var(--grid) 1px, transparent 1px) 0 0 / 32px 32px,
        var(--ink);
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--text); }
code, pre, .stCode, .stTextArea textarea { font-family: 'JetBrains Mono', monospace !important; }

.forge-header {
    display: flex; align-items: baseline; gap: 14px;
    border-bottom: 1px solid var(--grid);
    padding-bottom: 18px; margin-bottom: 28px;
}
.forge-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 28px; font-weight: 700; letter-spacing: -0.5px;
    color: var(--text);
}
.forge-title span { color: var(--amber); }
.forge-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px;
    color: var(--text-dim); border: 1px solid var(--grid);
    padding: 3px 8px; border-radius: 3px;
}

.log-entry {
    font-family: 'JetBrains Mono', monospace; font-size: 13px;
    padding: 10px 14px; margin-bottom: 6px; border-radius: 4px;
    border-left: 3px solid var(--grid);
    background: var(--ink-panel);
    display: flex; justify-content: space-between; align-items: center;
}
.log-entry.ok { border-left-color: var(--cyan); }
.log-entry.pending { border-left-color: var(--amber); }
.log-status { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
.log-status.ok { color: var(--cyan); }
.log-status.pending { color: var(--amber); }

.forge-panel {
    background: var(--ink-panel); border: 1px solid var(--grid);
    border-radius: 6px; padding: 20px 24px; margin-bottom: 16px;
}
.forge-label {
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    text-transform: uppercase; letter-spacing: 1.5px; color: var(--amber);
    margin-bottom: 10px;
}

.stButton > button {
    font-family: 'JetBrains Mono', monospace; font-weight: 600;
    border-radius: 4px; border: 1px solid var(--cyan);
    background: transparent; color: var(--cyan);
}
.stButton > button:hover { background: var(--cyan); color: var(--ink); }

.stTextArea textarea {
    background: var(--ink-panel) !important; border: 1px solid var(--grid) !important;
    color: var(--text) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="forge-header">
    <div class="forge-title">forge<span>.</span>build</div>
    <div class="forge-tag">multi-agent code generator</div>
</div>
""", unsafe_allow_html=True)

# Session state 
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "plan_preview" not in st.session_state:
    st.session_state.plan_preview = None
if "final_result" not in st.session_state:
    st.session_state.final_result = None

config = {"configurable": {"thread_id": st.session_state.thread_id}}

# Stage 1: input
if st.session_state.stage == "input":
    st.markdown('<div class="forge-label">Describe what to build</div>', unsafe_allow_html=True)
    user_request = st.text_area(
        "request", label_visibility="collapsed", height=110,
        placeholder="e.g. Build a command-line to-do list app with add, list, and save-to-file features"
    )

    if st.button("▸ Generate Plan") and user_request:
        project_path = f"./generated_projects/{st.session_state.thread_id[:8]}"
        os.makedirs(project_path, exist_ok=True)

        with st.spinner("Planner agent is scoping the request..."):
            result = app.invoke({
                "user_request": user_request,
                "project_path": project_path,
                "current_file_index": 0,
                "generated_files": {},
                "execution_results": {},
                "retry_counts": {}
            }, config=config)

        st.session_state.plan_preview = result.get("plan")
        st.session_state.project_path = project_path
        st.session_state.stage = "awaiting_approval"
        st.rerun()

#approval 
elif st.session_state.stage == "awaiting_approval":
    plan = st.session_state.plan_preview

    st.markdown('<div class="forge-label">Build Plan — Review</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="forge-panel">
        <b style="color:var(--cyan)">{plan.project_name}</b><br>
        <span style="color:var(--text-dim); font-size:14px">{plan.description}</span><br><br>
        <span class="forge-label" style="margin:0">stack</span> {', '.join(plan.tech_stack)}<br><br>
        <span class="forge-label" style="margin:0">features</span>
        <ul>{''.join(f'<li style="font-size:14px">{f}</li>' for f in plan.core_features)}</ul>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("▸ Approve & Build"):
            with st.spinner("Agents are building your project..."):
                try:
                    final = app.invoke(Command(resume={"approved": True}), config=config)
                    st.session_state.final_result = final
                    st.session_state.stage = "done"
                except Exception as e:
                    st.error(f"Build failed: {e}")
            st.rerun()
    with col2:
        if st.button("✕] Start Over"):
            st.session_state.stage = "input"
            st.session_state.plan_preview = None
            st.rerun()

#results
elif st.session_state.stage == "done":
    st.markdown('<div class="forge-label">Build Complete</div>', unsafe_allow_html=True)

    generated_files = st.session_state.final_result.get("generated_files", {})
    exec_results = st.session_state.final_result.get("execution_results", {})

    retry_counts = st.session_state.final_result.get("retry_counts", {})

    for filename, code in generated_files.items():
        status = exec_results.get(filename)
        ok = status and status.success
        css_class = "ok" if ok else "pending"
        label = "verified" if ok else "generated"
        st.markdown(f"""
        <div class="log-entry {css_class}">
            <span>{filename}</span>
            <span class="log-status {css_class}">● {label}</span>
        </div>
        """, unsafe_allow_html=True)
        with st.expander(f"view {filename}"):
            st.code(code, language="python")

    project_path = st.session_state.project_path
    zip_path = f"{project_path}.zip"
    if os.path.exists(zip_path):
        with open(zip_path, "rb") as f:
            st.download_button("⬇ Download Project (.zip)", f, file_name="forge_project.zip")

    if st.button("Build Another"):
        st.session_state.stage = "input"
        st.session_state.plan_preview = None
        st.session_state.final_result = None
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()