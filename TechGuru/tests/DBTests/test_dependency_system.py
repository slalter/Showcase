#set cwd to /app
import os
os.chdir('/app')
#make sure that cwd is loaded to python path
import sys
sys.path.append('/app')
import unittest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, File, Method, Class, Model, Session, Project
import uuid
from tests.utils.create_temp_db import create_temp_db, drop_temp_db
import json
# Mock DependencyAnalyzer and necessary imports
from features.appBuilderUtils.dependencyAnalyzer import DependencyAnalyzer

class DependencyAnalyzerTestCase(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.TemporaryDirectory()

        # Create test files with sample content
        self.create_file('__init__.py', '')
        self.create_file('test_file.py', """
import os
import sys
from subfolder1.subfile1 import SubClass1
from subfolder2.subfile2 import SubClass2
from subfolder2.subsubfolder.subsubfile import sub_function

def sample_function():
    print("Hello from test_file!")

class SampleClass:
    def class_method(self):
        pass

if __name__ == "__main__":
    sample_function()
    instance1 = SubClass1()
    instance2 = SubClass2()
    sub_function()
""")
        self.create_file('subfolder1/__init__.py', '')
        self.create_file('subfolder1/subfile1.py', """
from subfolder2.subfile2 import helper_function

def sub_function1():
    print("Hello from subfile1!")

class SubClass1:
    def __init__(self):
        self.helper = helper_function()
""")
        self.create_file('subfolder2/__init__.py', '')
        self.create_file('subfolder2/subfile2.py', """
def helper_function():
    print("Helper function in subfile2!")

def sub_function2():
    print("Hello from subfile2!")

class SubClass2:
    def class_method2(self):
        pass
""")
        self.create_file('subfolder2/subsubfolder/subsubfile.py', """
def sub_function():
    print("Hello from subsubfile!")
""")

        # Create a temporary database
        self.engine, self.Session, self.temp_db_name = create_temp_db()

    def tearDown(self):
        # Close the temporary directory
        self.test_dir.cleanup()

        # Drop the temporary database
        drop_temp_db(self.engine,self.temp_db_name)

    def create_file(self, relative_path, content):
        file_path = os.path.join(self.test_dir.name, relative_path)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(content)

    def test_dependency_analyzer(self):
        # Initialize the analyzer
        analyzer = DependencyAnalyzer(os.path.join(self.test_dir.name, 'test_file.py'))
        analyzer.analyze()
        print(json.dumps(analyzer.get_dependencies(), indent=4, default=lambda o: o.__dict__))
        # Save to DB
        project_id = str(uuid.uuid4())
        #make a project
        project = Project(id=project_id, name='test_project')
        with self.Session() as session:
            session.add(project)
            session.commit()
            analyzer.save_file_to_db(os.path.join(self.test_dir.name, 'test_file.py'), project_id=project_id, session=session)

        # Verify the results in the database
        with self.Session() as session:
            file_record = session.query(File).filter_by(path=os.path.join(self.test_dir.name, 'test_file.py')).first()
            self.assertIsNotNone(file_record)
            self.assertEqual(file_record.project_id, project_id)

            # Check functions
            methods = session.query(Method).filter_by(file_id=file_record.id).all()
            self.assertEqual(len(methods), 1)
            self.assertEqual(methods[0].name, 'sample_function')
            self.assertIn('print("Hello from test_file!")', methods[0].code)

            # Check classes
            classes = session.query(Class).filter_by(file_id=file_record.id).all()
            self.assertEqual(len(classes), 1)
            self.assertEqual(classes[0].name, 'SampleClass')
            self.assertIn('def class_method(self)', classes[0].code)

            # Check top-level code
            self.assertIn('if __name__ == "__main__":', file_record.top_level_code)

            # Check subfolder1/subfile1.py
            subfile1_record = session.query(File).filter_by(path=os.path.join(self.test_dir.name, 'subfolder1/subfile1.py')).first()
            self.assertIsNotNone(subfile1_record)

            # Check subfolder2/subfile2.py
            subfile2_record = session.query(File).filter_by(path=os.path.join(self.test_dir.name, 'subfolder2/subfile2.py')).first()
            self.assertIsNotNone(subfile2_record)

            # Check subfolder2/subsubfolder/subsubfile.py
            subsubfile_record = session.query(File).filter_by(path=os.path.join(self.test_dir.name, 'subfolder2/subsubfolder/subsubfile.py')).first()
            self.assertIsNotNone(subsubfile_record)

if __name__ == '__main__':
    unittest.main()
