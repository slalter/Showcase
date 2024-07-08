import os
import subprocess
import json
import dspy.teleprompt
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Dict, Any
import shutil

def execute(args, tool_call_id, session, feature_instance):
    '''
    ONLY CALLABLE WHEN ALL DEPENDENCIES HAVE BEEN COMPLETED.
    Run pyright starting in this feature's directory. 
    Builds the files.
    Catches output from pyright and returns it as a string. raises exceptions.
    '''
    from models import ObjectRequest, CodeMixin
    #get the code
    code = feature_instance.code
    if not feature_instance.file_path:
        object_requests = feature_instance.getObjectRequests(session)

        unfinished_ors = [or_ for or_ in object_requests if not or_.status=='fulfilled']
        if unfinished_ors:
            for or_ in unfinished_ors:
                if or_.name in code:
                    raise Exception('You cannot run pyright until all dependencies have been completed. We are still waiting for the following object requests to be fulfilled: ' + ', '.join([or_.name for or_ in unfinished_ors if or_.name in code]))


        code_object:CodeMixin = feature_instance.main_object_request.code_object
        if not code_object:
            return 'No code object found. Please submit code first.'
        code_object.build(f'/tmp/{code_object.id}')
        path = f'/tmp/{code_object.id}'
    else:
        path = '/tmp/'
        #ensure the path exists
        if not os.path.exists(path):
            os.makedirs(path)
        with open(f'/tmp/test.py', 'w') as f:
            f.write(code)
    if not os.path.exists(path):
        os.makedirs(path)
    os.chdir(path)
    with open('pyrightconfig.json', 'w') as f:
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


    result = subprocess.run(['pyright'], stdout=subprocess.PIPE)
    if result.returncode:
        raise Exception('Pyright failed. Please fix the errors and try again. Here are the errors: \n' + result.stdout.decode('utf-8'))
    return result.stdout.decode('utf-8')

def getJson():
    return{
            "type": "function",
            "function":{
                "name": "run_pyright",
                "description": "Run Pyright on the code for your assigned task. This will check for type errors and provide suggestions for improving your code.",
                "parameters": {}
            }
        }
import os
import dspy
from dspy.teleprompt import BootstrapFewShot
gpt35t = dspy.OpenAI(model='gpt-3.5-turbo', max_tokens=250)
gpt4o = dspy.OpenAI(model='gpt-4o', max_tokens=1000)
import subprocess

def runPyright(code):
    import uuid
    original_dir = os.getcwd()
    id = str(uuid.uuid4())
    path = f'/tmp/dspy/{id}'
    if not os.path.exists(path):
        os.makedirs(path)
    with open(f'{path}/test.py', 'w') as f:
        f.write(code)
    os.chdir(path)
    with open('pyrightconfig.json', 'w') as f:
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
    result = subprocess.run(['pyright'], stdout=subprocess.PIPE)
    #switch back to current dir
    os.chdir(original_dir)
    if result.returncode:
        return result.stdout.decode('utf-8')
    else:
        return 'No errors found.'


def assess_metric(gold, pred, trace=None):
    """metric for tuning the Assess signature"""
    original_code, pyright_errors, updated_code, new_pyright_errors = gold['original_code'], gold['pyright_errors'], gold['updated_code'], gold['new_pyright_errors']
    scores = {}
    with dspy.context(lm=gpt4o):
        for dimension in dimensions:
            scores[dimension] = dspy.Predict(Assess)(
                original_code=original_code,
                pyright_errors=pyright_errors,
                updated_code=updated_code,
                new_pyright_errors=new_pyright_errors,
                dimension=dimension
            ).score
            print(f"{dimension}: {scores[dimension]}")
            total_score += scores[dimension]
    total_score /= len(dimensions)
    return total_score


class PyrightRunner(dspy.Module):
    def __init__(self):
        super().__init__()
        self.prog = dspy.ChainOfThought("code, pyright_errors -> updated_code")
    
    def forward(self, code):
        pyright_errors = runPyright(code)
        return self.prog(code=code, pyright_errors=pyright_errors)
    
class CreateExampleSeeds(dspy.Signature):
    """Generate a list of 3-4 word example seeds for generating highly-diverse short example code snippets."""
    num_seeds:int = dspy.InputField()
    seeds:list[str] = dspy.OutputField(desc="Each of these should inspire a short distinct code example.")

class CreateExampleCode(dspy.Signature):
    """Generate a short example of code that would fail pyright due to lack of typing information."""
    seed = dspy.InputField()
    code = dspy.OutputField()

class CreateExampleCodePipeline(dspy.Module):
    def __init__(self):
        super().__init__()
        self.example_seed_signature = CreateExampleSeeds
        self.seed_predictor = dspy.TypedPredictor(self.example_seed_signature)
        self.example_code_signature = CreateExampleCode
        self.code_predictor = dspy.Predict(self.example_code_signature)
        self.examples = []
        
    
    def forward(self, num_seeds=10):
        seeds = self.seed_predictor(num_seeds=num_seeds).seeds
        for seed in seeds:
            code = self.code_predictor(seed=seed).code
            self.examples.append(dspy.Example(code=code))
        return dspy.Prediction(examples=self.examples)
    
class AssessExampleCode(dspy.Signature):
    """Assess whether the example code and pyright results constitute a quality example with respect to the provided dimension. Provide a score on a scale of 0 to 1. Provide no other context."""
    code:str = dspy.InputField()
    pyright_errors:str = dspy.InputField()
    dimension:str = dspy.InputField()
    score:int = dspy.OutputField(desc="The score of the example code with respect to the provided dimension on a scale of 0 to 10.")

#example code dimensions with weights
example_code_dimensions = [ # (dimension, weight)
    ("The code contains no excess information or irrelevant context.", 1),
    ("The code fails pyright.", 1.0),
    ("The code is a reasonable size (less than 50 lines).", 0.5),
    ("The pyright errors are reasonable and fixable with the given context, and don't depend on additional external context.", 0.5),
    ("The pyright errors are not trivial (e.g. missing a colon or indentation), and are related directly to missing or incorrect types.", 1),
    ("The seed used to generate the code is relevant to the code itself.", 1),
]

def eliminate_similar_examples(examples, threshold=0.9, max_reduction_ratio=0.5):
    """Eliminate examples that are too similar to each other. Uses semantic similarity."""
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    from packages.guru.GLLM import LLM
    examples = examples.examples
    embeddings = LLM.getEmbeddingsSyncFromList([example.code for example in examples])
    similarity_matrix = cosine_similarity(embeddings, embeddings)
    np.fill_diagonal(similarity_matrix, 0)
    to_remove = []
    for i in range(len(examples)):
        if i in to_remove:
            continue
        for j in range(i+1, len(examples)):
            if j in to_remove:
                continue
            if similarity_matrix[i][j] > threshold:
                to_remove.append(j)

    if len(to_remove) > max_reduction_ratio * len(examples):
        #remove the most similar examples
        print(f"Removing {len(to_remove)} examples, since too many examples met the threshold.")
        to_remove = sorted(to_remove, key=lambda x: similarity_matrix[x], reverse=True)[:int(max_reduction_ratio * len(examples))]
    results = [example for i, example in enumerate(examples) if i not in to_remove]
    return dspy.Example(examples=results).with_inputs(None)

def assess_examples(example: Any, pred: Any = None, trace: Any = None) -> Tuple[float, Dict[Any, Dict[str, float]]]:
    examples = example.examples
    total_score = 0
    scores = {}

    def handle_example(example, pyright_errors) -> Tuple[float, Dict[str, float]]:
        code = example.code

        example_scores = {}
        example_total = 0
        predictor = dspy.TypedPredictor(AssessExampleCode)
        with ThreadPoolExecutor(max_workers=len(example_code_dimensions)) as executor:
            futures = [
                executor.submit(predictor, code=code, pyright_errors=pyright_errors, dimension=dimension) 
                for dimension, weight in example_code_dimensions
            ]
            for i, future in enumerate(futures):
                result = future.result()
                score = result.score
                dimension, weight = example_code_dimensions[i]
                example_scores[dimension] = score
                example_total += score * weight

        example_total /= 10 * sum(weight for _, weight in example_code_dimensions)
    
        return example_total, example_scores

    pyright_error_list = [runPyright(example.code) for example in examples]
    # Handle all examples
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(handle_example, example, pyright_errors) for example, pyright_errors in zip(examples, pyright_error_list)]

        for i, future in enumerate(futures):
            e_total, e_scores = future.result()
            total_score += e_total
            scores[examples[i]] = e_total

    total_score /= len(examples)
    return total_score, scores

def test():
    try:
        dspy_path = 'dspy/'
        with dspy.context(lm=gpt35t):
            sets = 2
            example_sets = []
            for i in range(sets):
                base_pipeline = CreateExampleCodePipeline()
                examples = base_pipeline.forward(num_seeds=20)
                with open("examples.json", "w") as f:
                    examples_json = {
                        f'set{i}':[example.code for example in examples.examples]
                    }
                    f.write(json.dumps(examples_json))
                '''
                with open("examples.txt", "r") as f:
                    examples_raw = eval(f.read())
                    '''
                deduped_examples = eliminate_similar_examples(examples, threshold=0.9, max_reduction_ratio=0.5)
                total_score, scores = assess_examples(deduped_examples, None)
                sorted_examples = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                top_10_examples = [p[0] for p in sorted_examples[:10]]
                with open(f"{dspy_path}top_10_examples_set_{i}.txt", "w") as f:
                    f.write(str(top_10_examples))
                example_sets.append(top_10_examples)
            devset = [dspy.Example(examples=example).with_inputs(None) for example in example_sets]

            #evaluator = Evaluate(devset=examples, display_progress=True)
            #results = evaluator(CreateExampleCode,  metric= assess_example_code)
            kwargs = dict(num_threads=2, display_progress=True, display_table=0)
            teleprompter = dspy.teleprompt.COPRO(
                metric=lambda x,y: assess_examples(x,y)[0])
            #teleprompter = BootstrapFewShot(metric=assess_example_code, **config)
            baseline = CreateExampleCodePipeline()
            optimized_program = teleprompter.compile(baseline,
                trainset=devset,
                eval_kwargs = kwargs)
            
            print(optimized_program.dump_state())
            #create the optimized_program.py file.
            with open(f"{dspy_path}optimized_program.py", "w") as f:
                f.write(' ')

            optimized_program.save(f"{dspy_path}optimized_program.py")
    finally:
        #remove all /tmp/dspy/*
        shutil.rmtree('/tmp/dspy')
        


class FixPyrightErrors(dspy.Signature):
    """Fix the pyright errors in the code."""
    code = dspy.InputField()
    pyright_errors = dspy.InputField()
    fixed_code = dspy.OutputField(desc="The code with the pyright errors fixed.")

class AssessFixedCode(dspy.Signature):
    """Assess the quality of the updated code with respect to the provided dimension."""
    original_code = dspy.InputField()
    pyright_errors = dspy.InputField()
    updated_code = dspy.InputField()
    new_pyright_errors = dspy.InputField()
    dimension = dspy.InputField()
    score = dspy.OutputField(desc="The score of the updated code with respect to the provided dimension on a scale of 0 to 1.")

dimensions = [
    ("The resulting code is functionally identical to the original code.", 1.0),
    ("The number of pyright errors in the updated code is less than or the number of pyright errors in the original code.", 1.0),
    ("No new pyright errors were introduced.", 1.0),
    ("The updated code doesn't use any placeholders or dummy values.", 1.0),
]

def assess_fixed(original_code, pyright_errors, updated_code, new_pyright_errors):
    scores = {}
    total_score = 0
    with dspy.context(lm=gpt4o):
        for dimension in dimensions:
            scores[dimension] = dspy.Predict(AssessFixedCode)(
                original_code=original_code,
                pyright_errors=pyright_errors,
                updated_code=updated_code,
                new_pyright_errors=new_pyright_errors,
                dimension=dimension
            )
            print(f"{dimension}: {scores[dimension]}")
            total_score += scores[dimension]

    total_score /= sum(weight for _, weight in dimensions)
    return total_score, scores

class GeneratePyrightExamples(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generateExample = dspy.ChainOfThought(CreateExampleCode)
        self.fixErrors = dspy.ChainOfThought(FixPyrightErrors)
        self.examples: list[tuple[dspy.Example, float]] = []


    def forward(self, top_k=5, num_examples=10):
        with dspy.context(lm=gpt4o):
            for _ in range(num_examples):
                example_code = self.generateExample().code
                pyright_errors = runPyright(example_code)
                example_score, score_dict = assess_example_code(example_code, pyright_errors)
                if len(self.examples) > 5:
                    dspy.Suggest(
                        example_score < min([example[1] for example in self.examples]),
                        f"""This example code is not a good example. These are the scores it recieved for each dimension:
                        {score_dict}
                        """
                    )
                fixed_code = self.fixErrors(code=example_code, pyright_errors=pyright_errors)
                new_pyright_errors = runPyright(fixed_code)
                fixed_score, fixed_score_dict = assess_fixed(example_code, pyright_errors, fixed_code, new_pyright_errors)
                if len(self.examples) > 5:
                    dspy.Suggest(
                        fixed_score < min([example[1] for example in self.examples]),
                        f"""The fixed code is not a good example. These are the scores it recieved for each dimension:
                        {fixed_score_dict}
                        """
                    )
                self.examples.append((dspy.Example(original_code=example_code, pyright_errors=pyright_errors, updated_code=fixed_code, new_pyright_errors=new_pyright_errors), fixed_score))


        sorted_examples = sorted(self.examples, key=lambda x: x[1], reverse=True)
        return sorted_examples[:top_k]


#results = GeneratePyrightExamples()()
#print(results)
'''
teleprompter = BootstrapFewShot(metric=, **config)
optimized_program = teleprompter.compile(YOUR_PROGRAM_HERE)'''

