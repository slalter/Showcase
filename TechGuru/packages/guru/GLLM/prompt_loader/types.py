from typing import Optional
import os


class PromptParams:
    def __init__(self, 
                 provider: str, 
                 model: str, 
                 description: str = '',
                 timeout: int = 60, 
                 print_log: bool = False, 
                 json_mode: bool = False, 
                 timestamps: bool = False, 
                 return_type: str = 'Any'):
        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.print_log = print_log
        self.json_mode = json_mode
        self.timestamps = timestamps
        self.return_type = return_type
        self.description = description

    @classmethod
    def from_dict(cls, params: dict):
        return cls(
            provider=params.get('provider', os.environ.get('GLLM_DEFAULT_PROVIDER','')),
            model=params.get('model', os.environ.get('GLLM_DEFAULT_MODEL','')),
            description=params.get('description', ''),
            timeout=int(params.get('timeout', 60)),
            print_log=params.get('print_log', 'False').lower() in ['true', '1'],
            json_mode=params.get('json_mode', 'False').lower() in ['true', '1'],
            timestamps=params.get('timestamps', 'False').lower() in ['true', '1'],
            return_type=params.get('return_type', 'Any')
        )

    def to_dict(self):
        return {
            'provider': self.provider,
            'model': self.model,
            'description': self.description,
            'timeout': self.timeout,
            'print_log': self.print_log,
            'json_mode': self.json_mode,
            'timestamps': self.timestamps,
            'return_type': self.return_type
        }