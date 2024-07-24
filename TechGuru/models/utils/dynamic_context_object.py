from sqlalchemy import Column, String, Text, JSON, Integer, ForeignKey, Boolean, Float
from sqlalchemy.ext.declarative import declared_attr
from .vector import DCOVectorMixin, Vector
from .versioned_mixin import VersionedMixin
from .loggable import LoggableMixin
from prompt_classes import CompareCodeObjectPrompt, SummarizeForDCOVectorPrompt
from packages.guru.GLLM import LLM
from packages.guru.GLLM.log import Log
from sqlalchemy.orm import relationship
from .smart_uuid import SmartUUID
from ..database import Base
import uuid
from sqlalchemy import Table
from concurrent.futures import ThreadPoolExecutor

class DCOSemanticNamespace(Base, LoggableMixin):
    '''
    This represents a single embedding class for a dynamic context object.
    Should probably be polymorphic.
    Example embedding_columns:

    soft:
    - description (default)
    - use case
    - related concept
    - company description
    - temperment
    - style

    hard:
    - changed_text: the added text relative to the parent node
    etc.

    #NOTE: 
    These embedding_columns are always evaluated in the context of the parent node. 
    Ex: in what cases do we need this node instead of the parent node?
    general: how does this node differ from the parent node with respect to the embedding_column?
    
    This creates a namespace for comparisons with respect to the mixed-in class. Should also namespace by an id; currently, its project, we need to make that dynamic.

    '''
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)

    #conceptualization: how heavily should we weigh the delta between this node's comparison to the parent node's comparison?
    weight = Column(Float, default=1.0)

    #this is the column in which you describe the string that will be embedded.
    embedding_column = Column(String, nullable=False)

    def makeVector(self, child_node_id, parent_node_id = None):
        '''
        takes in the data to summarize or the summary and returns the vector.
        '''
        from models import Session
        with Session() as session:
            try:
                child_node = session.query(DCONode).filter(DCONode.id == child_node_id).first()
                parent_node = session.query(DCONode).filter(DCONode.id == parent_node_id).first()
                prompt = SummarizeForDCOVectorPrompt(
                    parent_data = parent_node.getData() if parent_node else None,
                    child_data = child_node.getData(),
                    given_topic = self.embedding_column
                )
                call = prompt.execute()
                log = call.log
                result = call.get()
                self.add_llm_log(log, session)
                embedding = LLM.getEmbedding(result)
                vector = DCOVector(
                    namespace_id = self.id,
                    summary = result,
                    embedding = embedding,
                    node=child_node
                )
                session.add(vector)
                session.commit()
                return vector.id
            except Exception as e:
                session.rollback()
                self.addLog(f'Error: {e}','',session)
                session.commit()
                raise

    def nearest(self, session, vector, method='cosine', threshold=0.9, limit=5):
        '''
        Returns the nearest vectors to the given vector.
        '''
        #get the first vector in this namespace.
        vec:DCOVector = session.query(DCOVector).filter(DCOVector.namespace_id == self.id).first()
        if not vec:
            return None
        return vec.nearest(session, vector, method, threshold, limit)


class DCOVector(Base, DCOVectorMixin):
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    node_id = Column(SmartUUID(), ForeignKey('dco_node.id'))
    node = relationship("DCONode", back_populates="vectors")
    namespace_id = Column(SmartUUID(), ForeignKey('dco_semantic_namespace.id'))
    namespace = relationship("DCOSemanticNamespace")
    summary = Column(String, nullable=False)

class DCONode(Base):
    '''
    this represents a single node in the dynamic context object tree.
    '''
    __tablename__ = 'dco_node'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    parent_id = Column(SmartUUID(), ForeignKey('dc_object.id'))
    parent = relationship("DCONode", back_populates="children")
    children = relationship("DCONode", back_populates="parent")
    vectors = relationship("DCOVector", back_populates="node")
    name = Column(String, nullable=True)
    data = Column(String)

    def getData(self, max_size=10000, divisions=4):
        """
        Returns data, but removes equally-distributed subsections of the data such that the data is less than max_size.
        
        Parameters:
            max_size (int): The maximum size of the data to be returned.
            divisions (int): The number of equally-distributed sections to keep.
            
        Returns:
            str: The processed data, reduced to be less than or equal to max_size.
        """
        data_length = len(self.data)
        
        if data_length <= max_size:
            return self.data
        else:
            difference = data_length - max_size
            # Size of one keeper subsection
            keep_size = max_size // divisions
            # Size of one removed subsection
            remove_size = difference // divisions
            
            # Collect the sections to keep
            output = []
            index = 0
            for i in range(divisions):
                output.append(self.data[index:index + keep_size])
                index += keep_size + remove_size
            
            return ''.join(output)
        
    def getVector(self, namespace_id):
        '''
        Returns the vector for the given namespace_id.
        '''
        return self.vectors.filter(DCOVector.namespace_id == namespace_id).first().embedding


#TODO: assess modes: 

#replacement mode: the child content's start and end indices are a subset of the parent content's start and end indices, AND
#the union across all children's start and end indices is equal to the parent content's start and end indices.
#this can be layer-wise non-partitioning or cascading, but the cascading mode is very complex to implement.
#if we do the cascading mode, we can break it into two sub-categories:
# - consecutive cascading mode: all combinations of consecutive children have up-summaries. This one isn't so bad.
# - non-consecutive cascading mode: all combinations of non-consecutive children have up-summaries. This one is very complex and applies to situations where the data is unordered.
# https://chatgpt.com/share/325e88ba-e75a-40a1-a666-6dc4d131fc0c

#layer-wise mode: 
# Partitioning: if a parent is not visible, the children (or their children, or their children, or...) are visible. If a child is not visible, the parent is visible.
# This is isomorphic to vertical, separated 'strands' of content with varying levels of specificity.
# 
# Non-partitioning: if a parent node is not visible, the child nodes MAY individually be visible. 
# this is the same as partitioning mode, except that less-relevant nodes may be removed completely from context (we don't partition the possible nodes, we just retrieve the most relevant ones with dynamic specificity).

#cascading mode:
# branches are joined s.t. we take one continuous path from an initial left-most depth to a final right-most depth, building a nested json object.
# good for hierarchical data.
#
# non-partitioning cascading mode: the path may not be continuous.
# in other words, we may remove nodes that are not relevant to the current context and have a resulting non-continuous path.
# dynamic cascade: individual nodes can be marked as 'removable' or not based on the context. 
# In the case that they are not removable, the context must contain a path through them; minimally just that node and maximally the entire path through the children of that node.
# example: retrieving information on a method from a codebase. The method's description is the parent node, and the method's code is broken up into children that themselves have greater specificity in their children.
# No matter what happens, that method node should be included in the context, but the children may be included or not based on the context, so the node is not removable.
# In the simplest case, this occurs when there are exact keyword or other deterministic matches to a node. 
# In the more complex case, this occurs when the node is a 'hub' for many other nodes that are relevant to the context, where the hub is identified as meaningful as a result of the high % frequency of relevant nodes that are children of the hub.


#TODO: assess how much we can gain by evaluating the shape of the score function as a function of the weights of the embedding columns and the relative cost of a token.
#what should the token cost function look like? How does it vary by usecase?
#identifying 'cliffs' in the score function may be more effective than assuming that the score function is smooth!
#TODO: design experiments to evaluate the effectiveness of the different modes, try to learn the weights, try to identify cliffs and A/B.

class DynamicContextObject(Base, DCOVectorMixin, LoggableMixin):
    '''
    This is a model for objects that have a fully-described state and up-summarized states.
    In other words, this is a tree where the sum of the bottom level is the complete state
    And the top level is the fully summarized state.
    This is very abstract. Here are some examples:
    - An app route: the bottom level is the entire codebase, the top level is the route.
    - A conversation: the bottom level is the entire conversation, the top level is the conversation summary.
    - A categorical sorting tree: the bottom level is all the items, the top level is the main category, and the middle levels represent varying levels of specificity.

    The benefit of this is that we can have a single object from which we can pull a dynamic summarized state based on the task at hand or query.
    '''
    __tablename__ = 'dc_object'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    root_id = Column(SmartUUID(), ForeignKey('dc_object.id'))
    root = relationship("DCONode", back_populates="parent", cascade="all")
    nodes = relationship("DCONode", back_populates="parent", cascade="all")
    namespaces = relationship("DCOSemanticNamespace", back_populates="node", cascade="all")
    
    mode = Column(String, nullable=False, default='cascading')

    def build(self, data, session):
        '''
        Builds the object from data. 
        '''
        if self.mode == 'cascading':
            self.build_cascading(data, session)
        else:
            raise NotImplementedError(f'Mode {self.mode} not implemented.')
        
    def build_cascading(self, data, session):
        '''
        Builds the object in cascading mode from a nested list/json.
        [
             {
                name: name,
                content: content,
                children: [{
                        name: name,
                        data: data,
                        children: [
                            ...
                        ]
                    ]
                }
        ]
        '''
        def handle_object(object):
            node = DCONode(
                name = object['name'],
                data = str(object['data'])
                )
            session.add(node)
            self.nodes.append(node)
            session.commit()
            if object['children']:
                for child in object['children']:
                    child_node = handle_object(child)
                    node.children.append(child_node)
                    session.commit()
            return node
        self.root = handle_object(data)
        session.commit()

        #build embeddings
        with ThreadPoolExecutor(max_workers=10) as executor:
            for node in self.nodes:
                for namespace in self.namespaces:
                    futures = executor.submit(namespace.makeVector, node.id, node.parent_id)
            
            for future in futures:
                try:
                    future.result()
                    if future.exception():
                        raise future.exception()
                except Exception:
                    raise 
        
    def getGraphPNG(self, highlighted_nodes=[]) -> bytes:
        '''
        Returns a bytes for the png of the graph.
        if highlighted_nodes is not empty, it will highlight those nodes in a different color.
        '''
        import networkx as nx
        import matplotlib.pyplot as plt
        import io
        G = nx.DiGraph()
        for node in self.nodes:
            G.add_node(node.id)
            if node.parent_id:
                G.add_edge(node.parent_id, node.id)
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_size=2000, node_color='skyblue', font_size=10, font_weight='bold')
        nx.draw_networkx_nodes(G, pos, nodelist=highlighted_nodes, node_color='r')

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        return buf.read()
    
    def curate(self, session, context, context_set = None, with_graph = False):
        '''
        Curates the object by removing nodes that are not relevant to the context.
        '''
        if not context_set:
            context_set = []
        if self.mode == 'cascading':
            return self.curate_cascading(session, context, context_set, with_graph)
        else:
            raise NotImplementedError(f'Mode {self.mode} not implemented.')
    
    def curate_cascading(self, session, context, context_set, with_graph):
        '''
        context set:
        {
            namespace_id: description, 
            namespace_id: description
            ...
        }
        
        '''
        for namespace in self.namespaces:
            to_summarize = []
            if namespace.id not in context_set:
                to_summarize.append(namespace.id)

        #summarize all remaining embedding_columns relative to the context.
        with ThreadPoolExecutor(max_workers=10) as executor:
            new_context = {}
            for namespace_id in to_summarize:
                future = executor.submit(self.getRelativeContextSummary, context, namespace_id)
                try:
                    result = future.result()
                    if future.exception():
                        raise future.exception()
                    new_context[namespace_id] = result
                except Exception:
                    raise

        context = {**context, **new_context}

        # embed all context descriptions
        embeddings = LLM.getEmbeddingsSyncFromList(list(context.values()))
        trios = [(namespace.id, context[namespace.id], embedding) for namespace, embedding in zip(self.namespaces, embeddings)]
        #get scores for all nodes for each namespace.
        scores = {}
        for namespace_id, description, embedding in trios:
            scores[namespace_id] = {}
            for node in self.nodes:
                scores[namespace_id][node.id] = LLM.compare(embedding, node.getVector(namespace_id))

        #use the namespace weights to get the final score for each node.
        final_scores = {}
        for node in self.nodes:
            final_score = 0
            for namespace in self.namespaces:
                final_score += namespace.weight*scores[namespace.id][node.id]
            final_scores[node.id] = final_score

        #build the text

    def getRelativeContextSummary(self, context, namespace_id):
        '''
        Returns the summarized context relative to the embedding_column in the namespace.
        multithreadable.
        '''
        from models import Session
        with Session() as session:
            namespace = session.query(DCOSemanticNamespace).filter(DCOSemanticNamespace.id == namespace_id).first()
            try:
                prompt = GetRelativeContextSummaryPrompt(
                    context = context,
                    given_topic = namespace.embedding_column,
                    object_description = self.description
                )
                call = prompt.execute()
                log = call.log
                result = call.get()
                namespace.add_llm_log(log, session)
                return result
            except Exception as e:
                session.rollback()
                namespace.addLog(f'Error: {e}','',session)
                session.commit()
                raise