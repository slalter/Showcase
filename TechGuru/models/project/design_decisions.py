from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models import SmartUUID
import uuid
from ..code_objects.model import Model
from ..code_objects.method import Method
from ..utils import ProjectVectorMixin, LoggableMixin
import shutil
import os
from packages.guru.GLLM import LLM

class RelevantFor(Base, ProjectVectorMixin):
    __tablename__ = 'relevant_for'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    relevant_for = Column(String, default='')
    design_decision = relationship("DesignDecision", back_populates="relevant_fors")
    design_decision_id = Column(SmartUUID(), ForeignKey('design_decisions.id'))
    relationship('Project')

    
    def embed(self, session):
        project_id = session.query(DesignDecision.project_id).filter(DesignDecision.id == self.design_decision_id).first().project_id
        if not project_id:
            raise Exception('No project_id found for this design decision.')
        
        self.namespace = f'relevant_for_{project_id[0]}'
        self.embedding = LLM.getEmbedding(self.relevant_for)
        session.commit()

    def __str__(self):
        return f'''
id: {self.id}
relevant_for: {self.relevant_for}
design_decision_id: {self.design_decision_id}
design_decision description: {self.design_decision.description}
'''

class DesignDecision(Base, ProjectVectorMixin, LoggableMixin):
    __tablename__ = 'design_decisions'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    description = Column(String, default='')
    relevant_fors = relationship("RelevantFor", back_populates="design_decision", cascade="all")
    project = relationship("Project", back_populates="design_decisions")
    decision = Column(String, default='')

    def __str__(self):
        return f'''
id: {self.id}
description: {self.description}
decision: {self.decision}'''
    
    def embed(self, session):
        self.namespace = f'design_decision_{self.project_id}'
        self.embedding = LLM.getEmbedding(self.description)
        session.commit()
    
    @staticmethod
    def processRequest(
        session,
        description,
        relevant_for_list,
        project_id,
        conversation_id
        ) -> 'DesignDecision':
        '''
        Handles a request for a new design decision.
        Checks to see if it is already made. Makes one if not.
        returns the designdecision object.
        commits.
        '''
        from prompt_classes import DesignDecisionComparePrompt
        from models import LLMLog
        existing:DesignDecision = session.query(DesignDecision).first()
        matches = []
        if existing:
            matches:list[DesignDecision] = existing.nearest(session, LLM.getEmbedding(description),threshold=0.9)
        #check to see whether we have already made a call on this.
        prompt = DesignDecisionComparePrompt(
            relevant_for_list=relevant_for_list,
            matches=matches,
            description=description,
            stack_description= 'SQLAlchemy with Postgres, Flask, jinja2. Docker compose for deployment.'
        )
        log, result = prompt.execute()
        LLMLog.fromGuruLogObject(log, conversation_id, session)
        if result.get('new_standardization',None):
            #create a new design decision.
            new_decision = DesignDecision(
                description=str(result['new_standardization']['description']),
                project_id=project_id,
                decision=str(result['new_standardization']['decision'])
            )
            session.add(new_decision)
            session.commit()
            new_decision.embed(session)
            for relevant_for in result['new_standardization']['relevant_for_list']:
                new_relevant_for = RelevantFor(
                    relevant_for=relevant_for,
                    design_decision_id=new_decision.id
                )
                session.add(new_relevant_for)
                session.commit()
            return new_decision
        elif result.get('standardization_already_exists',None):
            return matches[result.get('standardization_already_exists')]
        
    
            
    def getSimilar(self, task_description, task_embedding, session, threshold=0.9, max_results=5, relevant_for_top_k=10):
        '''
        Returns the most similar design decisions. Compositely scores the decision and the relevant fors.
        '''
        relevant_fors:list[ProjectVectorMixin] = self.relevant_fors
        top_nearest_relevant_fors:list[RelevantFor] = relevant_fors[0].nearest(
            session, 
            task_embedding, 
            limit=relevant_for_top_k,
            threshold=threshold
            )
        #compile hit counts by design_decision_id
        hit_counts:dict[str, int] = {}
        for relevant_for in top_nearest_relevant_fors:
            if hit_counts.get(relevant_for.design_decision_id, None):
                hit_counts[relevant_for.design_decision_id] += 1
            else:
                hit_counts[relevant_for.design_decision_id] = 1
        
        #get the top design decisions
        top_descriptions = self.nearest(session, task_embedding, limit=max_results, threshold=threshold)
        
        #return up to max_results design decisions.
        description_to_relevant_for_weight = 1
        scores:dict[str, float] = {}
        for description in top_descriptions:
            scores[description.id] = 1
        
        for relevant_for in top_nearest_relevant_fors:
            scores[relevant_for.design_decision_id] += description_to_relevant_for_weight*hit_counts[relevant_for.design_decision_id]
        self.addLog(
            'getSimilarDesignDecisions: ' + task_description,
            {
                'task_description': task_description,
                'top_descriptions': [str(t) for t in top_descriptions],
                'top_nearest_relevant_fors': [str(t) for t in top_nearest_relevant_fors],
                'hit_counts': hit_counts,
                'scores': scores
            },
            session
        )
        session.commit()
        dds = session.query(DesignDecision).filter(DesignDecision.id.in_(scores.keys()[:max_results])).all()
        return dds