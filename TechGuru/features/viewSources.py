from packages.guru.Flows import Feature
from abc import ABC, abstractmethod

class Source(ABC):
    def __init__(self, *args, **kwargs) -> None:
        self.ensureViewSourcesFeature()
        required_args = ['source_code', 'tool_name', 'reference_string_type', 'cite_sources']
        if not all([arg in dir(self) for arg in required_args]):
            raise Exception(f"Source classes must have the following attributes: {required_args} before calling super().__init__.")

        super().__init__(*args, **kwargs)
        

    @abstractmethod
    def getSourceDescription(self):
        pass

    def ensureViewSourcesFeature(self):
        if not self.assignment.getFeatureByType('ViewSources'):
            self.assignment.addFeature({'featureName':'ViewSources','args':{}})



class ViewSources(Feature):
    def __init__(self, assignment) -> None:
        super().__init__(assignment,self.__class__.__name__)


    def preAssignment(self):
        self.source_features = [f for f in self.assignment.features if 'Source' in [c.__name__ for c in f.__class__.__mro__]]
        if not self.source_features:
            raise Exception("ViewSources feature requires at least one Source feature in the assignment.")
        
        self.assignment.addInstructions(f"""
--------------SOURCES---------------
These are the sources you have available in your tools. If you don't see them in your tools now, that means they WILL be accessible in a later step, so plan accordingly. 
Some sources may require that you cite them (see 'cite_source' in the json below). If that is the case, the citations are always in the form '^$source_code:reference_string', including the dollar sign but not the quotes. Always cite in-line, because your citations will be replaced by a clickable icon automatically.
If you are citing multiple sources, use the same formatting for each with a space inbetween. For example, you might add ^$SID:ebb38d78-dd9d-4b3b-8956-8d6dd3efa950 ^$SID:382ea099-6fbc-4103-bdee-a2d92232b14f after the information you are citing if you are referencing two different sources with the 'SID' source_code.
Citations should NEVER be in parenthesis, braces, brackets, or other additional punctuation, and should NEVER be in markdown format.
Here are your sources:{'{' + "".join(['"'+feature.tool_name + '": ' + '{"source_code": "' + feature.source_code + '", ' + '"reference_string_type: "' + feature.reference_string_type + '", ' + '"description": "' + feature.getSourceDescription() + '", ' + '"cite_source": ' + str(feature.cite_sources) + '"}, ' for feature in self.source_features]) + "}"}
"--------------END SOURCES---------------\n""")


    def preLLM(self):
        pass

    def postLLM(self):
        pass

    def postResponse(self):
        pass

    def postTool(self):
        pass

    def checkComplete(self):
        return True
    
    def postAssignment(self):
        pass