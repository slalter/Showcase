from pinecone import Pinecone
import os

pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
index = pc.Index("main")
