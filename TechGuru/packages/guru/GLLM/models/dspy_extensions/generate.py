
from dsp.adapters import Template
from typing import Callable, Any
import dsp


def generate(template: Template, **kwargs) -> Callable:
    """Returns a callable function that generates completions for a given example using the provided template."""
    return _generate(template, **kwargs)

from dspy.primitives import Example
from dsp.primitives.predict import Completions
def _generate(template: Template, **kwargs) -> Callable:
    """Returns a callable function that generates completions for a given example using the provided template."""
    if not dsp.settings.lm:
        raise AssertionError("No LM is loaded.")

    generator = dsp.settings.lm

    def do_generate(example: Example, stage: str, max_depth: int = 2, original_example=None):
        if not dsp.settings.lm:
            raise AssertionError("No LM is loaded.")
        original_example = original_example or example
        assert stage is not None

        # Look up the appropriate fields in each demonstration.
        example = example.demos_at(lambda d: d[stage])

        # Generate and extract the fields.
        prompt = template(example)
        raw_completions: list[dict[str, Any]] = generator(prompt, **kwargs)

        completions: list[Example] = [template.extract(example, p) for p in raw_completions]

        # Find the completions that are most complete.
        field_names: list[str] = [field.input_variable for field in template.fields]

        last_field_idx = 0
        for field_idx, key in enumerate(field_names):
            completions_ = [c for c in completions if key in c.keys() and c[key] is not None]

            # Filter out completions that are missing fields that are present in at least one completion.
            if len(completions_):
                completions = completions_
                last_field_idx = field_idx + 1

        # If none of the completions is completed (i.e., none has the final field set).
        if last_field_idx < len(field_names):
            # Pick the first completion that has gone farthest.
            completion = completions[0]
            completion[field_names[last_field_idx]] = ""

            # Recurse with greedy decoding and a shorter length.
            max_tokens = kwargs.get("max_tokens", dsp.settings.lm.kwargs["max_tokens"])
            max_tokens = min(max(75, max_tokens // 2), max_tokens)
            new_kwargs = {**kwargs, "max_tokens": max_tokens, "n": 1, "temperature": 0.0,}

            assert max_depth > 0
            return generate(template, **new_kwargs)(completion, stage=stage,
                                                    max_depth=max_depth - 1,
                                                    original_example=original_example,)
        completions = Completions(completions, template=template)
        example = example.copy(completions=completions)

        # if len(completions) == 1:
        #     completion = completions[0]
        #     example[stage] = example.copy(**completion)

        #     if dsp.settings.compiling:
        #         inputs_ = set(original_example.keys())
        #         inputs = [
        #             f.input_variable
        #             for f in template.fields
        #             if f.input_variable in inputs_
        #         ]
        #         outputs = [
        #             f.output_variable
        #             for f in template.fields
        #             if f.input_variable not in inputs_
        #         ]

        #         example.compiling_stages = example.get("compiling_stages", [])
        #         example.compiling_stages.append(
        #             {
        #                 "name": stage,
        #                 "template": template,
        #                 "inputs": inputs,
        #                 "outputs": outputs,
        #             },
        #         )
        # else:
        #     # assert not dsp.settings.compiling, "TODO: At this point, cannot compile n>1 generations"
        #     example[stage] = dotdict(completions=completions)

        return example, completions

    return do_generate

def old_generate(demos, signature, kwargs, config, lm, stage):
    # Switch to legacy format for dsp.generate
    x = dsp.Example(demos=demos, **kwargs)
    template = signature_to_template(signature)
    if kwargs.get('json_mode'):
        config['json_mode'] = True
        pass
    x, C = generate(template, **config)(x, stage=stage)

    # assert stage in x, "The generated (input, output) example was not stored"

    completions = []

    for c in C:
        completions.append({})
        for field in template.fields:
            if field.output_variable not in kwargs.keys():
                completions[-1][field.output_variable] = getattr(c, field.output_variable)

    return completions

from dspy.signatures.field import InputField, OutputField, new_to_old_field, OldOutputField

def signature_to_template(signature, adapter=None) -> dsp.Template:
    """Convert from new to legacy format."""

    adapter = adapter or dsp.Template


    return adapter(
        signature.instructions,
        **{name: new_to_old_field(field) for name, field in signature.fields.items()},
    )
