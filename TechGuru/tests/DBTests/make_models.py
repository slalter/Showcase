from flask import jsonify

from models import Project, File, Method, Class, Model, Session
from packages.utils import recursive_dict
import traceback
from features.appBuilderUtils.dependencyAnalyzer import DependencyAnalyzer
def test():
    def getDisplay(object):
        d = recursive_dict(object)
        d['dependencies']= [d.name for d in object.dependencies]
        return d
    try:
        da = DependencyAnalyzer('project_skeleton/main.py', Session)
        da.analyze()
    except Exception as e:
        with Session() as session:
            #get all Files, Methods, Classes and Models.
            files = session.query(File).all()
            methods = session.query(Method).all()
            classes = session.query(Class).all()
            models = session.query(Model).all()
            
            return jsonify({
                'error': [t.split('\n') for t in traceback.format_exception(e)],
                'objects':{
                'files': [getDisplay(f) for f in files],
                'methods': [getDisplay(m) for m in methods],
                'classes': [getDisplay(c) for c in classes],
                'models': [getDisplay(m) for m in models]
                }

            })
    with Session() as session:
        project_id = da.project_id
        files = session.query(File).filter_by(project_id=project_id).all()
        methods = session.query(Method).filter_by(project_id=project_id).all()
        classes = session.query(Class).filter_by(project_id=project_id).all()
        models = session.query(Model).filter_by(project_id=project_id).all()
        return jsonify({
            'counts and names':{
                'files': {
                    'count':len(files),
                    'names':[f.name for f in files]
                },
                'methods': {
                    'count':len(methods),
                    'names':[m.name for m in methods]
                },
                'classes': {
                    'count':len(classes),
                    'names':[c.name for c in classes]
                },
                'models': {
                    'count':len(models),
                    'names':[m.name for m in models]
                }

            },
            'objects':{
                'files': [getDisplay(f) for f in files],
                'methods': [getDisplay(m) for m in methods],
                'classes': [getDisplay(c) for c in classes],
                'models': [getDisplay(m) for m in models]
            }
        })
        