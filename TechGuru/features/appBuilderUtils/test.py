import ast
import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class Node(Base):
    __tablename__ = 'nodes'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    node_type = Column(String, nullable=False)
    file = Column(String, nullable=False)

class Dependency(Base):
    __tablename__ = 'dependencies'
    id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey('nodes.id'), nullable=False)
    dependency = Column(String, nullable=False)

    node = relationship('Node', back_populates='dependencies')

Node.dependencies = relationship('Dependency', order_by=Dependency.id, back_populates='node')

engine = create_engine('sqlite:///codebase.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def parse_codebase(directory):
    ast_trees = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    source = f.read()
                    tree = ast.parse(source, filename=file)
                    ast_trees.append((file, tree))
    return ast_trees

class DependencyVisitor(ast.NodeVisitor):
    def __init__(self):
        self.dependencies = {}

    def visit_FunctionDef(self, node):
        self.dependencies[node.name] = {
            'type': 'function',
            'dependencies': [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]
        }
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.dependencies[node.name] = {
            'type': 'class',
            'dependencies': [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]
        }
        self.generic_visit(node)

def extract_dependencies(ast_trees):
    dependencies = {}
    for filename, tree in ast_trees:
        visitor = DependencyVisitor()
        visitor.visit(tree)
        dependencies[filename] = visitor.dependencies
    return dependencies

def store_dependencies(dependencies):
    for file, nodes in dependencies.items():
        for name, info in nodes.items():
            node = Node(name=name, node_type=info['type'], file=file)
            session.add(node)
            session.flush()  # Ensure node.id is available
            for dep in info['dependencies']:
                dependency = Dependency(node_id=node.id, dependency=dep)
                session.add(dependency)
    session.commit()

def get_all_dependencies(session, node_name, visited=None):
    if visited is None:
        visited = set()
    
    if node_name in visited:
        return set()
    
    visited.add(node_name)
    
    node = session.query(Node).filter_by(name=node_name).one_or_none()
    if node is None:
        return set()
    
    dependencies = set()
    for dep in node.dependencies:
        dependencies.add(dep.dependency)
        dependencies.update(get_all_dependencies(session, dep.dependency, visited))
    
    return dependencies

def generate_imports(dependencies):
    imports = []
    for dep in dependencies:
        # Assuming each dependency is a module or function in the same codebase
        imports.append(f"import {dep}")
    return "\n".join(imports)

def create_python_file(node_name, imports, output_directory):
    content = f"# Auto-generated file for {node_name}\n\n"
    content += imports
    file_path = os.path.join(output_directory, f"{node_name}_with_dependencies.py")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created file: {file_path}")

def generate_dependency_file(node_name, output_directory='output'):
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    
    dependencies = get_all_dependencies(session, node_name)
    imports = generate_imports(dependencies)
    create_python_file(node_name, imports, output_directory)