from .tree import Tree
from .element import Element
from guru.GLLM import LLM
import json
from .prompt_classes import ProcessContextPrompt
from packages.db.pinecone import index
from packages.celery import getSession
from models import RAGTree, CategoryNode, RAGDocument, ElementNode, ElementNodeVector
from itertools import combinations
from packages.devalert import quicklog, alert
import os
from datetime import datetime
from sqlalchemy.orm import noload
import numpy as np
from packages.utils.debug import time_each_line
from packages.utils.debug import TimeLogger
from concurrent.futures import ThreadPoolExecutor
tl = TimeLogger()

#only nodes care about alpha and cmax.
#additionally, a number of these are no longer active/relevant in the implementation for simplicity's sake.
#we are not using the 'balanced' search, just specific and categorical. Realistically they should have separate methods, not just different parameters, and we should consider what metadata is relevant in each case. AKA de-abstract this just a little.
DEFAULT_PARAMS = {
    'alpha': 1,
    'tmax': 8000,
    'cmax': 2000,
    'place_multiplier': 2,
    'element_usecase_weight': 1,
    'node_description_weight': 1,
    'element_chunk_weight': 2,
    'node_indirect_multiplier': 0.7,
    'element_indirect_multiplier': 0.25,
    'category_falloff': 0,
    'element_description_weight': 1.5
}


class TreeNavigator:
    def __init__(self, tree:Tree, rag_tree_id, branch_threshold = 0.7, reduce_to = 5) -> None:
        '''
        branch_threshold: the fraction of the fraction of 1 which triggers further investigation.
        '''
        self.tree = tree
        self.currentNodes = [node for node in tree.nodes if node.is_root]
        self.path = []
        self.nextNodes = []
        self.branchThreshold = branch_threshold
        self.reduce_to = reduce_to
        self.context = None
        self.result = []
        self.rag_tree_id = rag_tree_id

    def getNextNodes(self):
        #TODO: use the path variable in the model to get the next nodes, or cache them on the nodes.
        self.nextNodes = []
        for node in self.currentNodes:
            for childNode in node.getChildNodes():
                self.nextNodes.append(childNode)
        return self.nextNodes
    
    #not currently using
    def processWeights(self, weights):
        '''
        layer by layer.
        weights are on [0,1] for each node in childNodes.
        branches if branch_threshold is exceeded by 2 or more options.
        '''
        while not isinstance(weights, list):
            weights = eval(weights)
        weights = [float(w) for w in weights]
        zipped = zip(self.nextNodes, weights)
        self.currentNodes = [node for node in self.currentNodes if not node.childNodeIds]
        for node, weight in zipped:
            if weight > self.branchThreshold/len(self.nextNodes):
                self.currentNodes.append(node)

        print(f"{[node.description for node in self.currentNodes]}")
        if len(self.currentNodes)<1:
            print(f"WARNING: NO OPTIONS WERE OVER THRESHOLD. TAKING NO ACTION.")
            return "complete"
        
        elements = self.getElementList()
        self.getNextNodes()
        if len(elements) <= self.reduce_to or not self.nextNodes:
            self.result = [str(ele.description) for ele in elements]
            return 'complete'

    def getElementList(self, nodes = None):
        if not nodes:
            nodes = self.currentNodes
        elements = []
        for node in nodes:
            if node.childNodeIds:
                elements += self.getElementList([self.tree.getNode(id) for id in node.childNodeIds if self.tree.getNode(id)])
            else:
                elements += [element for element in self.tree.elements if element.id in node.elementIds]
        return elements

    
    def processContext(self, 
                       directive_context, 
                       related_to_context, 
                       task, 
                       embeddings = None, 
                       mode = 'semantic', 
                       params=None, 
                       save=False, 
                       ids = None
                       ):
        '''
        LLM mode:
        takes context and does its own LLM call to create and process weights.
        Does not make any changes if unclear from context.

        semantic mode:
        example: 
        tree directive: 'Document Type'
        request:
        'Looking for {directive_context} related to {related_to}'
        task description: {task}

        '''
        
        from packages.tasks import verify_pinecone_object, process_nodes_to_remove
        if ids:
            self.currentNodes = [node for node in self.tree.nodes if node.id in ids]
            Session = getSession()
            with Session() as session:
                all_matching_nodes = session.query(CategoryNode).filter(CategoryNode.id.in_(ids)).all()
                all_acceptable_base_paths = [node.path_from_root for node in all_matching_nodes]
        if mode == 'LLM':#TODO: implement? or discard.
            response = ""
            while not '[]' in response:
                if response:
                    print("processing...")
                    if self.processWeights(response)=='complete':
                        break

                prompt = ProcessContextPrompt(
                    information=directive_context + related_to_context,
                    categories=self.getOptions()
                )
                response = prompt.execute()

        elif mode == 'semantic':
            if not embeddings:
                #get all combinations of embeddings for easy testing and AB testing.
                embeddings = getEmbeddings({'directive_context':str(directive_context), 
                                            'related_to_context':str(related_to_context), 
                                            'task':str(task)})

            if not params:
                params = DEFAULT_PARAMS

            next_nodes = self.getNextNodes()
            
            
            Session = getSession()
            with Session() as session:
                rag_tree = session.query(RAGTree).options(noload(RAGTree.category_nodes)).options(noload(RAGTree.element_nodes)).filter(RAGTree.id==self.rag_tree_id).first()

                if save:
                    rag_tree.params = params
                    session.commit()

                #get the top k chunks so that we can use the scores in composite scoring...
                
                elements = self.getElementList()
                element_count = len(elements)
                element_ids = [element.id for element in elements]
                if ids:
                    elements = [element for element in elements if any(element.metadata.get('path_to_parent','').startswith(x) for x in all_acceptable_base_paths) or element.id in ids]
                    element_ids = [element.id for element in elements]

                    
                    
                    top_k_chunks = rag_tree.getTopKChunks(
                                    embeddings[('related_to_context',)],
                                    element_ids = element_ids, 
                                    k=80
                                    )
                else:
                    top_k_chunks = rag_tree.getTopKChunks(
                                    embeddings[('related_to_context',)],
                                    k=80
                                    )
                #TODO: if there are less than 4 elements: get more, and notify us (do they have more documents?)

                #consider: what if one element has more embeddings? should we normalize?
                #get the scores for each element in the extension of the state
                element_chunk_scores = {}
                try:
                    for match in top_k_chunks:
                        id = next((id for id in element_ids if match['metadata']['element_id']==id), None)
                        if not id:
                            if not element_ids:
                                pass
                            else:
                                alert(f"WARNING: element_id {match['metadata']['element_id']} not found in element_ids {element_ids}.", 'exception')
                                alert(f"element_ids is NOT empty, so there is probably a pinecone issue. queueing verify_pinecone.", 'exception')
                                verify_pinecone_object.delay(match['metadata']['element_id'],match['id'], 'ElementNode', namespace='document_chunks')
                            continue
                        if not element_chunk_scores.get(id,None):
                            element_chunk_scores[id] = match['score']
                        else:
                            if match['score']>element_chunk_scores[id]:
                                element_chunk_scores[id] = match['score']
                    if len(element_chunk_scores)<4:
                        print("WARNING: less than 4 elements were scored. Consider bigger querysize or more subdivision.")
                    print('\n\n ELEMENT CHUNK SCORES')
                    print(element_chunk_scores)
                except Exception as e:
                    print(f"Error in element_chunk_scores: {e}")
                    print(f"id: {match['metadata']['element_id']}")
                    print(f"element_ids: {element_ids}")
                    print(f"top_k_chunks: {top_k_chunks}")
                    print(f"next_nodes: {next_nodes}")
                    print(f"currentNodes: {self.currentNodes}")
                    raise


                
                element_description_scores = {}
                if embeddings.get(('related_to_context',), None):
                    top_k_element_description_chunks = ElementNode.getTopKDescriptionMatches(
                        embeddings[('related_to_context',)], 
                        element_ids, k=40)
                    for match in top_k_element_description_chunks:
                        id = next((id for id in element_ids if id==match['metadata']['element_id']), None)
                        if not id:
                            alert(f"WARNING: element_id {match['metadata']['element_id']} not found in element_ids {element_ids}.", 'exception')
                            if not element_ids:
                                alert(f"element_ids is empty.", 'exception')
                            else:
                                alert(f"element_ids is NOT empty, so there is probably a pinecone issue. queueing verify_pinecone.", 'exception')
                                verify_pinecone_object.delay(match['metadata']['element_id'],match['id'],'ElementNode', namespace='element_nodes')
                        if not element_description_scores.get(id,None):
                            element_description_scores[id] = 0
                        element_description_scores[id] += match['score']
                print("\n\nELEMENT DESCRIPTION SCORES")
                print(element_description_scores)

                #TODO: consider: what if there are more usecases on one node than another?
                #use the useful for embeddings to get the top 40 usecase matches for documents referenced in the extension of the state.
                #TODO: move usecases to the elements.
                #TODO: utilize cases where the elementnode is not 1-1 with the RAG document!
                
                query_result = session.query(ElementNode).with_entities(ElementNode.rag_document_id,ElementNode.id,ElementNode.parent).filter(ElementNode.id.in_(element_ids)).all()
                
                rag_document_ids = [result[0] for result in query_result]
                matched_element_ids = [result[1] for result in query_result]
                if embeddings.get(('task',), None):
                    top_40_document_usecase_chunks = RAGDocument.getTopKUsecaseMatches(embeddings[('task',)], 
                        rag_document_ids=rag_document_ids,
                        tenant_id=rag_tree.tenant_id, 
                        k=40)        
                    
                            
                    #compile the scores by element
                    element_usecase_scores = {}
                    for match in top_40_document_usecase_chunks:
                        index_of_element = next((i for i in range(0,len(rag_document_ids)) if str(rag_document_ids[i])==match['metadata']['rag_document_id']),None)
                        if not index_of_element:
                            #alert(f"WARNING: rag_document_id {match['metadata']['rag_document_id']} not found in rag_document_ids {rag_document_ids}.", 'exception')
                            if not rag_document_ids:
                                pass
                                #alert(f"rag_document_ids is empty.", 'exception')
                            else:
                                pass
                                #alert(f"rag_document_ids is NOT empty, so there is probably a pinecone issue. queueing verify_pinecone.", 'exception')
                                #verify_pinecone_object.delay(match['metadata']['rag_document_id'],match['id'],'RAGDocument', namespace='document_use_cases')
                            continue
                        id = matched_element_ids[index_of_element]
                        if not element_usecase_scores.get(id,None):
                            element_usecase_scores[id] = match['score']
                        else:
                            if match['score']>element_usecase_scores[id]:
                                element_usecase_scores[id] = match['score']


                
                
                print("\n\nELEMENT USECASE SCORES")
                print(element_usecase_scores)
               

                #get the best matching nodes based on description
                node_description_scores = {}
                if embeddings.get(('directive_context',), None):
                    extended_node_models = session.query(CategoryNode).filter(CategoryNode.id.in_([node.id for node in self.currentNodes])).all()
                    if not isinstance(extended_node_models, list):
                        extended_node_models = [extended_node_models]
                    next_node_models = session.query(CategoryNode).filter(CategoryNode.id.in_([node.id for node in next_nodes])).all()
                    for node_model in next_node_models:
                        additional = session.query(CategoryNode).filter(CategoryNode.path_from_root.like(f'%{node_model.path_from_root}%')).filter(CategoryNode.parent_tree==rag_tree.id).all()
                        if not isinstance(additional, list):
                            additional = [additional]
                        extended_node_models += additional
                        
                    extended_node_ids = [node.id for node in extended_node_models]
                    if extended_node_ids:
                        top_40_category_description_chunks = CategoryNode.getTopKDescriptionMatches(
                            embeddings[('directive_context',)], 
                            node_ids = extended_node_ids, 
                            k=40)
                        for match in top_40_category_description_chunks:
                            id = next((id for id in extended_node_ids if id==match['metadata']['node_id']), None)
                            if not id:
                                alert(f"WARNING: node_id {match['metadata']['node_id']} not found in extended_node_ids {extended_node_ids}.", 'exception')
                                if not extended_node_ids:
                                    alert(f"extended_node_ids is empty.", 'exception')
                                else:
                                    alert(f"extended_node_ids is NOT empty, so there is probably a pinecone issue. queueing verify_pinecone.", 'exception')
                                    verify_pinecone_object.delay(match['metadata']['node_id'],match['id'],'CategoryNode', namespace='category_nodes')
                            if not node_description_scores.get(id,None):
                                node_description_scores[id] = 0
                            node_description_scores[id] += match['score']
                    else:
                        node_description_scores = {}
                        top_40_category_description_chunks = []
                print("\n\nNODE DESCRIPTION SCORES")
                print(node_description_scores)
                
               
                scoring_class = ScoringClass(
                    node_description_scores=node_description_scores,
                    element_chunk_scores=element_chunk_scores,
                    element_description_scores=element_description_scores,
                    element_usecase_scores=element_usecase_scores,
                    top_40_document_usecase_chunks=top_40_document_usecase_chunks,
                    top_40_category_description_chunks=top_40_category_description_chunks,
                    top_k_chunks=top_k_chunks,
                    tree_id=self.rag_tree_id,
                    **params

                )

                state_tracker = StateTracker(scoring_class)

                state_tracker.refine('dynamic_alpha' )

                text, total_length = state_tracker.getText()
                #quicklog(f"total number of active nodes: {len(state_tracker.active_nodes)}. Total number of active elements: {len(state_tracker.active_elements)}. Total length of text: {total_length}.")
                
                if scoring_class.nodes_to_remove:
                    print(f"queuing {len(scoring_class.nodes_to_remove)} nodes to remove from pinecone...")
                    process_nodes_to_remove.delay(self.rag_tree_id, list(scoring_class.nodes_to_remove))
                    
                return text


                #calculate alpha

                #idea: an optimization algorithm (decision tree) that converges upon the best text arrangement based on:
                #max_text_size
                #token_cost_multiplier
                #
                #Each node or element candidate has a score. That score is added to the score of the arrangement if it is included:
                #directly: 100% of the score
                #indirectly: as a fraction of the score based on the number of objects summarized by the indirect reference? or just flat? or depends on tree depth?
                #NOTE: the ratio of direct to indirect reference values is directly correlated with the tradeoff of specificity and broadness.
                #TODO: approximate the relative value of scores WITHIN each scoring method. EX: is .9 twice as useful as .45? Or should it be logarithmic? Or better yet, should it be sorted and then have a predefined stepwise function that is independent of the values?
                #TODO: ultimately, this should be learned. For now, it should be tweakable.
                #TODO: Normalize scores cross-scoring method. Provide tweakable weights relative to 1.0 for each scoring method.
                #TODO: also should ultimately be learned.
                #NOTE: currently the default values are just trial-and-error, and only optimized for specific search.
 




    def getOptions(self, metadata=False):
        if not self.nextNodes:
            self.getNextNodes()
            if not self.nextNodes:
                return f"Here are the final nodes: {self.currentNodes}\n And here are the elements on the nodes: {[element.description for element in self.getElementList()] if not metadata else [str(element) for element in self.getElementList()]}"    
        return f"{[node.description for node in self.nextNodes]}"
        
    def reset(self):
        self.currentNodes = [node for node in self.tree.nodes if node.is_root]
        self.getNextNodes()
        self.result = []


def getEmbeddings(input_dict):
    '''
    Embeds all combinations of the input_dict keys. Each combination's keys are joined by spaces to form
    a string which is then passed to an embedding function.
    Keys in the result dictionary are tuples of the original dictionary keys.
    '''
    to_embed = []
    #remove any keys with empty values
    input_dict = {key: value for key, value in input_dict.items() if value}

    # Prepare dictionary of combinations
    keys = list(input_dict.keys())
    for i in range(1, len(keys) + 1):
        for combo in combinations(keys, i):
            # Creating a key for the dictionary as a tuple of combo keys
            combo_key = tuple(combo)
            # Joining the values associated with the keys in combo to create the string to embed
            combo_string = ' '.join(input_dict[key] for key in combo)
            to_embed.append((combo_key, combo_string))


    with ThreadPoolExecutor() as executor:
        results = list(executor.map(LLM.getEmbedding, [combo_string for combo_key, combo_string in to_embed]))
    out = dict(zip([combo_key for combo_key, combo_string in to_embed], results))

    # Returning a dictionary mapping tuples of keys to their embeddings
    return out


    
#TODO: why did it change the summaries that were shown when I removed the place multiplier?
#TODO: representatives of unique categories are more heavily weighted, examples in each category should be different as possible.
class ScoringClass:
    def __init__(self, 
                 node_description_scores, 
                 element_chunk_scores, 
                 element_usecase_scores, 
                 element_description_scores,
                 top_40_document_usecase_chunks,
                 top_40_category_description_chunks,
                 top_k_chunks,
                 tree_id,
                 **kwargs):
        
        self.node_description_scores_s = sorted(node_description_scores.items(), key=lambda x: x[1], reverse=True)
        self.element_chunk_scores_s = sorted(element_chunk_scores.items(), key=lambda x: x[1], reverse=True)
        self.element_usecase_scores_s = sorted(element_usecase_scores.items(), key=lambda x: x[1], reverse=True)
        self.element_description_scores = element_description_scores
        self.node_description_scores = node_description_scores
        self.element_chunk_scores = element_chunk_scores
        self.element_usecase_scores = element_usecase_scores
        self.nodes_to_remove = set()

        self.top_40_document_usecase_chunks = sorted(top_40_document_usecase_chunks, key=lambda x: x['score'], reverse=True)
        self.top_40_category_description_chunks = sorted(top_40_category_description_chunks, key=lambda x: x['score'], reverse=True)
        self.top_k_chunks = top_k_chunks

        self.tree_id = tree_id

        self.honorable_mentions = []


        Session = getSession()
        with Session() as session:
            self.candidate_nodes = [node for node in session.query(CategoryNode).filter(CategoryNode.parent_tree==self.tree_id).all()]
            self.candidate_node_ids = [node.id for node in self.candidate_nodes]
            self.candidate_elements = [element for element in session.query(ElementNode).filter(ElementNode.tree_id==self.tree_id).all()]
            self.candidate_element_ids = [element.id for element in self.candidate_elements]
            self.element_node_dict = {element.id:element.parent for element in self.candidate_elements}

        for key, value in DEFAULT_PARAMS.items():
            setattr(self, key, float(value))
        for key, value in kwargs.items():
            setattr(self, key, float(value))

      
        self.stored_scores = {}



    def score(self, active_nodes, active_elements, alpha):
        cost = 0
        value = 0        

        for node_id in active_nodes:
            temp_score, temp_text = self.scoreNode(node_id, active_elements, active_nodes)
            cost += alpha*len(temp_text)
            value += temp_score
            if not self.stored_scores.get(node_id, None):
                self.stored_scores[node_id] = {}
            self.stored_scores[node_id]['pre-alpha'] = temp_score

        return value-cost

    #NOTE: always score elements first, because their scores are used in scoring nodes when referenced indirectly.
    def scoreElement(self, element_id, omit_num=0):
        if self.stored_scores.get(element_id, None) and self.stored_scores[element_id].get(omit_num, None):
            return self.stored_scores[element_id][omit_num]['pre-alpha'], self.stored_scores[element_id][omit_num]['text']
        else:
            if not self.stored_scores.get(element_id, None):
                self.stored_scores[element_id] = {}
            if not self.stored_scores[element_id].get(omit_num, None):
                self.stored_scores[element_id][omit_num] = {}

        #TODO: base text (element description?)

        matches = [match for match in self.top_k_chunks if match['metadata']['element_id']==element_id]
        if not matches:
            self.stored_scores[element_id][omit_num]['text'] = ''
        
        sorted_matches = sorted(matches, key=lambda x: x['score'], reverse=True)
        if len(sorted_matches)<omit_num:
            raise Exception(f"Omit number {omit_num} is greater than the number of matches for element {element_id}.")
        matches = sorted_matches[:-omit_num] if omit_num>0 else sorted_matches
        #todo: cache these descriptions or put them in metadata.
        Session = getSession()
        with Session() as session:
            element = session.query(ElementNode).filter(ElementNode.id==element_id).first()
            description = element.description

        score = 0
        
        #TODO: cleanup. per-element text is now handled separately via tmax.
        
        if matches:
            #TODO: do we still want to care about top 5?
            #if the chunk is in the top 5 chunks, it gets a bonus multiplier of self.place_multiplier, interpolated.
            multiplier = self.getMultiplier(element_id, self.element_chunk_scores_s)
            score += self.element_chunk_scores.get(element_id, 0)*self.element_chunk_weight*multiplier
        
            score += self.element_description_scores.get(element_id, 0)*self.element_description_weight
        
        text = self.getTextForMatches(matches, element_id)

        
        multiplier = self.getMultiplier(element_id, self.element_chunk_scores_s)
        score += self.element_usecase_scores.get(element_id, 0)*self.element_usecase_weight*multiplier

        
        self.stored_scores[element_id][omit_num]['text'] = text
        self.stored_scores[element_id][omit_num]['pre-alpha'] = score


        return score,text
    
    def getTextForMatches(self, matches= None, element_id = None):
        '''
        many matches, one element, or no matches, yes element_id
        '''
        #TODO: stash this text. requires somewhat of a refactor.
        Session = getSession()
        text = ''
        if matches:
            element_id = matches[0]['metadata']['element_id']
        else:
            if not element_id:
                raise Exception("Either matches or element_id must be provided.")
        with Session() as session:
            element = session.query(ElementNode).filter(ElementNode.id==element_id).first()
            if element:
                description = element.description
            else:
                alert(f"Element with id {element_id} not found. TODO", 'exception')
                description = ''
                #TODO: verify!
            if matches:
                rag_doc = session.query(RAGDocument).filter(RAGDocument.id==matches[0]['metadata']['rag_document_id']).first()
                if not description:
                    description = rag_doc.description
                text =f"\nSourceId: {element_id}"+ rag_doc.getTextFromChunks(match_list=[int(match['metadata']['chunk_number']) for match in matches], with_metadata=True)
            else:
                text = f"\nSourceId: {element_id}\nDescription: {description}"
            return text


    #TODO: store partial final node scores based on states? maybe not. Setwise storage in some way might make this all a lot more efficient, esp for move evaluation.
    def scoreNode(self, node_id, active_elements, active_nodes):
        
        raw_score = self.getRawNodeScore(node_id)
        final_score = raw_score
        #get the indirect references - nodes
        current_node = next((node for node in self.candidate_nodes if node.id==node_id), None)
        if not current_node:
            self.nodes_to_remove.add(node_id)
            #alert(f"Node with id {node_id} not found in candidate nodes.", 'exception')
            return 0, ''
        child_node_ids = current_node.getAllChildNodeIds()
        for child_node_id in child_node_ids:
            if child_node_id not in active_nodes:
                #TODO: store state_ids in the scoring class and use them to get the score (caching)
                node_score = self.scoreNode(child_node_id, active_elements, active_nodes)[0]
                if node_score>0:
                    final_score += self.node_indirect_multiplier*node_score

        #get the indirect references - elements
        element_ids = current_node.getAllChildElementIds()
        for element_id in element_ids:
            if element_id not in active_elements:
                element_score = self.scoreElement(element_id, 0)
                if element_score[0]>0:
                    final_score += self.element_indirect_multiplier*element_score[0]

        #get the node description
        text = f'''{current_node.description}'''

        #print(f"scored node {node_id} with text {text} and pre-alpha score {final_score}", flush=True)
        return final_score, text


    def getRawNodeScore(self, node_id):
        raw_score = None
        if self.stored_scores.get(node_id, None):
            if self.stored_scores[node_id].get('raw', None):
                raw_score = self.stored_scores[node_id]['raw']
        if not raw_score:
            #make raw score
            node_description_score = self.node_description_scores.get(node_id, 0)
            raw_score = node_description_score*self.node_description_weight
            #if the node is in the top 5 nodes, it gets a bonus multiplier of self.place_multiplier, interpolated.
            if node_description_score:
                multiplier = self.getMultiplier(node_id, self.node_description_scores_s)
                raw_score *= multiplier
        #save the raw score
        if not self.stored_scores.get(node_id, None):
            self.stored_scores[node_id] = {}
        self.stored_scores[node_id]['raw'] = raw_score
        return raw_score
    
    def getMultiplier(self,object_id, sorted_scores):
        #TODO: parameterize this
        scores_to_boost = 5
        index = scores_to_boost
        for i in range(0, min(scores_to_boost,len(sorted_scores)-1,1)):
            if sorted_scores[i][0]==object_id:
                index = i
                break
        if index<scores_to_boost:
            multiplier = 1 + (self.place_multiplier-1)*(scores_to_boost-index)/scores_to_boost
        else:
            multiplier = 1
        return multiplier
    
    def makeHonorableMentions(self, alpha, active_element_ids):
        '''
        honorable mentions are elements that have no text in the final output, but are still mentioned.
        '''
        if self.cmax == 0:
            return
        inactive_elements = [element_id for element_id in self.candidate_element_ids if element_id not in active_element_ids]
        self.honorable_mentions = []
        for element_id in inactive_elements:
            text = self.getTextForMatches(element_id=element_id)

            chunk_matches = [match for match in self.top_k_chunks if match['metadata']['element_id']==element_id]
            chunk_total = 0
            if chunk_matches:
                chunk_total = sum([match['score'] for match in chunk_matches])
            element = next((element for element in self.candidate_elements if element.id==element_id), None)
            
            usecase_matches = [match for match in self.top_40_document_usecase_chunks if match['metadata']['rag_document_id']==element.rag_document_id]
            usecase_total = 0
            if usecase_matches:
                usecase_total = sum([match['score'] for match in usecase_matches])

            description_scores = self.element_description_scores.get(element_id,0)

            total_score = chunk_total*self.element_chunk_weight + usecase_total*self.element_usecase_weight + description_scores*self.element_description_weight

            cost = alpha*len(text)
            element_value = total_score
            if not self.stored_scores.get(element_id, None):
                self.stored_scores[element_id] = {}
            if not self.stored_scores[element_id].get(0, None):
                self.stored_scores[element_id][0] = {}
            self.stored_scores[element_id][0]['pre-alpha'] = element_value
            self.stored_scores[element_id][0]['text'] = text
            if element_value-cost>0:
                self.honorable_mentions.append(element_id)
        print(f"made {len(self.honorable_mentions)} honorable mentions", flush=True)

#this class is for actually finding the best context to provide.
class StateTracker:
    def __init__(self, scoring_class:ScoringClass, alpha=0.05) -> None:
        Session = getSession()
        with Session() as session:
            self.node_ids = scoring_class.candidate_node_ids
            self.element_ids = scoring_class.candidate_element_ids

            node_id_and_path = session.query(CategoryNode).with_entities(CategoryNode.id, CategoryNode.path_from_root).filter(CategoryNode.id.in_(self.node_ids)).all()
            
            self.all_nodes = {node_id: path_from_root for node_id, path_from_root in node_id_and_path}
            self.active_nodes = self.all_nodes
            #sort by the number of colons in the path_from_root. This is a heuristic for how deep the node is in the tree. Root first.
            self.active_nodes_s = sorted(self.active_nodes.items(), key=lambda x: x[1].count(':')) if self.active_nodes else []
            self.all_nodes_s = sorted(self.all_nodes.items(), key=lambda x: x[1].count(':')) if self.all_nodes else []

        #the number is the number of chunks OMITTED from that document. That is, we include everything for now.
        self.active_elements = {element_id:0 for element_id in self.element_ids}
        self.score = 0
        self.scoring_class:ScoringClass = scoring_class
        
        # how expensive tokens are
        self.alpha = float(alpha)/7

        self.no_cmax_text = ""


    def calculateScore(self):
        self.score = self.scoring_class.score(self.active_nodes, self.active_elements, self.alpha)




    def getText(self):
        '''
        node:{
            'text':str,
            'subnode':{
                'text':str,
            ... 'lastsubnode':{
                'text':str,
                elements:{
                    element_id: text,
                    ...
                }
            }
        }
        }
        '''

        if self.scoring_class.cmax == 0:
            return self.no_cmax_text, 0
        
        def buildText(parent_node_id, parent_node_path, children):
            '''
            returns total length and text. additional info (like scores) is added to the text but not the total_length.
            
            '''
            #print(f"building text for {parent_node_id} with children {children} and path {parent_node_path}", flush=True)
            direct_children = [(child_node_id,path) for child_node_id, path in children if len(path.split(':'))==len(parent_node_path.split(':'))+1]
            total_length = 0
            if parent_node_id in self.active_nodes:
                text = {}
                score, description = self.scoring_class.scoreNode(parent_node_id, self.active_elements, self.active_nodes)
                if description != 'ROOT_NODE':
                    text = {
                        'category_id':parent_node_id,
                        'description':description
                    }
                    total_length += len(description) + len('description') + len('category_id') + len(parent_node_id)
                    
                    if os.environ.get('debug',None):
                        text['score'] = score

                if direct_children:
                    #print(f"direct children for {parent_node_id}: {direct_children}", flush=True)
                    subcategories = []
                    for child, path in direct_children:
                        subchildren = [pair for pair in children if pair[1].startswith(path)]
                        subtext, new_len = buildText(child, path, subchildren)
                        if subtext:
                            subcategories.append(subtext.copy())
                        if new_len:
                            total_length += new_len
                    if subcategories:
                        if description == 'ROOT_NODE':
                            text = subcategories
                        else:
                            text['children'] = subcategories
                            total_length += len('children')
                else:
                    #print(f"no direct children for {parent_node_id}", flush=True)
                    #add the elements
                    #get all elements in the node
                    #since elements are limited by tmax, they don't factor in to text length.
                    Session = getSession()
                    with Session() as session:
                        element_ids = session.query(ElementNode).with_entities(ElementNode.id).filter(ElementNode.parent==parent_node_id).all()
                        element_ids = [result[0] for result in element_ids]
                        to_append = [pair for pair in self.active_elements.items() if pair[0] in element_ids]
                        best_matches = []
                        best_matches_scores = []
                        for element_id, omit_num in to_append:
                            best_matches.append(self.scoring_class.stored_scores[element_id][omit_num]['text'])
                            
                            if os.environ.get('debug',None):
                                best_matches_scores.append(self.scoring_class.stored_scores[element_id][omit_num]['text'] +f"\n 'score':{self.scoring_class.stored_scores[element_id][omit_num]['pre-alpha']-self.alpha*len(self.scoring_class.stored_scores[element_id][omit_num]['text'])}")
                        if self.scoring_class.honorable_mentions:
                            #print(f"{element_ids}")
                            for element_id in self.scoring_class.honorable_mentions:
                                if element_id in element_ids:
                                    print("adding hm")
                                    if element_id in to_append:
                                        raise Exception(f"Element {element_id} is both an honorable mention and an active element.")
                                    best_matches.append(self.scoring_class.getTextForMatches(element_id=element_id))
                                    best_matches_scores.append(self.scoring_class.getTextForMatches(element_id=element_id))
                                    total_length += len(best_matches[-1])
                        
                        if best_matches:
                            text['best_matches'] = best_matches if not os.environ.get('debug') else best_matches_scores

                

            else:
                if direct_children:
                    text = []
                    #print(f"inactive, but direct children for {parent_node_id}: {direct_children}", flush=True)
                    subcategories = []
                    for child, path in direct_children:
                        subchildren = [pair for pair in children if pair[1].startswith(path)]
                        subtext, new_len = buildText(child, path, subchildren)
                        if subtext:
                            subcategories.append(subtext)
                        total_length += new_len
                    if subcategories:
                        text=subcategories
                else:
                    #print(f"inactive, no direct children for {parent_node_id}", flush=True)
                    #add the elements
                    #get all elements in the node
                    Session = getSession()
                    text = {}
                    with Session() as session:
                        element_ids = session.query(ElementNode).with_entities(ElementNode.id).filter(ElementNode.parent==parent_node_id).all()
                        element_ids = [result[0] for result in element_ids]
                        to_append = [pair for pair in self.active_elements.items() if pair[0] in element_ids]
                        #print(f"to append: {to_append}", flush=True)
                        best_matches = []
                        best_matches_scores = []
                        if to_append:
                            for element_id, omit_num in to_append:
                                best_matches.append(self.scoring_class.stored_scores[element_id][omit_num]['text'])
                                if os.environ.get('debug',None):
                                    best_matches_scores.append(self.scoring_class.stored_scores[element_id][omit_num]['text'] +'\nscore:' + str(self.scoring_class.stored_scores[element_id][omit_num]['pre-alpha']-self.alpha*len(self.scoring_class.stored_scores[element_id][omit_num]['text'])))
                        if self.scoring_class.honorable_mentions:
                            for element_id in self.scoring_class.honorable_mentions:
                                if element_id in element_ids:
                                    if element_id in to_append:
                                        raise Exception(f"Element {element_id} is both an honorable mention and an active element.")
                                    best_matches.append(self.scoring_class.getTextForMatches(element_id=element_id))
                                    best_matches_scores.append(self.scoring_class.getTextForMatches(element_id=element_id))
                                    total_length += len(best_matches[-1])
                        text['best_matches'] = best_matches if not os.environ.get('debug') else best_matches_scores

            return text, total_length
        def cleanText(text):
            '''
            navigate through the nested dict and make a nice string.
            '''
            out = ""
            if isinstance(text, dict):
                if 'category_id' in text:
                    out += f"CategoryID: {cleanText(text['category_id'])}\n"
                if 'description' in text:
                    out += f"Description: {cleanText(text['description'])}"
                if 'best_matches' in text:
                    out += f"{cleanText(text['best_matches'])}"
                if 'children' in text:
                    out += '\nchildren:{'
                    for child in text['children']:
                        cleaned = cleanText(child)
                        if cleaned:
                            out += cleanText(child) + ',\n' 
                    out = out[:-2] + '}\n'
            elif isinstance(text, list):
                for item in text:
                    out += cleanText(item)
            elif isinstance(text, str):
                out += text
            return out
        
        def getTotalMatches(element_id):
            matches = [match for match in self.scoring_class.top_k_chunks if match['metadata']['element_id']==element_id]
            return len(matches)
        
        self.scoring_class.makeHonorableMentions(self.alpha, list(self.active_elements.keys()))
        #print(f"building text with active nodes {self.active_nodes} and active elements {[element + ':' + str((getTotalMatches(element) - int(omit_num)))+'/' + str(getTotalMatches(element)) + ' chunks' for element, omit_num in self.active_elements.items()]}", flush=True)
        text, length = buildText(self.all_nodes_s[0][0],'', self.all_nodes_s[1:])
        print(f"result: {text}", flush=True)
        return cleanText(text), length

        



    def refine(self, mode='default'):
        if mode == 'default':
            self.default_refine()
        elif mode == 'dynamic_alpha':
            self.dynamic_alpha_refine()

    
    def default_refine(self):
        from packages.tasks import verify_pinecone_object
        #remove the worst individual chunks until we are below the max length.
        sorted_chunks = sorted(self.scoring_class.top_k_chunks, key=lambda x: x['score'], reverse=True)
        chunk_text = [{i: self.scoring_class.getTextForMatches([sorted_chunks[i]])} for i in range(len(sorted_chunks))]
        total_length = sum([len(list(text.values())[0]) for text in chunk_text])        
        #TODO: make this more efficient. Also, it doesn't account for the text length of nodes.
        removed_chunks = []
        removed_text = []
        #integrity check:
        all_ids_from_matches = [match['metadata']['element_id'] for match in sorted_chunks]
        all_ids_from_elements = [element_id for element_id in self.active_elements]
        if set(all_ids_from_matches) != set(all_ids_from_elements):
            #determine the ids that are in one but not the other.
            missing_from_elements = [element_id for element_id in all_ids_from_matches if element_id not in all_ids_from_elements]
            print(f"missing from elements: {missing_from_elements}")
            for element_id in missing_from_elements:
                #remove the element from the sorted_chunks and chunk_text.
                index = next((i for i in range(len(sorted_chunks)) if sorted_chunks[i]['metadata']['element_id']==element_id), None)
                if index:
                    sorted_chunks.pop(index)
                    chunk_text.pop(index)
                else:
                    alert(f"Element {element_id} not found in sorted_chunks.", 'exception')
                verify_pinecone_object.delay(element_id, [match['id'] for match in self.scoring_class.top_k_chunks if match['metadata']['element_id']==element_id][0], 'ElementNode', namespace='document_chunks')

        while total_length>self.scoring_class.tmax:
            worst_chunk = sorted_chunks.pop(-1)
            removed_chunks.append(worst_chunk)
            total_length -= len(list(chunk_text[-1].values())[0])
            removed_text.append(chunk_text.pop(-1))

        #go through the removed chunks backwards, and re-add anything that fits.
        for i in reversed(range(len(removed_chunks))):
            new_length = total_length + len(list(removed_text[i].values())[0])
            if new_length <= self.scoring_class.tmax:
                total_length = new_length
                sorted_chunks.append(removed_chunks.pop(i))
                chunk_text.append(removed_text.pop(i))
        #set the active elements to the elements in the remaining chunks.
        print(f"removed chunks: {len(removed_chunks)}")
        chunks_by_element = {}
        for chunk in sorted_chunks:
            element_id = chunk['metadata']['element_id']
            if not chunks_by_element.get(element_id, None):
                chunks_by_element[element_id] = []
            chunks_by_element[element_id].append(chunk)
        new_chunk_text = [self.scoring_class.getTextForMatches(chunks, element_id) for element_id, chunks in chunks_by_element.items()]
        print(f"element text: {new_chunk_text}")
        if self.scoring_class.cmax==0:
            self.no_cmax_text = new_chunk_text

            return
        
        #activate all elements.
        self.active_elements = {element_id:0 for element_id in self.element_ids}
        for chunk in removed_chunks:
            element_id = chunk['metadata']['element_id']
            self.active_elements[element_id] += 1
        to_deactivate = []
        for element_id, omit_num in self.active_elements.items():
            all_matched_elements = list(set([match['metadata']['element_id'] for match in self.scoring_class.top_k_chunks]))
            if omit_num>0:
                max_omit_num = self.scoring_class.top_k_chunks.count(element_id)
                if omit_num>=max_omit_num:
                    to_deactivate += [element_id]
            elif element_id not in all_matched_elements:
                to_deactivate += [element_id]
        for element_id in to_deactivate:
            self.active_elements.pop(element_id)
        for element_id, omit_num in self.active_elements.items():
            self.scoring_class.scoreElement(element_id, omit_num)

        


        #Determine whether the element is more useful indirectly than directly. If so, deactivate it.
        ''' for element_id in elements:
            
            net = self.scoring_class.getElementNet(element_id, self.active_elements[element_id], self.alpha)
            #compare the contribution of the element to the score with the raw*element_indirect_multiplier.
            if net < self.scoring_class.scoreElement(element_id, 0)[0]*self.scoring_class.element_indirect_multiplier:
                if os.environ.get('debug',None):
                    print("deactivating element, as it is more useful indirectly.")
                self.active_elements = {element_idx: omit_num for element_idx, omit_num in self.active_elements.items() if element_idx!=element_id}
        '''

        #this is for the case where we want to value smaller chunks. Currently, it is creating a bias towards smaller chunks that is resulting in missed information.
        '''try:
            net = self.scoring_class.getElementNet(element_id, self.active_elements[element_id], self.alpha)
            while net<=0:
                if os.environ.get('debug',None):
                    print(f"Element {element_id} has a negative net score of {self.scoring_class.getElementNet(element_id, self.active_elements[element_id], self.alpha)}. Increasing omit_num.")
            
                self.active_elements[element_id] += 1
                net = self.scoring_class.getElementNet(element_id, self.active_elements[element_id], self.alpha)

        except Exception as e:
            #print(f"Element {element_id} has no positive net score. Removing from active_elements.")
            self.active_elements.pop(element_id)
            continue'''

        if os.environ.get('debug',None):
            print(f"remaining elements: {len(self.active_elements)}")

        self.calculateScore()
        if self.scoring_class.cmax>0 and self.alpha>0:
            self.active_nodes_s = sorted(self.active_nodes.items(), key=lambda x: x[1].count(':'))
            lowest_active_nodes = []
            all_active_nodes = self.active_nodes
            for node_id, path in self.active_nodes_s:
                    if node_id in all_active_nodes:
                        #since the nodes are sorted by depth, we can skip all parents of this node. see the model for CategoryNodes.
                        all_active_nodes = {node_id: path2 for node_id, path2 in all_active_nodes.items() if not path.startswith(path2)}
                        lowest_active_nodes.append(node_id)
            #for simplicity, we will activate all of the nodes that are lowest active nodes, then assess whether stepping up the tree is necessary.
            self.active_nodes = {node_id: path for node_id, path in self.active_nodes.items() if node_id in lowest_active_nodes}
            changed = True
            while changed==True:
                changed=False
                #create a list of parent_path:[child_ids] for all nodes who are parents of active nodes.
                parent_children = {}
                for node_id, path in self.active_nodes.items():
                    index = path.rfind(':')
                    if index == 1 or index == -1:#case: '0:x' or '0'
                        #this is a top-level node. save for last. Root node can never be an 'active node'
                        continue
                        
                    parent_path = path[:index]
                    parent_id = next((id for id, path in self.all_nodes.items() if path==parent_path), None)
                    if not parent_id:
                        #TODO: verify the integrity of the tree in the db. This should never happen.
                        pass
                    
                    if not parent_children.get(parent_id, None):
                        parent_children[parent_id] = []
                    parent_children[parent_id].append(node_id)

                #TODO: consider arrangements with a subset of children active.
                #for each parent node, calculate the score of the parent node with all children active (current state), and the score of the parent node active with all children inactive.
                #if the score goes up by activating the parent and deactivating the children, do so.
                #this only accounts for nodes, not elements!
                for parent_id, child_ids in parent_children.items():
                    #calculate the score of the parent node with all children active.
                    node_score, node_text = self.scoring_class.scoreNode(parent_id, self.active_elements, self.active_nodes)
                    current_score = node_score - len(node_text)*self.alpha
                    active_node_copy = self.active_nodes.copy()
                    for child_id in child_ids:
                        active_node_copy = {node_id: path for node_id, path in active_node_copy.items() if node_id!=child_id}
                    
                    active_node_copy[parent_id] = self.all_nodes[parent_id]
                    #calculate the score of the parent node with all children inactive.
                    new_score, new_text = self.scoring_class.scoreNode(parent_id, self.active_elements, active_node_copy)
                    new_score -= len(new_text)*self.alpha
                    #print(f"Parent node {parent_id} with children {child_ids} has a current score of {current_score} and a new score of {new_score}.")
                    if new_score>current_score:
                        #print(f"Activating parent node {parent_id} and deactivating children {child_ids}, resulting in a delta of {new_score-current_score}.")
                        changed=True
                        #activate the parent node and deactivate the children.
                        self.active_nodes[parent_id] = self.all_nodes[parent_id]
                        for child_id in child_ids:
                            self.active_nodes = {node_id: path for node_id, path in self.active_nodes.items() if node_id!=child_id}


            #lastly, remove any nodes who have negative score from active nodes.
            to_remove = []
            for node in self.active_nodes:
                temp_score, temp_text = self.scoring_class.scoreNode(node, self.active_elements, self.active_nodes)
                temp_score -= len(temp_text)*self.alpha
                if temp_score<=0:
                    #print(f"Node {node} has a negative score. Removing from active_nodes.")
                    to_remove.append(node)
            for node in to_remove:
                self.active_nodes.pop(node)
        else:
            self.active_nodes = {}

            

        text, length = self.getText()

        if os.environ.get('debug',None):
            print(f"final pruned score: {self.score}")
            print(f"final pruned text: {json.dumps(text, indent=4)}")


            


    def dynamic_alpha_refine(self, eps = None, max_iter=10, starting_alpha=1):
        '''
        instead of just pruning, we will iteratively increase the alpha value until the text length is below the maximum, with eps: #characters +-
        '''
        self.default_refine()
        if self.scoring_class.cmax == 0:
            print("Element only. Default refine, exit.")
            
            return
        if not eps:
            eps = self.scoring_class.cmax/10
        self.alpha = 0
        start_time = datetime.now()
        #get initial text length of response.
        text, length = self.getText()
        states = [
            {
                'state':self,
                'alpha':0,
                'length':length
            }
            ]
        if length <= self.scoring_class.cmax:
            print(f"No need to refine. Starting length: {length}. Target length: {self.scoring_class.cmax}.")
            return
        #make a state with starting_alpha
        new_state = StateTracker(self.scoring_class)
        new_state.alpha = starting_alpha
        print(f"Starting alpha: {starting_alpha}. Epsilon: {eps}. max length: {self.scoring_class.cmax}. Running default refine.")
        new_state.default_refine()
        new_state.calculateScore()
        text, length = new_state.getText()
        length = len(str(text))
        states.append({
            'state':new_state,
            'alpha':starting_alpha,
            'length':length
        })
        print(f"Starting alpha: {starting_alpha}. Score: {new_state.score}. Length: {len(str(text))}.")
        
        setup_iterations = 100
        tries = 0
        while tries < setup_iterations:
            tries += 1
            #if there is a tie, take the larger alpha
            max_length = max([state['length'] for state in states])
            min_length = min([state['length'] for state in states])
            max_alpha = max([state['alpha'] for state in states if state['alpha']!=0])
            min_alpha = min([state['alpha'] for state in states if state['alpha']!=0])
            if max_length <= self.scoring_class.cmax:
                new_state = StateTracker(self.scoring_class)
                new_state.alpha = min_alpha/2
                new_state.default_refine()
                new_state.calculateScore()
                text, length = new_state.getText()
                states.append({
                    'state':new_state,
                    'alpha':new_state.alpha,
                    'length':length
                })
                print(f"New alpha: {new_state.alpha}. Score: {new_state.score}. Length: {length}.")
                continue
            if min_length >= self.scoring_class.cmax:
                new_state = StateTracker(self.scoring_class)
                new_state.alpha = max_alpha*2
                new_state.default_refine()
                new_state.calculateScore()
                text, length = new_state.getText()
                states.append({
                    'state':new_state,
                    'alpha':new_state.alpha,
                    'length':length
                })
                print(f"New alpha: {new_state.alpha}. Score: {new_state.score}. Length: {length}.")
                continue
            break
        if tries == setup_iterations:
            raise Exception("Setup iterations exceeded.")
            
        #start at the alpha that is closest to the target length.
        new_state = min([state for state in states if state['length']>self.scoring_class.cmax], key=lambda x: abs(x['length']-self.scoring_class.cmax))
        new_alpha = new_state['alpha']
        new_length = new_state['length']
        old_length = 0
        while abs(new_length-self.scoring_class.cmax)>eps and len(states)<max_iter:
            new_alpha = 'undefined' #just to skip the code below, for now.
            '''#if nothing changed with the last alpha, we interpolate to make a sizable jump. This occurs when the dataset is too small.
            if new_length in [s['length'] for s in states if s['alpha']!=new_alpha]:
                new_alpha = 'undefined'
            else:
                # this one fits 1/x. Currently OFF because it seems to be increasing the number of iterations... that changes as the sample size increases.
                a, b = self.fitInverse([state['alpha'] for state in states], [state['length'] for state in states])
                
                new_alpha = b / (self.scoring_class.cmax - a) if b / (self.scoring_class.cmax - a) > 0 else 'undefined'
                print(f"new alpha (not deduped): {new_alpha}.")
                #if this alpha is too close to existing alphas... TODO: make this contingent upon a change in length, instead?
                while any(difference < 0.0001 for difference in [abs(new_alpha - old_alpha) for old_alpha in [state['alpha'] for state in states]]):
                    if states[-1]['length'] <= self.scoring_class.cmax:
                        new_alpha = new_alpha - 0.10*new_alpha
                    else:
                        new_alpha = new_alpha + 0.10*new_alpha'''
                    
                

            #this just bisects the interval between the two states that straddle the target length.
            if new_alpha == 'undefined':
                #find the smallest state which is larger than the target length.
                state_1 = None
                state_2 = None
                sorted_states = sorted(states, key=lambda x: x['alpha'])
                print([(s['alpha'], s['length']) for s in sorted_states])
                direction = 1 if sorted_states[0]['length']<self.scoring_class.cmax else -1
                if direction == 1:
                    for state in sorted_states:
                        if state['length'] > self.scoring_class.cmax:
                            state_2 = state
                            state_1 = sorted_states[sorted_states.index(state)-1]
                            break
                else: 
                    for state in sorted_states:
                        if state['length'] < self.scoring_class.cmax:
                            state_1 = state
                            state_2 = sorted_states[sorted_states.index(state)-1]
                            break
                print(f"bisecting: {state_1['alpha']} and {state_2['alpha']}.")
                new_alpha = (state_1['alpha'] + state_2['alpha'])/2
                print(f"resulting alpha: {new_alpha}.")

            print(f"new alpha: {new_alpha}.")
            #make a new state with the new alpha.
            new_state = StateTracker(self.scoring_class)
            #if alpha is a repeat, add a little noise.
            
            new_state.alpha = new_alpha
            new_state.default_refine()
            new_state.calculateScore()
            text, length = new_state.getText()
            old_length = new_length
            new_length = len(str(text))          
            print(f"New alpha: {new_alpha}. Score: {new_state.score}. Length: {len(str(text))}.")
            states.append({
                'state':new_state,
                'alpha':new_alpha,
                'length':len(str(text))
            })

        #select the best state. #{"alphas": [0, 1, 0.1, 0.01, 0.001, 0.27475705539145523, 0.27416278824003243, 0.27366766015931177, 0.27324331116243916, 0.2728720313470545], "lengths": [62456, 100, 398, 2613, 26148, 303, 303, 303, 303, 303], "scores": [-596.9766874864341, 123.97658402066463, 160.5948030046404, 173.28403225707552, 133.25416938422373, 143.07501884881887, 143.1409825026268, 143.19594171958678, 143.24304445823964, 143.28425651774734]}TODO: this should be based on score and length.
        best_state = min(states, key=lambda x: abs(x['length']-self.scoring_class.cmax))
        self.active_nodes = best_state['state'].active_nodes
        self.active_elements = best_state['state'].active_elements
        self.alpha = best_state['state'].alpha
        self.score = best_state['state'].score
        text, length = best_state['state'].getText()
        print(f"Final alpha: {self.alpha}. Final score: {self.score}. Final length: {length}. number of iterations: {len(states)}. \n elapsed time: {(datetime.now()-start_time).total_seconds()}")




    def fitInverse(self, x, y):
        def compute_error(a, b, x, y):
            """Compute total error for the model a + b/x."""
            total_error = 0.0
            for i in range(len(x)):
                predicted_y = a + b / x[i]
                total_error += (y[i] - predicted_y) ** 2
            return total_error

        def gradient_descent(x, y, initial_a, initial_b, learning_rate, iterations, clip_threshold=1e5):
            a = initial_a
            b = initial_b
            for j in range(iterations):
                grad_a = 0
                grad_b = 0
                n = len(x)
                for i in range(n):
                    xi = x[i]
                    yi = y[i]
                    pred = a + b / xi
                    error = yi - pred
                    grad_a += -2 * error / n
                    grad_b += -2 * error / (xi * n)
                # Clip gradients to prevent overflow
                grad_a = np.clip(grad_a, -clip_threshold, clip_threshold)
                grad_b = np.clip(grad_b, -clip_threshold, clip_threshold)
                a -= learning_rate * grad_a
                b -= learning_rate * grad_b
                if j % 100 == 0 and os.environ.get('debug'):
                    print(f"Iteration {j}. Error: {compute_error(a, b, x, y)}")
            return a, b

        # remove any zeros from x, y
        x,y  = np.array([x_val for x_val, y_val in zip(x, y) if x_val != 0 and y_val != 0]), np.array([y_val for x_val, y_val in zip(x, y) if x_val != 0 and y_val != 0])
        
        #dedupe the y values, keeping the lowest x value.
        x_deduped = []
        y_deduped = []
        for i in range(len(x)):
            if y[i] not in y_deduped:
                x_deduped.append(x[i])
                y_deduped.append(y[i])
        x, y = x_deduped, y_deduped

        print(f"fitting inverse with x: {x} and y: {y}.")
        
        learning_rate = 0.0001
        initial_a = 0
        initial_b = 1  
        num_iterations = 1000

        # Run gradient descent to find the optimal a and b
        a, b = gradient_descent(x, y, initial_a, initial_b, learning_rate, num_iterations)
        
        #return the function
        return a, b

