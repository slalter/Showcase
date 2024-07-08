import ast
import os
import importlib.util
import json
import stdlib_list
from functools import wraps
import sys
import networkx as nx
from typing import List
import matplotlib.pyplot as plt
import io
from prompt_classes import DescribeObjectPrompt
from concurrent.futures import ThreadPoolExecutor
import traceback
import pickle



'''
files depend on each other, but methods and classes within them explicitly depend on the packages, methods, and classes they call.
'''

#list of control structure classes from ast, so that we can use them to iterate inside their child nodes as if the control structures were not there
control_structures = [
    ast.If,           # If statements
    ast.For,          # For loops
    ast.AsyncFor,     # Asynchronous for loops
    ast.While,        # While loops
    ast.Try,          # Try/Except blocks
    ast.With,         # With statements
    ast.AsyncWith,    # Asynchronous with statements
    ast.FunctionDef,  # Function definitions
    ast.AsyncFunctionDef, # Asynchronous function definitions
    ast.ClassDef,     # Class definitions
    ast.Return,       # Return statements
    ast.Raise,        # Raise statements
    ast.Break,        # Break statements
    ast.Continue,     # Continue statements
    ast.Pass,         # Pass statements
    ast.Import,       # Import statements
    ast.ImportFrom,   # From-import statements
    ast.Assert,       # Assert statements
    ast.Global,       # Global statements
    ast.Nonlocal,     # Nonlocal statements
    ast.Delete,       # Delete statements
    ast.AugAssign,     # Augmented assignments
    ast.Expr
]

class DependencyAnalyzer:
    def __init__(self, root_file, Session, project_id=None, base_class_names = ['Base']):
        from models import File, Project
        self.root_file = root_file
        self.root_dir = os.path.dirname(os.path.abspath(root_file))
        self.visited = set()
        self.function_call_stack = []
        self.stdlib_modules = stdlib_list.stdlib_list()
        self.digraph = nx.DiGraph()
        self.base_class_names = base_class_names
        sys.path.insert(0, self.root_dir)  # Ensure the root directory is in the Python path
        self.Session = Session
        with Session() as session:
            #verify that the project exists, if id provided.
            project = None
            if project_id:
                project = session.query(Project).filter_by(id=project_id).first()
            if not project:
                #create it.
                project = Project(id=project_id)
                session.add(project)
                session.commit()

            self.project_id = project.id

    def analyze(self):
        from models import Project
        with self.Session() as session:
            root_file = self._process_file(self.root_file, session)
            print("cleaning up...")
            #self.cleanup(root_file, session)
            project = session.query(Project).filter_by(id=self.project_id).first()
            self.Session = None
            print("pickling...")
            project.dependency_analyzer = pickle.dumps(self)
            print("committing...")
            session.commit()
            print("done.")
            return root_file

    def _process_file(self, filepath, session):
        from models import File
        filepath = os.path.abspath(filepath)
        if filepath in self.visited:
            # Return the appropriate file object
            file = session.query(File).filter_by(path=filepath).first()
            if not file:
                raise Exception(f"File {filepath} not found in the database, even though it was visited.")
            return [{file:[]}]

        if not filepath.endswith('.py'):
            return None

        self.visited.add(filepath)
        # If no file exists for this path, create one.
        file = session.query(File).filter_by(path=filepath).first()
        if not file:
            file = File(
                name=os.path.basename(filepath),
                path=filepath,
                project_id=self.project_id,
                is_main=filepath == os.path.abspath(self.root_file),
                code=open(filepath).read(),
                description=os.path.basename(filepath)
            )
            session.add(file)
            session.commit()
        
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read(), filename=filepath)
        
        def walk(layer):
            if not layer:
                return
            print(f"walking layer")
            from models import Method, Class
            next_layer = []       
            for pair in layer:
                for existing_object, remaining_nodes in pair.items():
                    session.refresh(file)
                    if existing_object not in file.dependencies:
                        try:
                            file.addDependency(existing_object, session)
                            session.commit()
                        except Exception as e:
                            session.rollback()
                            print(f"Error adding dependency {existing_object.name} to file {file.name}: {e}")
                            pass
                    for node in remaining_nodes:
                        print(f"processing node: {node.__class__}")
                        if isinstance(node, ast.FunctionDef):
                            next_layer.append(self._process_function(node, file, session, existing_object))
                        elif isinstance(node, ast.ClassDef):
                            next_layer.append(self._process_class(node, file, session, existing_object))
                        elif node.__class__ in control_structures:
                            temp_nodes = [node]
                            while temp_nodes:
                                #print(f"temp nodes: {json.dumps(temp_nodes, indent=4, default=lambda o: o.__dict__)}")
                                for node in temp_nodes:
                                    new_temp = []
                                    for n in ast.iter_child_nodes(node):
                                        if isinstance(n, ast.FunctionDef):
                                            next_layer.append(self._process_function(node, file, session, existing_object))
                                        elif isinstance(n, ast.ClassDef):
                                            next_layer.append(self._process_class(node, file, session, existing_object))
                                        elif n.__class__ in control_structures:
                                            new_temp.append(n)
                                        else:
                                            if isinstance(existing_object, Method):
                                                next_layer.append(self._process_function(node, file, session, existing_object))
                                            elif isinstance(existing_object, Class):
                                                next_layer.append(self._process_class(node, file, session, existing_object))
                                            else:
                                                raise Exception(f"Object type {existing_object.__class__} not recognized.")
                                temp_nodes = new_temp  
            if next_layer:
                walk([l for l in next_layer if l])
            return [{file:[]}]


        def initial_walk(node, sets):
            for node in ast.iter_child_nodes(node):
                print(f"initial walk: {node.__class__}")
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
                    result = self.process_node(node, session, file)
                    if result:
                        if not isinstance(result, list):
                            result = [result]
                    else:
                        result = []
                    sets += result
                else:
                    tlc = ast.get_source_segment(open(filepath).read(), node)
                    print(f"adding top level code: {tlc}")
                    #this wont catch conditional imports or imports inside control structures. Thats probably okay.
                    if not file.top_level_code:
                        print("overwriting top level code")
                        file.top_level_code = [tlc]
                    else:
                        file.top_level_code = file.top_level_code + [tlc]
                    session.commit()
            return sets

        first_layer = initial_walk(tree,[])
        print(first_layer)
        walk([l for l in first_layer if l])

        return [{file:[]}]

    def process_node(self, node, session, file):
        if isinstance(node, ast.Import):
            return self._process_import(node, file, session)
        elif isinstance(node, ast.ImportFrom):
            return self._process_import_from(node, file, session)
        elif isinstance(node, ast.FunctionDef):
            return self._process_function(node, file, session)
        elif isinstance(node, ast.ClassDef):
            return self._process_class(node, file, session)

    def _process_import_from(self, node: ast.ImportFrom, file, session): 
        from models import File
        assert(isinstance(file, File))
        if not node.module or node.level:
            print(f"processing import for {file.name}: {node.__dict__}")
            base_path = os.path.dirname(file.path)
            level = node.level
            for _ in range(level-1):
                base_path = os.path.dirname(base_path)
            if node.module:
                file_path = self._resolve_relative_import_path(base_path, node.module)
            else:
                file_path = base_path
            print(f"file path: {file_path}")
        else:
            base_path = self.root_dir
            file_path = self._resolve_import_path(node.module)
        module_name = node.module if node.module else ''
        if module_name:
            package_type = self._get_package_type(module_name, file_path)
            if file_path:
                if package_type == 'pip_package':
                    file.addPip({'module':module_name, 'imports':[alias.name for alias in node.names]})
                    session.commit()
                    return None
                elif package_type == 'internal':
                    if file_path == file.path:
                        raise Exception(f"File {file_path} is the same as the current file. This should not happen.")
                    if not '*' in [alias.name for alias in node.names]:
                        return self._process_file(file_path, session)
                    else:
                        #get the init file and process it.
                        init_file = os.path.join(file_path, '__init__.py')
                        if os.path.exists(init_file):
                            return self._process_file(init_file, session)
                        else:
                            return self._process_file(file_path, session)
                        
                elif package_type == 'native_package':
                    file.addNative({'module':module_name, 'imports':[alias.name for alias in node.names]})
                    session.commit()
                    return None
            else:
                if package_type == 'native_package':
                    file.addNative({'module':module_name, 'imports':[alias.name for alias in node.names]})
                    session.commit()
                    return None
                elif package_type == 'internal':
                    files = []
                    for alias in node.names:
                        file_path = self._resolve_relative_import_path(base_path, alias.name)
                        if file_path:
                            files.append(file_path)
                    if files:
                        output = []
                        with ThreadPoolExecutor(max_workers=5) as executor:
                            futures = {executor.submit(self._process_file_in_thread, file_path): file_path for file_path in files}
                            for future in futures:
                                try:
                                    result = future.result()
                                    if result:
                                        output.append(future.result())
                                except Exception as e:
                                    file_path = futures[future]
                                    raise Exception(f"Error processing file {file_path}: {traceback.format_exception(e)}")
                        return output
                    return None
                elif package_type == 'pip_package':
                    file.addPip({'module':module_name, 'imports':[alias.name for alias in node.names]})
                    print(f"added pip {module_name}: {[alias.name for alias in node.names]} to {file.name}")
                    session.commit()
                    return None
        else:
            #these are internal packages, imported relatively with . or .. or...
            #if its from . import *, get init
            if any(alias.name == '*' for alias in node.names):
                file_path = self._resolve_relative_import_path(base_path, '')
                if file_path:
                    return self._process_file(file_path, session)
            #otherwise, we just try to process the files directly. If this fails, jedi will catch it in a future implementation.
            for alias in node.names:
                file_path = self._resolve_relative_import_path(base_path, alias.name)
                if file_path:
                    return self._process_file(file_path, session)
                                 
            return None

    def _process_file_in_thread(self, file_path):
        with self.Session() as session:
            return self._process_file(file_path, session)

    def _process_import(self, node, file, session):
        from models import File
        assert(isinstance(file, File))
        files = []
        for alias in node.names:
            module_name = alias.name
            package_type = self._get_package_type(module_name, file_path=None)
            if package_type == 'native_package':
                file.addNative({'module':module_name, 'imports':''})
                session.commit()
                continue
            elif package_type == 'pip_package':
                file.addPip({'module':module_name, 'imports':''})
                session.commit()
                continue
            elif package_type == 'internal':
                file_path = self._resolve_import_path(module_name)
                if file_path:
                    files.append(file_path)
                
        if files:
            if any(file_path == file.path for file_path in files):
                raise Exception(f"File {file.path} is the same as the current file. This should not happen.")
            output = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self._process_file_in_thread, file_path): file_path for file_path in files}
                for future in futures:
                    try:
                        result = future.result()
                        if result:
                            output.append(future.result())
                    except Exception as e:
                        file_path = futures[future]
                        raise Exception(f"Error processing file {file_path}: {traceback.format_exception(e)}")
            return output
        return None


    def _resolve_import_path(self, module_name):
        try:
            spec = importlib.util.find_spec(module_name)
            if spec and spec.origin:
                return spec.origin
        except Exception as e:
            print(f"Error resolving import: {module_name} {e}")
            return None
        return None

    def _resolve_relative_import_path(self, base_path, module_name):
        try:
            print(f"module name: {module_name}")
            try:
                module_spec = importlib.util.find_spec(module_name)
                if module_spec and module_spec.origin:
                    return os.path.abspath(module_spec.origin)
            except Exception as e:
                print(f"Error resolving relative import: {module_name} {traceback.format_exception(e)}")
            #if that didn't work, try just finding the path directly
            file_path = os.path.join(base_path, module_name.replace('.', '/'))
            print(f"file path: {file_path}")
            if os.path.exists(file_path + '.py'):
                return file_path + '.py'
            elif os.path.exists(file_path):
                #return the init.py, if it exists
                if os.path.exists(os.path.join(file_path, '__init__.py')):
                    return os.path.join(file_path, '__init__.py')
                return None
            else:
                return None
        except Exception as e:
            print(f"Error resolving relative import: {module_name} {traceback.format_exception(e)}")
            return None
        
    def _process_function(self, node: ast.FunctionDef, file, session, existing_object=None):
        from models import Method, File
        assert(isinstance(file, File))
        print(f"processing function {node.__dict__}")
        #check to see if we have already seen this function. Check name and dependency on parent file.
        if isinstance(node, ast.FunctionDef):
            name = node.name
            existing_function = session.query(Method).filter_by(name=name).first()
            if existing_function:
                print(f"Function {name} already exists in general - checking dependencies for file...")
                if existing_function in file.dependencies:
                    print(f"Function {name} already exists in {file.name}")
                    return None
                else:
                    print(f"Function {name} already exists in general, but not in {file.name}")
                
        
        #recursively add imports within this function to the file object at this filepath.
        self._extract_nested_imports(node, file,session)
        if not existing_object:
            code = ast.get_source_segment(open(file.path).read(), node)
            decorators = [ast.get_source_segment(open(file.path).read(), decorator) for decorator in node.decorator_list]
            method = Method(
                name=node.name, 
                code=code, 
                decorators=decorators,
                project_id = self.project_id
                )
            method.description = self.describeObject(method, session)
            session.add(method)
            file.addDependency(method, session)
            if existing_object:
                existing_object.addDependency(method, session)
            session.commit()
            existing_object = method
            return {
                existing_object:[node]
                }
            
        def walk(node):
            to_walk = []
            for node in ast.iter_child_nodes(node):
                #iterate through the child nodes, using that to determine the dependencies.
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        imp = self.findImportByName(node.func.id, file, session)
                    elif isinstance(node.func, ast.Attribute):
                        full_name = self.get_full_attribute_name(node.func)
                        imp = self.findImportByName(full_name.split('.')[0], file,session)
                    elif isinstance(node.func, ast.Subscript):
                        imp = self.findImportByName(node.func.value.id, file,session)
                    else:
                        raise Exception(f"Function call not recognized. Type: {type(node.func)}")
                    if imp:
                        if imp['type'] == 'internal':
                            existing_object.addDependency(imp['db_object'],session)
                            session.commit()
                        elif imp['type'] == 'pip_package':
                            existing_object.addPip(imp)
                            session.commit()
                        elif imp['type'] == 'native_package':
                            existing_object.addNative(imp)
                            session.commit()
                        elif imp['type'] == 'top_level':
                            pass
                        else:
                            raise Exception(f"Import type {imp['type']} not recognized")
                elif isinstance(node, ast.FunctionDef):
                    #walk through it to find any dependencies to add to this method object.
                    to_walk.append(node)
                elif isinstance(node, ast.ClassDef):
                    to_walk.append(node)
                elif isinstance(node, ast.Import):
                    #since we extracted imports from within file defs and classes, we don't need to do anything here except identify them.
                    for alias in node.names:
                        imp = self.findImportByName(alias.name, file,session)
                        if imp:
                            if imp['type'] == 'internal':
                                existing_object.addDependency(imp['db_object'], session)
                                session.commit()
                            elif imp['type'] == 'pip_package':
                                existing_object.addPip(imp)
                                session.commit()
                            elif imp['type'] == 'native_package':
                                existing_object.addNative(imp)
                                session.commit()
                            elif imp['type'] == 'top_level':
                                pass
                            else:
                                raise Exception(f"Import type {imp['type']} not recognized")
                elif isinstance(node, ast.ImportFrom):
                    #since we extracted imports from within file defs and classes, we don't need to do anything here except identify them.
                    for alias in node.names:
                        imp = self.findImportByName(alias.name, file,session)
                        if imp:
                            if imp['type'] == 'internal':
                                existing_object.addDependency(imp['db_object'],session)
                                session.commit()
                            elif imp['type'] == 'pip_package':
                                existing_object.addPip(imp)
                                session.commit()
                            elif imp['type'] == 'native_package':
                                existing_object.addNative(imp)
                                session.commit()
                            elif imp['type'] == 'top_level':
                                pass
                            else:
                                raise Exception(f"Import type {imp['type']} not recognized")
                elif node.__class__ in control_structures:
                    to_walk.append(node)
                else:
                    pass
            return to_walk

        
        return {existing_object:walk(node)}

    def get_full_attribute_name(self, node):
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        parts.reverse()
        return '.'.join(parts)

    def findImportByName(self, name, object,session):
        from models import File
        #pip packages in this object
        if object.pip_packages:
            for pip_package in object.pip_packages:
                if name == pip_package['module']:
                    return pip_package.update({'type':'pip_package'})
                if name in pip_package['imports']:
                    return {
                        'type':'pip_package',
                        'module':pip_package['module'], 
                        'imports':[name]
                        }
        
        #native packages in this object
        if object.native_packages:
            for native_package in object.native_packages:
                if name == native_package['module']:
                    return native_package.update({'type':'native_package'})
                if name in native_package['imports']:
                    return {
                        'type':'native_package',
                        'module':native_package['module'],
                        'imports':[name]
                    }

        #otherwise, we must be in one of the depenedencies of this object.
        if object.dependencies:
            for dependency in object.dependencies:
                #if that dependency's name matches, we are calling a method from a file directly.
                if name == dependency.name:
                    return {
                        'type':'internal',
                        'db_object':dependency
                    }
                #otherwise, recurse into the dependency.
                try:
                    result = self.findImportByName(name, dependency,session)
                    if result:
                        return result
                except Exception as e:
                    pass

        #finally, check to see if it is in the file's top level code.
        if object.top_level_code:
            for line in object.top_level_code:
                if name in line:
                    return {
                        'type':'top_level',
                        'db_object':object
                    }        
        
        #check if this is just a base python package
        if name in self.stdlib_modules:
            return None
        
        #check to see if this is a command native to python like print
        if name in __builtins__:
            return None

        print(f"Import {name} not found in file {object.name}. Assuming that it is something we already have a reference to.")
        return None

    def _extract_nested_imports(self, node, file, session):
        for inner_node in ast.walk(node):
            if isinstance(inner_node, ast.Import):
                self._process_import(inner_node, file, session)
            elif isinstance(inner_node, ast.ImportFrom):
                self._process_import_from(inner_node, file, session)


    def _process_class(self, node: ast.ClassDef, file, session, existing_object=None):
        from models import Class, Model, File
        assert(isinstance(file, File))
        print(f"processing class {node.__dict__}")
        #check to see if it already exists.
        if isinstance(node, ast.ClassDef):
            name = node.name
            existing_class = session.query(Class).filter_by(name=name).first()
            if existing_class:
                print(f"Class {name} already exists in general - checking dependencies for file...")
                if existing_class in file.dependencies:
                    print(f"Class {name} already exists in {file.name}")
                    return None
                else:
                    print(f"Class {name} already exists in general, but not in {file.name}")
            
        #recursively add imports to the file object at this filepath.
        self._extract_nested_imports(node, file, session)
        if not existing_object:
            code = ast.get_source_segment(open(file.path).read(), node)
            base_classes = [self._get_base_class_name(base) for base in node.bases]
            if all(base not in self.base_class_names for base in base_classes):
                class_obj = Class(
                    name=node.name,
                    code=code,
                    bases=base_classes,
                    project_id = self.project_id,
                )
                class_obj.description = self.describeObject(class_obj, session)
                session.add(class_obj)
                file.addDependency(class_obj, session)
                if existing_object:
                    existing_object.addDependency(class_obj, session)
                session.commit()
            else:
                class_obj = Model(
                    name=node.name,
                    code=code,
                    bases=base_classes,
                    project_id = self.project_id
                )
                class_obj.description = self.describeObject(class_obj, session)
                session.add(class_obj)
                file.addDependency(class_obj, session)
                if existing_object:
                    existing_object.addDependency(class_obj, session)
                session.commit()
            existing_object = class_obj
        def walk(node):
            to_walk=[]
            for node in ast.iter_child_nodes(node):
                if isinstance(node, ast.FunctionDef):
                    to_walk.append(node)
                elif isinstance(node, ast.ClassDef):
                    to_walk.append(node)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imp = self.findImportByName(alias.name, file,session)
                        if imp:
                            if imp['type'] == 'internal':
                                existing_object.addDependency(imp['db_object'],session)
                                session.commit()
                            elif imp['type'] == 'pip_package':
                                existing_object.addPip(imp)
                                session.commit()
                            elif imp['type'] == 'native_package':
                                existing_object.addNative(imp)
                                session.commit()
                            elif imp['type'] == 'top_level':
                                pass
                            else:
                                raise Exception(f"Import type {imp['type']} not recognized")
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imp = self.findImportByName(alias.name, file, session)
                        if imp:
                            if imp['type'] == 'internal':
                                existing_object.addDependency(imp['db_object'],session)
                                session.commit()
                            elif imp['type'] == 'pip_package':
                                existing_object.addPip(imp)
                                session.commit()
                            elif imp['type'] == 'native_package':
                                existing_object.addNative(imp)
                                session.commit()
                            elif imp['type'] == 'top_level':
                                pass        
                            else:
                                raise Exception(f"Import type {imp['type']} not recognized")
                elif node.__class__ in control_structures:
                    to_walk.append(node)
                else:
                    pass
            return to_walk
            
        return {existing_object:walk(node)}

    def _get_base_class_name(self, base):
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return self._get_attribute_name(base)
        elif isinstance(base, ast.Subscript):
            return self._get_subscript_name(base)
        else:
            return None

    def _get_attribute_name(self, node):
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        parts.reverse()
        return '.'.join(parts)

    def _get_subscript_name(self, node):
        if isinstance(node.value, (ast.Name, ast.Attribute)):
            base_name = self._get_base_class_name(node.value)
            if isinstance(node.slice, ast.Index):
                return f"{base_name}[{self._get_slice_name(node.slice.value)}]"
            elif isinstance(node.slice, ast.Slice):
                return f"{base_name}[{self._get_slice_name(node.slice)}]"
        return None

    def _get_slice_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        elif isinstance(node, ast.Subscript):
            return self._get_subscript_name(node)
        else:
            return None


    def _trace_function_call(self, func_name, filepath):
        base_path = os.path.dirname(filepath)
        for root, _, files in os.walk(base_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        tree = ast.parse(f.read(), filename=file_path)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef) and node.name == func_name and file_path.startswith(self.root_dir):
                                self._process_file(file_path)


    def _get_package_type(self, module_name, file_path):
        if module_name.startswith('.'):
            return 'internal'
        if file_path and file_path.startswith(self.root_dir):
            return 'internal'
        if module_name.split('.')[0] in self.stdlib_modules:
            return 'native_package'
        path = self._resolve_relative_import_path(self.root_dir, module_name)
        print(f"path for {module_name}: {path}")
        print("root dir: ", self.root_dir)
        if path:
            if path.startswith(self.root_dir):
                return 'internal'
            else:
                return 'pip_package'
        return 'pip_package'


    def track_function_call(self, function_name):
        self.function_call_stack.append(function_name)
        self.analyze()

    def describeObject(self, object, session):
        prompt = DescribeObjectPrompt(
            object_type=object.__class__.__name__, 
            object_data={'name':object.name, 'code':object.code}
            )
        log, response = prompt.execute(model='gpt-3.5-turbo')
        object.add_llm_log(log, session)
        return response['choices'][0]['message']['content']
        
    def cleanup(self, root_file, session):
        #go through all the dependencies on all the objects and dedupe them, including combining packages that have multiple imports from the same base module.
        def clean(object, session):
            if object.dependencies:
                for dependency in object.dependencies:
                    clean(dependency, session)
            #pip packages
            if object.pip_packages:
                pip_packages = {}
                for package in object.pip_packages:
                    if package['module'] in pip_packages:
                        pip_packages[package['module']] += package['imports']
                    else:
                        pip_packages[package['module']] = package['imports']
                object.pip_packages = [{'module':module, 'imports':imports} for module, imports in pip_packages.items()]
            #native packages
            if object.native_packages:
                native_packages = {}
                for package in object.native_packages:
                    if package['module'] in native_packages:
                        native_packages[package['module']] += package['imports']
                    else:
                        native_packages[package['module']] = package['imports']
                object.native_packages = [{'module':module, 'imports':imports} for module, imports in native_packages.items()]
            session.commit()
        clean(root_file, session)

    def update_dependency_digraph(self, session):
        from models import Project
        digraph = self.build_dependency_digraph(session)
        project = session.query(Project).filter_by(id=self.project_id).first()
        project.dependency_digraph = digraph
        session.commit()

    def build_dependency_digraph(self, session):
        from models import File, Model, Class, CodeMixin, Method
        from models.utils.code_mixin import code_object_dependencies
        self.digraph = nx.DiGraph()
        root_file = session.query(File).filter_by(project_id = self.project_id,path=os.path.abspath(self.root_file)).first()
        if not root_file:
            raise Exception(f"Root file {self.root_file} not found in the database.")
        def add_edges(object):
            print(f"handling edges for {object.name}")
            if object:
                for dependency in object.dependencies:
                    if not self.digraph.has_edge(f"{object.name}", f"{dependency.name}"):
                        self.digraph.add_edge(f"{object.name}", f"{dependency.name}")
                        add_edges(dependency)
                #find any objects that depend on this object and add them as well.
                dependents = session.query(CodeMixin).filter(CodeMixin.dependencies.any(CodeMixin.id == object.id)).all()
                print(f"dependents found: {dependents}")
                for dependent in dependents:
                    if not self.digraph.has_edge(f"{dependent.name}", f"{object.name}"):
                        self.digraph.add_edge(f"{dependent.name}", f"{object.name}")
                    add_edges(dependent)
                # do the same for models and classes
                dependents = session.query(Model).filter(Model.dependencies.any(CodeMixin.id == object.id)).all()
                for dependent in dependents:
                    if not self.digraph.has_edge(f"{dependent.name}", f"{object.name}"):
                        self.digraph.add_edge(f"{dependent.name}", f"{object.name}")
                    add_edges(dependent)
                dependents = session.query(Class).filter(Class.dependencies.any(CodeMixin.id == object.id)).all()
                for dependent in dependents:
                    if not self.digraph.has_edge(f"{dependent.name}", f"{object.name}"):
                        self.digraph.add_edge(f"{dependent.name}", f"{object.name}")
                    add_edges(dependent)
                #and methods
                dependents = session.query(Method).filter(Method.dependencies.any(CodeMixin.id==object.id)).all()
                for dependent in dependents:
                    if not self.digraph.has_edge(f"{dependent.name}", f"{object.name}"):
                        self.digraph.add_edge(f"{dependent.name}", f"{object.name}")
                    add_edges(dependent)
        add_edges(root_file)
        #add any missing edges by using the code_object_dependencies table.
        new_edges = session.query(code_object_dependencies).all()
        for pair in new_edges:
            obj = session.get(CodeMixin, pair[0])
            if obj:
                if obj.project_id == self.project_id:
                    add_edges(obj)
        session.commit()
        return self.digraph

    def display_dependency_digraph(self):
        pos = nx.spring_layout(self.digraph)
        plt.figure(figsize=(20, 20))

        node_colors = []
        for node in self.digraph.nodes():
            if node==self.root_file:
                node_colors.append('yellow')
            else:
                in_degree = self.digraph.in_degree(node)
                out_degree = self.digraph.out_degree(node)
                if in_degree == 0 and out_degree > 0:
                    node_colors.append('green')
                elif in_degree > 0 and out_degree == 0:
                    node_colors.append('red')
                else:
                    node_colors.append('blue')

        nx.draw_networkx_nodes(self.digraph, pos, node_color=node_colors, node_size=300)
        nx.draw_networkx_edges(self.digraph, pos)
        nx.draw_networkx_labels(self.digraph, pos, font_size=8, font_family="sans-serif")

        plt.title("Dependency Digraph")


        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return buf.getvalue()
   


def main():
    root_file = "app.py"  # Replace with the actual path to your main file
    analyzer = DependencyAnalyzer(root_file)
    analyzer.analyze()
    deps = analyzer.get_dependencies()
    #print(json.dumps(deps, indent=4, default=lambda o: o.__dict__))
    analyzer.build_dependency_digraph()
    return analyzer
    #print("Nodes in digraph:")
    #print(analyzer.digraph.nodes)
    #print("Edges in digraph:")
    #print(analyzer.digraph.edges)


if __name__ == "__main__":
    main()

