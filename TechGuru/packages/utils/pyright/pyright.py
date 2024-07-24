import uuid
import os
import subprocess
import tempfile


def runPyright(code: str) -> str:
    with tempfile.TemporaryDirectory() as tempdir:
        path = os.path.join(tempdir, str(uuid.uuid4()))
        os.makedirs(path)

        with open(os.path.join(path, 'test.py'), 'w') as f:
            f.write(code)

        with open(os.path.join(path, 'pyrightconfig.json'), 'w') as f:
            f.write('''{
"reportMissingImports": true,
"reportMissingTypeStubs": true,
"pythonVersion": "3.11",
"pythonPlatform": "Linux",
"typeCheckingMode": "strict",
"exclude": [
"**/node_modules",
"**/__pycache__"
]
}
''')

        result = subprocess.run(['pyright'], cwd=path, stdout=subprocess.PIPE)

    #if pyright returned no errors, return None
    if result.returncode == 0:
        return 'None.'
    return result.stdout.decode('utf-8') or 'None.'