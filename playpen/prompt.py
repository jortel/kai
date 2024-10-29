import json
import pprint
import re
from typing import List

import patch
from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain_aws import ChatBedrock

pp = pprint.PrettyPrinter(indent=2)

# anthropic.claude-3-5-sonnet-20240620-v1:0
# meta.llama3-70b-instruct-v1:0
llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs={"temperature": 0},
)

code = """
package com.example;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import jakarta.xml.bind.annotation.XmlRootElement;

public class Shape {
    public int getLen() {
        return 10;
    }
}
"""

code2 = """
1. package com.example;
2.
3. import jakarta.persistence.Column;
4. import jakarta.persistence.Entity;
5. import jakarta.persistence.Id;
6. import jakarta.persistence.Table;
7. import jakarta.persistence.UniqueConstraint;
8. import jakarta.xml.bind.annotation.XmlRootElement;
9.
10. public class Cat {
11.    public int age() {
12.        return 10;
13.    }
14.}
15.
16. public class Shape {
17.    public int getLen() {
18.        return 10;
19.    }
20.}
"""


def do_patch():
    path = "/tmp/shape.java"
    template = """
    # You are an expert java programmer.

    ## Patch Format:

    Each file that is modified in the patch has a header.
    The --- line indicates the original file path (before the changes).
    The +++ line indicates the new file path (after the changes).
    Change Blocks (or hunks):

    Changes are organized into "hunks," which show the specific lines modified in the file.
    Each hunk starts with an @@ line, which indicates the location of the change in the file (the line number and number of lines).
    Lines prefixed with a - indicate removed lines.
    Lines prefixed with a + indicate added lines.
    Unchanged context lines are shown without a prefix to provide context for the changes.

    ## Do the following changes to the input code:
    1. Add import jakarta.other.Test;
    2. Add a method name "toString" to the Shape class.
      a. Return type: string
      b. Body: return "Elmer"
    3. Rename the "getLen" method to "getLength"
    4. Add an parameter named "base" of type int to the "getLength" method. 

    ## Input File path: "/tmp/shape.java"

    ## Input Code:
    {code}

    ## Output:
    1. Express the updated code in patch format.
    2. Your reply must only include the patch.
    """
    with open(path, "w") as f:
        f.write(code)

    prompt = PromptTemplate(template=template)
    chain = LLMChain(llm=llm, prompt=prompt)
    reply = chain.invoke({"path": path, "code": code})

    output = reply["text"]
    print("OUTPUT:\n%s" % output)

    patch_set = patch.fromstring(output.encode("utf-8"))
    if patch_set:
        pprint.pprint("PARSED")
        applied = patch_set.apply(root="/")
        if applied:
            pp.pprint("APPLIED")
        else:
            return
    else:
        return

    with open(path, "r") as f:
        patched = f.read()

    print("PATCHED \n%s" % patched)


def do_patch2():
    path = "/tmp/shape.java"
    template = """
    # You are an expert java programmer.

    ## Patch Format:
    Each line in the input code is prefixed with a line number witch must be preserved in the patch.
    Each line in the output patch must contain the line number of the corresponding line in the input code.
    Lines prefixed with a - indicates a removed line.
    Lines prefixed with a + indicates an added line.

    ## Do the following changes to the input code:
    1. Add import jakarta.other.Test;
    2. Add a method name "toString" to the Shape class.
      a. Return type: string
      b. Body: return "Elmer"
    3. Rename the "getLen" method to "getLength"
    4. Add an parameter named "base" of type int to the "getLength" method.
    5. Add a new class named Dog with public methods:
       a. bark() with returns a string "woof".
       b. sit() void.
    6. Remove the age method from the Cat class.

    ## Input File path: "/tmp/shape.java"

    ## Input Code:
    {code}

    ## Output:
    1. Express the updated code in patch format.
    2. Your reply must only include the patch.
    """
    prompt = PromptTemplate(template=template)
    chain = LLMChain(llm=llm, prompt=prompt)
    print("SENDING:\n%s" % template.format(code=code2))
    reply = chain.invoke({"path": path, "code": code2})

    output = reply["text"]
    print("OUTPUT:\n%s" % output)


class Patch:
    def __init__(self, begin: str, end: str, code: str):
        self.begin = int(begin)
        self.end = int(end)
        self.code = code

    def update(self, code: str, skew: int) -> (str, int):
        self.begin += skew
        self.end += skew
        begin = code[: self.begin]
        fragment = self.code
        end = code[self.end :]
        patched = begin + fragment + end
        skew = len(self.code) - (self.end - self.begin)
        return patched, skew


def do_edit():
    template = """
    # You are an expert java programmer.
    
    ## Editor Functions:
    2. **Replace the specified code**:
      Name: replace
      Description: Replace a code between the `begin` and `end` offsets
        within the `input code` with a the desired `code`. The offset is the number of characters
        from the beginning of the input code.
      Arguments:
      - description: str - A description of the intended change.
      - selection: str - A description of how the begin and end offsets were determined.
      - selected: str - The input code between the begin and end offset.
      - begin: int - The beginning offset of the code fragment to be replaced.
      - end: int - The ending offset of the code fragment to be replaced.
      - code: str - The code to make the requested change.
      Example:
      ```json
      {{ 
        "name": "replace",
        "description": "Add method toString().",
        "selection": "The begin offset points to the end of the class declaration.",
        "selected": "CODE AT BEGIN and END INDEX.",
        "begin": 100,
        "end": 200,
        "code": "UPDATED CODE"
      }}
      
    ## Make the following changes to the input code:
    1. Add a method name "toString" to the Shape class.
      a. Return type: string
      b. Body: return "Elmer"
    2. Rename the "getLen" method to "getLength"
    3. Add an parameter named "base" of type int to the "getLength" method. 
    4. Add import jakarta.other.Test;

    ## Input Code:
    ```java
    {code}
    ```
    
    ## Output:
    1. Invoke the appropriate function to affect perform change.
    1. Make function calls using ONLY the provided functions to perform the requested changes.
    2. Respond with ONLY function calls needed to update the code as requested using json.
    """

    prompt = PromptTemplate(template=template)
    chain = LLMChain(llm=llm, prompt=prompt)
    print("SENDING:\n%s" % template.format(code=code))
    reply = chain.invoke({"code": code})
    output = reply["text"]
    print("OUTPUT:\n%s" % output)
    patches = find_patches(output)
    patched = code
    skew = 0
    for p in patches:
        print("FIND \n%s" % p.find(code))
        patched, p_skew = p.update(patched, skew)
        skew += p_skew
    # print("PATCHED \n%s" % patched)


def find_patches(response: str) -> List[Patch]:
    patches = []
    matched = re.search(r"(```)(json)?(.+)(```)", response, re.MULTILINE | re.DOTALL)
    if not matched:
        return patches
    d = json.loads(matched.group(3))
    if d is None:
        return patches
    for item in d:
        p = Patch(begin=item["begin"], end=item["end"], code=item["code"])
        patches.append(p)
    return patches


def main():
    do_patch2()


if __name__ == "__main__":
    main()
