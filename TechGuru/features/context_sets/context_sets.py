
def getModelContext(session, feature_instance):
    '''
    returns general information about the database setup
    '''
    from models import Model
    all_project_models = session.query(Model).filter(Model.project_id == feature_instance.project_id).all()
    all_project_model_names = [model.name for model in all_project_models]
    return f'''
This project's database is PSQL with SQLAlchemy ORM. 
Session, Base, and engine are available in db.database.py.
The database is set up with the following tables:
{all_project_model_names}.
If you need to see the implementation of an existing table, you can request it via 'get_model_definitions'.
'''
    
def getContext(session, feature_instance, context_name):
    '''
    returns the context for the given context_name
    '''
    if context_name == 'getModelContext':
        return getModelContext(session, feature_instance)
    else:
        raise Exception(f'Context {context_name} not found.')