from models import Base, Session
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, Text
from ...utils.code_mixin import CodeMixin
from ...utils.smart_uuid import SmartUUID
import uuid
import os
from packages.guru.GLLM import LLM
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy import Table, Column, Integer, ForeignKey
import json
import subprocess

class File(CodeMixin):
    __tablename__ = 'file'
    id = Column(SmartUUID(), ForeignKey('code_object.id'), primary_key=True, default=uuid.uuid4)
    path = Column(String, nullable=False)
    project = relationship("Project", back_populates="files")
    is_main = Column(Boolean, default=False)
    imports = Column(JSON, default=[])
    
    #this is important because this code needs to be built any time we build a method based in this file. 
    #greater granularity with this is achievable and will be implemented in the future.
    top_level_code = Column(JSON, default=[])

    
    __mapper_args__ = {
        'polymorphic_identity': 'file',
        'inherit_condition': (id == CodeMixin.id)
    }

    
    def build(self, folder_path, session):
        '''
        Builds the file and all its dependencies in the folder path.
        Builds a pipenv file based on pip_packages.

        '''
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        file_path = os.path.join(folder_path, self.path)
        with open(file_path, 'w') as f:
            f.write(self.code)


        #gather pip_packages and write code from all files that are dependencies of this file.
        pip_packages = self.pip_packages
        for dependency in self.dependencies:
            pip_packages += dependency.pip_packages
            with open(os.path.join(folder_path, dependency.path), 'w') as f:
                f.write(dependency.code)
        pip_packages = list(set(pip_packages))

        #make the pipfile
        with open(os.path.join(folder_path, 'Pipfile'), 'w') as f:
            f.write('[packages]\n')
            for package in pip_packages:
                f.write(f'{package} = "*"\n')

        #for each dependency, copy the file to the folder path.


        #cd to the main and run commands.
        current_dir = os.getcwd()
        os.chdir(folder_path)
        #make sure all the base packages are installed by executing the install_base_dependencies.sh script as root
        #TODO: add base dependency support (apt-get, etc.)
        #os.system('sudo ./install_base_dependencies.sh')


        # Try to lock the pipenv. If it fails, handle dependencies.
        try:
            subprocess.run(['pipenv', 'lock'], check=True)
        except subprocess.CalledProcessError:
            print("pipenv lock failed, checking for existing lockfile...")
            if os.path.exists('Pipfile.lock'):
                existing_deps = parse_pipfile_dependencies('Pipfile.lock')
                requested_deps = parse_pipfile_dependencies('Pipfile')
                new_deps = {dep: ver for dep, ver in requested_deps.items() if dep not in existing_deps or existing_deps[dep] != ver}
                
                for dep, ver in new_deps.items():
                    try:
                        subprocess.run(['pipenv', 'install', f'{dep}=={ver}'], check=True)
                        print(f"Successfully installed {dep}")
                    except subprocess.CalledProcessError:
                        print(f"Failed to install {dep}")
            else:
                print("No existing Pipfile.lock found. Attempting to install all dependencies...")
                for dep, ver in requested_deps.items():
                    try:
                        subprocess.run(['pipenv', 'install', f'{dep}=={ver}'], check=True)
                        print(f"Successfully installed {dep}")
                    except subprocess.CalledProcessError:
                        print(f"Failed to install {dep}")

        #os.system('docker compose up --build -d')

        print("Project built successfully.")
        print(f"Project located at {folder_path}")

        #change dir back
        os.chdir(current_dir)

def parse_pipfile_dependencies(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data['default']
        