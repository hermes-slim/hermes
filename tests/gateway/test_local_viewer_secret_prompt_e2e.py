"""E2E with real imports against the sandboxed HERMES_HOME: a local viewer's turn loads a skill whose
``required_environment_variables`` are missing → the gateway sends the desktop's ``secret`` request →
the viewer answers → the value is in the profile ``.env``, the skill is ready, and the value appears
in neither the tool result nor any frame other than the viewer's own response."""
import json
import threading
from types import SimpleNamespace

from gateway.config import Platform
from tests.gateway.test_local_viewer_secret_prompt import _answer_when_asked, _turn


def _write_skill(home, name, env_var):
    skill = home / 'skills' / 'test' / name
    skill.mkdir(parents=True)
    (skill / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: needs a key\nrequired_environment_variables:\n'
        f'  - name: {env_var}\n    prompt: Paste the key\n---\n# {name}\nUse ${env_var}.\n', encoding='utf-8')


def _view_in_turn(monkeypatch, name, file_path=None, answer='sekrit-123'):
    from gateway.session_secret_prompt import secret_prompt_scope
    from tools.skills_tool import skill_view
    from tools.thread_context import propagate_context_to_thread
    monkeypatch.setenv('HERMES_GATEWAY_SESSION', '1')
    monkeypatch.delenv('HERMES_INTERACTIVE', raising=False)
    turn, peer = _turn(Platform.LOCAL)
    out = {}
    with secret_prompt_scope(turn, SimpleNamespace()):
        worker = threading.Thread(target=propagate_context_to_thread(
            lambda: out.update(raw=skill_view(name, file_path=file_path))))
        worker.start()
        request = _answer_when_asked(peer, answer)
        worker.join(10)
    return request, peer, out['raw']


def test_skill_load_prompts_saves_env_and_becomes_ready(monkeypatch):
    from hermes_constants import get_hermes_home
    home = get_hermes_home()
    monkeypatch.delenv('E2E_SKILL_KEY', raising=False)
    _write_skill(home, 'e2e-keyed', 'E2E_SKILL_KEY')
    request, peer, raw = _view_in_turn(monkeypatch, 'e2e-keyed')
    assert request['params']['env_var'] == 'E2E_SKILL_KEY'
    assert 'E2E_SKILL_KEY=sekrit-123' in (home / '.env').read_text(encoding='utf-8')
    result = json.loads(raw)
    assert result['success'] and result['setup_needed'] is False, result
    assert result['missing_required_environment_variables'] == []
    assert 'sekrit-123' not in raw
    assert not any('sekrit-123' in repr(f) for f in peer.frames)


def test_typed_slash_skill_prompts_outside_a_turn(monkeypatch):
    """A desktop ``/skill`` is built in ``gateway/session_commands.py`` before any turn exists; it used
    to bake the "secure secret entry is not available" hint into the message instead of prompting."""
    from gateway.session_secret_prompt import session_secret_prompt_scope
    from hermes_constants import get_hermes_home
    from tools.skills_tool import skill_view
    home = get_hermes_home()
    monkeypatch.delenv('E2E_SLASH_KEY', raising=False)
    monkeypatch.setenv('HERMES_GATEWAY_SESSION', '1')
    monkeypatch.delenv('HERMES_INTERACTIVE', raising=False)
    _write_skill(home, 'e2e-slash', 'E2E_SLASH_KEY')
    turn, peer = _turn(Platform.LOCAL)
    authority, session_id, _ = turn._approval_owner
    out = {}

    def build():
        with session_secret_prompt_scope(authority, session_id):
            out['raw'] = skill_view('e2e-slash')
    worker = threading.Thread(target=build)
    worker.start()
    request = _answer_when_asked(peer, 'slash-value')
    worker.join(10)
    assert request['params']['env_var'] == 'E2E_SLASH_KEY'
    result = json.loads(out['raw'])
    assert result['setup_needed'] is False and 'gateway_setup_hint' not in result
    assert 'E2E_SLASH_KEY=slash-value' in (home / '.env').read_text(encoding='utf-8')


def test_builtin_secure_secret_skill_requests_on_demand(monkeypatch):
    """The bundled ``secure-secret`` skill is in the default catalog and, on demand, asks the desktop
    for any env var; the value lands in ``.env`` and never in the tool result or a published frame."""
    from hermes_constants import get_hermes_home
    from tools.skills_sync import sync_skills
    from tools.skills_tool import skills_list
    home = get_hermes_home()
    monkeypatch.delenv('E2E_ONDEMAND_TOKEN', raising=False)
    sync_skills(quiet=True)
    assert 'secure-secret' in {s['name'] for s in json.loads(skills_list())['skills']}
    request, peer, raw = _view_in_turn(monkeypatch, 'secure-secret', 'request/E2E_ONDEMAND_TOKEN', 'tok-987')
    assert request['params']['env_var'] == 'E2E_ONDEMAND_TOKEN'
    assert request['params']['metadata'] == {'skill_name': 'secure-secret'}
    result = json.loads(raw)
    assert result['success'] and result['stored'] and result['env_var'] == 'E2E_ONDEMAND_TOKEN'
    assert 'E2E_ONDEMAND_TOKEN=tok-987' in (home / '.env').read_text(encoding='utf-8')
    assert 'tok-987' not in raw and not any('tok-987' in repr(f) for f in peer.frames)


def test_builtin_secure_secret_rejects_bad_names_without_prompting(monkeypatch):
    from tools.skills_sync import sync_skills
    from tools.skills_tool import skill_view
    sync_skills(quiet=True)
    result = json.loads(skill_view('secure-secret', file_path='request/not a name'))
    assert result['success'] is False
