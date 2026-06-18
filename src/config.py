import yaml
from pathlib import Path

class AppConfig:
    def __init__(self, data):
        self.app = data.get('app', {})
        self.models = data.get('models', {})
        self.processing = data.get('processing', {})
        self.prompts = data.get('prompts', {})

    @classmethod
    def load(cls, path="config.yaml"):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(data)

settings = AppConfig.load()
