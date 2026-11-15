"""The shared template must boot without treating owner tags as config values."""
from pathlib import Path

from fastapi.testclient import TestClient

from assistant.db import load_env_file
from assistant.web import create_app


def test_env_template_boots_unconfigured_without_external_connections(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / '.env.example'
    content = source.read_text(encoding='utf-8')
    for line in content.splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            monkeypatch.delenv(line.partition('=')[0].strip(), raising=False)
    copied = tmp_path / '.env'
    copied.write_text(content, encoding='utf-8')
    # Imported before the fixture: exercise the real loader on this temp file,
    # while the fixture still blocks implicit loading of the developer .env.
    load_env_file(copied)
    with TestClient(create_app()) as client:
        assert client.get('/api/health').status_code == 200
        assert client.app.state.interview_service is None
        assert client.post('/api/interviews', json={'job_profile': {'title': 'Intern'}}).status_code == 503
