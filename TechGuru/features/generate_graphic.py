from packages.guru.GLLM import LLM
from openai import OpenAI
import os
import time
from datetime import datetime
import uuid
from packages.guru.Flows import Feature
from packages.guru.Flows.tool import Tool
import re
from models.database import Session
#TODO: revamp.
class GenerateGraphic(Feature):

    def __init__(self, assignment, inline=True) -> None:
        self.inline = inline
        super().__init__(assignment,self.__class__.__name__)
        assignment.tools.append(Tool(toolName='generate_graphic', assignment=self.assignment, source_feature=self))
        

    def preAssignment(self):
        if self.inline:
            self.assignment.addInstructions("You can insert images that you make via the generate_graphic tool in-line using exactly the format inside these quotes: '^$IMG:path.extension'. Do not use markdown format. For example: here is an image I made. ^$image001.png")
        pass

    def preLLM(self):
        pass

    def postLLM(self):
        content = self.assignment.messages[-1]['content'] 
        if '.png' in content:
            #go from .png backwards until we hit a space, a slash, or a colon. Take that text and replace it with ^$IMG: that text
            content = re.sub(r'[^a-zA-Z0-9_\-\.\/: ]+\.png', lambda x: f'^$IMG:{x.group()}', content)
            
            self.assignment.messages[-1]['content'] = content

    def postResponse(self):
        pass

    def postTool(self):
        pass

    def checkComplete(self):
        return True
    
    def postAssignment(self):
        pass

    def getToolJson(self, toolName):
        if toolName == 'generate_graphic':
            return {
                "type": "function",
                "function": {
                    "name": "generate_graphic",
                    "description": "Generate a graph or data image based on the provided description and data. Be very specific about what type of graph you want. If you want multiple graphics, call this tool in parallel. You must provide the data or the graphics agent will not be able to generate the graphic.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "A description of the graph or data image you want to create."
                            },
                            "data": {
                                "type": "string",
                                "description": "The data to be used for generating the graphic or data image. Don't forget to include the units."
                            }
                        }
                    }
                }
            }

    def executeTool(self, toolName, args, tool_call_id):
        session = Session()
        with session:
            if toolName == 'generate_graphic':
                return self.execute(self.assignment, args,session, tool_call_id)

    def execute(self, assignment, args, session, tool_call_id = None):
        '''
        give the description of the thing you want to make and the data for it.
        '''
        client = OpenAI(
            api_key=os.environ.get('OPENAI_KEY'),
            timeout=40,
            max_retries=0
        )
        max_retries = 2
        max_remakes = 1
        remakes = 0
        while True:
            try:
                for _ in range(max_retries):
                    try:
                        thread = client.beta.threads.create()
                        print("thread created")
                        break
                    except Exception as e:
                        if _ == max_retries - 1:
                            raise Exception("Failed to create thread after retries") from e

                for _ in range(max_retries):
                    try:
                        message = client.beta.threads.messages.create(
                            thread_id=thread.id,
                            role="user",
                            content=f"description:{args['description']}\n data:{args['data']}"
                        )
                        print("message created")
                        break
                    except Exception as e:
                        if _ == max_retries - 1:
                            raise Exception("Failed to create message after retries") from e

                for _ in range(max_retries):
                    try:
                        run = client.beta.threads.runs.create(
                            thread_id=thread.id,
                            assistant_id=getAssistant(),
                        )
                        print("run created.")
                        break
                    except Exception as e:
                        if _ == max_retries - 1:
                            raise Exception("Failed to create run after retries") from e

                complete = False
                while not complete:
                    for _ in range(max_retries):
                        try:
                            print(f"not complete. Retrying...")
                            status = client.beta.threads.runs.retrieve(
                                thread_id=thread.id,
                                run_id=run.id
                            )
                            time.sleep(4)
                            print(status)
                            complete = False if status.status == 'in_progress' or status.status == 'queued' else True
                            break
                        except Exception as e:
                            if _ == max_retries - 1:
                                raise Exception("Failed to retrieve run status after retries") from e

                for _ in range(max_retries):
                    try:
                        messages = client.beta.threads.messages.list(
                            thread_id=thread.id
                        )
                        print(messages.data)
                        break
                    except Exception as e:
                        if _ == max_retries - 1:
                            raise Exception("Failed to list messages after retries") from e

                for _ in range(max_retries):
                    try:
                        file_id = None
    
                        for message in messages.data:
                            if message.content:
                                for c in message.content:
                                    if hasattr(c, 'image_file'):
                                        file_id = c.image_file.file_id
                                        break
                            if hasattr(message, 'attachments'):
                                if message.attachments:
                                    for attachment in message.attachments:
                                        if hasattr(attachment, 'file_id') and attachment.file_id:
                                            file_id = attachment.file_id
                                            break
                        if not file_id:
                            if assignment.conversation_id:
                                from models import addLog
                                try:
                                    message = messages.data
                                except:
                                    message = "no message found"
                                addLog(assignment.conversation_id, 'Graphic Error', {'error':'no image file found!','request':args['description'], 'message': message})
                            return 'no image file found!'
                        image_data = client.files.content(file_id)
                        image_data_bytes = image_data.read()
                        break
                    except Exception as e:
                        if _ == max_retries - 1:
                            raise Exception("Failed to retrieve image data after retries") from e
            except Exception as e:
                if remakes < max_remakes:
                    remakeAssistant()
                    remakes +=1
                    continue
                else:
                    raise e
            break




        try:
            if assignment.run:
                directory = f'logs/{assignment.run}/images'
            else:
                directory = 'logs/images'

            # Ensure the directory exists
            if not os.path.exists(directory):
                os.makedirs(directory)

            # Create the file path
            file_path = os.path.join(directory, f'{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.png')

            # Write the image data to the file
            with open(file_path, 'wb') as f:
                f.write(image_data_bytes)
            
            if assignment.conversation_id:
                from models import addLog
                addLog(assignment.conversation_id, 'Graphic', {'file_path': file_path,'response':messages.data[0].content[0].text.value,'request':args['description']})

            
            
            return f"image saved to file at {file_path}"
        except Exception as e:
            try:
                message = messages.data[0].content[0].text.value
            except:
                message = "no message found"
            if assignment.conversation_id:
                from models import addLog
                addLog(assignment.conversation_id, 'Graphic Error', {'error':str(e),'request':args['description'],'message from agent':message})
            return f"error while generating graphic: {e}. The graphics agent said {message}."

def getAssistant():

    from openai import OpenAI

    client = OpenAI(
        api_key="",
        timeout=40,
        max_retries=0
    )

    response = client.beta.assistants.list()

    if response.data:
        return response.data[0].id
    else:
        return remakeAssistant()

def remakeAssistant():
    from openai import OpenAI

    client = OpenAI(
        api_key="",
        timeout=40,
        max_retries=0
    )

    response = client.beta.assistants.list()

    while response.data:

        for agent in response.data:
            try:
                client.beta.assistants.delete(agent.id)
            except Exception as e:
                print(e)
        print("retry")
        response = client.beta.assistants.list()
        print(response.data)
        
    assistant = client.beta.assistants.create(
            name= "Data Report Generator",
            instructions="""Take a deep breath. Let's think step-by-step. Your job is to build visual graphics using code interpreter based on the description and the provided data. Consider font sizes, abbreviations, new lines, and other things to create a visually appealing report. Make sure to never re-use the same color, and make the colors you do use as dissimilar as possible. Always represent the data accurately, and NEVER make things up to fill in the gaps. You will not be able to have any followup conversation for clarification, so do your very best to generate the graphic while maintaining accuracy. Do not respond with any text content unless you cannot complete the task; if that is the case, state why. Otherwise your response should just be the graphic. Use Matplotlib and Seaborn to create a professional and modern visualization that aligns with the provided branding colors. Ensure that the following specifications are met for any type of graphic:
- Title: Set an appropriate title for the graphic.
- Axis labels: Include descriptive labels for both axes.
- Colors: Use the blue tones and complimentary tones.
- Font sizes: Title font size should be 20, axis labels should be 15, and tick labels should be 12.
- Style: Ensure the plot has a clean and modern style, suitable for professional presentations.
- Prefer donut charts over pie charts for better readability and trendiness.
- Use light grid lines to help guide the reader's eye.
- Annotate key data points or trends to highlight important information.
- Ensure text and data labels are large and legible.
- Maintain a consistent style across all visuals.""",tools=[{"type": "code_interpreter"}],
            model="gpt-4o"
        )

    return assistant.id
