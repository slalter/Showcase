import functions_framework
import os
import openai
import time
import json

from twilio.rest import Client
from flask import Flask, request, render_template, make_response, jsonify, Response
from twilio.twiml.messaging_response import MessagingResponse
from google.cloud import storage



@functions_framework.http
def hello_http(request):
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
  storage_client = storage.Client()
  bucket_name = "leadsgpt"
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob("testconv.json")
  print(request.values.get('Body'))
  if 'restart'==str(request.values.get('Body')):
    print("restarting...")
    try:
        blob.delete()
    except:
        print("delete failed")
    blob = bucket.blob("testconv.json")
    conversation = Conversation(str(request.values.get('From')),1)
    with blob.open("w") as f:
        f.write(conversation.getJSON())
    return 'response'
  else:
    print(request.values)
    msgin = request.values.get('Body')
    message = Message("user",msgin)
    print("message recieved! " + msgin)
    with blob.open("r") as f:
      conversation = Conversation.loadJSON(f)
    try:
        result = conversation.newInbound(message)
        if(result == 0):
            conversation.addLog("failed to process new textIn")
            print("error logged in textIn for")
    except Exception as e:
        print("error processing inbound text due to " + str(e))
    
    return 'Response'

class Conversation:

    def __init__(self, number, initiate): 
        self.number = number
        self.closed = 0
        #pull these two from number.json in bin
        self.log = []
        self.messages = []

        if(initiate==1):
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
                print("error getting gpt response due to " + response['choices'][0]['finish_reason'])
                return "error"
        except Exception as e:
            print("attempt: failed to get GPT response due to " + str(e))
            return "error"
        msg = Message("assistant",response['choices'][0]['message']['content'])
        self.messages.append(msg.get())
        self.sendSMS(response['choices'][0]['message']['content'])
        if("$EC" in response['choices'][0]['message']['content']):
            self.closed = 1

        return response

    def sendSMS(self, content):
        #sendstwiliosms

        # Your Account SID from twilio.com/console
        account_sid = ""
        # Your Auth Token from twilio.com/console
        auth_token  = ""
        #twilio number
        twilio_number = "2766249384"
        client = Client(account_sid,auth_token)
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

    def getJSON(self):
      return {"number":self.number,"logs":self.logs,"messages":self.messages,"closed":self.closed}
    
    @staticmethod
    def loadJSON(jsonIn):
      conversation = Conversation(jsonIn.values.get("number"),0)
      conversation.messages = jsonIn.values.get('messages')
      conversation.logs = jsonIn.values.get('logs')
      conversation.closed = jsonIn.closed
      return conversation
    
    





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

  storage_client = storage.Client()
  bucket_name = "leadsgpt"
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob("prompt.txt")
  with blob.open("r") as f:
    out = f.read()
  return out