from .element import Element, getElementById
from .node import Node
from datetime import datetime, timedelta
import json
import os
from guru.GLLM import LLM
from CLTrees.promptspy import NewNodePrompt, NewTopLayerPrompt
from CLTrees.layer import Layer
from CLTrees.timeRange import TimeRange
import pickle

#TODO: determine k based on data?
#TODO: new node creation should require a couple of steps as context?
#TODO: should keeping things in time-order be so strict? what if we give more context - and decision-making power - to the llm?
#TODO: dig deeper to find chronological significance? Ex: 'django updates, db updates, ...' is not enough to be able to come up with a more general category above. 
#Identifying what those things had in common might be an iterative vector comparison.
class Tree:

    def __init__(self, k=6, alpha = 0.7, layers = [], elements = [], task_description = ""):
        self.k = k
        self.alpha = alpha
        #layers are always such that layers[0] is the visible layer
        self.layers = layers
        self.elements = elements
        self.task_description =task_description

    async def addElement(self, element):
        if not isinstance(element,Element):
            element = Element(description = element)
        self.elements.append(element)
        if self.layers:
            current_node = self.layers[len(self.layers)-1].nodes[-1]
            fits = await current_node.checkFit(element)
            if not fits:
                await self.newNode(element)
        else:
            if len(self.elements) > self.k:
                await self.newTopLayer()

        #extend all layers to current time. up-propogate and do any necessary splits.
        for layer in reversed(self.layers):
            layer.nodes[-1].time_range.addStamp(element.timestamp)
        for layer in reversed(self.layers):
            await layer.nodes[-1].checkSize()
        if self.layers:
            if len(self.layers[0].nodes)>self.k:
                await self.newTopLayer()
        return element

    def getNode(self, nodeId) -> Node:
        for node in self.nodes:
            if node.id == nodeId:
                return node
        raise Exception(f"node {nodeId} requested, but no such node exists.")

    async def newTopLayer(self):
        print("creating new top layer.")
        if self.layers:
            substeps=[[node.description, node.time_range] for node in self.layers[0].nodes]
        else:
            substeps=[[element.description, element.timestamp] for element in self.elements]

        prompt = NewTopLayerPrompt(
            max_steps=int(self.k*self.alpha),
            task_description=self.task_description,
            substeps=json.dumps([{'step':step[0], 'timestamp': str(step[1])} for step in substeps])
        ).get()
        log, general_steps = await LLM.json_response(prompt=prompt)
        if os.environ.get('debug',''):
            print(f"general steps: {general_steps}")
            try:
                del general_steps['reasoning']
            except:
                pass
        #increase layer indexes of all nodes.
        for layer in self.layers:
            for node in layer.nodes:
                node.layer += 1
        new_layer = Layer()
        for description, substeps_subset in general_steps.items():
            new_time_range = TimeRange()
            if self.layers:
                print(f"\ndescription:{description}\nsubsteps:{substeps_subset}")
                print(f"identified steps: \n{[f'{step[0]} {step[1]}' for step in substeps if step[0] in substeps_subset]}")
                new_time_range.compose([step[1] for step in substeps if step[0] in substeps_subset])
                print(f"resulting time_range: {new_time_range}\n")
            else:
                print(f"\ndescription:{description}\nsubsteps:{substeps_subset}")
                print(f"identified steps: \n{[f'{step[0]} {step[1]}' for step in substeps if step[0] in substeps_subset]}")
                new_time_range.addStamps([step[1] for step in substeps if step[0] in substeps_subset])
                print(f"resulting time_range: {new_time_range}\n")
            new_layer.add_node(Node(description=description,parentTree=self,layer=0, time_range=new_time_range.copy()))
        self.layers = [new_layer] + self.layers

    def save(self, file_path = None):
        if not file_path:
            file_path = f'data/{self.task_description}/{datetime.now().strftime("%y%m%d%H%M")}.pkl'
            # Split the path in head and tail pair using os.path.split
            head, tail = os.path.split(file_path)

            # Create the directories if they don't exist
            if not os.path.exists(head):
                os.makedirs(head)

        with open(file_path, "wb") as f:
            f.write(pickle.dumps(self))
        print(f"saved to {file_path}")

    async def makeGraph(self):
        print('Creating graph...', flush=True)
        try:
            import networkx as nx
            import matplotlib.pyplot as plt
            from networkx.drawing.nx_pydot import graphviz_layout
        except ImportError as e:
            print(f"Unable to display graph due to import error: {e}")
            return

        G = nx.DiGraph()  # Directed graph to represent the hierarchical structure

        # Function to find parent nodes
        def find_parents(node, layer_index):
            if layer_index == 0:
                return []  # Top layer nodes have no parents
            parent_layer = self.layers[layer_index - 1]
            return [parent_node for parent_node in parent_layer.nodes if node.time_range.subset_of(parent_node.time_range)]

        # Adding nodes and edges based on layers and nodes within each layer
        for layer_index, layer in enumerate(self.layers):
            for node in layer.nodes:
                # Add the node to the graph
                G.add_node(node.id, label=node.description)

                # Add edges to parent nodes
                parents = find_parents(node, layer_index)
                for parent_node in parents:
                    G.add_edge(parent_node.id, node.id)

        # Using graphviz layout for hierarchical display
        pos = graphviz_layout(G, prog="dot")

        # Drawing nodes and labels
        nx.draw(G, pos, with_labels=False, node_size=500, node_color='lightblue')

        # Node labels
        labels = {node: G.nodes[node]["label"] for node in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels=labels)

        # Display the graph
        plt.show()


    def displayTimeGraph(self):
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from datetime import datetime, timedelta
        except Exception as e:
            print(f"unable to make time graph due to {e}")
            return

        fig, ax = plt.subplots()

        # Setting up the date formatter for x-axis
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        plt.xticks(rotation=45)

        # Calculate total layers including the element layer
        total_layers = len(self.layers) + 1
        reference_date = datetime(2023, 1, 1).timestamp()

        # Find the maximum and minimum timestamp among all elements
        max_element_time = max(element.timestamp for element in self.elements)
        min_element_time = min(element.timestamp for element in self.elements)

        # Plotting each node in each layer with descriptions
        for layer_index, layer in enumerate(self.layers):
            for i, node in enumerate(layer.nodes):
                start_time = datetime.fromtimestamp(node.time_range.minTime + reference_date)
                end_time = datetime.fromtimestamp(node.time_range.maxTime + reference_date)

                # Adjust start and end times based on neighboring nodes
                if i > 0:
                    prev_end_time = datetime.fromtimestamp(layer.nodes[i-1].time_range.maxTime + reference_date)
                    start_time = prev_end_time + (start_time - prev_end_time) / 2
                if i < len(layer.nodes) - 1:
                    next_start_time = datetime.fromtimestamp(layer.nodes[i+1].time_range.minTime + reference_date)
                    end_time = end_time + (next_start_time - end_time) / 2

                # Plot the bar
                bar = ax.barh(layer_index, end_time - start_time, left=start_time, height=0.4, align='center')

                # Adding a text label for the node's description
                middle_point = start_time + (end_time - start_time) / 2
                ax.text(middle_point, layer_index, node.description, fontsize=8, verticalalignment='center', horizontalalignment='center')

        # Plotting elements at the bottom layer
        element_layer = total_layers - 1
        for element in self.elements:
            element_time = element.timestamp
            ax.scatter(element_time, element_layer, color='r')
            
            # Adding a text label for the element's description
            ax.text(element_time, element_layer, element.description, fontsize=8, verticalalignment='bottom', rotation=90)

        # Setting labels
        ax.set_yticks(range(total_layers))
        ax.set_yticklabels(['Layer {}'.format(i) for i in range(total_layers-1)] + ['Elements'])
        ax.set_xlabel('Time')
        ax.set_title('Tree Time Graph')
        ax.set_xlim(min_element_time, max_element_time)

        plt.show()



    
    def getElementById(self, elementId):
        for element in self.elements:
            if element.id == elementId:
                return element
        raise Exception(f"element {elementId} was requested, but no such element exists.")

    async def newNode(self, element:Element):
        print(f"creating new node at bottom layer for {element}")
        prompt = NewNodePrompt(
            existing_generalized_steps=[node.description for node in self.layers[-1].nodes],
            specific_task=element.description,
            overall_goal=self.task_description
        ).get()
        log, response = await LLM.json_response(prompt = prompt)
        new_step = response['new_generalized_step']
        print(f"new node name: {new_step}")
        newNode = Node(description=new_step,parentTree=self, layer=len(self.layers)-1,time_range=TimeRange(element.timestamp, element.timestamp))
        self.layers[-1].nodes.append(newNode)

        

    def __str__(self):
        return json.dumps({
            'nodes':[str(node) for node in self.nodes],
            'elements':[str(element) for element in self.elements],
            'k':self.k,
            'alpha':self.alpha
                    })

    def removeElement(self,elementId):
        node = self.findElementInTreeById(elementId)
        if node:
            node.elementIds.remove(elementId)
        getElementById(elementId).delete()

    def getPrevElement(self, elementId):
        matches = [[i,e] for i,e in enumerate(self.elements) if e.id == elementId]
        if not matches:
            return "NO SUCH ELEMENT."
        else:
            return self.elements[matches[0][0]-1]
        
    def getNextElement(self, elementId):
        matches = [[i,e] for i,e in enumerate(self.elements) if e.id == elementId]
        if not matches:
            return "NO SUCH ELEMENT."
        else:
            return self.elements[matches[0][0]+1]
         
#TODO: add other parameters.
def loadTree(filepath):
    with open(filepath, "rb") as f:
        txt = f.read()
    return pickle.loads(txt)

