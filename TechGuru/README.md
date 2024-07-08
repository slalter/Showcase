This project is my most recent, and is a culmination of the things I've learned/developed. It is a work in progress.

This app is the groundwork for automatic pyright and test cases, and ultimately for fully automated coding. Its largely complete but still needs work and some dspy work to increase effectiveness.


Automatic pyright and test cases:

existing codebase -> models w/ dependency digraph
run code, trace and gather sample inputs and outputs to all methods.
run pyright on sink nodes (Ns), build test cases for sink nodes
Calculate G \ Ns. repeat on G \Ns.

Along the way, the LLM can reach out to the user for clarification.


Automatic code generation:

flask/psql/sqlalchemy app by default
main llm writes the main.py file on an abstracted level (routes with un-implemented functions)
main llm requests objects 
requested objects request objects... repeat until no additional levels of abstraction are needed, at which point stop
use those models to build the dependency digraph
Repeat as in other algorithm, except with the addition of llms building the sink nodes and testing them.

ObjectRequests require strongly-typed input and outputs.


The key code is in features/appBuilder.