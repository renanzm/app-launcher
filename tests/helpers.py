from launcher.config import parse_config


def make_config(**overrides):
    data = {
        "app_name": "Test Launcher",
        "server": {"host": "127.0.0.1", "user": "u", "password": "p"},
        "apps": [{
            "id": "demo",
            "name": "Demo App",
            "remote_dir": "/apps/demo",
            "package": "demo.zip",
            "executable": "demo.exe",
            "options": [
                {"key": "flag", "label": "Flag", "type": "bool", "env": "DEMO_FLAG"},
                {"key": "name", "label": "Name", "type": "text", "env": "DEMO_NAME", "default": "x"},
            ],
        }],
    }
    data.update(overrides)
    return parse_config(data)
