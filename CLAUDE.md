# IELTS Super Learner Agent

CLI-based IELTS learning assistant powered by LangChain and BigModel (ZhipuAI/GLM).

## Commands

```bash
source venv/bin/activate
pip install -r requirements.txt

python -m ielts_agent                    # Show all commands
python -m ielts_agent tutor              # Interactive tutoring
python -m ielts_agent practice --skill writing --task 2
python -m ielts_agent score --skill writing --answer "..."
python -m ielts_agent progress
```

## Environment

- `ZHIPUAI_API_KEY`: Required. Get from https://open.bigmodel.cn/usercenter/apikeys

## Key Patterns

- **LLM Client**: Use `get_llm()` or `get_llm_for_scoring()` from `llm/client.py`. IMPORTANT: Uses native `zhipuai` SDK (NOT LangChain's OpenAI-compatible interface).
- **Models**: `glm-4-flash` for default tasks, `glm-4-plus` for scoring.
- **Database**: Every command calls `init_db()`. User lookup/creation happens at start of each command.
- **Agents**: Instantiated per command in `main.py`, not reused.
- **Progress**: Call `update_progress(user_id, skill, score)` after scoring.

## Git

- **Commit author**: Always use `mianlang@foxmail.com` for git commits.
