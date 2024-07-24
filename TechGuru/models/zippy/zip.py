
from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, LargeBinary, Enum, Text, TIMESTAMP, update, Float
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models.utils.smart_uuid import SmartUUID
from models.utils.vector import VectorMixin
import uuid
import json
import pickle
from packages.guru.GLLM import LLM

class CriterionValue(Base, VectorMixin):
    __tablename__ = 'criterion_value'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)
    content = Column(Text, nullable = True)

    #init override to call embed
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.embed()

    def embed(self):
        self.embedding = LLM.getEmbedding(self.content)

class Criterion(Base, VectorMixin):
    __tablename__ = 'criterion'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)
    content = Column(Text, nullable = True)
    criterion_value = relationship('CriterionValue', backref='criterion',lazy='joined', cascade='all, delete', uselist=False)
    criterion_value_id = Column(SmartUUID(), ForeignKey('criterion_value.id'))
    zip_id = Column(SmartUUID(), ForeignKey('zip.id'))
    weight = Column(Float, default = 1.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    #init override to call embed
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.embed()

    def embed(self):
        self.embedding = LLM.getEmbedding(self.content)

class RAGDatabase(Base):
    __tablename__ = 'rag_database'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)


    def query(self, query):
        pass

class KnowledgeSource(Base):
    __tablename__ = 'knowledge_source'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)
    content = Column(Text, nullable = True)
    zip_id = Column(SmartUUID(), ForeignKey('zip.id'))
    database_id = Column(SmartUUID(), ForeignKey('rag_database.id'))

#a table for tracking all of the interactions between different zips.
class Interaction(Base):
    __tablename__ = 'interaction'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)
    zip1_id = Column(SmartUUID(), ForeignKey('zip.id'), nullable=False)
    zip2_id = Column(SmartUUID(), ForeignKey('zip.id'), nullable=False)
    interaction_time = Column(DateTime, default=datetime.utcnow)
    conversation_id = Column(SmartUUID(), ForeignKey('db_conversation.id'), nullable=True)



    zip1_score = Column(JSON, nullable = True)
    zip2_score = Column(JSON, nullable = True)

    zip1_llm_score = Column(Float, nullable = True)
    zip2_llm_score = Column(Float, nullable = True)

    zip1 = relationship('Zip', foreign_keys=[zip1_id])
    zip2 = relationship('Zip', foreign_keys=[zip2_id])

class Provided(Base, VectorMixin):
    __tablename__ = 'provided'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)
    content = Column(Text, nullable = True)
    zip_id = Column(SmartUUID(), ForeignKey('zip.id'))

    #init override to call embed
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.embed()

    def embed(self):
        self.embedding = LLM.getEmbedding(self.content)

class Received(Base, VectorMixin):
    __tablename__ = 'received'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)
    content = Column(Text, nullable = True)
    zip_id = Column(SmartUUID(), ForeignKey('zip.id'))

    #init override to call embed
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.embed()

    def embed(self):
        self.embedding = LLM.getEmbedding(self.content)

DEFAULTS = {
    'description_weight': .5,
    'provided_weight': 3.0,
    'received_weight': 3.0,
    'criteria_weight': 1.0,
    'alpha': 0.9,
    'beta': 0.8
}

class ParamSet(Base):
    __tablename__ = 'learned_param_set'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)

    description_weight = Column(Float, default = DEFAULTS['description_weight'])
    provided_weight = Column(Float, default = DEFAULTS['provided_weight'])
    received_weight = Column(Float, default = DEFAULTS['received_weight'])
    criteria_weight = Column(Float, default = DEFAULTS['criteria_weight'])
    alpha = Column(Float, default = DEFAULTS['alpha'])#threshold for considering a criterion a match.
    beta = Column(Float, default = DEFAULTS['beta'])#threshold for considering a mutual interest and starting a conversation.


class Zip(Base, VectorMixin):
    __tablename__ = 'zip'
    id = Column(SmartUUID(), primary_key=True,default=uuid.uuid4)

    description = Column(Text, nullable = True)

    is_providing = relationship('Provided', backref='zip',lazy='joined', cascade='all, delete')
    is_seeking = relationship('Received', backref='zip',lazy='joined', cascade='all, delete')

    criteria = relationship('Criterion', backref='zip',lazy='joined', cascade='all, delete')
    knowledge_sources = relationship('KnowledgeSource', backref='zip',lazy='joined', cascade='all, delete')

    param_set_id = Column(SmartUUID(), ForeignKey('learned_param_set.id'))
    param_set = relationship('ParamSet', backref='zip',lazy='joined', uselist=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    interactions = relationship(
        'Interaction',
        primaryjoin="or_(Zip.id==Interaction.zip1_id, Zip.id==Interaction.zip2_id)",
        viewonly=True,
        lazy='joined'
    )
    
    def get_updated_at(self):
        #goes through all critera and self.updated_at to find the most recent updated_at.
        return max([c.updated_at for c in self.criteria if hasattr(c, 'updated_at')] + [self.updated_at])

    #init override to call embed
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.embed()

    def embed(self):
        self.embedding = LLM.getEmbedding(self.description)

    def getParamSet(self, session):
        if not self.param_set_id:
            ps = ParamSet()
            self.param_set = ps
            session.add(ps)
            session.commit()
            return ps
        else:
            return session.get(ParamSet, self.param_set_id)

    def run(self, session):
        #TODO: increase efficiency by symmetry.
        #find the nearest matches in the Zip namespace based on description.
        item_description_pairs = self.nearest(session, self.embedding, 10, with_scores=True) 
        providing_example = session.query(Provided).first()
        receiving_example = session.query(Received).first()
        item_providing_pairs = []
        item_receiving_pairs = []
        for providing in self.is_providing:
            providing_score_pairs = receiving_example.nearest(session, providing.embedding, 10, with_scores=True)
            item_providing_pairs.append([(session.get(Zip, item.zip_id), score) for item, score in providing_score_pairs])
        for receiving in self.is_seeking:
            receiving_score_pairs = providing_example.nearest(session, receiving.embedding, 10, with_scores=True)
            item_receiving_pairs.append([(session.get(Zip, item.zip_id), score) for item, score in receiving_score_pairs])
            
        #for each other zip, make an interaction object and calculate scores for both sides. 
        match_scores:dict = {}
        for item, description_score in item_description_pairs:
            match_scores[item] = description_score*self.getParamSet(session).description_weight

        for s in item_providing_pairs:
            for item, score in s:
                if item in match_scores:
                    match_scores[item] += score*self.getParamSet(session).provided_weight
                else:
                    match_scores[item] = score*self.getParamSet(session).provided_weight

        for s in item_receiving_pairs:
            for item, score in s:
                if item in match_scores:
                    match_scores[item] += score*self.getParamSet(session).received_weight
                else:
                    match_scores[item] = score*self.getParamSet(session).received_weight

        #filter out any zips we have interacted with if their current updated_at is not newer than the last interaction.
        to_remove = [self]
        for n in match_scores.keys():
            interaction = next((i for i in self.interactions if i.zip1_id == n.id or i.zip2_id == n.id), None)
            if interaction:
                if interaction.interaction_time > n.get_updated_at():
                    to_remove.append(n)

        match_scores = {k:v for k,v in match_scores.items() if k not in to_remove}

        #for each item, find the criteria that match and add the score to the match_scores.
        for item in match_scores.keys():
            for criterion in self.criteria:
                matching_criteria = [c for c in item.criteria if LLM.compare(c.embedding, criterion.embedding)>self.getParamSet(session).alpha]
                if not matching_criteria:
                    continue
                for matching_criterion in matching_criteria:
                    match_scores[item] += LLM.compare(matching_criterion.criterion_value.embedding, criterion.criterion_value.embedding)*criterion.weight*self.getParamSet(session).criteria_weight

        #sort the match_scores by score.
        sorted_match_scores = sorted(match_scores.items(), key = lambda x: x[1], reverse = True)
        print(f'top 10 matches: {sorted_match_scores[:5]}')

        #for the top 10 matches, determine the scores from both perspectives.
        for match, score in sorted_match_scores[:10]:
            this_score = score
            that_score = score #TODO! this is a placeholder. we need to calculate the score from the other perspective.
            #make the interaction
            interaction = Interaction(zip1_id = self.id, zip2_id = match.id, zip1_score = float(this_score), zip2_score = float(that_score))
            session.add(interaction)
            session.commit()
            #if mutual interest averages beta
            if (this_score + that_score)/2 > self.getParamSet(session).beta:
                print(f'mutual interest! conversation starting. these things were matched: {self.description} and {match.description}')
                #start_zip_conversation.delay(self.id, match.id, interaction.id)







    def get_good_interactions(self):
        matches = [i for i in self.interactions if i.zip1_llm_score]
        if not matches:
            return None
        #for each match, determine if we are zip1 or zip2
        match_zip_no_pairs = [(i, 1 if i.zip1_id==self.id else 2) for i in matches]
        #for each match, determine the score.
        match_score_pairs = [(i, i.zip1_llm_score*1/2 + i.zip1_score*1/2 if no==1 else i.zip2_llm_score*1/2 + i.zip2_score*1/2) for i, no in match_zip_no_pairs]
        #sort by score
        match_score_pairs.sort(key = lambda x: x[1], reverse = True)
        return match_score_pairs
    
    def get_html_element_for_interaction(self, session, interaction):
        '''returns an html element of class 'interaction' with the interaction's data, including:
        -both zip's descriptions
        -the interaction time
        -the scores
        -the conversation_id and a link to the conversation if it exists (report endpoint)
        -the llm scores
        '''
        #get the other zip
        other_zip = interaction.zip1 if interaction.zip2_id == self.id else interaction.zip2
        html = f'''
<div class="interaction">
    <div class="zip1">{self.description}</div>
    <div class="zip2">{other_zip.description}</div>
    <div class="interaction_time">{interaction.interaction_time}</div>
    <div class="zip1_score">{interaction.zip1_score}</div>
    <div class="zip2_score">{interaction.zip2_score}</div>
    <div class="llm_scores">{interaction.zip1_llm_score} {interaction.zip2_llm_score}</div>
    <a href="/report/{interaction.conversation_id}">Conversation</a>
</div>
'''
        return html
    
    def get_html_styles(self):
        return '''
<style>
.interaction{
    border: 1px solid black;
    padding: 10px;
    margin: 10px;
}
.zip1{
    font-weight: bold;
}
.zip2{
    font-weight: bold;
}
</style>
'''

    def getSortedInteractions(self, session):
        return sorted(self.interactions, key=lambda x: self.scoreInteraction(session, x), reverse=True)
    
    def scoreInteraction(self, session, interaction):
        '''
        determines which zip is self, then pulls the scores from the interaction and returns the 50/50 average of the score and the llmscore from our perspective.
        '''
        if interaction.zip1_id == self.id:
            return ((interaction.zip1_score or 0) + (interaction.zip1_llm_score or 0))/2
        else:
            return ((interaction.zip2_score or 0) + (interaction.zip2_llm_score or 0))/2


    def get_html_for_top_k_interactions(self, session, k = 10):
        #interactions = self.get_good_interactions()
        interactions=self.getSortedInteractions(session)
        if not interactions:
            return 'No good interactions found.'
        html = self.get_html_styles()
        for interaction in interactions[:k]:
            print(f"getting html for {self.id}")
            html += self.get_html_element_for_interaction(session, interaction)
        return html