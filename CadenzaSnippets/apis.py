ACTIVATION_THRESHOLD = 3

from prompt_classes import NewPIPrompt, MergeETsPrompt, SortDocumentationPrompt, GetTrainingQuerysetPrompt, GenerateAPIUseDescriptionPrompt, UpdatedPIPrompt, ProcessQuerySetPrompt, CategorizeErrorPrompt, GeneratePythonPrompt, DescribeErrorPrompt, CheckDataResultPrompt, GetPurposeFromDocumentationPrompt
from guru.GLLM import LLM
import asyncio
import uuid
import traceback
import os
from datetime import datetime
import json
import re
import time
import random
from models import Switch, acquire_lock_with_backoff, release_lock, HistoricalError, LLMLog, APIModel, EndpointModel, ErrorTrackerModel, PreventativeInstructionModel, PI_LEVELS, PI_ENTRY_POINTS
from packages.db.database import db
from app import celery
import ast
from packages.devalert import alert, quicklog
import yaml
from celery import chord, group
from models import addLog, Query, Queryset
from packages.db.pinecone import index
from pinecone.core.client.model.vector import Vector
from celery import group, chord
from celery.exceptions import MaxRetriesExceededError, Retry
from azure.storage.blob import BlobServiceClient
from packages.utils.ip import get_host_ip
from sqlalchemy import desc, update
from packages.celery import getSession

#TODO: allow tools to go out to workers abstractly.
#TODO: allow the llm to decide if it makes sense to make a PI for an error!
class ErrorTracker:
    def __init__(self, endpointId=None, entrypoint = 'generate_code', api_id = None, level = 'endpoint', dbid = None, active = False, count = 0, errorDescriptions = None, PIHistory = None, active_at = None) -> None:
        self.active = active
        self.count = count
        self.PIHistory:list[PreventativeInstruction] = PIHistory if PIHistory else []
        self.endpointId = endpointId
        self.errorDescriptions=errorDescriptions if errorDescriptions else []
        self.dbid = dbid
        self.api_id = api_id
        self.level = level
        self.entrypoint = entrypoint
        self.active_at = active_at

    def increaseCount(self, historical_error_id, conversation_id = None):
        try:
            if not self.dbid:
                self.saveToDB()
            if acquire_lock_with_backoff(ErrorTrackerModel, self.dbid,max_retries=10):
                try:
                    print("incrementing count for error.")
                    self.count += 1
                    self.saveToDB(True)
                    if self.PIHistory:
                        pi = self.PIHistory[-1]
                        PreventativeInstruction.markFailure(pi.dbid)
                        pi = PreventativeInstruction.load(pi.dbid)
                        self.PIHistory[-1] = pi
                        if pi.successes/(pi.failures+pi.successes) <= pi.success_rate_at_activation and pi.successes+pi.failures >= 4:
                            alert(f"{pi.dbid} has not shown any improvement after 4 attempts. api_id: {Endpoint.load(self.endpointId).api_id}\n creating new pi.",'pi-error')
                            self.makeUpdatedPI()
                        self.PIHistory[-1].saveToDB()
                    elif self.count >= ACTIVATION_THRESHOLD:
                        self.active = True
                        self.active_at = datetime.utcnow()
                        self.makeNewPI(conversation_id=conversation_id)

                    release_lock(ErrorTrackerModel, self.dbid)
                except Exception as e:
                    release_lock(ErrorTrackerModel, self.dbid)
                    alert(f"error while processing error: {traceback.format_exception(e)}\n {historical_error_id}", 'exception')
            else:
                raise
        except Exception as e:
            print(f"Error in increaseCount: {traceback.format_exception(e)}")

    def getPI(self):
        Session = getSession()
        with Session() as session:
            pis = session.query(PreventativeInstructionModel).filter(PreventativeInstructionModel.errorTracker_id==self.dbid).order_by(desc(PreventativeInstructionModel.created_at)).all()
            if pis:
                return PreventativeInstruction.load(pis[-1].id)
            else:
                print("WARNING - getPI called for an ErrorTracker that has not been activated.")
    
    def makeNewPI(self, conversation_id = None):
            '''
            to be called only when we have a lock!
            '''
            endpoint = Endpoint.load(self.endpointId)
            api = API.load(endpoint.api_id)
            
            #TODO: add the ability to modify the description of what can be found in the api!
            prompt = NewPIPrompt(
                similar_errors=self.errorDescriptions[-3:],
                auth_variables=list(api.auth_info.keys()),
                other_info = api.other_info,
                documentation=endpoint.baseDocumentation,
                levels = PI_LEVELS,
                entrypoints = PI_ENTRY_POINTS,
                successful_example = endpoint.general_example
            )
            log, result = prompt.execute()


            LLMLog.fromGuruLogObject(log, self.dbid)

            docupdate = result.get('request_documentation_update',None)
            if docupdate:
                alert(f"Doc update requested for {api.name}: {docupdate}",'general')

            if result['auth_error']:
                alert(f"Auth error suspected for tenantid:{api.tenant_id} on {api.name}/{Endpoint.load(self.endpointId).url}. Not making a pi.\nresult: {result}",'auth')
                self.active=False
                self.saveToDB(lock=True)
                return
            self.level = result['level']
            self.entrypoint = result['entrypoint']
            if self.entrypoint == 'endpoint_selection':
                self.level == 'api'
            if self.level == 'api':
                print("moving error to api...")
                #get all api-level errors
                api_descriptions, api_ets = ErrorTrackerModel.getErrorTrackerIDsForSimilarDescriptions(
                    self.errorDescriptions[0],
                    api_id=self.api_id,
                    include_levels=['api'],
                    include_matching_descriptions=True)
                prompt = CategorizeErrorPrompt(
                    error_description=self.errorDescriptions[0],
                    existing_errors=api_descriptions
                )
                log, result2 = prompt.execute()
                if conversation_id:
                    LLMLog.fromGuruLogObject(log, conversation_id)
                if result2['existing_error'] >= 0:
                    et = ErrorTracker.load(api_ets[result2['existing_error']])
                    if et:
                        self.saveToDB(True)
                        print(f"found matching error at api level. merging.")
                        ErrorTracker.merge([self.dbid,et.dbid])
                        return
                    else:
                        alert(f"unable to load error tracker with id: {api_ets[result2['existing_error']]}! Retrying...",'exception')
                        raise
                self.api_id = api.dbid
                self.endpointId = None

            if self.level == 'global':
                print("moving error to global...")
                #TODO
                #get all global-level errors
                global_descriptions, global_ets = ErrorTrackerModel.getErrorTrackerIDsForSimilarDescriptions(
                    self.errorDescriptions[0],
                    include_levels=['global'],
                    entrypoint=self.entrypoint, 
                    include_matching_descriptions=True)
                prompt = CategorizeErrorPrompt(
                    error_description=self.errorDescriptions[0],
                    existing_errors=global_descriptions
                )
                log, result3 = prompt.execute()
                if result3['existing_error'] >= 0:
                    et = ErrorTracker.load(global_ets[result3['existing_error']])
                    if et:
                        self.saveToDB()
                        print(f"found matching error at global level. merging.")
                        ErrorTracker.merge([self.dbid,et.dbid])
                        return
                    else:
                        alert(f"unable to load error tracker with id: {global_ets[result3['existing_error']]}! Retrying...",'exception')
                        raise

                self.endpointId = None

            endpoint = Endpoint.load(self.endpointId)
            if endpoint:
                success_rate = sum(endpoint.binary_history)/max(len(endpoint.binary_history),1)
            else:
                success_rate = 0

            newPI = PreventativeInstruction(content=result['new_preventative_instruction'], reference_errors=self.errorDescriptions[-3:],errorTracker_id=self.dbid,success_rate_at_activation=success_rate)
            newPI.saveToDB()

            self.active = True
            self.active_at = datetime.utcnow()
            
            try:
                alert(f"new PI created with LEVEL: {self.level} at ENTRYPOINT: {result['entrypoint']} and ENDPOINT: {Endpoint.load(self.endpointId).url if self.endpointId else None}. \n PI: {newPI.content}\n ID: {newPI.dbid}",'new-pi')
            except:
                quicklog("what? apis") 
            if self.PIHistory:
                self.PIHistory.append(newPI)
            else:
                self.PIHistory = [newPI]
            self.saveToDB(True)

    def makeUpdatedPI(self):
        'only call if we have lock!'
        endpoint = Endpoint.load(self.endpointId)
        api = API.load(endpoint.api_id)
        historical_pis = [f"instruction: {pi.content}, \nsuccess rate: {pi.success_rate}" for pi in self.PIHistory]
        if len(historical_pis)>4:
            self.active=False
            self.saveToDB(lock=True)
            return
        prompt = UpdatedPIPrompt(
            similar_errors=self.errorDescriptions[-3:],
            auth_variables=list(api.auth_info.keys()),
            other_info = api.other_info,
            documentation=endpoint.baseDocumentation,
            levels = PI_LEVELS,
            entrypoints = PI_ENTRY_POINTS,
            historical_preventative_instructions=historical_pis,
            successful_example = endpoint.general_example
        )
        log, result = prompt.execute()
        LLMLog.fromGuruLogObject(log, self.dbid)

        if result['investigation']:
            alert(f"Investigation requested for error tracker while attempting to improve the PI: \n ET_dbid: {self.dbid}.\n example error: {self.errorDescriptions[0]}\nhistorical_pis: {historical_pis}",'investigation')
        endpoint = Endpoint.load(self.endpointId)
        newPI = PreventativeInstruction(content=result['new_preventative_instruction'], reference_errors=self.errorDescriptions[-3:],errorTracker_id=self.dbid,success_rate_at_activation=sum(endpoint.binary_history)/max(len(endpoint.binary_history),1))
        newPI.saveToDB()
        self.PIHistory.append(newPI)
        self.saveToDB(lock=True)

    @staticmethod
    def merge(new, old):
        '''
        merges the new one onto the old one and deletes the new one.
        '''
        quicklog("running merge!")
        from app import app
        if acquire_lock_with_backoff(ErrorTrackerModel, old) and acquire_lock_with_backoff(ErrorTrackerModel, new):
            with app.app_context():
                try:
                    old = db.session.get(ErrorTrackerModel, old)
                    new = db.session.get(ErrorTrackerModel, new)
                    if not old or not new:
                        alert(f"unable to merge error trackers: {old}, {new}",'exception')
                        return
                    for historical_error in new.historical_errors:
                        historical_error.error_tracker_id = old.id
                    old.count += new.count
                    db.session.delete(new)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    alert(f"unable to merge error trackers: {old}, {new}",'exception')
                finally:
                    db.session.remove()
                    release_lock(ErrorTrackerModel, old)
                    release_lock(ErrorTrackerModel, new)
        else:
            alert(f"unable to acquire locks to merge error trackers: {old}, {new}",'exception')
            

    def saveToDB(self, lock=False):
        #TODO: multiple embeddings per ET? Or remake them if a new PI is made? upsert checks for changes in metadata!
        Session = getSession()
        with Session() as session:
            if self.dbid:
                if not lock and not acquire_lock_with_backoff(ErrorTrackerModel, self.dbid):
                    raise Exception("Unable to acquire lock to save ErrorTracker.")

                try:
                    model = session.get(ErrorTrackerModel,self.dbid)
                    if model:
                        if self.PIHistory and not self.active:
                            print(f"somehow we aren't active but do have a PI!")
                            self.active = True
                            self.active_at = datetime.utcnow()
                        # Update ErrorTracker fields
                        model.endpoint_id = self.endpointId
                        model.active = self.active
                        model.count = self.count
                        model.api_id = self.api_id
                        model.level = self.level
                        model.entrypoint = self.entrypoint
                        model.active_at = self.active_at



                        session.commit()
                    else:
                        raise Exception("ErrorTrackerModel with specified dbid not found.")
                finally:
                    if not lock:
                        release_lock(ErrorTrackerModel, self.dbid)
            else:
                n_id = str(uuid.uuid4())
                model = ErrorTrackerModel(id=n_id, endpoint_id=self.endpointId,count=self.count, level=self.level, entrypoint = self.entrypoint, api_id = self.api_id)
                session.add(model)
                self.dbid = n_id
                session.commit()
                

    


    def delete(self):
        try:
            result = ErrorTrackerModel.remove(self.dbid)
        except Exception as e:
            pass

    def refresh(self):
        Session = getSession()
        with Session() as session:
            # Fetch the updated error tracker model from the database
            error_tracker_model = session.get(ErrorTrackerModel, self.dbid)
            if not error_tracker_model:
                # Handle the case where the model is no longer in the database, if necessary
                return

            if error_tracker_model.preventative_instructions:
                pi_history = PreventativeInstruction.loadSet([pi.id for pi in error_tracker_model.preventative_instructions])
            else:
                pi_history = []
            # Update this instance's attributes with fresh data from the database
            self.endpointId = error_tracker_model.endpoint_id
            self.active = error_tracker_model.active
            self.count = error_tracker_model.count
            self.PIHistory = pi_history
            self.errorDescriptions = error_tracker_model.getErrorDescriptions()
            self.dbid = error_tracker_model.id  # This likely remains unchanged, but included for completeness
            self.api_id = error_tracker_model.api_id if error_tracker_model.api_id else None
            self.level = error_tracker_model.level if error_tracker_model.level else 'endpoint'
            self.entrypoint = error_tracker_model.entrypoint if error_tracker_model.entrypoint else 'generate_code'
            self.active_at = error_tracker_model.active_at



    @classmethod
    def load(cls, error_tracker_id):
        Session = getSession()
        with Session() as session:
            error_tracker_model = session.get(ErrorTrackerModel, error_tracker_id)
            if not error_tracker_model:
                return None  # or handle as appropriate
            if error_tracker_model.preventative_instructions:
                pis = session.query(PreventativeInstructionModel).with_entities(PreventativeInstructionModel.id).filter(PreventativeInstructionModel.errorTracker_id==error_tracker_model.id).order_by(PreventativeInstructionModel.created_at).all()
                pi_history = PreventativeInstruction.loadSet([pi[0] for pi in pis])
            else:
                pi_history = []
            return cls(
                endpointId=error_tracker_model.endpoint_id,
                active=error_tracker_model.active,
                count=error_tracker_model.count,
                PIHistory=pi_history,
                errorDescriptions=error_tracker_model.getErrorDescriptions(),
                dbid=error_tracker_model.id,
                api_id = error_tracker_model.api_id if error_tracker_model.api_id else None,
                level = error_tracker_model.level if error_tracker_model.level else 'endpoint',
                entrypoint = error_tracker_model.entrypoint if error_tracker_model.entrypoint else 'generate_code',
                active_at = error_tracker_model.active_at
            ) 
        
    @classmethod
    def loadSet(cls, error_tracker_ids, session=None):
        # Ensure the list is not empty
        if not error_tracker_ids:
            return []
        Session = getSession()
        with Session() as session:
            # Fetch all ErrorTrackerModel instances at once
            error_tracker_models = session.query(ErrorTrackerModel).filter(ErrorTrackerModel.id.in_(error_tracker_ids)).all()

            # Prepare a list to hold the class instances
            error_trackers = []

            # Iterate over each model instance to create class instances
            for etm in error_tracker_models:
                pi_history = []
                if etm.preventative_instructions:
                    pi_history = PreventativeInstruction.loadSet([pi.id for pi in etm.preventative_instructions])

                # Create an instance of the class for each ErrorTrackerModel
                error_tracker_instance = cls(
                    endpointId=etm.endpoint_id,
                    active=etm.active,
                    count=etm.count,
                    PIHistory=pi_history,
                    errorDescriptions=etm.getErrorDescriptions(),
                    dbid=etm.id,
                    api_id=etm.api_id if etm.api_id else None,
                    level=etm.level if etm.level else 'endpoint',
                    entrypoint=etm.entrypoint if etm.entrypoint else 'generate_code',
                    active_at = etm.active_at
                )
                error_trackers.append(error_tracker_instance)

                
            return error_trackers

class PreventativeInstruction:
    def __init__(self, errorTracker_id, content="",reference_errors = [], dbid = None, success_rate_at_activation=0, successes = 0, failures = 0):
        self.success_rate_at_activation = success_rate_at_activation
        self.successes = successes
        self.failures = failures
        self.content = content
        self.reference_errors=reference_errors
        self.dbid = dbid
        self.errorTracker_id = errorTracker_id

    def success_rate(self):
        if not self.successes or not self.failures:
            if self.successes:
                return 1
            else:
                return 0
        return self.successes/(self.failures + self.successes)
    

    def saveToDB(self, lock=False):
        Session = getSession()
        with Session() as session:
            if self.dbid:
                if not lock and not acquire_lock_with_backoff(PreventativeInstructionModel, self.dbid):
                    raise Exception("Unable to acquire lock to save PreventativeInstruction.")

                try:
                    model = session.get(PreventativeInstructionModel, self.dbid)
                    if model:
                        # Update PreventativeInstruction fields
                        model.content = self.content
                        model.reference_errors = str(self.reference_errors)
                        model.success_rate_at_activation = self.success_rate_at_activation
                        model.successes = self.successes
                        model.failures = self.failures
                        model.errorTracker_id = self.errorTracker_id

                        session.commit()
                    else:
                        raise Exception("PreventativeInstructionModel with specified dbid not found.")
                finally:
                    if not lock:
                        release_lock(PreventativeInstructionModel, self.dbid)
            else:
                model = PreventativeInstructionModel(content=self.content, reference_errors=str(self.reference_errors), errorTracker_id = self.errorTracker_id, success_rate_at_activation=self.success_rate_at_activation)
                session.add(model)
                session.commit()
                self.dbid = model.id


    @staticmethod
    def markFailure(pi_id):
        try:
            if acquire_lock_with_backoff(PreventativeInstructionModel, pi_id):
                pi = PreventativeInstruction.load(pi_id)
                pi.failures += 1
                pi.saveToDB(lock=True)
                release_lock(PreventativeInstructionModel, pi_id)
            else:
                raise Exception("Unable to acquire lock to mark failure for PreventativeInstruction.")
        except Exception as e:
            release_lock(PreventativeInstructionModel, pi_id)
            raise e
        
    @classmethod
    def load(cls, pi_id):
        Session = getSession()
        with Session() as session:
            pi_model = session.get(PreventativeInstructionModel, pi_id)
            if not pi_model:
                return None  # or handle as appropriate

            return cls(
                content=pi_model.content,
                reference_errors=ast.literal_eval(pi_model.reference_errors) if pi_model.reference_errors else [],
                success_rate_at_activation=pi_model.success_rate_at_activation,
                successes=pi_model.successes,
                failures=pi_model.failures,
                dbid=pi_model.id,
                errorTracker_id=pi_model.errorTracker_id
            )
        
    #database efficiency
    @classmethod
    def loadSet(cls, pi_ids, session=None):
        # Make sure the list is not empty to avoid unnecessary database calls
        if not pi_ids:
            return []
        Session = getSession()
        with Session() as session:
            # Fetch all PreventativeInstructionModels at once using the provided IDs
            pi_models = session.query(PreventativeInstructionModel).filter(PreventativeInstructionModel.id.in_(pi_ids)).all()

            # Convert each PreventativeInstructionModel to a PreventativeInstruction instance
            pi_list = []
            for pi_model in pi_models:
                pi_instance = cls(
                    content=pi_model.content,
                    reference_errors=ast.literal_eval(pi_model.reference_errors) if pi_model.reference_errors else [],
                    success_rate_at_activation=pi_model.success_rate_at_activation,
                    successes=pi_model.successes,
                    failures=pi_model.failures,
                    dbid=pi_model.id,
                    errorTracker_id=pi_model.errorTracker_id
                )
                pi_list.append(pi_instance)





#TODO: allow endpoints to be marked as inactive if their success rate is too low and not improving, and notify the tenant or the dev team.
class Endpoint:
    def __init__(self, url, baseDocumentation = "", trained = False, purpose = "", dbid = None, api_id = None, errorTrackers = None, binary_history=[],active=True, general_example = '', general_example_is_hq = False) -> None:
        self.dbid = dbid
        self.url = url
        self.baseDocumentation = baseDocumentation
        self.purpose = purpose
        self.api_id = api_id
        self.errorTrackers = errorTrackers
        self.binary_history = binary_history
        self.active=active
        self.trained = trained
        self.general_example = general_example
        self.general_example_is_hq = general_example_is_hq


    def getPurposeFromDocumentation(self, conversation_id = None):
        prompt = GetPurposeFromDocumentationPrompt(
            API_name=API.load(self.api_id).name,
            endpoint_url = self.url,
            documentation=self.baseDocumentation,
            example_data=EndpointModel.getExample(self.dbid,requested_data='{"example":"get one example from the endpoint."}')
        )
        log, result = prompt.execute()
        LLMLog.fromGuruLogObject(log, conversation_id)

        self.purpose = result['choices'][0]['message']['content']
        self.saveToDB()

    def mergeETs(self, conversation_id=None):
        #use top k to find the most similar errors, then prompt to merge them.

        prompt = MergeETsPrompt(
            errors=[err.errorDescriptions[0] for err in self.errorTrackers]
        )
        log, result = prompt.execute()
        if conversation_id:
            LLMLog.fromGuruLogObject(log, conversation_id)
        #if multithreading has lead to a repeat error tracker (or a general error has)
        merges = result.get('merges',None)
        if merges:
            print(f"merges found!{merges}")
            mergeList = []
            for merge in merges:
                mergeList.append([et for i,et in enumerate(self.errorTrackers) if i in merge])
            for merge in mergeList:

                keep:ErrorTracker = None
                try:
                    for i, et in enumerate(merge):
                        if i == 0:
                            if keep:
                                release_lock(ErrorTrackerModel, keep.dbid)
                            keep:ErrorTracker = et
                            if not acquire_lock_with_backoff(ErrorTrackerModel, keep.dbid):
                                raise Exception("unable to acquire lock on the kept ET in merge!")
                        else:
                            for err in et.errorDescriptions:
                                keep.errorDescriptions.append(err)
                                keep.count += 1
                            et.delete()
                    if keep.count>ACTIVATION_THRESHOLD:
                        keep.active = True
                        keep.active_at = datetime.utcnow()
                        keep.makeNewPI(conversation_id=conversation_id)

                except Exception as e:
                    if keep:
                        release_lock(ErrorTrackerModel,keep.dbid)
                    if conversation_id:
                        addLog(conversation_id, 'MERGE ERROR', {'content':f'unable to execute merge for {merge}, due to {e}'})
                finally:
                    keep.saveToDB(lock=True)
                    release_lock(ErrorTrackerModel, keep.dbid)
    
            
               
        
                                   

        
        

    def markSuccess(self):
        queue_mark_success.delay(self.dbid, [pi.dbid for pi in self.getPI()])
    
    def getPI(self, entrypoint='all'):
        pis = [tracker.getPI() for tracker in self.errorTrackers if tracker.active and (tracker.entrypoint == entrypoint or entrypoint=='all')]
        return [pi for pi in pis if pi]
        

    def getState(self):
        return f"""
        url: {self.url},
        baseDocumentation: {self.baseDocumentation},
        error trackers: {[str(err) for err in self.errorTrackers]}
...
        """


    def saveToDB(self, lock=False):
        Session = getSession()
        with Session() as session:
            if self.dbid:
                if not lock and not acquire_lock_with_backoff(EndpointModel, self.dbid):
                    raise Exception("Unable to acquire lock to save Endpoint.")

                try:
                    model = session.get(EndpointModel, self.dbid)
                    if model:
                        # Update Endpoint fields
                        model.url = self.url
                        model.baseDocumentation = self.baseDocumentation
                        model.purpose = self.purpose
                        model.api_id = self.api_id
                        model.binary_history = str(self.binary_history)
                        model.active = self.active
                        model.trained = self.trained
                        session.commit()
                        if not model.pc_id and model.purpose:
                            model.upsert()
                    else:
                        raise Exception("EndpointModel with specified dbid not found.")
                except Exception as e:
                    raise e
                finally:
                    if not lock:
                        release_lock(EndpointModel, self.dbid)
            else:
                model = EndpointModel(url=self.url, trained=self.trained, active = self.active, baseDocumentation=self.baseDocumentation, purpose=self.purpose, api_id = self.api_id)
                model.upsert()
                session.add(model)
                session.commit()
                self.dbid = model.id

    @classmethod
    def load(cls, endpoint_id, session=None):
        from models import EndpointModel

        Session = getSession()
        with Session() as session:
            endpoint_model = session.get(EndpointModel, endpoint_id)
            if not endpoint_model:
                return None  # or handle as appropriate
            
            out= cls(
                url=endpoint_model.url,
                baseDocumentation=endpoint_model.baseDocumentation,
                purpose=endpoint_model.purpose,
                dbid=endpoint_model.id,
                api_id=endpoint_model.api_id,
                binary_history=eval(endpoint_model.binary_history),
                active = endpoint_model.active,
                trained = endpoint_model.trained,
                general_example_is_hq = endpoint_model.general_example_is_hq,
                general_example = endpoint_model.general_example
            )
            et_ids = []
            if endpoint_model.error_trackers:
                et_ids = [et.id for et in endpoint_model.error_trackers]
        if et_ids:
            error_trackers = ErrorTracker.loadSet(et_ids)
        else:
            error_trackers = []
        out.errorTrackers = error_trackers
        return out
        
    @classmethod
    def loadSet(cls, endpoint_ids, session=None):
        from models import EndpointModel

        # Ensure the list is not empty
        if not endpoint_ids:
            return []
        
        endpoints = []
        Session = getSession()
        with Session() as session:
            # Fetch all EndpointModel instances at once
            endpoint_models = session.query(EndpointModel).filter(EndpointModel.id.in_(endpoint_ids)).all()

            for endpoint_model in endpoint_models:
                if endpoint_model.error_trackers:
                    error_trackers = ErrorTracker.loadSet([et.id for et in endpoint_model.error_trackers])
                else:
                    error_trackers = []
                # Create an instance of Endpoint for each EndpointModel
                endpoint_instance = cls(
                    url=endpoint_model.url,
                    baseDocumentation=endpoint_model.baseDocumentation,
                    purpose=endpoint_model.purpose,
                    dbid=endpoint_model.id,
                    api_id=endpoint_model.api_id,
                    errorTrackers=error_trackers,
                    binary_history=eval(endpoint_model.binary_history) if endpoint_model.binary_history else [],
                    active=endpoint_model.active,
                    trained=endpoint_model.trained,
                    general_example_is_hq=endpoint_model.general_example_is_hq,
                    general_example=endpoint_model.general_example
                )
                endpoints.append(endpoint_instance)
    
            return endpoints

        
    
        
class API:
    def __init__(self, name, tenant_id, tenant_api_dbid = '', active = True, general_instructions = '',use_description='',auth_info={},other_info={},endpoints=[], dbid=None, change_log = '') -> None:
        self.name = name
        self.endpoints = endpoints
        self.auth_info = auth_info
        self.other_info = other_info
        self.dbid = dbid
        self.tenant_id=tenant_id
        self.general_instructions = general_instructions
        self.use_description = use_description
        self.tenant_api_dbid = tenant_api_dbid
        self.change_log = change_log
    
    def runInitialTraining(self, conversation_id = None, direct_docs = None):
        #runs initial training. 

        existing_urls = [endpoint.url for endpoint in self.endpoints]
        if direct_docs:
            connection_string = os.getenv('AZURE_CONNECTION_STRING')
            container_name = 'api-docs'  
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            container_client = blob_service_client.get_container_client(container_name)
            
            blob_client = container_client.get_blob_client(direct_docs)
            
            sorted_docs={}
            
            for blob in container_client.list_blobs(name_starts_with=direct_docs):
                blob_client = container_client.get_blob_client(blob)
                stream = blob_client.download_blob()
                name = blob.name.split('/')[1]
                if name == 'general.txt':
                    sorted_docs['general_instructions'] =stream.readall().decode("utf-8")
                else:
                    sorted_docs[name] =stream.readall().decode("utf-8")
        else:
            docs = self.getDocumentationFromDB()
        

            prompt = SortDocumentationPrompt(
                api_name = self.name,
                existing_categories = existing_urls + ['general_instructions'],
                documentation = docs,
                other_info = self.other_info,
                auth_info = list(self.auth_info.keys())
            )

            log, sorted_docs = prompt.execute()
            if conversation_id:
                LLMLog.fromGuruLogObject(log, conversation_id)
            print(f"sorted docs.")
        if conversation_id:
            addLog(conversation_id,'Documentation Created',sorted_docs)
        if sorted_docs.get('insufficient_documentation', None):
            alert(f"did not start training for {self.name} for tenant_id {self.tenant_id}! SortDocumentation says: \n{sorted_docs['insufficient_documentation']}",'general')
            return
        general_instructions = sorted_docs['general_instructions']
        self.general_instructions = json.dumps(general_instructions)
        self.saveToDB()
        del(sorted_docs['general_instructions'])
        for url,docs in sorted_docs.items():
            if url in existing_urls:
                endpoint = [endpoint for endpoint in self.endpoints if endpoint.url==url][0]
                endpoint.baseDocumentation += f"\n{json.dumps(docs)}" 
            else:
                print(f"creating endpoint: {url}. dbid: {self.dbid}")
                new_ep = Endpoint(url,json.dumps(docs),api_id=self.dbid, active=False)
                new_ep.saveToDB()

        if conversation_id:
            addLog(conversation_id,f'Beginning to train endpoints. PIR link: http://4.246.137.240:5001/pir/{self.tenant_api_dbid}',{})
        begin_training.delay(self.tenant_api_dbid, conversation_id)


    def getDocumentationFromDB(self):
        from app import app
        from packages.db.database import db
        with app.app_context():
            try:
                api = db.session.get(APIModel, self.dbid)
                return api.raw_documentation
            except Exception as e:
                db.session.rollback()
                raise e
            finally:
                db.session.remove()

        
    def saveDocumentationToDB(self, doc_string, session):
        if session:
            api = session.get(APIModel, self.dbid)
            api.raw_documentation = doc_string
        else:
            from app import app
            from packages.db.database import db
            with app.app_context():
                try:
                    api = db.session.get(APIModel, self.dbid)
                    api.raw_documentation = doc_string
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    raise e
                finally:
                    db.session.remove()

    def processQueryset(self, queryset, callback_task, callback_args, conversation_id=None, max_tries = 2, training=False):
        '''
        output results:
        [[{key:reason} (bad requests)], 
        {'success': {}, 'failed': [['example_discount_code', 'get one example from the /admin/api/2021-01/discount_codes/lookup.json endpoint.']]}]
        '''
        os.environ['tenant_id'] = str(self.tenant_id)
        #TODO: include the ability to say that the descripions are insufficient for the task, and start an investigation.
        print("processing queryset...")
        if not self.use_description and self.getActive() and not training:
            createUseDescription.delay(self.tenant_api_dbid,conversation_id)
        requested_data=[{'request':query.requested_data,'purpose':query.purpose} for query in queryset.queries]

        if conversation_id:
            addLog(conversation_id=conversation_id, type='Query Request',content=
                                    {
                                        'requested_data':requested_data,
                                        'tapi': str(self.tenant_api_dbid)
                                    })
        ets = ErrorTrackerModel.getErrorTrackerIDsForSimilarRequests(requested_data, api_id = self.dbid, entrypoints = ['endpoint_selection'], include_levels=['api','global'])
        if ets:
            ets = ErrorTracker.loadSet(ets)
            pis = [et.getPI() for et in ets]
            pi_text = [pi.content for pi in pis if pi] + DEFAULT_PIs['endpoint_selection']
        else:
            pi_text = ''
        available_endpoints = self.getAvailableEndpointsString(queryset)
        prompt = ProcessQuerySetPrompt(
            requested_data=requested_data,
            API_name=self.name,
            available_endpoints=available_endpoints,
            endpoint_selection_pis = pi_text
        )
        log, result = prompt.execute()
        if conversation_id:
            LLMLog.fromGuruLogObject(log, conversation_id)
        if conversation_id:
            addLog(conversation_id, 'Queryset Processed', result)
        print(f"raw: {result}", flush = True)

        variable_dict = result['variable_names']

        del(result['variable_names'])
        bad_requests = []
        if result.get('bad_requests',None) and result['bad_requests']:
            bad_requests = result.get('bad_requests')
        
        del(result['bad_requests'])
        print("queryset processed. initiating queries...")
        print(result, flush = True)
        quicklog(f"current training: {training}")
        cgroup = group(
            [process_bad_requests.s(
                    bad_requests,
                    self.tenant_api_dbid,
                    conversation_id)] 
            + 
            [run_query.s(
                    url=endpoint_name, 
                    max_tries=max_tries,
                    api_id= self.tenant_api_dbid, 
                    tenant_id= os.environ['tenant_id'], 
                    variable_dict = {key: value for key, value in variable_dict.items() if key in variable_names}, 
                    conversation_id = conversation_id,
                    training = training
                ).set(
                    queue='high_priority' if not training else 'low_priority',
                    time_limit=30*60, # timeout. increase speed: shorter timeout with a retry? timeout is high due to exponential backoff in the case of a failure.
                    max_retries = 0 if not training else 8
                        )
        for endpoint_name, variable_names in result.items() if variable_names])
        if conversation_id:
            addLog(conversation_id, 'Querys Initialized', {})
        
        result = chord(cgroup)(callback_task.s(*callback_args))
            
                



    def getAvailableEndpointsString(self, queryset):
        if not self.getActive():
            return "\n".join([f"\nurl : {endpoint.url} \nsummary:\n{endpoint.purpose}\n" for endpoint in self.endpoints if (endpoint.active or not endpoint.trained)])
        if len(self.endpoints) < 10:
            return "\n".join([f"\nurl : {endpoint.url} \nsummary:\n{endpoint.purpose}\n" for endpoint in self.endpoints if (endpoint.active or not endpoint.trained)])
        else:
            requested_data = [query.requested_data for query in queryset.queries]
            ids = EndpointModel.getBestIDsForQuery(requested_data, self.dbid)
            endpoints = [ep for ep in self.endpoints if ep.dbid in ids]
            if len(endpoints) < 10:
                quicklog(f"not enough endpoints found for queryset! Used getBestIDsForQuery. api_id: {self.dbid}")
                return "\n".join([f"\nurl : {endpoint.url} \nsummary:\n{endpoint.purpose}\n" for endpoint in self.endpoints if (endpoint.active or not endpoint.trained)])


            return "\n".join([f"\nurl : {endpoint.url} \nsummary:\n{endpoint.purpose}\n" for endpoint in endpoints if (endpoint.active or not endpoint.trained)])


    def tryQuery(self, url, endpoint, variable_dict,err_list,conversation_id):
        success=False
        print(f"auth variables: {list(self.auth_info.keys())}")
        ets = endpoint.errorTrackers + ErrorTracker.loadSet(ErrorTrackerModel.getGlobalIds('generate_code')) + ErrorTracker.loadSet(ErrorTrackerModel.getAPILevelIds(self.dbid,'generate_code'))
        pis = [et.getPI() for et in ets if et.entrypoint=='generate_code' and et.active]
        pi_text = '\n'.join([pi.content for pi in pis if pi] + DEFAULT_PIs['generate_code'])
        #TODO: tenant specific PIs
        prompt = GeneratePythonPrompt(
                url=url,
                general_instructions=self.general_instructions,
                base_documentation=endpoint.baseDocumentation,
                example_data=EndpointModel.getExample(endpoint.dbid,requested_data=str(variable_dict)),
                preventative_instructions= pi_text,
                auth_variables=list(self.auth_info.keys()),
                other_info= self.other_info,
                requested_data=variable_dict,
                errors = f"this is the previous attempt and the result: {err_list[-1]}" if err_list else ""
            )
        log, response = prompt.execute()
        if conversation_id:
            LLMLog.fromGuruLogObject(log, conversation_id)

        #TODO: both of these are not active. the code generation llm seems to pick them too much.
        if response.get('additional_information_needed', ''):
            quicklog(f"additional info needed: {response.get('additional_information_needed')}\n{url}: {variable_dict}")
            return 'ERROR','more info needed!',[f'more info needed: {response.get("additional_information_needed")}'],False
        #TODO: handle this case. Endpoint selection PI!
        if response.get('wrong_endpoint', ''):
            quicklog(f"wrong endpoint! {url}: {variable_dict}")
            return 'ERROR','wrong endpoint!',["wrong endpoint!"],False
        
        code = response['code_to_execute']
        split = code.split('\n')
        code = '\n'.join([s for s in split if 'access_token =' not in s])
        context = self.auth_info.copy()
        context.update({key:None for key, value in variable_dict.items()})
        try:
            timeout = 60
            print(f"executing code: {code}")
            exec(code, context, context)
            results = {key:context[key] for key, value in variable_dict.items()}
            for request, result in results.items():
                if len(str(result))>10000:
                    #TODO: manage this more dynamically - for example: llm can change the query structure, or kick back to the conversational one...
                    raise Exception(f"result for {request} was too long! This system has a max of 10000 characters for each result variable! Save 'results too long! try a more specific query' to the results variable when its too long.")
            print("success!")
            success = True
        except Exception as e:
            try:
                res = traceback.format_exception(e)
                print(f"exception occurred in executing code: {res}")
                error = '\n'.join(res[-3:])
            except Exception as e2:
                error = str(e)
            
            err_list.append({"code":code, "error":error})
            process_error.delay(endpoint_id = endpoint.dbid, error_description=str({"code":code, "error":error}), data_request=str(variable_dict), tenant_id=os.environ['tenant_id'],conversation_id=conversation_id)
            
        
        results = {key:context[key] for key, value in variable_dict.items()}

        
        return code,results,err_list, success        


    def processDocumentation(self, documentation = ""):
        if not documentation:
            print("processing base documentation...")
            documentation = self.documentation

    def setActive(self, active):
        from models import TenantAPIModel
        Session = getSession()
        with Session() as session:
            tapi = session.get(TenantAPIModel, self.tenant_api_dbid)
            tapi.active = active
            session.commit()

    def getActive(self):
        from app import app
        from models import TenantAPIModel
        Session = getSession()
        with Session() as session:
            tapi = session.get(TenantAPIModel, self.tenant_api_dbid)
            return tapi.active

    def saveToDB(self, lock=False):
        Session = getSession()
        with Session() as session:
            if self.dbid:
                if not lock and not acquire_lock_with_backoff(APIModel, self.dbid):
                    raise Exception("Unable to acquire lock to save API.")

                try:
                    model = session.get(APIModel, self.dbid)
                    if model:
                        # Update API fields
                        model.API_name = self.name
                        model.general_instructions=self.general_instructions
                        model.use_description = self.use_description
                        model.change_log = self.change_log
                        session.commit()
                    else:
                        raise Exception("APIModel with specified dbid not found.")
                finally:
                    if not lock:
                        release_lock(APIModel, self.dbid)
            else:
                model = APIModel(API_name=self.name, use_description=self.use_description, general_instructions=self.general_instructions)
                session.add(model)
                session.commit()
                if not model.id:
                    alert(f"unable to save APIModel for {self.name}!","exception")
                self.dbid = model.id
                
                session.commit()
                
    
    def getAuthInfo(self):
        from models import TenantAPIModel
        Session = getSession()
        with Session() as session:
                api = session.get(TenantAPIModel, self.tenant_api_dbid)
                api.updateAuthInfo()
                self.auth_info=api.auth_info
                self.other_info=api.other_info

    @classmethod
    def load(cls, tenant_api_model_id, session = None):#TODO: remove session as an option

        Session = getSession()
        from models import APIModel, TenantAPIModel
        with Session() as session:
            tapim = session.get(TenantAPIModel, tenant_api_model_id)
            if not tapim:
                print(f"no API found for {tenant_api_model_id}. Assuming that is an api_id, and using environ tenant_id...")
                apim = session.get(APIModel, tenant_api_model_id)
                if not apim:
                    raise Exception(f"unable to find EITHER kind of apimodel for {tenant_api_model_id}")
                tapim = session.query(TenantAPIModel)\
                    .filter(TenantAPIModel.tenant_id==os.environ.get('tenant_id'))\
                    .filter(TenantAPIModel.api_id==apim.id)\
                    .order_by(desc(TenantAPIModel.created_at))\
                    .first()
            else:
                apim = session.get(APIModel, tapim.api_id)
                os.environ['tenant_id']=str(tapim.tenant_id)
            tapim.updateAuthInfo()
            auth_info = tapim.auth_info
            other_info = tapim.other_info
            tenant_id=tapim.tenant_id

            if not apim:
                raise Exception(f"no API found for {tapim.api_id}")
            name = apim.API_name
            if apim.endpoints:
                endpoints = Endpoint.loadSet([ep.id for ep in apim.endpoints])
            else:
                endpoints = []
                
            return cls(
                name=name,
                endpoints=endpoints,
                auth_info=auth_info,
                tenant_id=tenant_id,
                tenant_api_dbid=tapim.id,
                dbid=apim.id,
                general_instructions=apim.general_instructions,
                use_description=apim.use_description,
                other_info = other_info,
                change_log = apim.change_log if apim.change_log else ''
            )

    def generate_html_report(self):
        html_report = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #F4F4F8; }}
                .main-content {{ padding: 20px; }}
                .api-info {{ background-color: #E8EAF6; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
                .api-name {{ font-size: 24px; font-weight: bold; color: #3F51B5; }}
                .endpoint {{ background-color: #FFFFFF; padding: 15px; border-radius: 5px; margin-bottom: 15px; }}
                .endpoint-url {{ font-size: 18px; font-weight: bold; color: #0D47A1; margin-bottom: 10px; }}
                .success-stats {{ color: #388E3C; font-weight: bold; }}
                .pi-content {{ color: #D32F2F; font-weight: bold; font-size: 16px; }}
                .toggle {{ cursor: pointer; color: #2196F3; font-weight: bold; }}
                .editable, .dropdown {{ background-color: #f9f9f9; border: 1px solid #ccc; padding: 10px; border-radius: 4px; width: calc(100% - 24px); box-sizing: border-box; }}
                .collapsible-content {{ padding: 5px; margin-top: 5px; border-left: 3px solid #2196F3; font-size: 14px; display: none; }}
                .editable collapsible-content {{ padding: 5px; margin-top: 5px; border-left: 3px solid #2196F3; font-size: 14px; display: none; }}

                .error-tracker, .pi {{ margin-left: 20px; }}
                .error-stat {{ font-size: 16px; color: #F44336; font-weight: bold; }}
                .info-icon {{ font-size: 12px; }}
                pre {{
                    white-space: pre-wrap;       /* Since CSS 2.1 */
                    white-space: -moz-pre-wrap;  /* Mozilla, since 1999 */
                    white-space: -pre-wrap;      /* Opera 4-6 */
                    white-space: -o-pre-wrap;    /* Opera 7 */
                    word-wrap: break-word;       /* Internet Explorer 5.5+ */
                }}
            </style>
            <script>
                function toggleContent(id) {{
                    var x = document.getElementById(id);
                    if (x.style.display === 'none' || x.style.display === '') {{
                        x.style.display = 'block';
                    }} else {{
                        x.style.display = 'none';
                    }}
                }}
            </script>
        </head>
        <body>
            <div class='main-content'>
                <button onclick="submitChanges()" class="submit-button">Submit Changes</button>

                <div class='api-info'>
                    <div class='api-name'>API Report: {self.name}</div>
                    <div> active: {self.getActive()} </div>
                    <div>Total Endpoints: {len(self.endpoints)}</div>
                    <div class='toggle' onclick='toggleContent("apiPurpose")'>Toggle API Purpose</div>
                    <div class='editable collapsible-content' id='apiPurpose' contenteditable="true"><pre>{self.use_description}</pre></div>
                    <div class='toggle' onclick='toggleContent("apiGeneral")'>Toggle General Instructions</div>
                    <div class='editable collapsible-content' id='apiGeneral' contenteditable="true"><pre>{self.general_instructions}</pre></div>
                </div>
        """

        # Global Error Trackers
        global_error_trackers = ErrorTracker.loadSet(ErrorTrackerModel.getGlobalIds())
        html_report += self._generate_error_tracker_section(global_error_trackers, 1, "Global")

        # API-level Error Trackers
        api_error_trackers = ErrorTracker.loadSet(ErrorTrackerModel.getAPILevelIds(self.dbid))
        html_report += self._generate_error_tracker_section(api_error_trackers, 1, "API")

        for i, endpoint in enumerate(self.endpoints):
            example_data_id = f"exampleData{i}"
            base_documentation_id = f"baseDocumentation{i}"
            success_rate = sum(endpoint.binary_history)/max(len(endpoint.binary_history),1)
            rolling_rate = [sum(endpoint.binary_history[-10*i: None if i == 1 else -10*(i-1)])/max(len(endpoint.binary_history[-10*i: None if i == 1 else -10*(i-1)]), 1) for i in range(1, int(len(endpoint.binary_history)/10)+1)]
            pis = endpoint.getPI()
            html_report += f"""
        <div class='endpoint'>
            <div class='endpoint-url' contenteditable="true">Endpoint: {endpoint.url} - - - ID: {endpoint.dbid}</div>
            
            <!-- Editable Purpose -->
            <div>Purpose: <div contenteditable="true" class="editable" id="purpose_{endpoint.dbid}"><pre>{endpoint.purpose}<pre></div></div>
            
            <div>Trained: 
                <select id="trained_{endpoint.dbid}" class="dropdown">
                    <option value="True" {"selected" if endpoint.trained else ""}>True</option>
                    <option value="False" {"selected" if not endpoint.trained else ""}>False</option>
                </select>
            </div>

            <div>Active: 
                <select id="active_{endpoint.dbid}" class="dropdown">
                    <option value="True" {"selected" if endpoint.active else ""}>True</option>
                    <option value="False" {"selected" if not endpoint.active else ""}>False</option>
                </select>
            </div>
            <div class='success-stats'>Success Rate: {success_rate:.2f}</div>
            <div class='success-stats'>Rolling Success Rate (sets of 10, most recent first): {[f'{r:.2f}' for r in rolling_rate]}</div>
            <div>PI Count: {len(pis)}</div>
            <div>Total Calls: {len(endpoint.binary_history)}</div>
            
            <!-- Editable Example Data -->
            <div class='toggle' onclick='toggleContent("{example_data_id}")'>Toggle Example Data</div>
            <div contenteditable="true" class="editable collapsible-content" id='{example_data_id}'><pre>'QUALITY':{endpoint.general_example_is_hq}<br>{endpoint.general_example}<pre></div>
            
            <!-- Editable Base Documentation -->
            <div class='toggle' onclick='toggleContent("{base_documentation_id}")'>Toggle Base Documentation</div>
            <div contenteditable="true" class="editable collapsible-content" id='{base_documentation_id}'><pre>{endpoint.baseDocumentation}<pre></div>
        </div>
    """
            # Endpoint-level Error Trackers
            endpoint_error_trackers = endpoint.errorTrackers  # Assuming this is how you get endpoint-level ETs
            html_report += self._generate_error_tracker_section(endpoint_error_trackers, i, f"{len(endpoint_error_trackers)} ")
        html_report += '''</div><script>
                function submitChanges() {
                    const currentUrl = window.location.href;

                    // Extract the UUID from the URL
                    const segments = currentUrl.split('/');
                    const uuid = segments[segments.length - 1];
                    const apiInfo = {
                        name: document.querySelector('.api-name').textContent.replace('API Report: ', ''),
                        use_description: document.getElementById('apiPurpose').textContent,
                        general_instructions: document.getElementById('apiGeneral').textContent,
                        endpoints: [],
                        tapi_dbid: uuid
                    };

                    document.querySelectorAll('.endpoint').forEach(endpointElement => {
                        const dbid = endpointElement.querySelector('.endpoint-url').textContent.split(' - - - ID: ')[1];
                        const endpoint = {
                            url: endpointElement.querySelector('.endpoint-url').textContent.replace('Endpoint: ', '').split(' - - - ID: ')[0],
                            dbid: dbid,
                            purpose: endpointElement.querySelector(`[id^='purpose_']`).textContent, // Adjusted selector
                            trained: endpointElement.querySelector(`[id^='trained_']`).value === "True",
                            active: endpointElement.querySelector(`[id^='active_']`).value === "True",
                            exampleData: endpointElement.querySelector('.editable.collapsible-content[id^="exampleData"] pre').textContent, // Adjusted selector
                            baseDocumentation: endpointElement.querySelector('.editable.collapsible-content[id^="baseDocumentation"] pre').textContent, // Adjusted selector
                            successRate: parseFloat(endpointElement.querySelector('.success-stats').textContent.replace('Success Rate: ', '')),
                            ets: [],
                            pis: []
                        };

                         // Error Trackers
                        endpointElement.querySelectorAll('.error-tracker').forEach(etElement => {
                            const et = {
                                count: parseInt(etElement.querySelector('.error-stat').textContent.replace('Error Tracker - (Count: ', '').replace(')', '')),
                                errorDescriptions: etElement.querySelector('.collapsible-content pre').textContent
                            };
                            endpoint.ets.push(et);
                        });

                        // (PIs)
                        endpointElement.querySelectorAll('.pi').forEach(piElement => {
                            const pi = {
                                content: piElement.querySelector('.pi-content').textContent.replace('Most Recent PI Content: ', '').replace('Older PI Content: ', ''),
                                successRate: parseFloat(piElement.querySelector('div:nth-child(2)').textContent.replace('Success Rate: ', '')),
                                successRateAtActivation: parseFloat(piElement.querySelector('div:nth-child(3)').textContent.replace('Success Rate at activation: ', '')),
                                timesUsed: parseInt(piElement.querySelector('div:nth-child(4)').textContent.replace('Times Used: ', '')),
                                errorRecurrences: parseInt(piElement.querySelector('div:nth-child(5)').textContent.replace('Error Recurrences: ', '')),

                                referenceErrors: piElement.querySelector('.collapsible-content pre') ? piElement.querySelector('.collapsible-content pre').textContent.split(', ') : []
                            };
                            endpoint.pis.push(pi);
                        });

                        // Add endpoint to apiInfo
                        apiInfo.endpoints.push(endpoint);
                    });

                    // POST request with fetch
                    fetch(segments[0] + '/admin', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({'request_type':'update_api', 'data':apiInfo})
                    })
                    .then(response => response.text())
                    .then(data => {
                        console.log('Success:', data);
                        alert('Changes submitted successfully!');
                    })
                    .catch((error) => {
                        console.error('Error:', error);
                        alert('An error occurred while submitting the changes.');
                    });
                }
            </script>
            '''
        html_report += "</body></html>"

        return html_report

    def _generate_error_tracker_section(self, error_trackers, n, section_name):
        active_ets = [et for et in error_trackers if et.active]
        inactive_ets = [et for et in error_trackers if not et.active]

        active_et_html = f"<div style='background-color: #E0F7FA;'><div class='toggle' onclick='toggleContent(\"active{n}{section_name}ETs\")'>Active Error Trackers ({len(active_ets)})</div><div class='collapsible-content' id='active{n}{section_name}ETs'>"
        inactive_et_html = f"<div style='background-color: #FCE4EC;'><div class='toggle' onclick='toggleContent(\"inactive{n}{section_name}ETs\")'>Inactive Error Trackers ({len(inactive_ets)})</div><div class='collapsible-content' id='inactive{n}{section_name}ETs'>"

        for et in active_ets:
            active_et_html += self._generate_error_tracker_details(et, "active", section_name, et.dbid)
        active_et_html += "</div></div>"

        for et in inactive_ets:
            inactive_et_html += self._generate_error_tracker_details(et, "inactive", section_name, et.dbid)
        inactive_et_html += "</div></div>"

        return active_et_html + inactive_et_html

    def _generate_error_tracker_details(self, et, status, section_name, et_id):
        from app import app
        from packages.db.database import db
        with app.app_context():
            etm = ErrorTrackerModel.query.get(et_id)
        et_html = f"""
        <div class='error-tracker'>
            <div>
                Error Tracker - (Count: {et.count}) id: {et.dbid}<br>
                Recurrences when not used as PI: {etm.num_unused_errors}<br>
                Entrypoint: {et.entrypoint}<br>
                <div class='toggle' onclick='toggleContent(\"{status}2_et_{section_name}_{et_id}\")'>
                    Example Errors
                </div>
            </div>
            <div class='collapsible-content' id='{status}2_et_{section_name}_{et_id}'>
                <pre>{etm.getErrorDescriptions()[:10]}</pre>
            </div>
            <div>
                {self._generate_pi_section(et, status)}
            </div>
        </div>
        """
        return et_html

    def _generate_pi_section(self, error_tracker, status):
        pi_html = ""
        Session = getSession()
        with Session() as session:
            PIHistory = session.query(PreventativeInstructionModel).filter(PreventativeInstructionModel.errorTracker_id == error_tracker.dbid).order_by(PreventativeInstructionModel.updated_at.desc()).all()
        if PIHistory:
            # Most recent PI
            recent_pi = PIHistory[0]
            pi_html += self._generate_individual_pi(recent_pi, error_tracker.dbid, "Most Recent PI")

            # Older PIs
            if len(PIHistory) > 1:
                older_pis_id = f"olderPis_{error_tracker.dbid}"
                pi_html += f"<div class='toggle' onclick='toggleContent(\"{older_pis_id}\")'>Toggle Older PIs</div>"
                pi_html += f"<div class='collapsible-content' id='{older_pis_id}'>"

                for pi in PIHistory[1:]:
                    pi_html += self._generate_individual_pi(pi, error_tracker.dbid, "Older PI")

                pi_html += "</div>"
        return pi_html

    def _generate_individual_pi(self, pi, error_tracker_id, pi_type):
        assert(isinstance(pi, PreventativeInstructionModel))
        reference_errors_id = f"referenceErrors_{error_tracker_id}_{pi.id}"

        pi_html = f"""
        <div class='pi'>
            <div class='pi-content' contenteditable="true">{pi_type} Content: {pi.content}</div>
            <div>Success Rate: {pi.successes/max((pi.failures+pi.successes),1)}</div>
            <div>Success Rate at activation: {pi.success_rate_at_activation}</div>
            <div>Times Used: {pi.successes + pi.failures}</div>
            <div>Error Recurrences: {pi.failures}</div>
            <div class='toggle' onclick='toggleContent(\"{reference_errors_id}\")'>Toggle Reference Errors</div>
            <div class='collapsible-content' id='{reference_errors_id}'><pre>{pi.reference_errors}</pre></div>
        </div>
        """
        return pi_html
    
DEFAULT_PIs={
    'generate_code':[
        "Minimize comments.",
        "Don't forget to import all necessary packages.",
        "NEVER catch exceptions.",
        "Raise a proper HTTPError if the API doesn't respond with 200 via response.raise_for_status()",
        "Each result variable must be less than 10000 characters. If the result is too long, save 'results too long! Try a more specific query' to the variablename",
        "Always include names over ids.",
        "Be careful to consider anything in the documentation that indicates a required field.",
        "To avoid 429 errors, consider using exponential backoff with a max wait of 10 seconds.",],
    'endpoint_selection':[
        "Do not include endpoints which don't need to be used to acquire the requested_data."
        ]
    }

#TODO: reevaluate the tenant_id global variable.
#CRITICAL: this needs to be on high prio in training, but should be low prio on production!
@celery.task(queue='high_priority', max_retries=4)
def process_error(error_description, tenant_id = None, endpoint_id=None, api_id=None, data_request = None, conversation_id=None, used_et_ids = None, used_et_timestamp = None, training=False):
    '''
    error_description should include the code.
    '''
    if not used_et_ids:
        used_et_ids = []
    Session = getSession()
    try:
        tries = 0
        max_tries = 4
        lock_expiration_time = 3/2*sum([2.5**i for i in range(1, max_tries+1)])

        with Session() as session:
            while True:
                if endpoint_id:
                    handler_id = str(uuid.uuid4())
                    # Construct an UPDATE statement
                    stmt = (
                        update(EndpointModel).
                        where(EndpointModel.id == endpoint_id, EndpointModel.error_handler == "none").
                        values(error_handler=handler_id).
                        returning(EndpointModel.id)
                    )
                    result = session.execute(stmt)
                    session.commit()

                    # Check if the row was updated
                    if result.fetchone():
                        #set error_handler_updated_at to now
                        try:
                            stmt = (
                                update(EndpointModel).
                                where(EndpointModel.id == endpoint_id).
                                values(error_handler_updated_at=datetime.now())
                            )
                            session.execute(stmt)
                            session.commit()
                        except Exception as e:
                            try:
                                stmt = (
                                    update(EndpointModel).
                                    where(EndpointModel.id == endpoint_id).
                                    values(error_handler='none').
                                    returning(EndpointModel.id)
                                )
                                session.execute(stmt)
                                session.commit()
                            except Exception as e:
                                session.rollback()
                                alert(f"unable to remove lock!:\n{traceback.format_exception(e)}",'exception')
                                raise
                            alert(f"uncaught exception in process_error:2. Queueing a retry with 20 second delay:\n{traceback.format_exception(e)}",'exception')
                            raise

                        # The row was updated, so we can process the error
                        break
                    if tries in [0,max_tries-1]:
                        #check to see if the error_handler_updated_at is too old
                        epm = session.get(EndpointModel, endpoint_id)
                        if epm.error_handler_updated_at and (datetime.now()-epm.error_handler_updated_at).total_seconds() > lock_expiration_time:
                            quicklog(f"lock expired for error processor for endpoint {endpoint_id}! taking over...")
                            epm.error_handler = handler_id
                            epm.error_handler_updated_at = datetime.now()
                            session.commit()
                            break
                    tries+=1
                    time.sleep(2.5**tries)
                    if tries>max_tries:
                        raise Exception(f"Unable to acquire lock for endpoint {endpoint_id}.")

        

        new_he = HistoricalError(
            error_description=error_description,
            data_request=data_request
        )
        if endpoint_id:
            new_he.endpoint_id = endpoint_id
            if not api_id:
                api_id = Endpoint.load(endpoint_id).api_id

        with Session() as session:
            session.add(new_he)
            session.commit()
            error_description = new_he.error_description
            new_he_id = new_he.id

        if tenant_id:
            os.environ['tenant_id'] = str(tenant_id)
        print(f"recieved error. processing")
        if conversation_id:
            addLog(conversation_id,'ProcessingError...',{'content':'error'})

        if not endpoint_id and not api_id:
            raise Exception("No endpoint or api id provided. Unable to process error.")
        
        #occurs iff this error came from a query attempt.
        if endpoint_id:
            ep = Endpoint.load(endpoint_id, session)
            ep.binary_history.append(0)
            ep.saveToDB()
            if not api_id:
                api_id = ep.api_id
        

        #dynamically construct arguments for getErrorTrackerIDsForSimilarDescriptions as keyword arguments
        args = {
            'error_description': error_description,
            'include_matching_descriptions': True
        }
        if api_id:
            args['api_id'] = api_id
        if endpoint_id:
            args['endpoint_id'] = endpoint_id


        matching_descriptions, et_ids = ErrorTrackerModel.getErrorTrackerIDsForSimilarDescriptions(**args)
        addLog(conversation_id, 'Matching Descriptions Query Result', {'matches':f'{matching_descriptions}','error_description':error_description,'args':args})
        if et_ids:
            ets = ErrorTracker.loadSet(et_ids)
            existing_errors = '---END ERROR---\n'.join([f"ERROR {i}:\n{et.errorDescriptions[0]}" for i, et in enumerate(ets)])
        else:
            existing_errors = ''

        with Session() as session:
            new_he = session.get(HistoricalError, new_he_id)
            #TODO: tenant ets?
            et_id = None
            if et_ids:
                prompt = CategorizeErrorPrompt(
                    error_description=error_description,
                    existing_errors=existing_errors
                )
                log, result = prompt.execute()
                if conversation_id:
                    LLMLog.fromGuruLogObject(log, conversation_id)
                if result['existing_error'] >= 0:
                    message = f"matching error found. Using existing error tracker."
                    et_id = et_ids[result['existing_error']]
                    new_he.error_tracker_id = et_id
                    new_he_id = new_he.id
                    new_he.upsertToPinecone()
                    session.commit()
            if not et_id:
                print(f"no matching ets found. Creating new error tracker, upserting")
                message = f"no matching ets found. new et created."
                etm = ErrorTrackerModel()
                etm.count = 0
                if endpoint_id:
                    etm.endpoint_id = endpoint_id
                else:
                    etm.entrypoint = 'initial_data_request'
                if api_id:
                    etm.api_id = api_id
                session.add(etm)
                session.flush()
                new_he.error_tracker_id = etm.id
                et_id = etm.id
                new_he.upsertToPinecone()
                session.commit()
        if et_id:
            et = ErrorTracker.load(et_id)
        if not et:
            alert(f"unable to load error tracker with id: {et_ids[result['existing_error']]}! retrying...",'exception')
            raise Exception(f"unable to load error tracker with id: {et_ids[result['existing_error']]}! retrying...")
            
        if et.dbid in used_et_ids:
            addLog(conversation_id, f'{message}. increasing count.', {'original_error':error_description,'matching_error':et.errorDescriptions[0]})
            et.increaseCount(historical_error_id=new_he_id, conversation_id=conversation_id)
            return
        else:
            if et.active:
                #use the datetime.utcnow object on the et and compare to the used_et_timestamp, if provided.
                if used_et_timestamp and et.active_at and et.active_at > used_et_timestamp:
                    addLog(conversation_id, 'Matching Error Found: pi was not active yet, but is now..', {'original_error':error_description,'matching_error':et.errorDescriptions[0]})
                    quicklog("this was wasted as the pi wasn't active yet. If this happens a lot we need to wait for errors to process before running more queries.")
                    return
                else:
                    addLog(conversation_id, 'Matching Error Found: pi was not used.', {'original_error':error_description,'matching_error':et.errorDescriptions[0]})
                    et_metrics_update.delay(et.dbid, 'num_unused_errors', 1)
                    #TODO: this should consider which ets were active at the time of the error!
                    alert(f"an error tracker was not used, and the error recurred! consider increasing k... et_dbid:{et.dbid}","pi-error")
                    return
            else:
                addLog(conversation_id, f'{message} increasing count.', {'original_error':error_description,'matching_error':et.errorDescriptions[0]})
                
                et.increaseCount(historical_error_id=new_he_id, conversation_id=conversation_id)
                return
    except Exception as e:
        if conversation_id:
            addLog(conversation_id, 'Error Processing Error', {'error':str(e)})
        alert(f"error processing error: {e}. endpoint_id: {endpoint_id}.",'exception')
        raise           
    finally:
        with Session() as session:
            epm = session.get(EndpointModel, endpoint_id)
            if epm.error_handler == handler_id:
                epm.error_handler = 'none'
                session.commit()
            else:
                if epm.error_handler == 'none':
                    pass
                else:
                    alert("error handler was changed during processing!",'exception')


#TODO: strip out POST endpoints!
@celery.task(queue='low_priority')
def begin_training(tapi_id, conversation_id = None):
    Switch.set('investigations','True')
    api = API.load(tapi_id)
    task_group = group(getExample.s(endpoint.dbid, api.tenant_id, conversation_id) for endpoint in api.endpoints)
    task_group.apply_async()


@celery.task(queue='low_priority')
def completed_training(results,*args, **kwargs):
    try:
        endpoint_id = args[0]
        tenant_id = args[1]
        conversation_id = args[2]
        endpoint = Endpoint.load(endpoint_id)

        if conversation_id:
            addLog(conversation_id,'Final set training complete: ',{'results':str(results)})
        print(f"result for set two training for {endpoint.url}:{results}")
        os.environ['tenant_id'] = str(tenant_id)
        endpoint = Endpoint.load(endpoint_id)
        api = API.load(endpoint.api_id)
        endpoint = Endpoint.load(endpoint_id)
        endpoint.trained = True
        endpoint.active = True
        endpoint.saveToDB()

        print("finding purposes for endpoint...")
        endpoint.getPurposeFromDocumentation(conversation_id)

        endpoint = Endpoint.load(endpoint_id)
        if conversation_id:
            addLog(conversation_id,f'Endpoint training complete: {endpoint.url}',{'trained':[endpoint.trained for endpoint in api.endpoints]})
        
        api = API.load(endpoint.api_id)
        if all([endpoint.trained for endpoint in api.endpoints]):
            if conversation_id:
                addLog(conversation_id,'All Endpoints Complete! making use description for API.',{})
            createUseDescription.delay(api.tenant_api_dbid, conversation_id)
            api.setActive(True)
            Switch.set('investigations','False')
            if conversation_id:
                addLog(conversation_id,'Training complete.',{})
            alert(f"initial training completed for \napi: {api}",'general')
    except Exception as e:
        raise e

@celery.task(queue = 'low_priority',max_retries = 5)
def getExample(endpoint_id, tenant_id, conversation_id = None):
    os.environ['tenant_id'] = tenant_id
    from models import EndpointModel
    Session = getSession()
    with Session() as session:
        endpoint = session.get(EndpointModel, endpoint_id)
        qs = Queryset()
        q = Query(
            purpose = 'get an example',
            requested_data = f'get one example from the {endpoint.url} endpoint.'
        )
        qs.queries = [q]
        apim = session.get(APIModel, endpoint.api_id)
        api = API.load(apim.id)

        api.processQueryset(qs, max_tries = 6, conversation_id=conversation_id, training = True,callback_task=run_initial_queries, callback_args=[endpoint_id, tenant_id, conversation_id])


@celery.task(queue='low_priority')
def run_initial_queries(results, *args, **kwargs):
    total_sets = 5
    endpoint_id = args[0]
    tenant_id = args[1]
    conversation_id = args[2]
        
    os.environ['tenant_id'] = str(tenant_id)
    endpoint = Endpoint.load(endpoint_id)
    api = API.load(endpoint.api_id)


    endpoint = Endpoint.load(endpoint_id)
    api = API.load(endpoint.api_id)


    prompt = GetTrainingQuerysetPrompt(
        API_name=api.name,
        endpoint_url=endpoint.url,
        endpoint_documentation=endpoint.baseDocumentation,
        num_requests = 4
    )
    log, results = prompt.execute()

    if conversation_id:
        LLMLog.fromGuruLogObject(log, conversation_id)

    queryset = Queryset()
    queryset.queries = []
    for data in results['requests']:
        q = Query(
            purpose = '',
            requested_data= data
        )
        queryset.queries.append(q)
    
    api.processQueryset(queryset, training=True, conversation_id=conversation_id, max_tries = 3, callback_task=run_set_two, callback_args = [str(endpoint.dbid), tenant_id, conversation_id, 2, total_sets])



@celery.task(queue='low_priority')
def run_set_two(results, *args, **kwargs):
    endpoint_id = args[0]
    tenant_id = args[1]
    conversation_id = args[2]
    set_num = args[3]
    final_set = args[4]
    os.environ['tenant_id'] = str(tenant_id)
    endpoint = Endpoint.load(endpoint_id)
    #check to see if the endpoint has a 0% success rate
    if len(endpoint.binary_history)>10 and sum(endpoint.binary_history) == 0:
        endpoint.active = False
        endpoint.trained = True
        endpoint.saveToDB()
        alert(f"endpoint {endpoint.url} has a 0% success rate. deactivating.",'pi-error')
        return
    print(f"result for set {set_num-1}/{final_set} training for {endpoint.url}:{results}")
    if conversation_id:
        addLog(conversation_id,f'Set {set_num-1}/{final_set} Training complete: ',{'results':str(results)})
    
    if conversation_id:
        addLog(conversation_id,f'Merging ETs from set {set_num-1}...',{})
    api = API.load(endpoint.api_id)


    prompt = GetTrainingQuerysetPrompt(
        API_name=api.name,
        endpoint_url=endpoint.url,
        endpoint_documentation=endpoint.baseDocumentation,
        num_requests = 4
    )
    log, results = prompt.execute()
    if conversation_id:
        LLMLog.fromGuruLogObject(log, conversation_id)
    queryset = Queryset()
    queryset.queries = []
    for data in results['requests']:
        q = Query(
            purpose = '',
            requested_data= data
        )
        queryset.queries.append(q)
    if set_num < final_set:
        set_num += 1
        api.processQueryset(queryset, training=True,conversation_id=conversation_id, max_tries = 3, callback_task=run_set_two, callback_args = [str(endpoint.dbid), tenant_id, conversation_id, set_num, final_set])
    else:
        api.processQueryset(queryset,training=True,conversation_id=conversation_id, max_tries = 3, callback_task = completed_training, callback_args= [str(endpoint.dbid), tenant_id, conversation_id])

        

@celery.task(queue='low_priority')
def createUseDescription(tenant_api_dbid, conversation_id=None):
    api = API.load(tenant_api_dbid)
    prompt = GenerateAPIUseDescriptionPrompt(
        api_name = api.name,
        endpoint_description_tenant_example_trios = '\n\n'.join([f"{endpoint.url}: \npurpose: {endpoint.purpose}\n"+f"example data: {endpoint.general_example}" for endpoint in api.endpoints])
    )
    log, summary = prompt.execute()

    if conversation_id:
        LLMLog.fromGuruLogObject(log, conversation_id)

    api.use_description = summary['choices'][0]['message']['content']
    api.saveToDB()

@celery.task(queue='high_priority')
def process_bad_requests(bad_requests, tapi_id, conversation_id=None):
    quicklog("TODO: process bad requests.")
    return bad_requests

@celery.task(queue='high_priority', bind=True)
def run_query(self, api_id, url, variable_dict, tenant_id, conversation_id=None, max_tries = 4, training = True):
    from packages.ipythongather import gather_with_ipython
    if Switch.get("ipythonqueries"):
        tries = 0 
        while tries < max_tries:
            try:
                result = gather_with_ipython(api_id, url, variable_dict, tenant_id, conversation_id, max_tries, training = training)
            except Exception as e:
                #this case occurs
                if isinstance(e, Retry):
                    try:
                        quicklog(f"Retry raised internally in run_query. Retrying with delay. {self.request.retries}")
                        self.retry(countdown=30)
                    except Exception as e:
                        if isinstance(e, MaxRetriesExceededError):
                            alert(f"MAX RETRIES EXCEEDED! INTERNAL! retries: {self.request.retries} endpoint: {url}. giving up...",'exception')
                            return {'failed':{key:'timeout' for key,value in variable_dict.items()}}
                        if isinstance(e, Retry):
                            raise

                if isinstance(e, TimeoutError):
                        
                    try:
                        alert(f"Timeout while running query. Retrying...",'exception')
                        self.retry()
                    except Exception as e:
                        if isinstance(e, MaxRetriesExceededError):
                            alert(f"MAX RETRIES EXCEEDED! endpoint: {url}. giving up...",'exception')
                            return {'failed':{key:'timeout' for key,value in variable_dict.items()}}
                        if isinstance(e, Retry):
                            raise
                else:
                    try:
                        alert(f"Error while running query: {traceback.format_exception(e)}. Retrying...",'exception')
                        self.retry()
                    except Exception as e:
                        if isinstance(e, MaxRetriesExceededError):
                            alert(f"Error while running query: MAX RETRIES EXCEEDED! {traceback.format_exception(e)}. giving up...",'exception')
                            return {'failed':{key:f'error: unknown' for key,value in variable_dict.items()}}
                        if isinstance(e, Retry):
                            raise
            output = {}
            output['failed'] = []
            output['success'] = []
            for key, value in result.items():
                if 'error' in value.lower():
                    output['failed'].append({key: value})
                else:
                    output['success'].append({key: value})
            variable_dict = {key: variable_dict[key] for key, value in result.items() if 'error' in value.lower()}
            if not output['failed']:
                addLog(conversation_id, f'Ipython Query Complete: {url}', result)
                return output
            tries += 1
        addLog(conversation_id, f'Ipython Query Failed: {url}', result)
        return output 
    try:
        os.environ['tenant_id'] = tenant_id
        api = API.load(api_id)
        api.getAuthInfo()
        #print(f"current auth info: {api.auth_info}")
        err_list = []
        confirmed_results={}
        to_gather = variable_dict
        additional = {}

        #only gather a few at a time. TODO: replace this via IPython.
        while len(to_gather) > 3:
            item_to_move = list(to_gather.items())[0]
            del to_gather[item_to_move[0]]
            additional[item_to_move[0]] = item_to_move[1]
        tries = 0
        data_replaced = False
        while (to_gather or additional) and tries < max_tries:
            #move additional into to_gather
            while len(to_gather) < 3 and additional:
                err_list = []
                tries = 0
                item_to_move = list(additional.items())[0]
                del additional[item_to_move[0]]
                to_gather[item_to_move[0]] = item_to_move[1]
            matches = [endpoint for endpoint in api.endpoints if endpoint.url==url]
            if not matches or len(matches)>1:
                #TODO: why? this could be an endpoint selection error...
                raise Exception(f"error while getting endpoint from url! \nmatches:{[endpoint.url for endpoint in matches]}\nurl:{url}\nendpoints:{[endpoint.url for endpoint in api.endpoints]}")
            endpoint:Endpoint = matches[0]
            endpoint = Endpoint.load(endpoint_id=endpoint.dbid) #make sure we have the latest info on the endpoint!
            tries+=1
            code, results, err_list, success = api.tryQuery(url, endpoint, to_gather, err_list, conversation_id)
            print(f"attempt {tries}/{max_tries}\nresult:{results}")
            response = ''
            #TODO: figure out how to separate out the affected variables.
            if code == 'ERROR':
                return {'failed':to_gather, 'reason':results}
            #check for secondary errors.
            if success:
                print("Checking for secondary errors...")
                prompt = CheckDataResultPrompt(
                    variable_dict=variable_dict,
                    code=code,
                    results=results,
                    auth_variables=list(api.auth_info.keys()),
                    documentation= f"{endpoint.baseDocumentation} {api.general_instructions}" 
                )
                log, response = prompt.execute()

                if conversation_id:
                    LLMLog.fromGuruLogObject(log, conversation_id)
                print(f"response for CheckDataResult: {response}")



                new_errs = []
                investigations = [{variable_name: analysis['details']} for variable_name, analysis in response.items() if analysis['status']=='investigate' and variable_name in list(results.keys())]

                if Switch.get('investigations') and investigations:

                    investigation_results = runInvestigation(
                                        json.dumps({
                                                'requested_investigations':investigations,
                                                'requested_data':{variable_name:variable_dict[variable_name] for variable_name in [list(i.keys())[0] for i in investigations]}, 
                                                'executed_code':code,
                                                'original_results':results,
                                                'endpoint documentation':LLM.cleanStringForLLM(json.dumps(endpoint.baseDocumentation)), 
                                                'general documentation':api.general_instructions,
                                                'additional instructions':LLM.cleanStringForLLM([pi.content for pi in endpoint.getPI()])
                                            }),
                                            {
                                                'results':{
                                                    list(i.keys())[0]:{
                                                    'conclusive':'true or false, depending on whether you were able to reach a conclusion about the investigation.',
                                                    'original_result_is_accurate': 'true or false, depending on the result of your investigation. Should be true only if the original result provided the data for "requested_data."',
                                                    'error_identified':'the error that was made in the original code, if any, otherwise omit this field. Include the lines of code that contained the original error, as well as a description of the error.',
                                                    'corrected_result':'the corrected result, if you were able to correct it - otherwise, omit this field. This should be the actual data response to the "requested_data," or should not be included at all.',
                                                    'additional_notes':'additional notes, if necessary.',
                                                    'is_auth_error':'true or false'}
                                                    for i in investigations
                                                }
                                            },
                                        tapi_id = api.tenant_api_dbid,
                                        parent_id=conversation_id)
                    for variable, investigation_result in investigation_results['results'].items():
                        try:
                            if (not investigation_result['conclusive']) or (isinstance(investigation_result['conclusive'], str) and investigation_result['conclusive'].lower()=='false'):
                                if str(investigation_result.get('is_auth_error','false')).lower() !='false':
                                    response[variable] ={
                                        'status':'error',
                                        'details':"auth error suspected!"
                                    }
                                    quicklog("auth error suspected after investigation!")
                                else:
                                    quicklog(f'inconclusive investigation! original result for this one is: {investigation_result.get("original_result_is_accurate","")} TODO: summarize and vectordb these, compare them.')
                                    if investigation_result.get('original_result_is_accurate',''):
                                        response[variable] ={
                                        'status':'good'
                                    }
                                    else:
                                        prompt = DescribeErrorPrompt(
                                            code=code,
                                            error=investigation_result.get('error_identified',''),
                                            documentation = LLM.cleanStringForLLM(json.dumps(endpoint.baseDocumentation)) + str(api.general_instructions)
                                        )
                                        log, summary = prompt.execute()
                                        response[variable] ={
                                            'status':'error',
                                            'details':summary
                                        }
                            else:
                                if investigation_result['original_result_is_accurate'] and not (isinstance(investigation_result['original_result_is_accurate'], str) and investigation_result['conclusive'].lower()=='false'):
                                    response[variable]['status'] ='good'
                                else:
                                    #TODO: this doesn't work! The llm is providing a description. Or hallucinating.
                                    '''if investigation_result.get('corrected_result',''):
                                        data_replaced=True
                                        response[variable]['status'] ='good'
                                        results[variable] = investigation_result.get('corrected_result','')'''
                                    if investigation_result.get('error_identified',''):
                                        new_errs.append(f"For {variable}, {investigation_result['error_identified']}")
                                        process_error.delay(endpoint_id = endpoint.dbid, error_description=investigation_result['error_identified'], data_request = str({variable_dict:variable_dict[variable]}),tenant_id = os.environ['tenant_id'], conversation_id=conversation_id)
                                    else:
                                        response[variable]['status'] ='error'
                        except Exception as e:
                            response[variable]['status'] ='good'
                            addLog(conversation_id, f'FAILED INVESTIGATION: {variable}', {'content':f'treating as correct. Error: {traceback.format_exception(e)}'})
                elif investigations:
                    addLog(conversation_id, f'Investigations requested, but are off!', {'content':investigations})
                if investigations:
                    for variable_name, analysis in response.items():
                        if analysis['status'] == 'investigate':
                            response[variable_name]['status'] = 'good'

                for variable_name, analysis in response.items():
                    if variable_name not in list(results.keys()):
                        quicklog("still happening. Not breaking shit anymore tho. 1515.")
                        continue
                    try:
                        if analysis['status']=='good':
                            print(f"confirmed result of {variable_name}.")
                            confirmed_results.update({variable_name:{'data':results[variable_name],'notes':response.get('details','')}})
                            del to_gather[variable_name]
                            endpoint.markSuccess()
                            endpoint = Endpoint.load(endpoint.dbid)
                            '''if not endpoint.exampleData and not data_replaced:
                                #TODO: delay vetExample
                                endpoint.exampleData = f"code: \n{code}\n\n result:\n{confirmed_results}"
                                endpoint.saveToDB()'''
                        elif analysis['status']=='error':
                            print(f"error found in {variable_name}.")
                            print(f"starting task to learn from it with this description: {analysis['details']}")
                            process_error.delay(endpoint_id = endpoint.dbid, error_description=analysis['details'], tenant_id = os.environ['tenant_id'], conversation_id=conversation_id)
                            new_errs.append(f"For {variable_name}, {analysis['details']}")
                            '''if tries == max_tries:
                                if conversation_id:
                                    addLog(conversation_id, 'RETURNING FAULTY RESPONSE?', {'content': 'the third attempt resulted in a secondary error. Treating it like it was accurate...'})
                                confirmed_results.update({variable_name:results[variable_name]})
                                to_gather = [x for x in to_gather if x[0]!=variable_name]'''
                    except Exception as e:
                        quicklog(f"key error. response: {response}, results: {results}")
                        raise e
                                                
                err_list.append({'code':code,'errors':new_errs})
            if conversation_id:
                addLog(conversation_id=conversation_id, type=f'Query Attempt: {endpoint.url}',content=
                                        {
                                            'query':variable_dict,
                                            'code':code,
                                            'result':results,
                                            'analysis':response if response else err_list,
                                            'auth variables': api.auth_info
                                        })


        output = {}
        output['success'] = confirmed_results
        output['failed'] = to_gather 
        
        return output
    except Exception as e:
        alert(f'exception processing query: {url}:{variable_dict} for {conversation_id}: \n {traceback.format_exception(e)}','exception')
        if conversation_id:
            addLog(conversation_id=conversation_id, type=f'Query Attempt FAILED DUE TO EXCEPTION! {url}',content=
                                    {
                                        'exception':f"{traceback.format_exception(e)}"
                                    })
        try:
            output = {}
            output['success'] = confirmed_results
            output['failed'] = to_gather 
            
            return output
        except Exception as e:
            return {'failed due to exception!':variable_dict}


@celery.task(queue='high_priority', max_retries=7, bind=True)
def queue_mark_success(self, endpoint_id, pi_ids=None, num=1):
    #TODO: do this without a lock via an atomic operation.
    if not acquire_lock_with_backoff(EndpointModel, endpoint_id, base_delay=0.2):
        raise Exception(f"Failed to acquire lock for endpoint: {endpoint_id}")
    else:
        try:
            endpoint = Endpoint.load(endpoint_id)
            for _ in range(num):
                endpoint.binary_history.append(1)
            endpoint.saveToDB(lock=True)
            release_lock(EndpointModel, endpoint_id)

            if not pi_ids:
                pis = endpoint.getPI()
                pi_ids = [pi.dbid for pi in pis if pi]
            
            Session = getSession()
            with Session() as session:
                session.execute(
                    update(PreventativeInstructionModel)
                    .where(PreventativeInstructionModel.id.in_(pi_ids))
                    .values(successes=PreventativeInstructionModel.successes + num)
                )
                session.commit()
        except Exception as e:
            alert(f"exception in queue_mark_success. retrying in 60...: {traceback.format_exception(e)}",'exception')
            self.retry(countdown=60, exc=e)
        finally:
            release_lock(EndpointModel, endpoint_id)

#TODO:
@celery.task(queue = 'small_tasks')
def process_bad_request_as_error(tapi_id, bad_request, conversation_id=None):
    #TODO!!!!
    if conversation_id:
        addLog(conversation_id, 'bad request as error', {'br':bad_request})
    pass



#TODO: make the auth info integrate with the tool!
#always has: conclusive
def runInvestigation(context, output_dict, tapi_id, parent_id):
    from guru.Flows import Conversation
    from main_assistant import DEFAULT_ASSIGNMENT_JSON
    from models import TenantAPIModel, DBConversation
    from app import app
    from packages.tasks import emit_from_celery

    initial_message = "Begin."
    investigation_assignments = {}
    investigation_assignments['assignments'] = [assignment.copy() for assignment in DEFAULT_ASSIGNMENT_JSON['assignments'] if 'investigation' in assignment['id']]
    investigation_assignments['personality'] = "you are an investigator in a system that queries data trying to solve an issue through experimentation."
    with app.app_context():
        dbc = DBConversation(
                    tenant_id = '-1',
                    status = 'processing',
                    conversation_type = 'internal'
                )
        db.session.add(dbc)
        db.session.commit()
        n_id = dbc.id
        if not n_id:
            quicklog("no id!!!")
        if parent_id:
            addLog(parent_id, 'Investigation Running...', {'context':context,'output_dict':output_dict, 'conversation_id':str(n_id)})
        else:
            quicklog("this investigation has no parent!" +str({'conversation_id':str(n_id)}))
        tapim = db.session.get(TenantAPIModel, tapi_id)
        tapim.updateAuthInfo()
        os.environ['tenant_id'] = tapim.tenant_id
        auth = [tapim.auth_info, tapim.other_info]

        #TODO: make this json mode!
        conversation = Conversation(investigation_assignments, entry_assignment='investigation', conversation_id = n_id)
        
        conversation.currentAssignment.objectives = []
        conversation.currentAssignment.instructions = []
        conversation.currentAssignment.addObjective(f"When you reach your conclusion, respond with a JSON with the following key:value pairs, plus one additional field called 'results' for justifying your conclusion. Respond with the json and nothing more. Your response should be loadable via json.loads().:\n{json.dumps(output_dict)}")
        conversation.currentAssignment.addInstructions(f"this is the auth info that is relevant to the task at hand: {auth}")
        conversation.currentAssignment.addInstructions(f"here is the relevant context for your investigation: {context}")
        conversation.currentAssignment.addInstructions(f"Begin by assuming the documentation is accurate, but explore the possibility that there is an error with it, as well.")
        resp = False
        session = db.session
        try:
            while not resp:
                resp = conversation.getResponse(initial_message)
                result = resp.replace('```json\n','').replace('\n```','')
            result = json.loads(result)
        except Exception as e:
            result = {'conclusive':False,'notes':f'Error: {traceback.format_exception(e)}'}
        
        if parent_id:
            addLog(parent_id, 'Investigation Result', {'response':result, 'investigation_conversation_id':str(n_id), 'messages':str(conversation.currentAssignment.getMessages())})
        
        LLMLog.moveLogs(dbc.id, parent_id)
        
        return result
    

@celery.task(queue='low_priority')
def investigation_test():

    api = API.load('9596569a-1d96-476d-b2fb-7894fe1fbc55')
    endpoint = Endpoint.load('f09badbf-3f44-4d68-9bea-bfd6b89b0284')
    quicklog(runInvestigation(
        {
            'requested_investigation':"Gather the necessary data from the endpoint. You have a limited number of calls that you can make to the code running tool (8), but also have a limit to the size of the output from your code (5000 characters). Try to be mindful and intentional with how you use these resources. Save the results to the variables in the environment to the variable names given to you. You do not need to view the entire contents - just verify the contents with a spot-check.",
            'endpoint documentation':LLM.cleanStringForLLM(json.dumps(endpoint.baseDocumentation)), 
            'general documentation':api.general_instructions,
            'variables_to_gather': {'sales_and_revenue_breakdown': 'total sales, average order value, and month-over-month changes for 2023', 
         'customer_transaction_details': 'frequency of purchases, average spend per customer, and customer segmentation based on spending for 2023', 
         'product_sales_figures': 'total sales, number of units sold, and profit margins for each product sold in 2023', 
         'order_cancellations_and_returns_data': 'the total number and value of cancelled and returned orders, and reasons for cancellations and returns for 2023'},

        },
       {
           "success":"true or false",
           "summary": "summarize your investigation."
       },    
       tapi_id = "9596569a-1d96-476d-b2fb-7894fe1fbc55",
    parent_id="953c605b-97ba-4363-8863-82866f631ecb"
    ))

   
@celery.task(queue='medium_priority')
def queueETIncreaseCount(historical_error_id, dbid, conversation_id = None):
    quicklog(f"had to retry getting a lock! Probably okay as long as this isn't happening a whole ton. et_id: {dbid}")
    et = ErrorTracker.load(dbid)
    if et:
        et.increaseCount(historical_error_id, conversation_id = conversation_id)
    else:
        quicklog("et no longer exists...")

@celery.task(queue='high_priority')
def et_metrics_update(dbid, field, value, tries = 0):
    Session = getSession()
    with Session() as session:
        et = session.get(ErrorTrackerModel, dbid)
        if acquire_lock_with_backoff(ErrorTrackerModel, dbid,max_retries = 3):
            try:
                setattr(et, field, getattr(et, field) + value)
                if field == 'num_unused_errors':
                    if et.num_unused_errors > 5 and et.num_unused_errors/et.count>0.2:
                        alert(f"an error tracker has had more than 5 unused errors with a recurrence rate of 20%! . {et.id}","pi-error")
                session.commit()
            except Exception as e:
                raise 
            finally:
                release_lock(ErrorTrackerModel, dbid)
        else:
            #requeue the task to retry in 10 minutes.
            if tries < 5:
                et_metrics_update.apply_async((dbid, field, value, tries+1), countdown=600)
            else:
                raise Exception(f"unable to acquire lock for et_metrics_update task after {tries} attempts.")
         
       