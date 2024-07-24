import random

from pydantic import BaseModel

import dsp
from dspy.predict.parameter import Parameter
from dspy.primitives.program import Module

from dspy.primitives.prediction import Prediction
from dspy.signatures.signature import ensure_signature, signature_to_template
from .generate import generate, old_generate

from dspy.predict.predict import Predict as old_Predict
class Predict(old_Predict,Module, Parameter):
    def __init__(self, signature, **config):
        self.stage = random.randbytes(8).hex()
        self.signature = ensure_signature(signature)
        self.config = config
        self.reset()

    def reset(self):
        self.lm = None
        self.traces = []
        self.train = []
        self.demos = []

    def dump_state(self):
        state_keys = ["lm", "traces", "train"]
        state = {k: getattr(self, k) for k in state_keys}

        state["demos"] = []
        for demo in self.demos:
            demo = demo.copy()

            for field in demo:
                if isinstance(demo[field], BaseModel):
                    demo[field] = demo[field].model_dump_json()

            state["demos"].append(demo)

        # Cache the signature instructions and the last field's name.
        *_, last_key = self.signature.fields.keys()
        state["signature_instructions"] = self.signature.instructions
        state["signature_prefix"] = self.signature.fields[last_key].json_schema_extra["prefix"]

        # Some special stuff for CoT.
        if hasattr(self, "extended_signature"):
            # Cache the signature instructions and the last field's name.
            state["extended_signature_instructions"] = self.extended_signature.instructions
            state["extended_signature_prefix"] = self.extended_signature.fields[last_key].json_schema_extra['prefix']

        return state

    def load_state(self, state):
        for name, value in state.items():
            setattr(self, name, value)

        # Reconstruct the signature.
        if "signature_instructions" in state:
            instructions = state["signature_instructions"]
            self.signature = self.signature.with_instructions(instructions)

        if "signature_prefix" in state:
            prefix = state["signature_prefix"]
            *_, last_key = self.signature.fields.keys()
            self.signature = self.signature.with_updated_fields(last_key, prefix=prefix)
        
        # Some special stuff for CoT.
        if "extended_signature_instructions" in state:
            instructions = state["extended_signature_instructions"]
            self.extended_signature = self.extended_signature.with_instructions(instructions)

        if "extended_signature_prefix" in state:
            prefix = state["extended_signature_prefix"]
            *_, last_key = self.extended_signature.fields.keys()
            self.extended_signature = self.extended_signature.with_updated_fields(last_key, prefix=prefix)

    def __call__(self, **kwargs):
        return self.forward(**kwargs)

    def forward(self, **kwargs):
        assert not dsp.settings.compiling, "It's no longer ever the case that .compiling is True"

        # Extract the three privileged keyword arguments.
        new_signature = ensure_signature(kwargs.pop("new_signature", None))
        signature = ensure_signature(kwargs.pop("signature", self.signature))
        demos = kwargs.pop("demos", self.demos)
        config = dict(**self.config, **kwargs.pop("config", {}))

        # Get the right LM to use.
        lm = kwargs.pop("lm", self.lm) or dsp.settings.lm
        assert lm is not None, "No LM is loaded."

        # If temperature is 0.0 but its n > 1, set temperature to 0.7.
        temperature = config.get("temperature")
        temperature = lm.kwargs["temperature"] if temperature is None else temperature

        num_generations = config.get("n")
        if num_generations is None:
            num_generations = lm.kwargs.get("n", lm.kwargs.get("num_generations", 1))

        if (temperature is None or temperature <= 0.15) and num_generations > 1:
            config["temperature"] = 0.7
            # print(f"#> Setting temperature to 0.7 since n={num_generations} and prior temperature={temperature}.")

        if new_signature is not None:
            signature = new_signature

        if not all(k in kwargs for k in signature.input_fields):
            present = [k for k in signature.input_fields if k in kwargs]
            missing = [k for k in signature.input_fields if k not in kwargs]
            print(f"WARNING: Not all input fields were provided to module. Present: {present}. Missing: {missing}.")

        completions = old_generate(demos, signature, kwargs, config, self.lm, self.stage)

        pred = Prediction.from_completions(completions, signature=signature)

        if kwargs.pop("_trace", True) and dsp.settings.trace is not None:
            trace = dsp.settings.trace
            trace.append((self, {**kwargs}, pred))

        return pred

    def update_config(self, **kwargs):
        self.config = {**self.config, **kwargs}

    def get_config(self):
        return self.config

    def __repr__(self):
        return f"{self.__class__.__name__}({self.signature})"

