import os
import pytest
from pydantic import ValidationError
from app.schemas import Settings
from app.security import Workspace
from app.tools import ToolRegistry
from app.database import Task


@pytest.mark.parametrize('path', ['../outside.py','a/../../b','C:\\Windows\\a','\\\\host\\share\\x','/absolute','a:b', 'NUL.txt','COM1.py','foo.','foo ','a//b','a/./b','bad\x00file',''])
def test_path_traversal(tmp_path, path):
    with pytest.raises(ValueError):
        Workspace(tmp_path).path(path)


def test_safe_files_and_limits(tmp_path):
    ws = Workspace(tmp_path)
    ws.write('src/main.py','print(1)')
    assert ws.files() == ['src/main.py']
    assert ws.read('src/main.py') == 'print(1)'
    assert len(ws.hashes()['src/main.py']) == 64
    with pytest.raises(ValueError):
        ws.write('big.txt', 'x'*100001)


def test_hardlinks_rejected(tmp_path):
    outside = tmp_path/'outside'
    outside.write_text('private')
    ws = Workspace(tmp_path/'project')
    os.link(outside, ws.root/'linked')
    with pytest.raises(ValueError):
        ws.read('linked')


def test_symlink_rejected(tmp_path):
    ws = Workspace(tmp_path/'project')
    outside = tmp_path/'outside'
    outside.mkdir()
    try:
        (ws.root/'link').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Windows does not grant symlink creation to this process')
    with pytest.raises(ValueError):
        ws.path('link/file')


@pytest.mark.parametrize('changes', [{'ollama_url':'https://api.example.com'}, {'ollama_url':'http://127.0.0.1@evil.test'}, {'ollama_url':'http://localhost/a'}, {'max_iterations':6}, {'llm_concurrency':2}, {'internet_enabled':True}, {'timeout':0}])
def test_config_validation(changes):
    with pytest.raises(ValidationError):
        Settings(**changes)


def test_cloud_model_rejected():
    models = Settings().models
    models['ceo']='qwen-cloud'
    with pytest.raises(ValidationError):
        Settings(models=models)


def test_tool_permissions_and_user_file(system):
    service, worker, http, runner = system
    project = service.create_project('Tools')
    task = service.enqueue(project.id,'Build', 'unique-tool-test')
    ws = service.project_workspace(project.id)
    ws.write('user.txt','important')
    with service.sessions.begin() as s:
        registry = ToolRegistry(ws,s,task,{})
        with pytest.raises(PermissionError):
            registry.call('arbitrary_function',{},['arbitrary_function'])
        with pytest.raises(PermissionError):
            registry.call('write_file',{'path':'user.txt','content':'oops'},['write_file'])
        assert ws.read('user.txt') == 'important'
