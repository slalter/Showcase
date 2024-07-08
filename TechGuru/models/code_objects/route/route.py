from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from datetime import datetime
from models import SmartUUID
import uuid


class Route(Base):    
    __tablename__ = 'route'
    id = Column(SmartUUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, default = '')
    is_admin = Column(Boolean, default = False)
    login_required = Column(Boolean, default = False)
    allowable_methods = Column(JSON, default = [])
    args = Column(JSON, default = [])


    target_method_id = Column(SmartUUID(), default = None)


    #override the write_code_to_file method to behave differently since we are a route
    def write_code_to_file(self, file_path):
        raise Exception("Routes should not be written to file directly. Instead, they should be handled by their Main object.")
    
    def build(self, project_path, session):
        from models import Method, InputClass, OutputClass
        method:Method = self.target_method

        #recursive call!
        method.build(project_path, session)

        self.main.addImport(self.target_method.getImportRoute(), session)
        code = ''
        if self.is_admin:
            code += '@admin_required\n'
        if self.login_required:
            code += '@login_required\n'
        code += '@app.route(\'/' + self.name + '\', methods=[' + ', '.join(self.allowable_methods) + '])\n'
        code += 'def ' + self.name + '(' + ', '.join(self.args) + '):\n'
        #code to verify that the args match the input class
        input_class:InputClass = method.input_class
        #import the input class
        code += '    from models.io import ' + input_class.name + '\n'
        #create an instance of the input class
        code += '    input = ' + input_class.name + '()\n'
        #fill the instance with the args
        for arg in self.args:
            code += '    input.' + arg + ' = ' + arg + '\n'
        #validate the input
        code += '    input.validate()\n'
        #return an error if not valid
        code += '    if input.errors:\n'
        code += '        return jsonify(input.errors), 400\n'
        #call the method
        code += '    output = ' + method.name + '(input)\n'
        #return the output
        code += '    return jsonify(output)\n'

        return code