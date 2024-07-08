from CLTrees.element import Element
from CLTrees.layer import Layer

class TimeChain:
    def __init__(self, starting_layer, tree):
        self.tree = tree
        if isinstance(starting_layer, Layer):
            self.links = [ChainLink(node, tree) for node in starting_layer.nodes]
        elif isinstance(starting_layer[0], Element):
            self.links = starting_layer

    def get(self):
        out = []
        for link in self.links:
            if isinstance(link, ChainLink):
                out.append(link.get())
            else:
                assert isinstance(link, Element)
                out.append(f"this node contains an event, and cannot be expanded. Here are the details of the event: {str(link)}")
        return out
    
    def __str__(self):
        out = []
        for link in self.links:
            if isinstance(link, ChainLink):
                out.append(link.get())
            else:
                out.append(f"this node contains an event, and cannot be expanded. Here are the details of the event: {link.description} {link.data}")
        return str(out)
    
    def processLabels(self, label_list):
        '''
        returns True if complete, False OW.
        '''
        
        new_links = []
        for link, label in zip(self.links, label_list):
            if label == 'remove':
                pass
            elif label == 'maintain':
                new_links.append(link)
            elif label == 'expand':
                if isinstance(link, Element):
                    raise Exception("ERROR. THIS IS AN ELEMENT, NOT A NODE.")
                new_links += link.subdivide()
        self.links = new_links
        print(f"\n\nlinks:{[str(link) for link in self.links]}\n\n")
        if all(item in ['maintain','remove'] for item in label_list):
            return True
        return False
        



class ChainLink:
    def __init__(self, node, tree):
        self.tree = tree
        self.time_range=node.time_range
        self.node = node
        self.layer = node.layer
    
    def subdivide(self):
        if self.layer == len(self.tree.layers)-1:
            return [element for element in self.tree.elements if self.time_range.contains(element.timestamp)]
        return [ChainLink(node, self.tree) for node in self.tree.layers[self.layer+1].nodes]
    
    def get(self):
        return f"{self.node.description}"
    
    def __str__(self) -> str:
        return self.get()