from guru.GLLM import LLM
import asyncio
import json
random_words = [
    "Serendipity",
    "Quixotic",
    "Mellifluous",
    "Ephemeral",
    "Persnickety",
    "Luminous",
    "Resplendent",
    "Nebulous",
    "Cacophony",
    "Petrichor"
]
async def generateCandidates():
    with open("prompts/makeCandidatePrompt.txt", "r") as f:
        prompt = f.read()

    tasks = [LLM.json_response(prompt=prompt+random_words[i]) for i in range(0,10)]
    results = await asyncio.gather(*tasks)

    candidates = {}
    for i in range(0,10):
        candidates.update({i:results[i]}) 

    with open("data/candidates.json", "w") as f:
        f.write(json.dumps(candidates))

asyncio.run(generateCandidates())