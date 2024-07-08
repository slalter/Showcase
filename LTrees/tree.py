from .element import Element
from .node import Node, loadNode
from datetime import datetime
import json
import os
from guru.GLLM import LLM
import shutil
import uuid
import io

class Tree:

    def __init__(self, id, directive = "", max_node_size=10, max_layer_width = 5, objectType = "", sortBy = "", nodes = None, timestamps = True, elements=None):
        self.max_node_size = max_node_size
        self.max_layer_width = max_layer_width
        self.nodes = nodes if nodes else []
        self.timestamps = timestamps
        self.directive = directive
        self.elements = elements if elements else []
        if objectType:
            self.description = f"{objectType}"
            if sortBy:
                self.description+=f" by {sortBy}"
        else:
            self.description = "ROOT_NODE"
        if not nodes:
            self.nodes=[Node(self.description, self, is_root=True)]
        self.id = str(id) if id else str(uuid.uuid4())

    def addElement(self, element, conversation_id=None):
        if not isinstance(element, Element):
            print("element must be an instance of Element. Making one...")
            element = Element(parent_tree=self,raw_text=element,timestamps=self.timestamps)
        self.elements.append(element)
        element.parent_tree = self
        root = [node for node in self.nodes if node.is_root][0]
        root.processElement(element, conversation_id=conversation_id)
        return element

    def getNode(self, nodeId) -> Node:
        matches = [node for node in self.nodes if node.id == nodeId]
        if matches:
            return matches[0]
        return False
    
    def removeNode(self, nodeId):
        self.nodes = [node for node in self.nodes if node.id != nodeId]
        for node in self.nodes:
            if nodeId in node.childNodeIds:
                node.childNodeIds.remove(nodeId)

    def save(self, file_path = None):
        if not file_path:
            file_path = f'data/{self.description}/{datetime.now().strftime("%y%m%d%H%M")}.txt'
        # Split the path into head and tail
        head, tail = os.path.split(file_path)

        # Create the directories if they don't exist
        if not os.path.exists(head):
            os.makedirs(head)

        # Check if the file already exists
        if os.path.exists(file_path):
            # Create a timestamp
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

            # Create the backup directory if it doesn't exist
            backup_dir = os.path.join(head, "backups")
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)

            # Move the file to the backup directory with timestamp appended
            backup_file_path = os.path.join(backup_dir, f"{timestamp}_{tail}")
            shutil.move(file_path, backup_file_path)
            print(f"Existing file moved to backup: {backup_file_path}")

        # Write to the file
        with open(file_path, "w") as f:
            f.write(json.dumps(self.getJson()))
        print(f"Saved to {file_path}")

    def makeGraph(self):
        '''
        makes a ByteIO object with a graph of the tree.
        '''
        print('making graph...',flush=True)
        try:
            import networkx as nx
            import matplotlib.pyplot as plt
            from networkx.drawing.nx_pydot import graphviz_layout
        except Exception as e:
            print(f"unable to display graph due to import error: {e}")
            return
        
        G = nx.DiGraph()  # Changed to Directed Graph
        for node in self.nodes:
            info = []
            if node.elementIds:
                info = [f"{len(node.elementIds)}"]
            G.add_node(node.id, label=node.description.replace(":", ""), descriptions=info)
        
        for node in self.nodes:
            for bnode in node.getChildNodes():
                G.add_edge(node.id, bnode.id)

        pos = graphviz_layout(G, prog="dot")

        plt.figure(figsize=(36, 24), dpi=150)
        nx.draw(G, pos, with_labels=False, node_size=400, node_color='lightgreen', arrows=True)

        label_pos = {node: (position[0], position[1] - 5) for node, position in pos.items()}  # Shift y-position lower by 20

        descriptions = {node: "\n".join(G.nodes[node]["descriptions"]) for node in G.nodes()}
        nx.draw_networkx_labels(G, pos=label_pos, labels=descriptions, font_size=3.5, verticalalignment="top", bbox=dict(facecolor='white', alpha=0.5))

        labels = {node: G.nodes[node]["label"] for node in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=4, verticalalignment='bottom', bbox=dict(facecolor='white', alpha=0.7))

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
        plt.close()
        buffer.seek(0)
        return buffer

    def findElementInTreeById(self, elementId):
        for node in self.nodes:
            for element in node.getElements():
                if element.id == elementId:
                    return node
        return False

    def getElements(self):
        return self.elements


    #TODO: add other parameters.
    def __str__(self):
        return json.dumps({'nodes':[str(node) for node in self.nodes],
                    'max_layer_width':self.max_layer_width,
                    'max_node_size':self.max_node_size,
                    'timestamps':self.timestamps,
                    'directive':self.directive})
    
    def getJson(self):
        return {'nodes':[node.getJson() for node in self.nodes],
                'elements':[element.getJson() for element in self.elements],
                    'max_layer_width':self.max_layer_width,
                    'max_node_size':self.max_node_size,
                    'timestamps':self.timestamps,
                    'directive':self.directive}
    
    def removeElement(self,elementId):
        node = self.findElementInTreeById(elementId)
        if node:
            node.elementIds.remove(elementId)
        self.elements = [element for element in self.elements if element.id != elementId]

    @classmethod
    def loadTreeFromModel(cls, model):
        from models import RAGTree
        assert isinstance(model, RAGTree)
        if model.category_nodes:
            nodes = [Node.loadNodeFromModel(node) for node in model.category_nodes]
        else:
            nodes = [Node('ROOT_NODE', is_root=True)]
        if model.element_nodes:
            elements = [Element.loadElementFromModel(element) for element in model.element_nodes if element.parent]
        else:
            elements = []
        tree = cls(
            id=model.id, 
            directive=model.directive, 
            max_node_size=model.max_node_size, 
            max_layer_width=model.max_layer_width, 
            objectType=model.object_type, 
            sortBy=model.sort_by, 
            timestamps=model.timestamps,
            nodes=nodes,
            elements=elements
            )
        #this is obviously a crappy way to do this, its just a connection with the base program which is older. Could stand to be cleaned up.
        #TODO: clean up
        if nodes:
            for node in nodes:
                node.parentTree = tree
        if elements:
            for element in elements:
                element.parent_tree=tree
        return tree
    
#TODO: add other parameters.
def loadTree(filepath):
    with open(filepath, "r") as f:
        txt = f.read()
    loaded = json.loads(txt)
    nodes = loaded['nodes']
    if not isinstance(nodes, list):
        nodes = eval(list)
    nodesJson = [node if isinstance(node, dict) else json.loads(node) for node in nodes]
    tree = Tree(max_layer_width=loaded['max_layer_width'],max_node_size=loaded['max_node_size'],timestamps=loaded['timestamps'])
    nodes = [loadNode(node, tree) for node in nodesJson] 
    tree.nodes = nodes
    return tree


