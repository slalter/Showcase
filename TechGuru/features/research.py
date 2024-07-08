from packages.guru.Flows import Feature
from features.viewSources import Source
from models.conversation.db_conversation import addLog
import re
from models.database import Session

class Research(Feature, Source):
    def __init__(self, assignment, 
                 max_context=10000, 
                 mode='perplexity', 
                 cite_sources=True,
                 active=True,
                 keep_previous_data=True
                 ) -> None:
        from packages.guru.Flows.tool import Tool
        self.source_code='URL'
        self.tool_name='external_research'
        self.reference_string_type = 'URL'
        self.cite_sources = cite_sources
        super().__init__(assignment,self.__class__.__name__)
        self.active = active
        if self.active:
            self.assignment.tools.append(Tool(toolName='external_research',assignment=self.assignment, source_feature = self))

        self.search_results = []
        self.max_context = max_context
        self.mode = mode
        self.keep_previous_data = keep_previous_data


    def preAssignment(self):
        if self.prevFeature and self.keep_previous_data:
            self.search_results = self.prevFeature.search_results

    def preLLM(self):
        if self.active:
            self.assignment.addContext(self.getText())

    def postLLM(self):
        #TODO: cleanup.
        content = self.assignment.messages[-1]['content']
        new_content = content  # Start with original content

        # Find all markdown links and process them one by one
        try:
            for full_match, link_text, url in re.findall(r'(\[(.*?)\]\((.*?)\))', new_content):
                if 'http' in url:
                    # Replace the markdown link with the custom URL format only for valid URLs
                    new_content = new_content.replace(full_match, f'^$URL:{url}', 1)

            # Log changes or no change status
            if new_content != content:
                addLog(self.assignment.conversation_id, 'replaced_url_formatting', {'old': content, 'new': new_content})
            else:
                return

            self.assignment.messages[-1]['content'] = new_content
        except Exception as e:
            addLog(self.assignment.conversation_id, 'url_formatting_error', {'error': str(e)})
            


    def postResponse(self):
        pass

            

    def postTool(self):
        #TODO: cleanup.
        content = self.assignment.messages[-1]['content']
        new_content = content  # Start with original content

        # Find all markdown links and process them one by one
        try:
            for full_match, link_text, url in re.findall(r'(\[(.*?)\]\((.*?)\))', new_content):

                if 'http' in url:
                    # Replace the markdown link with the custom URL format only for valid URLs
                    new_content = new_content.replace(full_match, f'^$URL:{url}', 1)

            # Log changes or no change status
            if new_content != content:
                addLog(self.assignment.conversation_id, 'replaced_url_formatting', {'old': content, 'new': new_content})
            else:
                return
            
            self.assignment.messages[-1]['content'] = new_content
        except Exception as e:
            addLog(self.assignment.conversation_id, 'url_formatting_error', {'error': str(e)})


    def checkComplete(self):
        return True
    
    def postAssignment(self):
        pass

    def getSourceDescription(self):
        return """
This tool allows you to ask a specialized agent to search the web for information. This is useful for finding supporting data or directly answering queries.
"""
    
    def getToolJson(self, toolName):
        if toolName == 'external_research':
            return {
    "type": "function",
    "function": {
        "name": "external_research",
        "description": "Send a set of queries to a specialized agent to search the web for information. The agent only returns the top 5 results, so think of a few different ways to ask for the information and send a query for each, so that you are more likely to get the information you want. For example, you might have one query that is very specific and another that is more general, or one query that asks for scholarly articles and one that asks for blog posts. The agent will return the results of each query.",
        "parameters": {
            "type": "object",
            "properties": {
                "requests": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "This is the query that the agent will read and then use to guide its search. Be as specific as possible, and include the type of data source you would like to search, if applicable, like 'scholarly articles' or 'news articles' or '{entity_name}'s website. Include any relevant entity names, dates/years, or other high-precision search terms."
                            }
                        },
                        "required": ["query"],
                        "description": "Each item represents a single search request with specific parameters."
                    }
                }
            },
            "required": ["requests"]
        }
    }
}
    
    #TODO: regularize the structure of the returned data.
    def executeTool(self, toolName, args, tool_call_id):
        session = Session()
        with session:
            print(args)
            new_results = []
            if self.assignment.conversation_id:
                addLog(self.assignment.conversation_id, 'external_search', {'search_requests':args['requests']},session)
            if self.mode == 'you':
                from packages.research.you import get_response, YouResponse, Result
                for q in args['requests']:
                    result:YouResponse = get_response(q['query'], session)
                    new_results.append((q['query'],result.__dict__))
            elif self.mode == 'perplexity':
                from packages.research.perplexity import get_response
                for q in args['requests']:
                    result = get_response(q['query'], self.assignment.conversation_id,session)
                    new_results.append((q['query'],result))
            elif self.mode == 'bing':
                from packages.research.bing import get_response
                for q in args['requests']:
                    result = get_response(q['query'], self.assignment.conversation_id,session)
                    new_results.append((q['query'],result))
            if self.assignment.conversation_id:
                addLog(self.assignment.conversation_id, 'external_search', {'search_results':new_results}, session)
            
            removed = 0
            while len(str(new_results))>self.max_context:
                removed += 1
                new_results.pop()
            self.search_results += new_results
            session.commit()
            return 'results have been added to the external_search results.' + f' the results were too large, and {removed} results were ommitted' if removed>0 else ''
            

    def getText(self):
        
        current_length = len(self.buildText())
        remaining_length = self.max_context - current_length
        while remaining_length < 0:
            self.search_results.pop(0)
            current_length = len(self.buildText())
            remaining_length = self.max_context - current_length
        text = f'''
--------- START external_search results ------------
window usage: {current_length}/{self.max_context}{ "WARNING: oldest searches will be automatically deleted to make room for new searches. Consider clearing less useful searches if you need to keep older search results." if remaining_length < self.max_context/7 else ""}
{[{'search_number':i,
   'search_request':self.search_results[i][0],
   'search_result':self.search_results[i][1]} 
   for i in range(len(self.search_results))]}                                   
--------- END external_search results ------------                            
 '''
        return text
    
    def buildText(self):
        return  f'''
--------- START external_search results ------------
window usage: {0}/{self.max_context}
{[{'search_number':i,
   'search_request':self.search_results[i][0],
   'search_result':self.search_results[i][1]} 
   for i in range(len(self.search_results))]}                                   
--------- END external_search results ------------'''

        
