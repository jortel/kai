import os

import tree_sitter
import tree_sitter_java
from sqlalchemy import Column, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, relationship

engine = create_engine("sqlite:///java_ast.db")


class Base(DeclarativeBase):
    pass


# Define SQLAlchemy models for each table
class Import(Base):
    __tablename__ = "Import"
    id = Column(Integer, primary_key=True)
    code = Column(Text, nullable=False)


class Class(Base):
    __tablename__ = "Class"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(Text, nullable=True)

    annotations = relationship("ClassAnnotation", back_populates="class_")
    methods = relationship("Method", back_populates="class_")


class ClassAnnotation(Base):
    __tablename__ = "ClassAnnotation"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("Class.id"), nullable=False)
    code = Column(Text, nullable=False)

    class_ = relationship("Class", back_populates="annotations")


class Method(Base):
    __tablename__ = "Method"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("Class.id"), nullable=False)
    name = Column(String, nullable=False)
    signature = Column(Text, nullable=False)
    code = Column(Text, nullable=True)

    class_ = relationship("Class", back_populates="methods")
    annotations = relationship("MethodAnnotation", back_populates="method")
    parameters = relationship("MethodParameter", back_populates="method")


class MethodAnnotation(Base):
    __tablename__ = "MethodAnnotation"
    id = Column(Integer, primary_key=True)
    method_id = Column(Integer, ForeignKey("Method.id"), nullable=False)
    code = Column(Text, nullable=False)

    method = relationship("Method", back_populates="annotations")


class MethodParameter(Base):
    __tablename__ = "MethodParameter"
    id = Column(Integer, primary_key=True)
    method_id = Column(Integer, ForeignKey("Method.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)

    method = relationship("Method", back_populates="parameters")


# Insert data into tables based on parsed Java code
def insert_import(session, code):
    session.add(Import(code=code))


def insert_class(session, name, code):
    new_class = Class(name=name, code=code)
    session.add(new_class)
    session.flush()  # Flush to get ID for relationships
    return new_class.id


def insert_class_annotation(session, class_id, code):
    session.add(ClassAnnotation(class_id=class_id, code=code))


def insert_method(session, class_id, name, signature, code):
    new_method = Method(class_id=class_id, name=name, signature=signature, code=code)
    session.add(new_method)
    session.flush()  # Flush to get ID for relationships
    return new_method.id


def insert_method_annotation(session, method_id, code):
    session.add(MethodAnnotation(method_id=method_id, code=code))


def insert_method_parameter(session, method_id, name, param_type):
    session.add(MethodParameter(method_id=method_id, name=name, type=param_type))


def parse(path, parser, session):
    with open(path, "r") as file:
        code = file.read()
    tree = parser.parse(bytes(code, "utf8"))

    def traverse(node):
        match node.type:
            case "package_declaration":
                print("(%s) found.", node.type)
                for n in node.children:
                    traverse(n)
            case "import_declaration":
                print("(%s) found. %s" % (node.type, node.text.decode("utf8")))
                for n in node.children:
                    traverse(n)
            case "class_declaration":
                print("(%s) found. %s" % (node.type, node.text.decode("utf8")))
                for n in node.children:
                    traverse(n)
            case "method_declaration":
                print("(%s) found. %s" % (node.type, node.text.decode("utf8")))
                for n in node.children:
                    traverse(n)
            case "formal_parameters":
                print("(%s) found. %s" % (node.type, node.text.decode("utf8")))
                for n in node.children:
                    traverse(n)
            case _:
                print("(%s) found. %s" % (node.type, node.text.decode("utf8")[:20]))
                for n in node.children:
                    traverse(n)

    traverse(tree.root_node)
    print("parsed")


def main():
    Base.metadata.create_all(engine)
    java = tree_sitter_java.language()
    parser = tree_sitter.Parser(tree_sitter.Language(java))
    with Session(engine) as session:
        for root, _, files in os.walk("."):
            for file in files:
                if file.endswith(".java"):
                    path = os.path.join(root, file)
                    parse(path, parser, session)
        session.commit()

    print("Java source code parsed and data inserted into the database.")


if __name__ == "__main__":
    main()
