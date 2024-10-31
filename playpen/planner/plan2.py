import pprint
import re
import time

import tree_sitter
import tree_sitter_java
import yaml
from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain_aws import ChatBedrock
from tree_sitter_languages.core import Language

pp = pprint.PrettyPrinter(indent=2)

m_id = "meta.llama3-70b-instruct-v1:0"
m_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
llm = ChatBedrock(
    model_id=m_id,
    model_kwargs={"temperature": 0.1},
)

issues = """
### Issue 1
Issue to fix: "Replace the `javax.ejb` import statement with `jakarta.ejb` "
Line number: 3
### Issue 2
Issue to fix: "Replace the `javax.ejb` import statement with `jakarta.ejb` "
Line number: 4
### Issue 3
Issue to fix: "Replace the `javax.inject` import statement with `jakarta.inject` "
Line number: 5
### Issue 4
Issue to fix: "Replace the `javax.jms` import statement with `jakarta.jms` "
Line number: 6
### Issue 5
Issue to fix: "Replace the `javax.jms` import statement with `jakarta.jms` "
Line number: 7
### Issue 6
Issue to fix: "Replace the `javax.jms` import statement with `jakarta.jms` "
Line number: 8
### Issue 7
Issue to fix: "Replace the `javax.jms` import statement with `jakarta.jms` "
Line number: 9
### Issue 8
Issue to fix: "Enterprise Java Beans (EJBs) are not supported in Quarkus. CDI must be used.
 Please replace the `@MessageDriven` annotation with a CDI scope annotation like `@ApplicationScoped`."
Line number: 14
### Issue 9
Issue to fix: "The `destinationLookup` property can be migrated by annotating a message handler method (potentially `onMessage`) with the
 `org.eclipse.microprofile.reactive.messaging.Incoming` annotation, indicating the name of the queue as a value:

 Before:
 ```
 @MessageDriven(name = "HelloWorldQueueMDB", activationConfig = 
 public class MessageListenerImpl implements MessageListener 
 }
 ```

 After:
 ```
 public class MessageListenerImpl implements MessageListener 
 }
 ```"
Line number: 15
### Issue 10
Issue to fix: "The `destinationLookup` property can be migrated by annotating a message handler method (potentially `onMessage`) with the
 `org.eclipse.microprofile.reactive.messaging.Incoming` annotation, indicating the name of the queue as a value:

 Before:
 ```
 @MessageDriven(name = "HelloWorldQueueMDB", activationConfig = 
 public class MessageListenerImpl implements MessageListener 
 }
 ```

 After:
 ```
 public class MessageListenerImpl implements MessageListener 
 }
 ```"
Line number: 16
### Issue 11
Issue to fix: "The `destinationLookup` property can be migrated by annotating a message handler method (potentially `onMessage`) with the
 `org.eclipse.microprofile.reactive.messaging.Incoming` annotation, indicating the name of the queue as a value:

 Before:
 ```
 @MessageDriven(name = "HelloWorldQueueMDB", activationConfig = 
 public class MessageListenerImpl implements MessageListener 
 }
 ```

 After:
 ```
 public class MessageListenerImpl implements MessageListener 
 }
 ```"
Line number: 17
### Issue 12
Issue to fix: "References to JavaEE/JakartaEE JMS elements should be removed and replaced with their Quarkus SmallRye/Microprofile equivalents."
Line number: 6
### Issue 13
Issue to fix: "References to JavaEE/JakartaEE JMS elements should be removed and replaced with their Quarkus SmallRye/Microprofile equivalents."
Line number: 7
### Issue 14
Issue to fix: "References to JavaEE/JakartaEE JMS elements should be removed and replaced with their Quarkus SmallRye/Microprofile equivalents."
Line number: 8
### Issue 15
Issue to fix: "References to JavaEE/JakartaEE JMS elements should be removed and replaced with their Quarkus SmallRye/Microprofile equivalents."
Line number: 9
"""

plan7 = """
You are an expert java programming assistant.

I will provided a set of issues to be addressed in java code.
For each issue, you will fetch code snips needed to fix the issue using the provided actions.

## Actions:
- fetch: fetch a code snip for the code construct kind.
  parameters:
    kind (string): kind of code construct. Supported values:
      - import - The import statements (block).
      - class   - The entire class declaration including the body.
      - method - The entire method declaration including the body.
      - class-declaration - A class declaration without the body.
      - method-declaration - A method declaration without the body
    name (string): The (OPTIONAL) name of the named kinds such as classes and methods.
    match (string): The (OPTIONAL) matching criteria. This is a regex used to match.
    reason (string): The rationale for the action.

## Issues
{issues}

## Output
Return a list of actions in YAML grouped by issue number. 
The YAML schema for each action is:
- issues (array of int): List of associated issue numbers.
- actions (array): List of actions.
Ensure YAML has markdown syntax highlighting.
"""


class Fragment(object):
    def __init__(self, kind: str, begin: int, end: int, code: str):
        self.kind = kind
        self.begin = begin
        self.end = end
        self.code = code
        self.issues = []
        self.reason = ""

    def __repr__(self):
        return (
            f"\n\nFRAGMENT({self.kind}): code:\n{self.code} @ {self.begin}/{self.end}"
        )

    def __str__(self):
        return repr(self)


class Kind(object):
    IMPORT = "import"
    CLASS = "class"
    CLASS_DECLARATION = f"{CLASS}-declaration"
    METHOD = "method"
    METHOD_DECLARATION = f"{METHOD}-declaration"


class Action(object):
    @classmethod
    def new(cls, d) -> "Action":
        if "fetch" in d:
            return Fetch(d["fetch"])

    def __call__(self, language, root) -> Fragment:
        pass


class Fetch(Action):
    def __init__(self, d):
        self.kind = ""
        self.name = ""
        self.match = ""
        self.reason = ""
        self.__dict__.update(d)

    def __call__(self, language: Language, root) -> Fragment:
        fragment = None
        match self.kind:
            case Kind.IMPORT:
                if not self.match:
                    self.match = ".+"
                q = f"""
                ((import_declaration)
                    @constant (#match? @constant "{self.match}"))
                """
                tq = tree_sitter.Query(language, q)
                captured = tq.captures(root)
                for capture in captured:
                    node, name = capture
                    text = node.text.decode("utf8")
                    fragment = Fragment(
                        kind=self.kind,
                        begin=node.start_byte,
                        end=node.end_byte,
                        code=text,
                    )
            case Kind.CLASS_DECLARATION:
                q = f"""
                ((class_declaration) @constant)
                """
                tq = tree_sitter.Query(language, q)
                captured = tq.captures(root)
                for capture in captured:
                    node, name = capture
                    body = None
                    for child in node.children:
                        if child.type == "class_body":
                            body = child
                            break
                    end = body.start_byte - node.start_byte
                    text = node.text[:end]
                    fragment = Fragment(
                        kind=self.kind,
                        begin=node.start_byte,
                        end=body.start_byte,
                        code=text,
                    )
            case Kind.METHOD:
                q = f"""
                ((method_declaration) @constant)
                """
                tq = tree_sitter.Query(language, q)
                captured = tq.captures(root)
                for capture in captured:
                    node, name = capture
                    text = node.text.decode("utf8")
                    fragment = Fragment(
                        kind=self.kind,
                        begin=node.start_byte,
                        end=node.end_byte,
                        code=text,
                    )
            case _:
                print("kind {self.kind} not supported.")
        return fragment


class Planner(object):

    def __init__(self, path, prompt):
        self.prompt = prompt
        java = tree_sitter_java.language()
        self.language = tree_sitter.Language(java)
        self.parser = tree_sitter.Parser(self.language)
        with open(path, "r") as file:
            content = file.read()
        tree = self.parser.parse(bytes(content, "utf8"))
        self.root = tree.root_node

    def query(self, q):
        print(f"\n\nFind:{q})\n\n")
        tq = tree_sitter.Query(self.language, q)
        captured = tq.captures(self.root)
        for capture in captured:
            node, name = capture
            print(
                f"\n\nMatched ({name}) code:{node.text.decode('utf8')} @ {node.start_byte}/{node.end_byte}"
            )

    def fetch(self):
        mark = time.time()
        prompt = PromptTemplate(template=self.prompt)
        chain = LLMChain(llm=llm, prompt=prompt)
        reply = chain.invoke({"issues": issues})
        output = reply["text"]
        duration = time.time() - mark
        print(f"\n\nLLM (duration={duration:.2f}s)\n{output}\n\n")

        pattern = r"(```yaml)(.+)(```)"
        matched = re.findall(pattern, output, re.DOTALL)
        for m in matched:
            document = m[1]
            actions = yaml.safe_load(document)
            for d in actions:
                for action in d["actions"]:
                    print(f"\n\nACTION: :\n{action}\n\n")
                    action = Action.new(action)
                    fragment = action(self.language, self.root)
                    if fragment:
                        print(fragment)

    def patch(self):
        pass


def query():
    while True:
        print("> ")
        lines = []
        while True:
            line = input()
            if line:
                lines.append(line)
            else:
                break
        try:
            q = "\n".join(lines)
            planner.query(q)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    planner = Planner(path="./mdb.java", prompt=plan7)
    planner.fetch()
