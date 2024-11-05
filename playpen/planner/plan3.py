import json
import pprint
import re
import shutil
import time
from os.path import basename
from typing import List

import tree_sitter
import tree_sitter_java
from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain_aws import ChatBedrock
from tree_sitter_languages.core import Language

pp = pprint.PrettyPrinter(indent=2)

m_id = "meta.llama3-70b-instruct-v1:0"
m_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
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

fetch_prompt = """
You are an java programming assistant designed to generate json actions.
I will provided a set of issues found in java code.
For each issue, you will generate json to fetch relevant code fragments needed to fix the issue.

## Guidelines
1. Consolidate actions when possible.
2. kind=import actions can ALL be consolidated.

## Terms
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

## Actions:
1. fetch: fetch a code snip for the code construct kind.
   parameters:
     kind (string): kind of code construct. Supported values:
     - import -  The import statements (block).
     - class   - The class declaration. This includes annotations but no body.
     - method -  The method declaration. This includes annotations, signature and body.
     reason (string): The rationale for the fetching the code.
     name (string): The optional name of the named kinds such as classes and methods.
     match (string): The optional matching criteria. This is a regex used to match.
  example:
  ```json
  {{
    "action": "fetch",
    "parameters": {{
      "kind": "import",
      "reason": "The reason explained.",
      "match": "Regex here."
    }}
  }}
  ```

## Issues
{issues}

## Output
A json block for each action grouped by issue.
Ensure json block has markdown syntax highlighting.
Example:
## Issue: 1-4
```json
  {{
    "action": "fetch",
    "parameters": {{
      "kind": "import",
      "reason": "The reason explained.",
      "match": "Regex here."
    }}
  }}
  ```
  ## Issue: 4,5
  ```json
  {{
    "action": "fetch",
    "parameters": {{
      "kind": "import",
      "reason": "The reason explained.",
      "match": "Regex here."
    }}
  }}
  ```
"""

patch_prompt = """
You are an expert java programming assistant.

I will provided a set of issues to be addressed within the provided java code patches.
Each `Patch` object has the schema:
```json
{{
  "path": "/path/to/file",
  "begin": 12,
  "end": 200,
  "reason": Replace @jeff annotation to fix issues 1, 2."
  "code": "The code needs to be fixed."
}}
```
You will fix the issues in the provided code patches.
After all of the issues have been fixed, output the fixed code fragments.

## Patches (to be fixed):
{patches}

## Issues
{issues}

## Output
Return json object for each patch.
Ensure json has markdown syntax highlighting.
Be sure to copy the input patch begin, end and reason fields
to the output objects.
Example:
```json
{{
  "path": "/path/to/file",
  "begin": 12,
  "end": 200,
  "reason": Replace @jeff annotation to fix issues 1, 2."
  "code": "Fixed code."
}}
```json
{{
  "path": "/path/to/file",
  "begin": 333,
  "end": 443,
  "reason": Replace @This annotation to fix issues 3, 4."
  "code": "Fixed code."
}}
"""


class Patch(object):
    def __init__(self, d: dict = None, begin: int = 0, end: int = 0, code: str = ""):
        self.kind = ""
        self.path = ""
        self.begin = begin
        self.end = end
        self.code = code
        self.reason = ""
        if d:
            self.update(d)

    def dict(self) -> dict:
        return self.__dict__

    def update(self, d):
        self.__dict__.update(d)

    def __repr__(self):
        return (
            f"\n\nPatch({self.kind}):\n"
            f"path: {self.path}\n"
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


class Action(object):
    @classmethod
    def new(cls, d: dict, path: str) -> "Action":
        return Fetch(d["parameters"], path)

    def __init__(self, d: dict, path: str):
        self.path = path
        self.kind = ""
        self.name = ""
        self.match = ""
        self.reason = ""
        self.__dict__.update(d)

    def __call__(self, language: Language, root) -> Patch:
        pass


class Fetch(Action):
    def __call__(self, language: Language, root) -> Patch:
        patch = None
        match self.kind:
            case Kind.IMPORT:
                q = f"""
                ((import_declaration) @constant)
                """
                tq = tree_sitter.Query(language, q)
                captured = tq.captures(root)
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
                tq = tree_sitter.Query(language, q)
                captured = tq.captures(root)
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
                tq = tree_sitter.Query(language, q)
                captured = tq.captures(root)
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

    def fetch(self) -> List[Patch]:
        output = self.send(tag="fetch", template=fetch_prompt, issues=issues)

        patches = []
        pattern = r"(```json)(.*?)(```)"
        matched = re.findall(pattern, output, re.DOTALL)
        for m in matched:
            document = m[1]
            d = json.loads(document)
            print(f"\n\nACTION: :\n{d}\n\n")
            action = Action.new(d, self.path)
            patch = action(self.language, self.root)
            if patch:
                patch.path = self.path
                patches.append(patch)
                print(patch)
            else:
                pass
        collated = {}
        for p in patches:
            collated[hash(p.code)] = p
        patches = list(collated.values())
        return patches

    def patch(self, patches: List[Patch]) -> List[Patch]:
        part = []
        for p in patches:
            d = p.dict()
            p = "```json\n%s\n```" % json.dumps(d, indent=2)
            part.append(p)
        patches = "\n".join(part)
        output = self.send(
            tag="patch", template=patch_prompt, issues=issues, patches=patches
        )

        patches = []
        pattern = r"(```json)(.*?)(```)"
        matched = re.findall(pattern, output, re.DOTALL)
        for m in matched:
            document = m[1]
            d = json.loads(document)
            patch = Patch(d=d)
            patches.append(patch)
            print(patch)
        return patches

    def apply(self, patches: List[Patch]):
        patches = sorted(patches, reverse=True)
        for patch in patches:
            print(f"\nAPPLY: {patch}")
            n = patch.end - patch.begin
            with open(self.path, "r+") as file:
                # DEBUG
                file.seek(patch.begin)
                content = file.read(patch.end - patch.begin)
                print(f"\nREPLACE: >>>{content}<<<")
                file.seek(0)
                # DEBUG

                part = [
                    file.read(patch.begin),
                    patch.code,
                ]
                file.seek(patch.end)
                part.append(file.read())
            with open(self.path, "w") as file:
                for p in part:
                    file.write(p)

    def send(self, tag: str, template: str, **params) -> str:
        mark = time.time()
        prompt = PromptTemplate(template=template)
        chain = LLMChain(llm=llm, prompt=prompt)
        reply = chain.invoke(params)
        output = reply["text"]
        duration = time.time() - mark
        print(f"\n\nLLM (duration={duration:.2f}s)\n{output}\n\n")
        sent = template.format(**params)
        with open(f"./output/{tag}.prompt", "w") as file:
            file.write(sent)
        with open(f"./output/{tag}.output", "w") as file:
            file.write(output)
        return output

    def plan(self):
        mark = time.time()
        print("\n*************  PREDICT PATCHES ****************")
        patches = self.predict()
        print("\n*************  FETCH PATCHES ****************")
        patches = self.fetch()
        print("\n*************  FIX ISSUES IN PATCHES ****************")
        patches = self.patch(patches)
        print("\n*************  APPLY PATCHES ****************")
        self.apply(patches)
        duration = time.time() - mark
        print(f"\nDONE (duration={duration:.2f}s)\n")


if __name__ == "__main__":
    input = "./input/mdb.java"
    output = "./output/" + basename(input)
    shutil.copy(input, output)
    planner = Planner(path=output)
    planner.plan()
