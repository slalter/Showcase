import os
import openai
import time 
import jinja2
import json

from twilio.rest import Client
from flask import Flask, request, render_template, make_response, jsonify, Response
from twilio.twiml.messaging_response import MessagingResponse

# Your Account SID from twilio.com/console
account_sid = ""
# Your Auth Token from twilio.com/console
auth_token  = ""
#twilio number
twilio_number = ""
client = Client(account_sid,auth_token)

#openai
OPEN_AI_KEY = ""
openai.api_key = OPEN_AI_KEY

#dictionary of conversations by phone number
conversations = {}

#dictionary of completed logs for ended conversations
oldLogs = {}

app = Flask(__name__)

class Conversation:

    def __init__(self, number):
        self.number = number
        self.log = []
        self.messages = []
        self.begin()

    def begin(self):
        #add prompt to messages
        msg = Message("system", loadPrompt())
        self.messages.append(msg.get())
        self.GPTrequest()

    #call this when a new message is received from candidate. Returns 1 on success and 0 on fail.
    def newInbound(self, message):
        self.messages.append(message.get())
        response = "error"
        i=0
        tries = 3
        while(response=="error"):
            i = i + 1
            if(i==tries):
                break
            response = self.GPTrequest()
            
        if(response=="error"):
            print("failed to send response to GPT for " + self.number + "after " + tries + "attempts")
            return 0
        return 1

    #sends message chain to GPT for response. Returns a GPT response object on success, and "error" on fail.
    def GPTrequest(self):
        try:
            print(self.messages)
            response =  openai.ChatCompletion.create(
                model="gpt-3.5-turbo",messages = self.messages)
            print(response)
            if(response['choices'][0]['finish_reason']!='stop'):
                print("error getting gpt response for " + self.number + " due to " + response['choices'][0]['finish_reason'])
                return "error"
            if(response['choices'][0]['message']['content'] == "end conversation"):
                self.end()
        except Exception as e:
            print("attempt: failed to get GPT response for " + self.number + " due to " + e.__cause__())
            response = "error"
        msg = Message("assistant",response['choices'][0]['message']['content'])
        self.messages.append(msg.get())
        self.sendSMS(response['choices'][0]['message']['content'] )
        return response

    def sendSMS(self, content):
        #sendstwiliosms
        try:
            message = client.messages.create(
                              body=content,
                              from_=twilio_number,
                              to=self.number
                          )
        except Exception as e:
            self.addLog(e)

    def addLog(self,log):
        print("error logged for " + self.number)
        self.log.append(time.now + ": " + log)
    
    def clearLog(self):
        self.log = []
    
    #save logs of conversation, delete self.
    def end(self):
        oldLogs.update({self.number, str(logs)})
        del(self)




class Message:
    def __init__(self, role, content):
        self.role = role
        self.content = content
    
    def getRole(self):
        return self.role
    
    def get(self):
        return {"role": self.role, "content": self.content}
    
    def __str__(self):
        return self.role + ":" + self.content

#loads initial prompt for AI
def loadPrompt():
    f = open("prompt.txt", "r")
    out = f.read()
    f.close()
    return out



#triggered functions

#triggered on new lead
@app.route("/newLead", methods=("GET", "POST"))
def newLead():
    leads = ["5309412745"] #get leads from request instead
    for lead in leads:
        conversations.update({lead:Conversation(lead)})
    print("added leads: " + conversations[lead] for lead in leads)
    return 'Response'

#triggered on text message in
@app.route("/text", methods=("GET","POST"))
def textIn():
    print(request.values)
    fromnum = request.values.get('From')[2:]
    msgin = request.values.get('Body')
    message = Message("user",msgin)
    print("message recieved! " + msgin)
    try:
        result = conversations[fromnum].newInbound(message)
        if(result == 0):
            conversations[fromnum].addLog("failed to process new textIn")
            print("error logged in textIn for" + fromnum)
    except Exception as e:
        print("error processing inbound text due to " + str(e))
    
    return 'Response'

#logs.html
@app.route("/")
def logs():
    return render_template('logs.html',logs=[conversation.log for conversation in conversations])

if __name__ == "__main__":
    app.run(host="localhost", port=8000, debug=True)

@app.route("/testPOST",methods = ("GET", "POST"))
def testPOST():
    print(request)
    f = open("samplejson.txt", "w")
    f.write(json.dumps(request.get_json()))
    f.close()
    
    return rprocess(request.get_json())
    


Leads = []

#accept or reject.
def rprocess(request):
    reason = ""
    print("json loaded")
    #if(compare to existing leads):
    try:
        request["body"]["parent_id"]
        request["body"]["sub_id"]
        if request["body"]["number"] in Leads:
            reason = "duplicate"
        if ((int(request["body"]["age"])>63) or (int(request["body"]["age"])<19)):
            reason = "bad field: age must be between 19 and 63."
        if request["body"]["MM_enroll"]==1:
            reason = "bad field: MM_enroll must be 0"
        if int(request["body"]["yearly_income"])>30000 or int(request["body"]["yearly_income"])<13000:
            reason = "bad field: yearly_income must be between 13000 and 30000"
    except Exception as e:
        print("failed to check due to " + str(e))
        return make_response("bad request. Refer to documentation or contact dev.",400)
    
    if reason == "":
        return make_response(jsonify({"accepted":1, "parent_id":request["body"]["parent_id"], "sub_id":request["body"]["sub_id"]}),200,{})
    else:
        Leads.append(request["body"]["number"])
        #####send lead to server to begin conversation
        return make_response(jsonify({"accepted":0, "parent_id":request["body"]["parent_id"],"sub_id":request["body"]["sub_id"],"reason":reason}),409,{})