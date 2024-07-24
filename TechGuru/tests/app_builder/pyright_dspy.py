import os
import subprocess
import json
import dspy.teleprompt
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Dict, Any
import shutil
import traceback
from flask import jsonify
from dataclasses import dataclass


dspy_path = 'tests/app_builder/examples/dspy/'
if not os.path.exists(dspy_path):
    os.makedirs(dspy_path)

        
import dspy
from dspy.teleprompt import BootstrapFewShot
from packages.guru.GLLM.models import AnthropicModel
import subprocess
from packages.guru.GLLM.models.dspy_extensions.typed_predictor_copy import TypedPredictor
from packages.guru.GLLM.models.dspy_extensions.predict import Predict
from packages.guru.GLLM.models.dspy_extensions.chain_of_thought import ChainOfThought
from datetime import datetime
from packages.utils.pyright import runPyright

from .generate_pipeline import CreateExampleCode, CreateExampleSeeds, AssessExampleCode, eliminate_similar_examples, generate_examples, load_examples
#from dspy import TypedPredictor

@dataclass
class PyrightRunnerAttempt:
    attempt_no: int
    updated_code: str
    new_pyright_errors: str

    def to_dict(self):
        return {
            "attempt_no": self.attempt_no,
            "updated_code": self.updated_code,
            "new_pyright_errors": self.new_pyright_errors
        }

@dataclass
class PyrightRunnerOutput:
    attempts: list[PyrightRunnerAttempt]
    original_code: str
    original_errors: str
    final_code: str
    success: bool

    def to_dict(self):
        return {
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "original_code": self.original_code,
            "original_errors": self.original_errors,
            "final_code": self.final_code,
            "success": self.success
        }

    @classmethod
    def load_from_file(cls, file) -> list['PyrightRunnerOutput']:
        '''Load a PyrightRunnerOutput object from a file.'''
        with open(file, "r") as f:
            loaded = json.load(f)
            if isinstance(loaded, list):
                return [cls(**x) for x in loaded]
            else:
                return [cls(**json.load(f))]
        
    @staticmethod
    def load_list_from_dir(directory):
        '''Load a list of PyrightRunnerOutput objects from a file by trying to load from each file in the dir.'''
        outputs = []
        for file in os.listdir(directory):
            try:
                outputs += PyrightRunnerOutput.load_from_file(f"{directory}/{file}")
            except:
                print(f"failed to load {file}")
                continue
        return outputs


class PyrightRunner(dspy.Module):
    def __init__(self):
        super().__init__()
        self.prog = ChainOfThought("code, pyright_errors -> updated_code")
    
    def forward(self, original_code, pyright_errors, max_tries = 3):
        '''Run the code through pyright and return the updated code. Iterates up to max_tries.'''
        attempts = []
        code = original_code
        result = self.prog(code=code, pyright_errors=pyright_errors)
        new_pyright_errors = runPyright(result.updated_code)
        attempts.append(
            PyrightRunnerAttempt(
                attempt_no=1,
                updated_code=result.updated_code,
                new_pyright_errors=new_pyright_errors
            )
        )
        tries = 1
        while tries < max_tries and new_pyright_errors and new_pyright_errors != 'None.':
            result = self.prog(code=result.updated_code, pyright_errors=new_pyright_errors)
            new_pyright_errors = runPyright(result.updated_code)
            attempts.append(
                PyrightRunnerAttempt(
                    attempt_no=tries + 1,
                    updated_code=result.updated_code,
                    new_pyright_errors=new_pyright_errors
                )
            )
            tries += 1
        output = PyrightRunnerOutput(
            attempts=attempts,
            original_code=code,
            original_errors=pyright_errors,
            final_code=result.updated_code,
            success=new_pyright_errors=='None.' or not new_pyright_errors
        )
        return output.to_dict()

def test():
    try:
        
        sonnet35 = AnthropicModel("sonnet35", 45)
        lm = sonnet35
        '''
        #clear the pyright_runner_output directory
        if os.path.exists(f"{dspy_path}pyright_runner_output"):
            shutil.rmtree(f"{dspy_path}pyright_runner_output")
        
        examples = generate_examples("examples-50", 50, lm)
        #examples = load_examples("initial_examples")
        #run the examples thru the pyright runner
        pyright_runner = PyrightRunner()
        def run(code, pyright_errors):
            dspy.settings.lm = lm
            return pyright_runner(code=code, pyright_errors=pyright_errors)
        
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(run, example['code'], example['errors']) for example in examples]
            pyright_runner_results:list[PyrightRunnerOutput] = [future.result() for future in futures]

        
        #save output to file
        if not os.path.exists(f"{dspy_path}pyright_runner_output"):
            os.makedirs(f"{dspy_path}pyright_runner_output")
        with open(f"{dspy_path}pyright_runner_output/{datetime.now().isoformat()}.json", "w") as f:
            f.write(json.dumps(pyright_runner_results, indent=4, default=lambda x: x.__dict__))
        '''
        #load existing results
        pyright_runner_results = PyrightRunnerOutput.load_list_from_dir(f"{dspy_path}pyright_runner_output")
       
        #assess the results
        def assess(result: PyrightRunnerOutput) -> float:
            return assess_fixed(result,lm)

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(assess, result) for result in pyright_runner_results]
            scores = [future.result() for future in futures]

        #sort the examples by score, save them to a file
        examples = sorted(zip(pyright_runner_results, scores), key=lambda x: x[1], reverse=True)
        with open(f"{dspy_path}sorted_examples{datetime.now().isoformat()}.json", "w") as f:
            f.write(json.dumps(examples, indent=4, default=lambda x: x.__dict__))

        #train pyright runner.
        initial_cost = lm.get_total_cost()
        examples = [example[0] for example in examples]
        devset = []

        baseline = PyrightRunner()
        for example in examples:
            devset.append(dspy.Example(
                original_code=example.original_code,
                pyright_errors=example.original_errors,
                updated_code=example.final_code
            ).with_inputs('original_code','pyright_errors'))
        
        teleprompter = dspy.teleprompt.COPRO(
            metric=lambda x,y: assess_fixed(y,lm)[0])
        kwargs = dict(num_threads=1, display_progress=True, display_table=0)
        dspy.settings.lm = lm
        optimized_program = teleprompter.compile(baseline,
                trainset=devset[:10],
                eval_kwargs = kwargs)
        print(f"cost of optimizing program: {lm.get_total_cost()- initial_cost}")
        
        print(optimized_program.dump_state())
        #create the optimized_program.py file.
        if not os.path.exists(f"{dspy_path}pyright_program"):
            os.makedirs(f"{dspy_path}pyright_program")
        with open(f"{dspy_path}pyright_program/optimized_program{datetime.now().isoformat()}.py", "w") as f:
            f.write(' ')

        optimized_program.save(f"{dspy_path}pyright_program/optimized_program{datetime.now().isoformat()}.py")


        

    except Exception as e:
        print(traceback.format_exc())
        #inspect history
        print(lm.inspect_history())
        #inspect 
    finally:
        print("total cost for session: ", lm.get_total_cost())
        print("total calls: ", len(lm.history))
        #save log objects to file
        with open(f"{dspy_path}log_objects.json", "w") as f:
            f.write(json.dumps([log.to_dict() for log in lm.log_objects], indent=4))

        #remove all /tmp/dspy/*
        try:
            shutil.rmtree('/tmp/dspy')
        except:
            pass
        return jsonify({"status": "success"}),200        


class AssessFixedCode(dspy.Signature):
    """A developer sequentially attempted to fix pyright errors in their code. Evaluate their work with respect to the provided dimensions."""
    original_code = dspy.InputField()
    attempts = dspy.InputField()
    success = dspy.InputField()
    dimensions = dspy.InputField()
    scores = dspy.OutputField(desc="The scores of the updated code with respect to the provided dimension on a scale of 0 to 10, as a python list.")
    issues = dspy.OutputField(desc="A text string describing any issues you that may hinder the accuracy of this assessment. Blank if none.")

dimensions = [
    ("The resulting code is functionally identical to the original code.", 2.0),
    ("The developer reached the fixed version efficiently.", 1.0),
    ("'Any' was only used in cases that require it.", 1.0),
    ("Minimal assumptions were made.", 1.0)
]

def assess_fixed(result: PyrightRunnerOutput|dict,lm) -> float:
    if isinstance(result, dict):
        result = PyrightRunnerOutput(**result)
    scores = {}
    total_score = 0
    with dspy.context(lm=lm):
        result = Predict(AssessFixedCode)(
            original_code=result.original_code,
            original_errors=result.original_errors,
            attempts=json.dumps(result.attempts, default=lambda x: x.__dict__),
            success=str(result.success),
            dimensions=json.dumps([d[0] for d in dimensions])
        )
        scores = result.scores
        if not isinstance(scores, list):
            scores = json.loads(scores)
        issues = result.issues
        print(scores)
        print(f"issues: {issues}")
        for score, weight in zip(scores, [d[1] for d in dimensions]):
            total_score += score * weight

    total_score /= sum(weight for _, weight in dimensions)
    return total_score, scores




#results = GeneratePyrightExamples()()
#print(results)
'''
teleprompter = BootstrapFewShot(metric=, **config)
optimized_program = teleprompter.compile(YOUR_PROGRAM_HERE)'''

