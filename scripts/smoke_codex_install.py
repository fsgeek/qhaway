"""Exercise the installed wheel's Codex wiring and MCP server without a model/API key.

Run with the clean wheel environment's Python, not the checkout interpreter.
The server uses that same installed Python instead of downloading a PyPI build.
"""
import asyncio
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def smoke(project):
    config = project / '.codex/config.toml'
    config.parent.mkdir()
    original = b'# preserve unrelated configuration\n[mcp_servers.other]\ncommand = "other"\n'
    config.write_bytes(original)
    store = project / 'curated store'
    command = [sys.executable, '-m', 'qhaway.cli']
    install = [*command, 'init', '--host', 'codex', '--project', str(project), '--dir', str(store)]
    subprocess.run(install, check=True, timeout=30)
    installed = config.read_bytes()
    subprocess.run(install, check=True, timeout=30)
    assert installed == config.read_bytes()
    settings = tomllib.loads(installed.decode())['mcp_servers']['qhaway']
    assert settings['args'][:4] == ['--isolated', '--python', '3.14', 'qhaway']
    params = StdioServerParameters(
        command=sys.executable,
        args=['-m', 'qhaway.cli', *settings['args'][settings['args'].index('qhaway') + 1:]],
        cwd=str(project),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialization = await session.initialize()
            # Windows TEMP can contain an 8.3 alias (RUNNER~1); the installer
            # and handshake deliberately publish the resolved absolute path.
            assert str(store.resolve()) in initialization.instructions
            saved = await session.call_tool('remember', {
                'type': 'project', 'title': 'Wheel integration',
                'description': 'installed wheel check', 'body': 'Synthetic wheel evidence.',
            })
            assert not saved.is_error, saved
            recalled = await session.call_tool('recall', {'query': 'wheel', 'limit': 1})
            assert not recalled.is_error, recalled
            assert 'Wheel integration' in recalled.content[0].text
    topics = {p.name: p.read_bytes() for p in store.glob('*.md') if p.name != 'MEMORY.md'}
    assert topics
    subprocess.run([*command, 'uninstall', '--host', 'codex', '--project', str(project)], check=True, timeout=30)
    assert config.read_bytes() == original
    assert topics == {p.name: p.read_bytes() for p in store.glob('*.md') if p.name != 'MEMORY.md'}
    print('PASS: installed-wheel Codex init, repeat init, MCP read/write, uninstall, preservation')


with tempfile.TemporaryDirectory(prefix='qhaway-wheel-') as temporary:
    asyncio.run(asyncio.wait_for(smoke(Path(temporary)), timeout=30))
