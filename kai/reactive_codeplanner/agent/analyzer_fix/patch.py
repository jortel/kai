import json
import pprint
import re
import time
from typing import List, Tuple, override

import tree_sitter
import tree_sitter_java
from jinja2 import Template
from langchain_core.messages import HumanMessage, SystemMessage
from tree_sitter import Node

from kai.analyzer_types import Incident
from kai.llm_interfacing.model_provider import ModelProvider

pp = pprint.PrettyPrinter(indent=2)


class Patch(object):
    kind: str = ""
    path: str = ""
    begin: int = 0
    end: int = 0
    code: str = ""
    reason = ""

    def __init__(self, begin: int = 0, end: int = 0, code: str = ""):
        self.begin = begin
        self.end = end
        self.code = code

    def json(self) -> str:
        return json.dumps(self.__dict__, indent=2)

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


class Filter(object):
    kind: str = ""
    name: str = ""
    pattern: str = ""

    def __init__(self, kind: str, name: str = "", pattern: str = ""):
        self.kind = kind
        self.name = name
        self.pattern = pattern

    def match(self, node: Node):
        return node.type == self.kind and self.named(node) and self.match_pattern(node)

    def named(self, node: Node) -> bool:
        if self.name == "":
            return True
        for child in node.children:
            text = node.text.decode("utf-8")
            if child.type == "identifier" and text == self.name:
                return True
        return False

    def match_pattern(self, node: Node) -> bool:
        if self.pattern == "":
            return True
        text = node.text.decode("utf-8")
        match = re.search(self.pattern, text, re.DOTALL)
        return match is not None


class Tree(object):
    IMPORT = "import_declaration"
    CLASS = "class_declaration"
    FIELD = "field_declaration"
    METHOD = "method_declaration"

    def __init__(self, path: str, content: str, root: Node):
        self.path = path
        self.content = content
        self.root = root

    def find(self, filter: Filter) -> List[Node]:
        matched = []

        def find(node: Node):
            if filter.match(node):
                matched.append(node)
                return
            for child in node.children:
                find(child)

        find(self.root)
        return matched

    def first(self, filter: Filter) -> Tuple[bool, Node | None]:
        matched = self.find(filter)
        if len(matched) > 0:
            return True, matched[0]
        return False, None

    def find_at(self, line: int) -> Tuple[bool, Node | None]:
        def at(node) -> Tuple[bool, Node | None]:
            found = False
            row = node.start_point.row + 1
            if row != line:
                for child in node.children:
                    found, node = at(child)
                    if found:
                        break
            else:
                found = True
            return found, node

        return at(self.root)

    def patch(self, node: Node) -> Patch:
        match node.type:
            case self.IMPORT:
                matched = self.find(Filter(kind=node.type))
                begin = 0
                end = 0
                for node in matched:
                    if begin == 0:
                        begin = node.start_byte
                    end = node.end_byte
                content = self.content[end:begin]
                return Patch(begin=begin, end=end, code=content)
            case self.CLASS:
                begin = node.start_byte
                end = node.end_byte
                text = node.text
                for child in node.children:
                    if child.type == "class_body":
                        end = child.start_byte
                        break
                text = text[: end - begin]
                text = text.decode("utf-8")
                return Patch(begin=begin, end=end, code=text)
            case self.METHOD | self.FIELD:
                text = node.text.decode("utf-8")
                return Patch(begin=node.start_byte, end=node.end_byte, code=text)
            case _:
                if node.parent:
                    return self.patch(node.parent)


class Action(object):
    tree: Tree
    kind: str = ""
    name: str = ""
    match: str = ""
    reason: str = ""

    @classmethod
    def new(cls, d: dict, tree: Tree) -> "Action":
        return Fetch(d["parameters"], tree)

    def __init__(self, d: dict, tree: Tree):
        self.__dict__.update(d)
        self.tree = tree

    def __call__(self) -> Patch:
        pass


class Fetch(Action):
    IMPORT = "import"
    CLASS = "class"
    FIELD = "field"
    METHOD = "method"

    @override
    def __call__(self) -> Patch:
        patch = None
        match self.kind:
            case Fetch.IMPORT:
                filter = Filter(kind=Tree.IMPORT)
                found, node = self.tree.first(filter)
                if found:
                    patch = self.tree.patch(node)
            case Fetch.CLASS:
                filter = Filter(kind=Tree.CLASS, name=self.name, pattern=self.match)
                found, node = self.tree.first(filter)
                if found:
                    patch = self.tree.patch(node)
            case Fetch.FIELD:
                filter = Filter(kind=Tree.FIELD, name=self.name, pattern=self.match)
                found, node = self.tree.first(filter)
                if found:
                    patch = self.tree.patch(node)
            case Fetch.METHOD:
                filter = Filter(kind=Tree.METHOD, name=self.name, pattern=self.match)
                found, node = self.tree.first(filter)
                if found:
                    patch = self.tree.patch(node)
            case _:
                print("kind {self.kind} not supported.")
        if patch:
            patch.kind = self.kind
            patch.reason = self.reason
        return patch


class PatchRequest(object):
    provider: ModelProvider = None
    path: str = ""
    content: str = ""
    incidents: List[Incident] = None
    #
    root: Node = None
    #
    fetch_system_prompt = """
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
4 Field `declaration` - Field/Attribute declaration.  Includes:
   - annotations
   - type
   - name

## Actions:
1. fetch: fetch a code snip for the code construct kind.
   parameters:
     kind (string): kind of code construct. Supported values:
     - import -  The import statements (block).
     - class   - The class declaration. This includes annotations but no body.
     - method -  The method declaration. This includes annotations, signature and body.
     - field - The field declaration. This includes annotations.
     reason (string): The rationale for the fetching the code.
     name (string): The optional name of the named kinds such as classes and methods.
     match (string): The optional matching criteria. This is a regex used to match.
  example:
  ```json
  {
    "action": "fetch",
    "parameters": {
      "kind": "import",
      "reason": "The reason explained.",
      "match": "Regex here."
    }
  }
  ```

## Output
A json block for each action grouped by issue.
Ensure json block has markdown syntax highlighting.
Example:
## Issue: 1-4
```json
  {
    "action": "fetch",
    "parameters": {
      "kind": "import",
      "reason": "The reason explained.",
      "match": "Regex here."
    }
  }
  ```
  ## Issue: 4,5
  ```json
  {
    "action": "fetch",
    "parameters": {
      "kind": "import",
      "reason": "The reason explained.",
      "match": "Regex here."
    }
  }
  ```
    """

    fetch_human_prompt = """
## Issues
{% for incident in incidents %}
### Issue {{ loop.index0 }}
Issue to fix: "{{ incident.message | safe }}"
Line number: {{ incident.line_number }}
{% endfor %}
    """

    patch_system_prompt = """
You are an expert java programming assistant.

I will provided a set of issues to be addressed within the provided java code patches.
Each `Patch` object has the schema:
```json
{
  "path": "/path/to/file",
  "begin": 12,
  "end": 200,
  "reason": Replace @jeff annotation to fix issues 1, 2."
  "code": "The code needs to be fixed."
}
```
You will fix the issues in the provided code patches.
After all of the issues have been fixed, output the fixed code fragments.

## Output
Return json object for each patch.
Ensure json has markdown syntax highlighting.
Be sure to copy the input patch begin, end and reason fields
to the output objects.
Example:
```json
{
  "path": "/path/to/file",
  "begin": 12,
  "end": 200,
  "reason": Replace @jeff annotation to fix issues 1, 2."
  "code": "Fixed code."
}
```json
{
  "path": "/path/to/file",
  "begin": 333,
  "end": 443,
  "reason": Replace @This annotation to fix issues 3, 4."
  "code": "Fixed code."
}
    """

    patch_human_prompt = """
## Patches (to be fixed):
{% for patch in patches %}
```json
{{ patch.json() }}
```
{% endfor %}

## Issues
{% for incident in incidents %}
### Issue {{ loop.index0 }}
Issue to fix: "{{ incident.message | safe }}"
Line number: {{ incident.line_number }}
{% endfor %}
    """

    def __init__(
        self,
        provider: ModelProvider,
        path: str,
        content: str,
        incidents: List[Incident],
    ):
        self.provider = provider
        self.content = content
        self.path = path
        self.incidents = incidents
        java = tree_sitter_java.language()
        language = tree_sitter.Language(java)
        parser = tree_sitter.Parser(language)
        tree = parser.parse(bytes(self.content, "utf8"))
        self.root = tree.root_node

    def predict_patches(self) -> List[Patch]:
        patches = []
        tree = Tree(path=self.path, content=self.content, root=self.root)
        for incident in self.incidents:
            found, node = tree.find_at(incident.line_number)
            if found:
                patch = tree.patch(node)
                if patch:
                    patches.append(patch)
        collated = {}
        for p in patches:
            collated[hash(p.code)] = p
        patches = list(collated.values())
        pp.pprint(patches)
        return patches

    def fetch_patches(self) -> List[Patch]:
        tree = Tree(path=self.path, content=self.content, root=self.root)
        system = SystemMessage(self.fetch_system_prompt)
        human = Template(self.fetch_human_prompt)
        human = human.render(incidents=self.incidents)
        human = HumanMessage(human)
        message = self.provider.invoke([system, human])
        patches = []
        pattern = r"(```json)(.*?)(```)"
        matched = re.findall(pattern, message.content, re.DOTALL)
        for m in matched:
            document = m[1]
            d = json.loads(document)
            print(f"\n\nACTION: :\n{d}\n\n")
            action = Action.new(d, tree)
            patch = action()
            if patch:
                patch.path = self.path
                patches.append(patch)
            else:
                pass
        collated = {}
        for p in patches:
            collated[hash(p.code)] = p
        patches = list(collated.values())
        pp.pprint(patches)
        return patches

    def update_patches(self, patches: List[Patch]) -> List[Patch]:
        system = SystemMessage(self.patch_system_prompt)
        human = Template(self.patch_human_prompt)
        human = human.render(incidents=self.incidents, patches=patches)
        human = HumanMessage(human)
        message = self.provider.invoke([system, human])
        patches = []
        pattern = r"(```json)(.*?)(```)"
        matched = re.findall(pattern, message.content, re.DOTALL)
        for m in matched:
            document = m[1]
            d = json.loads(document)
            patch = Patch()
            patch.update(d)
            patches.append(patch)
        pp.pprint(patches)
        return patches

    def apply_patches(self, patches: List[Patch]):
        patches = sorted(patches, reverse=True)
        for patch in patches:
            print(f"\nAPPLY: {patch}")
            print(f"\nREPLACE: >>>{self.content}<<<")
            patched = (
                self.content[: patch.begin] + patch.code + self.content[patch.end :]
            )
            self.content = patched
            print(f"\nREPLACED: >>>{self.content}<<<")

    def __call__(self):
        mark = time.time()
        print("\n*************  PREDICT PATCHES ****************")
        patches = self.predict_patches()
        print("\n*************  FETCH PATCHES ****************")
        patches = self.fetch_patches()
        print("\n*************  FIX ISSUES IN PATCHES ****************")
        patches = self.update_patches(patches)
        print("\n*************  APPLY PATCHES ****************")
        self.apply_patches(patches)
        duration = time.time() - mark
        print(f"\nDONE (duration={duration:.2f}s)\n")
