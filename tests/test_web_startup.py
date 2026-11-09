import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest
import uvicorn

from assistant import web
from assistant.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('flag', ['--ui', '--web', '--serve', '--interview-api'])
def test_cli_aliases_use_the_canonical_web_entry(monkeypatch, flag):
    monkeypatch.setattr(web, 'serve_ui', lambda **kwargs: 7 if kwargs['port'] == 8123 else 1)
    assert main([flag, '--port', '8123']) == 7


@pytest.mark.parametrize('render', [False, True])
def test_local_and_render_host_defaults(monkeypatch, render):
    for name in ('HOST', 'PORT', 'RENDER'):
        monkeypatch.delenv(name, raising=False)
    if render:
        monkeypatch.setenv('PORT', '10000')
        monkeypatch.setenv('RENDER', 'true')
    configs = []
    class Server:
        started = False
        def __init__(self, config):
            configs.append(config)
        def run(self):
            self.started = True
    monkeypatch.setattr(uvicorn, 'Server', Server)
    assert web.serve_ui(open_browser=False) == 0
    config = configs[0]
    assert config.host == ('0.0.0.0' if render else '127.0.0.1')
    assert config.port == (10000 if render else 8000)
    paths = set(config.app.openapi()['paths'])
    assert '/api/interviews/{interview_id}/finalize' in paths
    assert '/api/cv' not in paths and '/api/demo/session' not in paths


def test_startup_failure_returns_nonzero(monkeypatch):
    class FailedServer:
        started = False
        def __init__(self, config):
            pass
        def run(self):
            pass
    monkeypatch.setattr(uvicorn, 'Server', FailedServer)
    assert web.serve_ui(open_browser=False) == 1


def test_real_cli_serves_backend_without_exposing_fake_login():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env = {**os.environ, 'HOST': '127.0.0.1', 'PORT': str(port), 'INTERVIEW_STORAGE': 'auto'}
    process = subprocess.Popen([sys.executable, '-m', 'assistant', '--ui', '--port', str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=2, trust_env=False) as client:
            deadline = time.monotonic() + 10
            while True:
                assert process.poll() is None
                try:
                    if client.get('/api/health').status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                assert time.monotonic() < deadline
                time.sleep(0.05)
            assert client.get('/').status_code == 200
            assert '/api/interviews' in client.get('/openapi.json').json()['paths']
            assert client.post('/api/interviews', json={'job_profile': {'title': 'Intern'}}).status_code == 503
            assert client.post('/api/demo/session').status_code == 404
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
