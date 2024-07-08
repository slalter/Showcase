from packages.guru.Flows.features import Feature
from models.conversation.db_conversation import DBConversation

class TaskTracker(Feature):
    def __init__(self, assignment) -> None:
        super().__init__(assignment,self.__class__.__name__)
        self.last_tasks_seen = ''

    def preAssignment(self):
        self.updateTask()

    def preLLM(self):
        self.updateTask()

    def postLLM(self):
        self.updateTask()

    def postResponse(self):
        self.updateTask()

    def postTool(self):
        self.updateTask()

    def checkComplete(self):
        return True
    
    def postAssignment(self):
        self.updateTask()


    def updateTask(self):
        if self.assignment.tasks and self.assignment.tasks != self.last_tasks_seen:
            tasks = self.assignment.tasks
            for i in range(len(tasks)):
                if tasks[i] == 'mark_complete':
                    tasks[i] = 'Determining Next Task'
            DBConversation.setTask(self.assignment.conversation_id, str(tasks))

            self.last_tasks_seen = tasks
