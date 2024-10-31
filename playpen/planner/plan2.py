import io
import pprint
import re
import time

import tree_sitter
import tree_sitter_java
from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain_aws import ChatBedrock
from ruamel.yaml import YAML
from tree_sitter_languages.core import Language

pp = pprint.PrettyPrinter(indent=2)


def str_representer(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml = YAML()
yaml.default_flow_style = False
yaml.indent(sequence=4, offset=2)
yaml.representer.add_representer(str, str_representer)

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

fetch_prompt = """
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

patch_prompt = """
You are an expert java programming assistant.

I will provided a set of issues to be addressed in java code.
You will fix the issues in the provided code Patchs (of java code).
After all of the issues have been fixed, output the fixed code Patchs.

## Fragments:
```yaml
{patches}
```

## Issues
{issues}

## Output
Return the fixed Patchs in YAML.
Ensure YAML has markdown syntax highlighting.
Make sure to copy the input Patch begin, end, reason and issues fields
to the output objects.
"""


class Patch(object):
    def __init__(self, d: dict = None, begin: int = 0, end: int = 0, code: str = ""):
        self.kind = ""
        self.begin = begin
        self.end = end
        self.code = code
        self.issues = set()
        self.reason = ""
        if d:
            self.update(d)
            return

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
            f"issues: {self.issues}\n"
            f"reason: {self.reason}\n"
            f"code:\n{self.code} "
            f"@ {self.begin}/{self.end}"
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

    def __call__(self, language, root) -> Patch:
        pass


class Fetch(Action):
    def __init__(self, d):
        self.kind = ""
        self.name = ""
        self.match = ""
        self.reason = ""
        self.__dict__.update(d)

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
                statements = []
                for capture in captured:
                    node, name = capture
                    text = node.text.decode("utf8")
                    statements.append(text)
                    begin = node.start_byte
                    end = node.end_byte
                patch = Patch(
                    begin=begin,
                    end=end,
                    code="\n".join(statements),
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
                    text = text.decode("utf-8")
                    patch = Patch(
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
                    patch = Patch(
                        begin=node.start_byte,
                        end=node.end_byte,
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
        java = tree_sitter_java.language()
        self.language = tree_sitter.Language(java)
        self.parser = tree_sitter.Parser(self.language)
        with open(path, "r") as file:
            content = file.read()
        tree = self.parser.parse(bytes(content, "utf8"))
        self.root = tree.root_node

    def fetch(self):
        mark = time.time()
        prompt = PromptTemplate(template=fetch_prompt)
        chain = LLMChain(llm=llm, prompt=prompt)
        reply = chain.invoke({"issues": issues})
        output = reply["text"]
        duration = time.time() - mark
        print(f"\n\nLLM (duration={duration:.2f}s)\n{output}\n\n")

        patches = []
        pattern = r"(```yaml)(.+)(```)"
        matched = re.findall(pattern, output, re.DOTALL)
        for m in matched:
            document = m[1]
            actions = yaml.load(io.StringIO(document))
            for d in actions:
                for item in d["actions"]:
                    print(f"\n\nACTION: :\n{item}\n\n")
                    action = Action.new(item)
                    patch = action(self.language, self.root)
                    if patch:
                        patch.issues.update(set(d["issues"]))
                        patches.append(patch)
                        print(patch)

        collated = {}
        for p in patches:
            key = hash(p.code)
            if key in collated:
                collated[key].issues.update(p.issues)
            else:
                collated[key] = p
        patches = list(collated.values())
        return patches

    def patch(self, patches):
        dicts = []
        for p in patches:
            dicts.append(p.dict())
        stream = io.StringIO()
        yaml.dump(dicts, stream)
        patches = stream.getvalue()
        mark = time.time()
        prompt = PromptTemplate(template=patch_prompt)
        chain = LLMChain(llm=llm, prompt=prompt)
        reply = chain.invoke({"issues": issues, "patches": patches})
        output = reply["text"]
        duration = time.time() - mark
        print(f"\n\nLLM (duration={duration:.2f}s)\n{output}\n\n")

        patches = []
        pattern = r"(```yaml)(.+)(```)"
        matched = re.findall(pattern, output, re.DOTALL)
        for m in matched:
            document = m[1]
            patched = yaml.load(io.StringIO(document))
            for d in patched:
                patch = Patch(d=d)
                patches.append(patch)
                print(patch)
        return patches

    def apply(self, patches):
        pass

    def plan(self):
        patches = self.fetch()
        patches = self.patch(patches)
        self.apply(patches)


if __name__ == "__main__":
    planner = Planner(path="./mdb.java")
    planner.plan()
