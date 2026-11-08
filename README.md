# assistant-team06 — Smart Virtual Assistant

> **WIP — chưa hoàn thành tích hợp 100%.** Nhánh `feat/LOCAL-01-interview-lifecycle`
> chia sẻ backend interview và hàm kiểm tra token để nhóm ghép tiếp. Đã kiểm thử
> local; còn chốt schema/format AI, cấu hình và thử dịch vụ thật, review rồi deploy.
> Xem [hướng dẫn lấy hàm token và những việc còn lại](docs/backend-handoff.md).

Yourin interview backend (local demo): see [the FastAPI walkthrough and API contract](docs/interview-api.md).
This adds a separate `python -m assistant --interview-api` entry point; the CLI and `--ui` below still work.

The team branches are now integrated locally. On Windows / PowerShell, after installing requirements:

```powershell
$env:INTERVIEW_DEMO_ENABLED = "1"
.\.venv\Scripts\python.exe -m assistant --interview-api
```

Open **http://127.0.0.1:8000/app/**, sign in with `demo_user` / `demo12345`, then create an interview.
This explicitly labeled local demo uses SQLite and mock AI without cloud keys.
Progress, answers and reports come from the backend. See [completed checkpoints and remaining work](docs/backend-progress.md).

Small rule-based study assistant for CSC10014 Lab 1. Follow the steps below and it must run without extra help.

## Setup

Prerequisites: Python 3.10+, Git.

```bash
git clone git@github.com:Mcrvc/assistant-team06.git
cd assistant-team06
python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## Run

With the virtual environment active:

```bash
python -m assistant "hi"
```

Expected output:

```
Hello! Ask me where an office is, or when it opens.
```

See what the assistant can do:

```bash
python -m assistant "help"
```

Expected output:

```
I can: greet you (try 'hi'), tell you where an office is and when it opens (e.g. 'where is the training office?'), and say goodbye ('bye').
```

Interactive mode:

```bash
python -m assistant
```

Expected:

```
Study assistant (starter). Type 'quit' to exit.
```

Type `hi` or `help`, then `quit` to exit.

## Test

```bash
python scripts/check_env.py
```
```bash
pytest -q
```



## Troubleshooting

- `No module named assistant` -> venv not active or you forgot `pip install -e .`.
- PowerShell blocks `Activate.ps1` -> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.
- `python: command not found` (Windows) -> use `py`. Inside venv, `python` works.
- `FileNotFoundError: data/offices.csv` on office questions -> expected on `main`, the file is not merged yet.

## Evaluation

Run the benchmark script:

```bash
python eval/run.py
```
