import os

os.environ['OPENAI_KEY'] = ''
os.environ['GLLM_LOGGING_PATH'] = 'logs/'
os.environ['DEFAULT_MODEL'] = 'gpt-4-1106-preview'

import asyncio
import random
from multiprocessing import Process
import json
import builtins
from guru.GLLM import LLM
from CLTrees.tree import Tree
import prompt_loader
# Save the original print function
original_print = builtins.print

# Define a new print function that sets flush=True by default
def new_print(*args, **kwargs):
    kwargs['flush'] = True
    original_print(*args, **kwargs)

# Overwrite the built-in print with the new print function
builtins.print = new_print


async def runTree(data, max_node_size = 5, max_layer_width = 5, objectType = "", sortBy = "", timestamps = True, pause_after = 20):
    t=Tree(max_node_size=max_node_size, max_layer_width=max_layer_width, objectType=objectType, sortBy=sortBy, timestamps=timestamps)
    i=0
    if isinstance(data, dict):
        for id, dat in data.items():
            i+=1
            print(f"processing element number {i}")
            await t.addElement(str(dat))
            if i%5==0:
                print("displaying graph.")
                t.makeGraph()
    if isinstance(data, list):
        for dat in data:
            i+=1
            print(f"processing element number {i}")
            newElement = str(dat)
            newElement = await t.addElement(newElement)
            if not t.findElementInTreeById(newElement.id):
                print(f"element lost! {newElement}")
                input()
            if i%pause_after==0:
                print("displaying graph.")
                totalElements = 0
                for id,node in t.nodes.items():
                    totalElements += len(node.elementIds)
                    print(f"{node.description}: {len(node.elementIds)} elements: \n{[element.description for id,element in node.getElements().items()]}")
                print(f"total elements: {totalElements}")
                await t.makeGraph()
                inp = input("q to quit any key to continue")
                if inp == 'q':
                    break
    t.save()
    return t


async def treeNavTest():
    print("loading tree...")
    t = loadTree("data/ROOT_NODE/23112642.txt")
    tn = TreeNavigator(t, reduce_to=3)
    information = "I am an expert in python"
    with open("prompts/treeNavigator.txt", "r") as f:
        txt = f.read()
    prompt = txt.replace('$information', information)

    while True:
        prompt = prompt.replace('$categories', f'{[str(node.description) for node in tn.getNextNodes()]}')
        log, response = await LLM.ex_oai_call(prompt=prompt)
        print(eval(eval(response)))
        result = tn.processWeights(eval(eval(response)))
        if result=='complete':
            print(tn.result)
            break


async def CLTreeTest():
    from testdata.generate import detailed_software_development_timeline
    from CLTrees.tree import Tree
    from CLTrees.element import Element
    t = Tree()
    i=0
    for example in detailed_software_development_timeline:
        await t.addElement(Element(
            description=example[0],
            timestamp=example[1]))
        i+=1
        if i==0:
            for i, layer in enumerate(t.layers):
                print(f"\n\nlayer: {i}")
                print(f"\n\nnodes:{[node.description for node in layer.nodes]}")
                print(f"\n\nlayer{i} TimeRanges: {[str(node.time_range) for node in layer.nodes]}")
            print(f"\n\nelements:{[str(element) for element in t.elements]}")
            t.displayTimeGraph()

    t.save()

async def troubleshoot():
    
    from CLTrees.tree import Tree
    from CLTrees.element import Element, createElement
    t = Tree()
    i=0
    data = [
    {
        "id": "0d16432f-0814-4ec1-a3a8-bce458e16912",
        "description": "Create Project Directory",
        "timestamp": "2024-01-03T23:01:16.926455",
        "detailed_description": "The task involved setting up the initial project directory for a Pong game development. The directory, named '/pong/', was to be created in the current working directory. This step is foundational for organizing the project's files and resources as development progresses.",
        "data": "The project directory '/pong/' has been created. This directory serves as the root for all the files related to the Pong game project. It is essential for maintaining a structured file system for the project's assets, source code, and any other related documents. To access the project files, navigate to the '/pong/' directory within the current working directory."
    },
    {
        "id": "072be31e-92d6-4d21-a04c-dc171ab5dd45",
        "description": "Directory Created",
        "timestamp": "2024-01-03T23:02:16.897468",
        "detailed_description": "The task involved establishing the initial project directory for the development of a Pong game. The directory, named '/pong/', was successfully created in the current working directory. This action sets the stage for organizing the project's files, including assets, source code, and related documents, as development progresses.",
        "data": {
            "event_id": "0d16432f-0814-4ec1-a3a8-bce458e16912",
            "description": "Create Project Directory",
            "timestamp": "2024-01-03 23:01:16.926455",
            "detailed_description": "The '/pong/' directory has been created and is ready to house the project files. To access these files, one must navigate to the '/pong/' directory within the current working directory.",
            "data": "The existence of the '/pong/' directory is confirmed. It is the root directory for the Pong game development project."
        }
    },
    {
        "id": "39c65491-d15e-4d75-b871-fd617168046e",
        "description": "Initialize Git Repository",
        "timestamp": "2024-01-03T23:03:12.457063",
        "detailed_description": "The next step in the Pong game development project involved setting up version control. This was achieved by initializing a Git repository within the newly created '/pong/' directory. The command 'git init' was executed in the directory to prepare for tracking the changes to the project files.",
        "data": {
            "description": "Git repository initialization",
            "commands": ["git init"],
            "directory": "/pong/",
            "purpose": "The purpose of initializing a Git repository is to track changes, facilitate version control, and support collaboration among developers. The 'git init' command is used to create a new Git repository in the specified directory. To verify initialization, one can look for a '.git' folder within the '/pong/' directory."
        }
    },
    {
        "id": "b5f8c436-58eb-4287-b87e-73651bad7644",
        "description": "Initialized Git",
        "timestamp": "2024-01-03T23:04:21.712969",
        "detailed_description": "The task involved setting up a version control system for the Pong game development project. This was done by initializing a Git repository within the '/pong/' directory. The command 'git init' was executed, which is the standard procedure for beginning version tracking in a new repository.",
        "data": {
            "event_id": "39c65491-d15e-4d75-b871-fd617168046e",
            "description": "Initialize Git Repository",
            "timestamp": "2024-01-03 23:03:12.457063",
            "detailed_description": "A Git repository was initialized in the '/pong/' directory to track changes and support collaboration for the Pong game development. The 'git init' command was used, and the presence of a '.git' folder within the directory confirms the successful initialization.",
            "data": {
                "description": "Git repository initialization",
                "commands": ["git init"],
                "directory": "/pong/",
                "purpose": "To track changes, enable version control, and facilitate collaboration."
            }
        }
    },
    {
        "id": "9e83ca8e-1c0f-4939-bbe9-fc66e360341f",
        "description": "File Structure Creation",
        "timestamp": "2024-01-03T23:05:49.383456",
        "detailed_description": "The next step in the Pong game development project was to create a basic file structure within the '/pong/' directory. This involved creating a main application file, 'main.py', and establishing separate files or directories for assets and game logic. The assets directory was named 'assets/', and the game logic file was named 'game.py'.",
        "data": {
            "directory_structure": {
                "main_application_file": "main.py",
                "assets_directory": "assets/",
                "game_logic_file": "game.py"
            },
            "purpose": "The main.py file serves as the entry point for the game. The assets/ directory is intended to store game resources like images and sounds. The game.py file is designated for the game's core logic and mechanics.",
            "verification": "To verify the creation of the file structure, one should check the '/pong/' directory for the presence of 'main.py', 'assets/' folder, and 'game.py'."
        }
    },
    {
        "id": "74eec1cc-799f-453d-ae84-6f0033d82013",
        "description": "File Structure Setup",
        "timestamp": "2024-01-03T23:13:14.228866",
        "detailed_description": "The basic file structure for the Pong game project within the '/pong/' directory has been established. This includes the creation of a main application file named 'main.py', a game logic file within a subdirectory 'game_logic/game.py', and an 'assets/' directory with subdirectories for images and sounds. Placeholder '.gitkeep' files have been added to the assets subdirectories to ensure their inclusion in the Git repository. The files have been committed to the Git repository with an initial commit message.",
        "data": {
            "file_paths": [
                "/pong/main.py",
                "/pong/game_logic/game.py",
                "/pong/assets/.gitkeep",
                "/pong/assets/images/.gitkeep",
                "/pong/assets/sounds/.gitkeep"
            ],
            "commit_message": "Initial commit with basic file structure",
            "git_status": "Files committed"
        }
    },
    {
        "id": "0cb69390-cc9d-4cca-9b1c-15aedea0857a",
        "description": "Create Initial Script",
        "timestamp": "2024-01-03T23:14:32.208512",
        "detailed_description": "An initial Python script for the Pong game, 'main.py', was created in the '/pong/' directory. This script includes the basic structure, such as import statements, initialization of the game window, and the main game loop. This setup is essential for starting the development of the game's functionality.",
        "data": {
            "file_path": "/pong/main.py",
            "contents": "Basic structure with import statements, game window initialization, and main game loop.",
            "purpose": "Serves as the entry point for the game, where game components are loaded, and the game loop is executed."
        }
    }]
    for example in data:
        element = await createElement(str(example))
        await t.addElement(element)
        i+=1
        if i==0:
            for i, layer in enumerate(t.layers):
                print(f"\n\nlayer: {i}")
                print(f"\n\nnodes:{[node.description for node in layer.nodes]}")
                print(f"\n\nlayer{i} TimeRanges: {[str(node.time_range) for node in layer.nodes]}")
            print(f"\n\nelements:{[str(element) for element in t.elements]}")
            t.displayTimeGraph()

    t.save()

os.environ['debug'] = 'True'
asyncio.run(troubleshoot())

from CLTrees.tree import loadTree
from CLTrees.treeNavigator import TreeNavigator

t = loadTree('data/2312311507.pkl')
tn = TreeNavigator(t, min_threshold=0.3)

print(asyncio.run(tn.getContext("What steps have been taken?")))
