#DEFAULT IMPORTS
import os
from flask import Flask, request, jsonify, render_template
import dotenv


dotenv.load_dotenv('.env')

##IMPORTS##


from auth import login_required
from db.database import Base, engine
from db.models import *
#default build code
app = Flask(__name__)



##LLM CODE##


#default routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

##ROUTES##




if __name__ == "__main__":
    app.run(debug=True, port=5000)