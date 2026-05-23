# IELTS Super Learner Agent

CLI + Streamlit IELTS learning assistant powered by ZhipuAI **GLM-5.1** (native `zhipuai` SDK).

## Commands

```bash
source venv/bin/activate
pip install -r requirements.txt

python -m ielts_agent                    # Show all commands
python -m ielts_agent tutor              # Interactive coaching (diagnostic + drills)
python -m ielts_agent practice --skill writing --task 2
python -m ielts_agent score --skill writing --answer "..."
python -m ielts_agent progress

streamlit run streamlit_app.py           # Web app (Coach / Practice / Score)
```

## Environment

- `ZHIPUAI_API_KEY`: Required. Get from https://open.bigmodel.cn/usercenter/apikeys
- `IELTS_DISABLE_LOCALSTORAGE=1`: optional — forces the Streamlit app's in-session profile fallback (used by headless tests).

## Key Patterns

- **LLM Client**: Use `get_llm()` (interactive) or `get_llm_for_scoring()` (scoring) from `llm/client.py`. Native `zhipuai` SDK — no LangChain. Messages are `ielts_agent.llm.messages` objects or OpenAI-format dicts.
- **Models**: `glm-5.1` everywhere. Hybrid-reasoning model: **thinking off** for interactive/streaming (snappy), **thinking on** for scoring (quality). The client handles `reasoning_content`.
- **Tool calling**: `SimpleLLM.invoke(messages, tools=...)` returns `LLMResponse` with `.tool_calls`. The Coach (`agents/tutor.py`) runs the tool loop.
- **Coach orchestrator**: `TutorAgent` calls Practice + Score + profile updates as GLM tools. `start()` greets/diagnoses, `chat()` runs one coached turn; both return `{content, events, profile_changed}`.
- **Learner profile**: `ielts_agent/profile.py` (`LearnerProfile`). Persisted to SQLite for the CLI and browser localStorage for the web app. Injected into the Coach's system prompt each turn.
- **Database**: Every command calls `init_db()`. User lookup/creation happens at start of each command.
- **Agents**: Instantiated per command in `main.py`, not reused.
- **Progress**: Call `update_progress(user_id, skill, score)` after scoring.

## Git

- **Commit author**: Always use `mianlang@foxmail.com` for git commits.
