from models.database import Session
def start_project(json, sid):
    with Session() as session:
        from models import Project, DBConversation
        from packages.tasks import start_conversation_task
        project = Project(
            name = 'test',

        )
        session.add(project)
        session.commit()
        nc = DBConversation(
                    conversation_type='project', 
                    status = 'processing',
                    task = ['processing user input'],
                    socket_id = sid
                    )
        session.add(nc)
        session.commit()
        project.logging_cid = nc.id
        session.commit()

        json['session'] = session
        json['sid'] = sid
        json['conversation_id'] = nc.id
        json['conversation_type'] = 'project'
        json['initial_messages'] = [{'role':'system',
                                     'content':"Begin by asking the user about the project."}]
        json['feature_args'] =[
                {'featureName':'AppBuilder','args':{
                    'project_id':project.id,
                    'object_request_id':'MAIN'
                    }
                    },
            ]
        
        json.pop('request_type')
        json.pop('request_id')
        json.pop('session')
        start_conversation_task.delay(**json)
        nc.sendUpdate('project_started', {'project_id': project.id, 'conversation_id': nc.id})

        return {'content': 'Project Started'}
