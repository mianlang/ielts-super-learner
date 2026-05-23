"""IELTS Super Learner — Streamlit web app.

Three modes:
- Coach: a GLM-5.1 orchestrator that diagnoses you, then drills your weak spots
  by calling Practice + Score as tools, all backed by a learner profile that
  persists in your browser (localStorage).
- Practice: generate an authentic question for any skill, then submit your
  answer for an instant band score.
- Score: paste a question + your answer and get a band score with feedback.
"""

import os
import time
from datetime import date

import streamlit as st

# ----------------------------------------------------------------------------
# Secrets: Streamlit Cloud first, then a local .env for development.
# ----------------------------------------------------------------------------
if "ZHIPUAI_API_KEY" in st.secrets:
    os.environ["ZHIPUAI_API_KEY"] = st.secrets["ZHIPUAI_API_KEY"]
else:
    from dotenv import load_dotenv

    load_dotenv()

from streamlit_local_storage import LocalStorage

from ielts_agent.agents.practice import PracticeAgent
from ielts_agent.agents.scorer import ScorerAgent
from ielts_agent.agents.tutor import TutorAgent, tool_label
from ielts_agent.profile import LearnerProfile

PROFILE_KEY = "ielts_profile_v1"

st.set_page_config(page_title="IELTS Super Learner", page_icon="🎓", layout="wide")

st.markdown(
    """
<style>
    .main-header { text-align: center; padding: 1rem 0 0.5rem; }
    .stChatMessage { font-size: 0.97rem; }
</style>
""",
    unsafe_allow_html=True,
)

if not os.getenv("ZHIPUAI_API_KEY"):
    st.error("⚠️ ZHIPUAI_API_KEY not configured.")
    st.info("Locally: create a `.env` with `ZHIPUAI_API_KEY=your_key`. On Streamlit Cloud: set it in Secrets.")
    st.stop()


# ----------------------------------------------------------------------------
# Profile persistence (browser localStorage, with a safe in-session fallback).
#
# streamlit-local-storage's constructor blocks until a real browser frontend
# returns the stored data. That's fine in a browser, but it would hang with no
# frontend (headless tests, or a browser that blocks storage). We fall back to
# a session-only store in those cases so the app always loads.
# ----------------------------------------------------------------------------
_DISABLE_BROWSER_STORAGE = os.getenv("IELTS_DISABLE_LOCALSTORAGE") == "1"


class _SessionStore:
    """Drop-in localStorage substitute scoped to the current session."""

    def getItem(self, item_key):
        return st.session_state.get(f"_ls_{item_key}")

    def setItem(self, item_key, item_value, key=None):
        st.session_state[f"_ls_{item_key}"] = item_value

    def deleteItem(self, item_key, key=None):
        st.session_state.pop(f"_ls_{item_key}", None)


def _make_storage():
    if _DISABLE_BROWSER_STORAGE:
        return _SessionStore()
    try:
        return LocalStorage()
    except Exception:  # noqa: BLE001 - degrade to session-only, never crash
        return _SessionStore()


if "browser_storage" not in st.session_state:
    st.session_state.browser_storage = _make_storage()
local_storage = st.session_state.browser_storage


def load_profile() -> LearnerProfile:
    """Hydrate the profile from localStorage once per session."""
    raw = local_storage.getItem(PROFILE_KEY)
    return LearnerProfile.from_json(raw) if raw else LearnerProfile()


def request_persist() -> None:
    """Queue the current profile to be written to localStorage this run."""
    st.session_state.profile_to_persist = st.session_state.profile.to_json()


def flush_persist() -> None:
    """Write the queued profile to localStorage at most once per run."""
    pending = st.session_state.get("profile_to_persist")
    if pending and pending != st.session_state.get("profile_persisted"):
        local_storage.setItem(PROFILE_KEY, pending, key="persist_profile_slot")
        st.session_state.profile_persisted = pending
    st.session_state.profile_to_persist = None


# ----------------------------------------------------------------------------
# Session state.
# ----------------------------------------------------------------------------
if "profile" not in st.session_state:
    st.session_state.profile = load_profile()
if "mode" not in st.session_state:
    st.session_state.mode = "coach"
if "harsh" not in st.session_state:
    st.session_state.harsh = False
if "coach" not in st.session_state:
    st.session_state.coach = TutorAgent(profile=st.session_state.profile, harsh=st.session_state.harsh)
if "coach_messages" not in st.session_state:
    st.session_state.coach_messages = []


def reset_coach() -> None:
    """Rebuild the coach (e.g. after a tone change) keeping the same profile."""
    st.session_state.coach = TutorAgent(profile=st.session_state.profile, harsh=st.session_state.harsh)
    st.session_state.coach_messages = []


def stream_text(text: str, delay: float = 0.010):
    """Yield text word-by-word for a typing effect (no extra API cost)."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(delay)


# ----------------------------------------------------------------------------
# Sidebar: the learner profile the Coach is working from.
# ----------------------------------------------------------------------------
def render_sidebar() -> None:
    p = st.session_state.profile
    with st.sidebar:
        st.header("📋 Learner profile")

        if p.current_band is not None or p.target_band is not None:
            c1, c2 = st.columns(2)
            c1.metric("Current", p.current_band if p.current_band is not None else "—")
            gap = p.band_gap()
            c2.metric(
                "Target",
                p.target_band if p.target_band is not None else "—",
                delta=(f"{gap:+.1f} to go" if gap else None),
                delta_color="off",
            )

        days = p.days_until_exam()
        if days is not None:
            st.caption(f"🗓️ Exam {p.exam_date} — **{days} days** away" if days >= 0 else f"🗓️ Exam {p.exam_date} (passed)")

        st.caption(f"🎯 Focus: **{p.focus_skill}** · Diagnostic: {'✅' if p.diagnostic_done else '⬜️ not done'}")

        if p.weaknesses:
            st.markdown("**Weaknesses to drill**")
            st.markdown("\n".join(f"- {w}" for w in p.weaknesses))

        if p.score_history:
            st.markdown("**Band trend**")
            st.line_chart(
                {"band": [r.band for r in p.score_history]},
                height=140,
                use_container_width=True,
            )

        if not (p.diagnostic_done or p.current_band or p.score_history):
            st.info("No profile yet — open **Coach** and start a session to run your diagnostic.")

        with st.expander("✏️ Edit / override"):
            name = st.text_input("Name", p.name)
            cur = st.number_input("Current band", 0.0, 9.0, float(p.current_band or 0.0), 0.5)
            tgt = st.number_input("Target band", 0.0, 9.0, float(p.target_band or 7.0), 0.5)
            try:
                exam_default = date.fromisoformat(p.exam_date) if p.exam_date else None
            except ValueError:
                exam_default = None
            exam = st.date_input("Exam date", value=exam_default)
            focus = st.selectbox(
                "Focus skill",
                ["writing", "speaking", "reading", "listening"],
                index=["writing", "speaking", "reading", "listening"].index(p.focus_skill)
                if p.focus_skill in ["writing", "speaking", "reading", "listening"]
                else 0,
            )
            if st.button("💾 Save profile", use_container_width=True):
                p.name = name
                p.current_band = cur if cur > 0 else None
                p.target_band = tgt if tgt > 0 else None
                p.exam_date = exam.isoformat() if exam else None
                p.focus_skill = focus
                p.touch()
                request_persist()
                st.success("Saved to your browser.")

        if st.button("🗑️ Reset profile & chat", use_container_width=True):
            st.session_state.profile = LearnerProfile()
            local_storage.deleteItem(PROFILE_KEY, key="delete_profile_slot")
            st.session_state.profile_persisted = None
            reset_coach()
            st.rerun()

        st.divider()
        st.caption("Your profile is stored only in this browser (localStorage).")


# ----------------------------------------------------------------------------
# Header + mode switch.
# ----------------------------------------------------------------------------
st.markdown(
    """
<div class="main-header">
    <h1>🎓 IELTS Super Learner</h1>
    <p>Your AI coach — diagnoses your level, then drills your real weaknesses.</p>
</div>
""",
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns(3)
if c1.button("🧑‍🏫 Coach", use_container_width=True, type="primary" if st.session_state.mode == "coach" else "secondary"):
    st.session_state.mode = "coach"
    st.rerun()
if c2.button("🎯 Practice", use_container_width=True, type="primary" if st.session_state.mode == "practice" else "secondary"):
    st.session_state.mode = "practice"
    st.rerun()
if c3.button("📊 Score", use_container_width=True, type="primary" if st.session_state.mode == "score" else "secondary"):
    st.session_state.mode = "score"
    st.rerun()

st.divider()

render_sidebar()


# ----------------------------------------------------------------------------
# Coach mode.
# ----------------------------------------------------------------------------
def run_coach_turn(prompt=None, start=False):
    coach = st.session_state.coach
    with st.chat_message("assistant"):
        status = st.status("Coaching…", expanded=False)

        def on_event(kind, data):
            if kind == "tool_start":
                status.update(label=tool_label(data["name"]))
                status.write(tool_label(data["name"]))

        result = coach.start(on_event=on_event) if start else coach.chat(prompt, on_event=on_event)
        status.update(label="Done", state="complete")
        st.write_stream(stream_text(result["content"]))

    st.session_state.coach_messages.append({"role": "assistant", "content": result["content"]})
    if result["profile_changed"]:
        request_persist()


if st.session_state.mode == "coach":
    tcol, scol = st.columns([3, 1])
    tcol.subheader("🧑‍🏫 Your IELTS Coach")
    harsh = scol.toggle("🔥 Drill mode", value=st.session_state.harsh, help="Blunt drill-instructor tone")
    if harsh != st.session_state.harsh:
        st.session_state.harsh = harsh
        reset_coach()
        st.rerun()

    for msg in st.session_state.coach_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # First contact: a button kicks off the diagnostic (cost-safe on a public URL).
    if not st.session_state.coach_messages:
        st.info(
            "👋 Your AI coach will run a quick **2-minute diagnostic**, then drill your "
            "weak spots. Your profile is saved privately in this browser."
        )
        if st.button("▶️ Start my session", type="primary"):
            run_coach_turn(start=True)
            st.rerun()

    if prompt := st.chat_input("Message your coach… (e.g. your band, target, exam date)"):
        st.session_state.coach_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        run_coach_turn(prompt=prompt)


# ----------------------------------------------------------------------------
# Practice mode.
# ----------------------------------------------------------------------------
elif st.session_state.mode == "practice":
    st.subheader("🎯 Practice")

    pc1, pc2, pc3 = st.columns(3)
    skill = pc1.selectbox("Skill", ["writing", "speaking", "reading", "listening"])

    task_num = None
    if skill == "writing":
        choice = pc2.selectbox("Task", ["Task 2", "Task 1 (experimental)"])
        task_num = 1 if "1" in choice else 2
    elif skill == "speaking":
        choice = pc2.selectbox("Part", ["Part 1", "Part 2", "Part 3"])
        task_num = int(choice.split()[-1])
    topic = pc3.text_input("Topic (optional)", placeholder="e.g. technology")

    if skill == "writing" and task_num == 1:
        st.warning("Writing Task 1 needs a chart/diagram we don't render yet — the question is text-only for now.")

    if st.button("Generate question", type="primary"):
        agent = PracticeAgent()
        kwargs = {"topic": topic} if topic.strip() else {}
        placeholder = st.empty()
        with st.spinner("Generating…"):
            question = placeholder.write_stream(
                agent.generate_practice_stream(skill, task=task_num, **kwargs)
            )
        st.session_state.practice_question = question
        st.session_state.practice_meta = {"skill": skill, "task": task_num}
        st.rerun()  # re-render once from state (avoids the stream + repaint double-render)

    if st.session_state.get("practice_question"):
        meta = st.session_state.practice_meta
        st.markdown("#### 📄 Your question")
        st.info(st.session_state.practice_question)

        if meta["skill"] in ("writing", "speaking"):
            answer = st.text_area("Your answer", height=240, key="practice_answer")
            wc = len(answer.split())
            if meta["skill"] == "writing":
                min_words = 250 if meta["task"] == 2 else 150
                warn = " ⚠️ below the recommended minimum" if 0 < wc < min_words else ""
                st.caption(f"Word count: {wc} (aim for {min_words}+){warn}")
            if st.button("Submit for scoring", type="primary"):
                if not answer.strip():
                    st.warning("Write your answer first.")
                else:
                    with st.spinner("Scoring…"):
                        scorer = ScorerAgent()
                        kwargs = {"question": st.session_state.practice_question}
                        if meta["skill"] == "writing":
                            kwargs["task"] = meta["task"]
                        else:
                            kwargs["part"] = meta["task"]
                        result = scorer.score(meta["skill"], answer, **kwargs)
                    band = result.get("overall_band_score", 0)
                    st.metric("Band score", band)
                    st.markdown(result.get("feedback", ""))
                    st.session_state.profile.add_score(
                        meta["skill"], meta["task"], float(band),
                        summary=st.session_state.practice_question[:80],
                    )
                    request_persist()
        else:
            st.info(
                "Reading & Listening come with an answer key in the question above — "
                "self-check against it. For graded feedback, use **Score** (Writing/Speaking) "
                "or the **Coach**."
            )


# ----------------------------------------------------------------------------
# Score mode.
# ----------------------------------------------------------------------------
elif st.session_state.mode == "score":
    st.subheader("📊 Score your answer")
    st.caption("We score Writing and Speaking against the question. (Reading/Listening are self-checked against their answer key — use Practice.)")

    sc1, sc2 = st.columns(2)
    skill = sc1.selectbox("Skill", ["writing", "speaking"])

    if skill == "writing":
        choice = sc2.radio("Task", ["Task 2", "Task 1 (experimental)"], horizontal=True)
        task = 1 if "1" in choice else 2
        min_words = 250 if task == 2 else 150
    else:
        choice = sc2.radio("Part", ["Part 1", "Part 2", "Part 3"], horizontal=True)
        task = int(choice.split()[-1])
        min_words = 0

    question = st.text_area("Question / prompt", height=120, placeholder="Paste the IELTS question you're responding to…")
    answer = st.text_area("Your answer", height=260, placeholder="Paste your essay or spoken-response transcript…")

    wc = len(answer.split())
    if skill == "writing":
        warn = " ⚠️ below the recommended minimum" if 0 < wc < min_words else ""
        st.caption(f"Word count: {wc} (aim for {min_words}+){warn}")

    if st.button("Get score", type="primary"):
        if not answer.strip():
            st.warning("Enter your answer first.")
        else:
            with st.spinner("Scoring…"):
                scorer = ScorerAgent()
                kwargs = {}
                if question.strip():
                    kwargs["question"] = question
                if skill == "writing":
                    kwargs["task"] = task
                else:
                    kwargs["part"] = task
                result = scorer.score(skill, answer, **kwargs)
            band = result.get("overall_band_score", 0)
            st.metric("Band score", band)
            st.subheader("Feedback")
            st.markdown(result.get("feedback", "No feedback available."))
            st.session_state.profile.add_score(skill, task, float(band), summary=question[:80])
            request_persist()


# ----------------------------------------------------------------------------
# Persist any queued profile change, then footer.
# ----------------------------------------------------------------------------
flush_persist()

st.divider()
st.markdown(
    """
<div style="text-align: center; color: #888; font-size: 0.85rem;">
    <p>Powered by GLM-5.1 · Get a free API key at
    <a href="https://open.bigmodel.cn/usercenter/apikeys" target="_blank">ZhipuAI</a></p>
</div>
""",
    unsafe_allow_html=True,
)
