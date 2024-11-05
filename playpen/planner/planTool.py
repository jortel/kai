import pprint
import re
import shutil
import time
from typing import List

import tree_sitter
import tree_sitter_java
from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from tree_sitter_languages.core import Language

pp = pprint.PrettyPrinter(indent=2)

# m_id = "meta.llama3-70b-instruct-v1:0"
m_id = "meta.llama3-2-90b-instruct-v1:0"
# m_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
llm = ChatBedrock(model_id=m_id, model_kwargs={"temperature": 0.1})


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

fetch_system = """
You are an expert java programming assistant designed to designed to fetch code needed to fix issues.
Foreach tool YOU invoked, explain how the invocation would fetch code needed to fix the issue.
Include the issue number in your description.

## Terms:
1. Class `declaration` - Class declaration without the body. Includes:
   - annotations
   - decorators
   - name
   - superclass
2. Class `body` - Class declaration with the body. Includes:
   - attributes
   - methods
3. Method `declaration` - Method declaration without the body. Includes:
   - annotations
   - name
   - parameters
   - returned type
   - exceptions raised

## Notes:
1. Annotations are part of class and method declarations.
2. Mention associated issues numbers in function reasons.
"""

fetch_human = """
Invoke tools to fix these issues:
{issues}
"""

patch_system = """
You are an expert java programming assistant.

I will provided a set of issues to be addressed in java code.
You will fix the issues in the provided code fragments (of java code).
After all of the issues have been fixed, output the fixed code fragments.

## Output:
Return the fixed patches in JSON.
Ensure JSON has markdown syntax highlighting.
Make sure to copy the input fragment begin, end, reason and issues fields
to the output objects.
"""

patch_human = """
I will provided a set of issues to be addressed in java code.
You will fix the issues in the provided code fragments (of java code).
After all of the issues have been fixed, output the fixed code fragments.

## Fragments:
```json
{patches}
```

## Issues:
{issues}

## Output:
Return the fixed patches in JSON.
Ensure JSON has markdown syntax highlighting.
Make sure to copy the input fragment begin, end, reason and issues fields
to the output objects.
"""


class Patch(object):
    def __init__(self, d: dict = None, begin: int = 0, end: int = 0, code: str = ""):
        self.kind = ""
        self.path = ""
        self.begin = begin
        self.end = end
        self.code = code
        self.issues = set()
        self.reason = ""
        if d:
            self.update(d)

    def dict(self) -> str:
        d = {}
        d.update(self.__dict__)
        d["issues"] = list(self.issues)
        return d

    def update(self, d):
        self.__dict__.update(d)
        self.issues = set(self.issues)

    def __repr__(self):
        return (
            f"\n\nPatch({self.kind}):\n"
            f"path: {self.path}\n"
            f"issues: {self.issues}\n"
            f"reason: {self.reason}\n"
            f"begin: {self.begin}\n"
            f"end: {self.end}\n"
            f"code:\n{self.code} "
        )

    def __str__(self):
        return repr(self)

    def __lt__(self, other):
        return self.begin < other.begin

    def __eq__(self, other):
        return self.begin == other.begin


class Kind(object):
    IMPORT = "import"
    CLASS = "class"
    METHOD = "method"


class Tool(object):
    def __init__(self, d: dict, path: str):
        self.path = path
        self.kind = ""
        self.name = ""
        self.match = ""
        self.reason = ""
        self.__dict__.update(d)

    def __call__(self, language: Language, root) -> Patch:
        pass


class Fetch(object):
    def __init__(self, language: Language, root):
        self.language = language
        self.root = root
        self.path = ""
        self.kind = ""
        self.name = ""
        self.match = ""
        self.reason = ""

    @tool
    def fetch(self, kind: str, reason: str, name: str, match: str) -> Patch:
        """
        fetch code constructs by kind.
        """
        pass

    def __call__(self, d: dict, path: str) -> Patch:
        self.__dict__.update(d)
        patch = None
        match self.kind:
            case Kind.IMPORT:
                q = f"""
                ((import_declaration) @constant)
                """
                tq = tree_sitter.Query(self.language, q)
                captured = tq.captures(self.root)
                begin = 0
                end = 0
                for capture in captured:
                    node, name = capture
                    if begin == 0:
                        begin = node.start_byte
                    end = node.end_byte
                with open(self.path, "r") as file:
                    file.seek(begin)
                    content = file.read(end - begin)
                patch = Patch(
                    begin=begin,
                    end=end,
                    code=content,
                )
            case Kind.CLASS:
                q = f"""
                ((class_declaration) @constant)
                """
                tq = tree_sitter.Query(self.language, q)
                captured = tq.captures(self.root)
                for capture in captured:
                    node, name = capture
                    begin = node.start_byte
                    end = node.end_byte
                    text = node.text
                    for child in node.children:
                        if child.type == "class_body":
                            end = child.start_byte
                            break
                    text = text[: end - begin]
                    text = text.decode("utf-8")
                    patch = Patch(
                        begin=begin,
                        end=end,
                        code=text,
                    )
            case Kind.METHOD:
                q = f"""
                ((method_declaration) @constant)
                """
                tq = tree_sitter.Query(self.language, q)
                captured = tq.captures(self.root)
                for capture in captured:
                    node, name = capture
                    begin = node.start_byte
                    end = node.end_byte
                    text = node.text
                    text = text.decode("utf-8")
                    patch = Patch(
                        begin=begin,
                        end=end,
                        code=text,
                    )
            case _:
                print("kind {self.kind} not supported.")
        if patch:
            patch.kind = self.kind
            patch.reason = self.reason
        return patch


class Planner(object):

    def __init__(self, path):
        self.path = path
        java = tree_sitter_java.language()
        self.language = tree_sitter.Language(java)
        self.parser = tree_sitter.Parser(self.language)
        with open(path, "r") as file:
            content = file.read()
        tree = self.parser.parse(bytes(content, "utf8"))
        self.root = tree.root_node

    def predict(self) -> List[Patch]:
        pass

    def fetch(self, predicted: List[Patch]) -> List[Patch]:
        tools = [
            Fetch(self.language, self.root).fetch,
        ]
        message = self.send(
            messages=[
                # SystemMessage(fetch_system),
                # HumanMessage(fetch_human.format(issues=issues)),
                HumanMessage("fetch a method named 'hello' using the tools provided."),
            ],
            tools=tools,
        )

        patches = []
        for fn in message.tool_calls:
            pass

        collated = {}
        for p in patches:
            key = hash(p.code)
            if key in collated:
                collated[key].issues.update(p.issues)
            else:
                collated[key] = p
        patches = list(collated.values())
        return patches

    def send(self, messages: List[BaseMessage], tools=()) -> AIMessage:
        mark = time.time()
        model = llm.bind_tools(tools)
        message = model.invoke(messages)
        duration = time.time() - mark
        print(f"\n\nLLM (duration={duration:.2f}s)\n{message.content}\n\n")
        return message

    def plan(self):
        mark = time.time()
        print("\n*************  PREDICT PATCHES ****************")
        patches = self.predict()
        print("\n*************  FETCH PATCHES ****************")
        patches = self.fetch(patches)
        duration = time.time() - mark
        print(f"\nDONE (duration={duration:.2f}s)\n")


if __name__ == "__main__":
    _in = "./mdb.java"
    _out = _in + ".patched"
    shutil.copy(_in, _out)
    planner = Planner(path=_out)
    planner.plan()
