import uuid
from guru.GLLM import LLM
from .element import Element
import json
from .prompt_classes import BestFitPrompt, NewNodePrompt, ReorganizeCondensePrompt, InsertRowCondensePrompt, LlmSplitPrompt
from models import addLog, LLMLog
from packages.celery import getSession
import Levenshtein


class Node:
    def __init__(self, description, parentTree=None, childNodeIds = None, elementIds = None, id=None, is_root=False) -> None:
        
        if not id:
            self.id = str(uuid.uuid4())
        else:
            self.id = id
        self.childNodeIds = childNodeIds if childNodeIds is not None else []
        self.description = description
        if parentTree:
            self.parentTree = parentTree
            parentTree.nodes.append(self)
        self.elementIds = elementIds if elementIds else []
        self.is_root = is_root

    def getPath(self):
        if self.is_root:
            return 'ALL_OBJECTS'
        else:
            prev_node = [node for node in self.parentTree.nodes if self.id in node.childNodeIds]
            if not prev_node:
                return ''
            else:
                return f"{prev_node[0].getPath()}/{self.description}"

    def addChildNode(self, node):
        self.childNodeIds.append(node.id)


    def processElement(self, element:Element, conversation_id=None):
        print(f"processing element: {element.description} within node: {self.description}.\nhave {len(self.elementIds)} elements on node.")
        if not self.childNodeIds:
            print("saving to node.")
            if len(self.elementIds) < self.parentTree.max_node_size:
                self.elementIds.append(element.id)
                if conversation_id:
                    addLog(conversation_id, f"Added {element.description} to {self.description}. Elements on node: {len(self.elementIds)}.")
            else:
                print("splitting node.")
                if conversation_id:
                    addLog(conversation_id, f"Splitting {self.description}.")
                self.split(conversation_id) 
                self.processElement(element, conversation_id)

        else:
            print("forwarding.")
            self.forward(element, conversation_id=conversation_id)
                          

    def forward(self, element, mode = 'llm', conversation_id=None):
        '''
        this method is used to pass an element on to the appropriate child node for sorting.
        '''
        if mode == 'llm':
            self.llmForward(element, conversation_id)
        elif mode == 'semantic':
            self.semanticForward(element, conversation_id)
        else:
            raise NotImplementedError(f"forward mode {mode} not implemented.")

    def llmForward(self, element, conversation_id=None, model='gpt-3.5-turbo', mode='OPEN_AI'):
        if self.childNodeIds:
            prompt = BestFitPrompt(
                categories = [{node.id:node.description} for node in self.getChildNodes()],
                input = element.description,
                directive = self.parentTree.directive,
                category_path = self.getPath()
            )
            log, result = prompt.execute(model=model, mode=mode)
            if conversation_id:
                LLMLog.fromGuruLogObject(log, conversation_id)
            if result.get('categoryId', None):
                if result['categoryId'] not in [node.id for node in self.parentTree.nodes]:
                    matches = [node for node in self.parentTree.nodes if node.id == result['categoryId']]
                    if not matches:
                        #check to see if there is one that is one or two characters off to handle typos.
                        fuzzy_matches = [node for node in self.parentTree.nodes if Levenshtein.distance(node.id, result['categoryId']) <= 2]                        
                        if len(fuzzy_matches) == 1:
                            fuzzy_matches[0].processElement(element, conversation_id)
                        else:
                            if model=='gpt-4o':
                                raise Exception(f"unable to find category {result['categoryId']} in {[n.description for n in self.parentTree.nodes]}.")
                            self.llmForward(element, conversation_id=conversation_id, model='gpt-4o', mode='AZURE')
                            return
                    
                    else:
                        matches[0].processElement(element, conversation_id)
                       
                else:
                    node = [node for node in self.parentTree.nodes if node.id == result['categoryId']][0]
                    node.processElement(element, conversation_id)
            else:
                self.newNode(element, result['proposed_new_category'], conversation_id)

    #ANTEQUATED: this method no longer works (nodes and elements do not have embeddings on them directly anymore!)
    #TODO: build this with the new system.
    def semanticForward(self, element):
        bestNode = None
        high_score = 0
        for nodeId in self.childNodeIds:
            node = self.getNode(nodeId)
            score = LLM.compare(node.embedding, element.embedding)
            if score > high_score:
                bestNode = node
        bestNode.processElement(element)

    #TODO:
    def hybridForward(self, element):
        raise NotImplementedError("hybridForward not implemented.")
        
    def split(self, conversation_id=None):
        #debated a semantic split (see cluster split), decided this needs to be LLM driven. Here's why:
        #the categories need to be disjoint. Simple enough. 
        categories = self.llmSplit(conversation_id=conversation_id)
        print(f"split: {self.description} into {categories}")
        if conversation_id:
            addLog(conversation_id, f"Split {self.description} into {categories}.")
        for category, elements in categories.items():
            print(f"adding child.")
            if not isinstance(elements, list):
                try:
                    elements = eval(elements)
                except Exception as e:
                    print(f"unable to eval elements {elements}. {e}")
                    if conversation_id:
                        addLog(conversation_id, f"unable to eval elements {elements}. assuming [] will fix... {e}")
                    elements = [elements]
            node = Node(category, self.parentTree)
            node.elementIds = elements
            for element in elements:
                self.elementIds.remove(element)
            self.addChildNode(node)
        self.trim()
        if self.elementIds:
            #reprocess remaining elements in the node starting at our location. Occurs when the number of elements on the node was too high to directly put in the prompt.
            for element_id in self.elementIds:
                element = [element for element in self.parentTree.elements if element.id ==element_id][0]
                self.processElement(element, conversation_id)
                self.elementIds.remove(element_id)
        if conversation_id:
            addLog(conversation_id, "split complete.", self.parentTree.getJson())
        


    def clusterSplit(self):
        #compare all vectors to 0. sort them. identify the 3 largest deltas between adjacent scores. Ask llm to summarize groups this way, split. LLM verification?
        return None
    
    def llmSplit(self, conversation_id=None, retries = 0, max_retries = 1):
        '''
        retuns a list of new categories.
        '''
        if len(self.elementIds) <15:
            elements = [f"{element.id}:\n{element.description}\n\n" for element in self.parentTree.elements if element.id in self.elementIds]
            prompt = LlmSplitPrompt(
                category_path = self.getPath(),
                elements = elements,
                directive = self.parentTree.directive
            )
            log, response = prompt.execute()
            if conversation_id:
                LLMLog.fromGuruLogObject(log, conversation_id)
                
            #verify that each element is in one of the response keys.
            for element in elements:
                found = False
                subcategories = response['subcategories']
                for key, value in subcategories.items():
                    if element.split(':')[0] in value:
                        found = True
                if not found:
                    if retries < max_retries:
                        retries += 1
                        return self.llmSplit(conversation_id, retries = retries)
                    else:
                        raise Exception(f"element {element} not found in response keys. {response}")
            return response['subcategories']
        else:
            #get the most dissimilar pairs. Use them to encourage the new groups.
            all_elements = [element for element in self.parentTree.elements if element.id in self.elementIds]
            tuples = LLM.find_top_k_pairs([element.embedding for element in self.parentTree.elements if element.id in self.elementIds], k=15, descending=False)
            example_elements = []
            for i, j, score in tuples:
                example_elements.append(all_elements[i])
                example_elements.append(all_elements[j])
            example_elements = list(set(example_elements))[:15]
            element_string = [f"{element.id}:\n{element.description}\n\n" for element in example_elements]
            prompt = LlmSplitPrompt(
                category_path = self.getPath(),
                elements = element_string,
                directive = self.parentTree.directive
            )
            log, response = prompt.execute()
            if conversation_id:
                LLMLog.fromGuruLogObject(log, conversation_id)
            return response['subcategories']

    
    #TODO: is this better if it gives a couple semantically similar options?
    def getExamples(self):
        '''
        returns a list of the max_layer_width -1 most semantically dissimilar examples
        '''
        elements = [element for element in self.parentTree.elements if element.id in self.elementIds]
        

        #TODO: matrix multiply to get the cosine similarity of a list of embeddings and return the matrix
        #rework this as 'get most dissimilar' with an input of a list of embeddings and the num dissimilar to return.
        #currently this really just compares everything to 1, and then we sort and return every skip'th one.
        scores = LLM.compareList([element.embedding for element in elements])
        pairs = list(zip(scores, elements))
        sortedPairs = sorted(pairs, key=lambda x:x[0])
        return [element.description for element in [sortedPairs[n][1] for n in range(0,len(sortedPairs)-1,max(int(len(sortedPairs)/self.parentTree.max_layer_width),1))]]
    
    def getChildNodes(self):
        return [node for node in self.parentTree.nodes if node.id in self.childNodeIds]
    
    def newNode(self, element:Element, proposed_new_category, conversation_id):
        print(f"creating new node for {str(element)}:")
        '''prompt = NewNodePrompt(
            categories = {node.id:node.description for node in self.getChildNodes()},
            input = element.description,
            directive = self.parentTree.directive,
            category_path = self.getPath()
        )
        log, response = prompt.execute()
        if conversation_id:
            LLMLog.fromGuruLogObject(log, conversation_id)
        newCat = response['newCategory']'''
        newCat = proposed_new_category
        print(f"new node name: {newCat}")
        if conversation_id:
            addLog(conversation_id, f"Created new category {newCat}.")
        newNode = Node(newCat, self.parentTree)
        newNode.elementIds.append(element.id)
        self.childNodeIds.append(newNode.id)
        if len(self.childNodeIds) > self.parentTree.max_layer_width:
            print(f"too many childNodes for {self.description}: {len(self.childNodeIds)} vs {self.parentTree.max_layer_width}. condensing...")
            self.condense(conversation_id)

    def trim(self):
        print("trimming...")
        for node in self.getChildNodes():
            if not (node.childNodeIds or node.elementIds):
                print(f"removing {node.description}.")
                node.delete()

    def condense(self, conversation_id, mode = 'insert_row'):
        if mode == 'reorganize':
            self.reorganizeCondense(conversation_id)
        elif mode == 'insert_row':
            self.insertRowCondense(conversation_id)
                
    def insertRowCondense(self, conversation_id = None, min_new_cats = None, max_new_cats = None):
        '''
        condense by inserting a row of nodes between this node and its children, 
        and processing the element.
        '''
        if not min_new_cats:
            #round up max_layer_width/5
            min_new_cats = max(self.parentTree.max_layer_width//2, 2)
        if not max_new_cats:
            max_new_cats = max(self.parentTree.max_layer_width//1.2, 3, min_new_cats+1)
        print("condensing...")
        prompt = InsertRowCondensePrompt(
            categories = {node.id:node.description for  node in self.getChildNodes()},
            directive = self.parentTree.directive,
            category_path = self.getPath(),
            min_new_cats = min_new_cats,
            max_new_cats = max_new_cats
        )
        log, response = prompt.execute()
        if conversation_id:
            LLMLog.fromGuruLogObject(log,conversation_id)
        #verify response
        if len(response) < min_new_cats or len(response) > max_new_cats:
            #retry once
            prompt = InsertRowCondensePrompt(
                categories = {node.id:node.description for  node in self.getChildNodes()},
                directive = self.parentTree.directive,
                category_path = self.getPath(),
                min_new_cats = min_new_cats,
                max_new_cats = max_new_cats
            )
            log, response = prompt.execute()
            if conversation_id:
                LLMLog.fromGuruLogObject(log,conversation_id)
            if len(list(response.items())) > max_new_cats:
                #if it still doesn't work, raise exception.
                raise Exception(f"unable to condense. {response}")
        

        self.childNodeIds = []
        for category, children in response.items():
            newNode = Node(category, self.parentTree, childNodeIds=children)
            self.childNodeIds.append(newNode.id)





    def reorganizeCondense(self, conversation_id = None):
        '''
        combine existing categories into broader categories. Resort. (antequated, not recommended.)
        '''
        print("condensing...")
        prompt = ReorganizeCondensePrompt(
            categories = {node.id:node.description for  node in self.getChildNodes()},
            directive = self.parentTree.directive,
            category_path = self.getPath()
        )
        log, response = prompt.execute()
        if conversation_id:
            LLMLog.fromGuruLogObject(log,conversation_id)
        print(f"condensed {str([node.id for node in self.getChildNodes()])} into{response.keys()}")
        for key, value in response.items():
            elementsToProcess = []
            newNode = Node(key,self.parentTree)
            self.childNodeIds.append(newNode.id)
            for existingNodeId in value:
                try:
                    existingNode = [node for node in self.parentTree.nodes if node.id == existingNodeId][0]
                except Exception as e:
                    print(f"unable to get existingNode. Maybe it was already deleted? May have been a duplicated output. {e}")
                    if conversation_id:
                        addLog(conversation_id, f"unable to get existingNode. Maybe it was already deleted? May have been a duplicated output. {e}")
                    continue
                for node in existingNode.getChildNodes():
                    newNode.childNodeIds.append(node.id)
                for element in existingNode.getElements():
                    elementsToProcess.append(element.id)
                existingNode.delete()
            if len(newNode.childNodeIds) > self.parentTree.max_layer_width:
                newNode.condense(conversation_id, mode = 'reorganize')
            for id in elementsToProcess:
                element = [element for element in self.parentTree.elements if element.id == id][0]
                self.processElement(element, conversation_id) #note: if we separate splitting from processElement, we can parallelize these.
          
    def delete(self):
        self.parentTree.removeNode(self.id)
    
    def getJson(self):
        return {"id": str(self.id),
                "description": str(self.description),
                "childNodes": self.childNodeIds,
                "elements": str([element.getJson() for element in self.getElements()]),
                "is_root": self.is_root,
        
                }
    
    def getElements(self):
        return [element for element in self.parentTree.elements if element.id in self.elementIds]

    def __str__(self):
        return json.dumps({"id": self.id,
                "description": self.description,
                "childNodes": str([node.id for node in self.getChildNodes()]),
                "elements": str([element.getJson() for element in self.getElements()])
                })
    
    @classmethod
    def loadNodeFromModel(cls, nodeModel):
        from models import CategoryNode
        assert isinstance(nodeModel, CategoryNode)

        node = cls(
            description=nodeModel.description, 
            childNodeIds=[str(id) for id in nodeModel.children if nodeModel.children], 
            elementIds=nodeModel.getAllDirectChildElementIds(), 
            id=nodeModel.id,
            is_root=nodeModel.is_root if hasattr(nodeModel, 'is_root') else False
            )
        return node
        
def loadNode(nodeJson, tree):
    elementDictList = eval(nodeJson['elements'])
    elementDictList = [element for element in elementDictList]
    if len(elementDictList)>0:
        elements = [Element(
            parent_tree=tree,
            description=elementDict['description'], 
            id=elementDict['id'], 
            raw_text=elementDict['raw_text'],
            embedding=elementDict['embedding'] if isinstance(elementDict['embedding'], list) else eval(elementDict['embedding'])) for elementDict in elementDictList]
    else:
        elements = []
    return Node(nodeJson['description'],parentTree=tree, childNodeIds=eval(nodeJson['childNodes']), elementIds=[element.id for element in elements], id=nodeJson['id'], embedding=nodeJson['embedding'] if isinstance(nodeJson['embedding'], list) else eval(nodeJson['embedding']))
    