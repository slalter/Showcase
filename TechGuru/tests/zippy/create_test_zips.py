from models import Zip, Criterion, CriterionValue
import dspy
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from packages.guru.GLLM import LLM
from prompt_classes import ZipExamplePrompt
import json
from packages.guru.GLLM.models.dspy_extensions.typed_predictor_copy import TypedPredictor

class ZipSeedsSquared(dspy.Signature):
    """Generate a list of short strings describing different types of things someone might want to try to find or offer. Use general categories like 'food' or 'friendship' or 'goods' rather than specific examples like 'pizza' or 'John Doe'."""
    num_examples = dspy.InputField()
    seeds:list[str] = dspy.OutputField()

class ZipExampleSeeds(dspy.Signature):
    """Generate a set of short strings describing something someone could be seeking or offering. This could be a good, service, or simply an attempt to find a friend."""
    seed = dspy.InputField(desc="A categorical seed to generate examples from.")
    num_examples = dspy.InputField()
    seeds:list[str] = dspy.OutputField(desc="Some of these should match, some should not. There should be highly varied levels of specificity. Try to break a complex software system with your response.")

class ZipExample(dspy.Signature):
    """Generate the following based on the seed. Respond with a JSON. Only include the JSON object, nothing more or less."""
    seed = dspy.InputField(desc="A short string describing something someone could be seeking or offering.")
    criteria:list[tuple[str,str]] = dspy.OutputField(desc="A list of tuples that describe the criteria for the user's search or offer. Should be comprehensive. Example: [('price':'free'), ('location':'San Francisco'),...]}")
    description:str = dspy.OutputField(desc="A short description of the user's search or offer in natural language.")
    providing:list[str] = dspy.OutputField(desc="A list of strings that describe what the user is offering.")
    seeking:list[str] = dspy.OutputField(desc="A list of strings that describe what the user is seeking.")

class MakeZips(dspy.Module):
    def __init__(self):
        self.seed2_signature = ZipSeedsSquared
        self.seed2_predictor = TypedPredictor(self.seed2_signature)
        self.seed_signature = ZipExampleSeeds
        self.seed_predictor = TypedPredictor(self.seed_signature)
        self.example_zip_signature = ZipExample
        self.zip_predictor = TypedPredictor(self.example_zip_signature)

    def forward(self, num_seeds, num_seeds_squared):
        seed_seeds = self.seed2_predictor(num_examples=str(num_seeds_squared))
        zip_list = []
        def handle_seed_seed(seed):
            seeds = self.seed_predictor(num_examples=str(num_seeds), seed=seed)
            print(f"seeds: {seeds.seeds}")
            zips = []
            def handle_seed(seed):
                print(f"handling seed: {seed}")
                try:
                    prompt = ZipExamplePrompt(seed=seed)
                    z = prompt.execute().get()
                except Exception as e:
                    print(f"error: {e}")
                    return None
                print(f"zip: {z}")
                return z
            with ThreadPoolExecutor() as executor:
                zips = executor.map(handle_seed, seeds.seeds)
                results = [z for z in zips if z]
            
            results = [r for r in results if r]
            return results
            
        with ThreadPoolExecutor() as executor:
            results = executor.map(handle_seed_seed, seed_seeds.seeds)
            results = [r for r in results if r]
            for r in results:
                zip_list.extend(r)

        return zip_list
        

import traceback
dspy_path = 'tests/zippy/dspy'
def create_test_zips():
    from models import Session, Provided, Received
    from packages.guru.GLLM.models.google_api.anthropic import AnthropicModel
    lm = AnthropicModel(model='sonnet35', timeout=120)
    try:
        with dspy.context(lm=lm):
            make_zips = MakeZips()
            dspy.settings.lm = lm
            zips = make_zips.forward(10,30)
            def save_zip(zip):
                with Session() as session:

                
                    z = Zip(
                        description=zip['description'],
                        is_providing = [],
                        is_seeking = []

                    )

                    if zip.get('is_providing'):
                        for p in zip['is_providing']:
                            provided = Provided(content=p)
                            session.add(provided)
                            z.is_providing.append(provided)
                    if zip.get('is_seeking'):
                        for s in zip['is_seeking']:
                            received = Received(content=s)
                            session.add(received)
                            z.is_seeking.append(received)

                    try:
                        if not isinstance(zip['criteria'], dict):
                            criteria_dict = json.loads(zip['criteria'])
                        else:
                            criteria_dict = zip['criteria']
                        if not criteria_dict:
                            print(f"error1: {zip['criteria']}")
                            return
                    except Exception as e:
                        print(f"error2: {zip['criteria']} {e}")
                        return
                    for key, value in criteria_dict.items():
                        cv = CriterionValue(content=str(value))
                        c = Criterion(
                            content=str(key), 
                            zip=z,
                            criterion_value=cv)
                        session.add(c)
                        session.add(cv)
                    session.add(z)
                    print(f"zip created.")
                    session.commit()
                    return z
                
            #execute save_zip with a retry in parallel. As completed, increment the counter and print the x/y.
            with ThreadPoolExecutor(max_workers = 10) as executor:
                futures = [executor.submit(save_zip, z) for z in zips]
                i=0
                for future in as_completed(futures):
                    i+=1
                    print(f"{i}/{len(zips)}")
                    future.result()
            
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


                
