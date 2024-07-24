import dspy
from packages.guru.GLLM.models.dspy_extensions.typed_predictor_copy import TypedPredictor
from packages.guru.GLLM.models.dspy_extensions.predict import Predict
from concurrent.futures import ThreadPoolExecutor
import json
import traceback
import shutil
from flask import jsonify
from typing import Any, Dict, Tuple
from packages.utils.pyright import runPyright
from .pyright_dspy import dspy_path

class CreateExampleSeeds(dspy.Signature):
    """As an expert code generator, create a list of 3-4 word example seeds that can be used to generate diverse, concise code snippets across various programming languages and paradigms. Each seed should be unique and suggestive of a specific coding concept, algorithm, or programming technique. Aim for a mix of difficulty levels and applicability to different domains of software development."""
    num_seeds:int = dspy.InputField()
    seeds:list[str] = dspy.OutputField(desc="Each of these should inspire a short distinct code example.")

class CreateExampleCode(dspy.Signature):
    """As a Python code generator specializing in type-related issues, your task is to create a concise code snippet that would trigger a pyright error due to insufficient typing information. The code should be syntactically correct but lack proper type annotations, causing pyright to raise concerns. Focus on common scenarios where type hints are crucial for static type checking. Provide only the code snippet without any explanations or comments."""
    seed = dspy.InputField()
    code = dspy.OutputField()

class CreateExampleCodePipeline(dspy.Module):
    def __init__(self, num_seeds=10):
        super().__init__()
        self.example_seed_signature = CreateExampleSeeds
        self.seed_predictor = TypedPredictor(self.example_seed_signature)
        self.example_code_signature = CreateExampleCode
        self.code_predictor = Predict(self.example_code_signature)
        self.examples = []
        self.num_seeds = num_seeds
        
    
    def forward(self, num_seeds=None):
        num_seeds = num_seeds or self.num_seeds
        seeds = self.seed_predictor(num_seeds=num_seeds).seeds
        for seed in seeds:
            code = self.code_predictor(seed=seed).code
            self.examples.append(dspy.Example(code=code))
        return dspy.Prediction(examples=self.examples)
    
class AssessExampleCode(dspy.Signature):
    """Assess whether the example code and pyright results constitute a quality example with respect to the provided dimension. Provide a score on a scale of 0 to 10. Provide the integer and nothing more."""
    code:str = dspy.InputField()
    pyright_errors:str = dspy.InputField()
    dimension:str = dspy.InputField()
    score:int = dspy.OutputField(desc="The score of the example code with respect to the provided dimension on a scale of 0 to 10.")

#example code dimensions with weights
example_code_dimensions = [ # (dimension, weight)
    ("The code contains no excess information or irrelevant context, and would compile as-is.", 1),                    
    ("The code is a reasonable size (less than 50 lines).", 0.5),
    ("The pyright errors are reasonable and fixable with the given context, and don't depend on additional external context.", 0.5),
    ("The pyright errors are not trivial (e.g. missing a colon or indentation), and are related directly to missing or incorrect types.", 2),
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
        predictor = TypedPredictor(AssessExampleCode)
        with ThreadPoolExecutor(max_workers=len(example_code_dimensions)) as executor:
            futures = [
                executor.submit(predictor, code=code, pyright_errors=pyright_errors, dimension=dimension) 
                for dimension, weight in example_code_dimensions
            ]
            for i, future in enumerate(futures):
                result = future.result()
                score = result.score
                dimension, weight = example_code_dimensions[i]
                print(f"{dimension}: {score}")
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

def generate_examples(file_name=None, num_examples=20, lm=None)->list[dict]:
    try:
        with dspy.context(lm=lm):
            dspy.settings.lm = lm
            base_pipeline = CreateExampleCodePipeline()
            examples = base_pipeline.forward(num_seeds=num_examples).examples
            make_examples_cost = lm.get_total_cost()
            print(f"cost so far: {make_examples_cost} with a total of {len(lm.log_objects)} logs.")


            pyright_error_list = [runPyright(example.code) for example in examples]
            with open(dspy_path + f"{file_name}.json", "w") as f:
                examples_json = [{
                    'code':example.code,
                    'errors': errors} for example, errors in zip(examples, pyright_error_list)]
                
                f.write(json.dumps(examples_json))
            '''
            with open("examples.txt", "r") as f:
                examples_raw = eval(f.read())
                '''
            return examples_json
    except Exception as e:
        print(traceback.format_exc())
        #inspect history
        print(lm.inspect_history())
        #inspect 
    finally:
        print("total cost for session: ", lm.get_total_cost())
        #save log objects to file
        with open(f"{dspy_path}log_objects.json", "w") as f:
            f.write(json.dumps([log.to_dict() for log in lm.log_objects], indent=4))

        #remove all /tmp/dspy/*
        try:
            shutil.rmtree('/tmp/dspy')
        except:
            pass   

def load_examples(file_name) -> list[dict] |None:
    '''returns a list of examples from a file.
    format:
    [
        {
            'code': str,
            'errors': str
        },...
    ]
    '''
    try:
        with open(f"{dspy_path}{file_name}.json", "r") as f:
            examples = json.load(f)
            return examples
    except Exception as e:
        print(traceback.format_exc())
        return None
    
def tune_example_pipeline(examples, lm):
    '''doesn't update automatically, just saves the output.'''
    examples = [e['code'] for e in examples]
    devset = dspy.Example(examples=examples).with_inputs(None)
    initial_cost = lm.get_total_cost()
    #evaluator = Evaluate(devset=examples, display_progress=True)
    #results = evaluator(CreateExampleCode,  metric= assess_example_code)
    kwargs = dict(num_threads=1, display_progress=True, display_table=0)
    teleprompter = dspy.teleprompt.COPRO(
        metric=lambda x,y: assess_examples(x,y)[0])
    #teleprompter = BootstrapFewShot(metric=assess_example_code, **config)
    baseline = CreateExampleCodePipeline()
    optimized_program = teleprompter.compile(baseline,
        trainset=devset,
        eval_kwargs = kwargs)
    print(f"cost of optimizing program: {lm.get_total_cost()- initial_cost}")
    
    print(optimized_program.dump_state())
    #create the optimized_program.py file.
    with open(f"{dspy_path}optimized_program.py", "w") as f:
        f.write(' ')

    optimized_program.save(f"{dspy_path}optimized_program.py")