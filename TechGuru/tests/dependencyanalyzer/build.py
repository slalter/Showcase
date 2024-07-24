
def build():
    from models import Session
    from models import Project
    from packages.utils import recursive_dict
    from features.appBuilderUtils.dependencyAnalyzer import DependencyAnalyzer
    def getDisplay(object):
        d = recursive_dict(object)
        d['dependencies']= [d.name for d in object.dependencies]
        return d
    with Session() as session:
        da = DependencyAnalyzer('app.py', Session, '6609c9e2-e750-4881-9876-3eb6a54b3f7b')
        da.analyze()
        da.build_dependency_digraph(session)
        digraph:bytes = da.display_dependency_digraph()
        #return html snippet to display the png
        import base64
        return f'<img src="data:image/png;base64,{base64.b64encode(digraph).decode()}"/>'
