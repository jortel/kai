import pprint
import re

import tree_sitter
import tree_sitter_java
import yaml
from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain_aws import ChatBedrock

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

plan1 = """
I will provided a set of issues to be addressed in java code.
You will determine the steps necessary to fix each issue. Each step must be 
one of the predefined `Functions`. Remember goal is to provide a plan. I will
make a subsequent requests to execute each step.

Programming languages are a collection of named constructs:
- import - The block of import statements.
- class.{{name}} - A class definition. {{name}} is the name of the class.
- class.{{name}}.method.{{name}} - {{name}} is the name of the method.
- function.{{name}} - A function definition. {{name}} is the name of the function.

# Functions:
1. Name: fetch
   Description: Fetch a block of source code.
   Return: The requested block of code.
   Parameters:
   - kind: str - Kind of code construct to be fetched.
   Example-1 Fetch import block.:
   ```json
   {{
     "name": "fetch",
     "kind": "import"
   }}
   ```
   Example-1 Return:
   ```java
   import javax.ejb.ActivationConfigProperty;
   import javax.ejb.MessageDriven;
   import javax.inject.Inject;
   import javax.jms.JMSException;
   import javax.jms.Message;
   ```
   Example-2 fetch class definition:
   ```json
   {{
     "name": "fetch",
     "kind": "class.Shape"
   }}
   ```
   Example-2 Return:
   ```java
   public class Shape {{
       public int getLen() {{
           return 10;
       }}
   }}
   ```

## Issues

### Issue 1
Replace the `javax.*` import statements with `jakarta.*`
"""

code = """
package com.redhat.coolstore.service;

import javax.ejb.ActivationConfigProperty;
import javax.ejb.MessageDriven;
import javax.inject.Inject;
import javax.jms.JMSException;
import javax.jms.Message;
import javax.jms.MessageListener;
import javax.jms.TextMessage;

import com.redhat.coolstore.model.Order;
import com.redhat.coolstore.utils.Transformers;

@MessageDriven(name = "OrderServiceMDB", activationConfig = {
	@ActivationConfigProperty(propertyName = "destinationLookup", propertyValue = "topic/orders"),
	@ActivationConfigProperty(propertyName = "destinationType", propertyValue = "javax.jms.Topic"),
	@ActivationConfigProperty(propertyName = "acknowledgeMode", propertyValue = "Auto-acknowledge")})
public class OrderServiceMDB implements MessageListener { 

	@Inject
	OrderService orderService;

	@Inject
	CatalogService catalogService;

	@Override
	public void onMessage(Message rcvMessage) {
		System.out.println("\nMessage recd !");
		TextMessage msg = null;
		try {
				if (rcvMessage instanceof TextMessage) {
						msg = (TextMessage) rcvMessage;
						String orderStr = msg.getBody(String.class);
						System.out.println("Received order: " + orderStr);
						Order order = Transformers.jsonToOrder(orderStr);
						System.out.println("Order object is " + order);
						orderService.save(order);
						order.getItemList().forEach(orderItem -> {
							catalogService.updateInventoryItems(orderItem.getProductId(), orderItem.getQuantity());
						});
				}
		} catch (JMSException e) {
			throw new RuntimeException(e);
		}
	}
}
"""

plan2 = """
You are an expert java programming assistant.

I will provided a set of issues to be addressed in java code.
You will determine the steps necessary to fix each issue. The steps should be a combination
of fetching relevant code blocks and a description of how it should be edited. 

Code fetching steps should fetch complete code constructs.
Constructs are identified using the following convention:
- `import` - The block of import statements.
- `class.Shape` - To fetch the entire `Shape` class definition.
- `class.Shape.method.open` - To fetch the `Shape` class's method named `open`.
- `class.Shape.attribute.weight` - To fetch the `Shape` class's attribute named `weight`.

## Issues
### Issue 1
Replace the `javax.*` import statements with `jakarta.*`

## Output
Return a list of steps in markdown.
"""

plan3 = """
You are an expert java programming assistant.

I will provided a set of issues to be addressed in java code.
You will determine the steps necessary to fix each issue. The steps should be a combination
of fetching relevant code block and a description of how it should be edited.

The code has been parsed and stored in a relation database. See `Tables` for the schema.

## Tables
1. Import - contains import statements.
   columns:
   - code TEXT
2. Class - contains class definitions.
   columns:
   - id INT
   - name TEXT
   - code TEXT
3. ClassAnnotation - contains class method annotations.
   columns:
   - id INT
   - class_id TEXT
   - code TEXT
4. Method - contains class method definitions.
   columns:
   - id INT
   - class_id INT
   - name TEXT
   - code TEXT
5. MethodAnnotation - contains class method annotations.
   columns:
   - id INT
   - method_id TEXT
   - code TEXT
6. MethodParameter - contains class method parameters.
   columns:
   - id INT
   - method_id TEXT
   - name TEXT
   - type TEXT
   
An example query to fetch the definition (code) for class named "Shape":
```sql
SELECT code FROM Method WHERE name = 'Shape';
```

Consider that imported types may be referenced in:
- method parameter types. 

## Issues
### Issue 1
Replace the `javax.*` import statements with `jakarta.*`

## Output
Return a list of steps in markdown grouped by issue number. Steps to fetch code MUST be expressed using SQL.
"""

plan4 = """
You are an expert java programming assistant.

I will provided a set of issues to be addressed in java code.
For each issue, you will provide a SQL query used to fetch the code snip needed
to fix the issue. Build your SQL in a way that returns only the data necessary and with the
most specific WHERE clause as possible. It's fine to fetch code snips to determine if the
snip is relevant. When sufficient, fetch minimal information such as method signatures and
instead of code snips.
Give the reason to fetch the code snip and how the code needs to be changed.

The code has been parsed and stored in a relation database. See `Tables` for the schema.

## Tables
1. Import - contains import statements.
   columns:
   - code TEXT # import statement.
2. Class - contains class definitions.
   columns:
   - id INT     # primary key.
   - name TEXT  # class name.
   - code TEXT  # class definition. Does not contain methods and attributes.
3. ClassAnnotation - contains class method annotations.
   columns:
   - id INT         # primary key.
   - class_id TEXT  # foreign key to class table.
   - code TEXT      # annotations code snip.
4. Method - contains class method definitions.
   columns:
   - id INT         # primary key.
   - class_id INT   # foreign key to class table.
   - name TEXT      # method name.
   - signature TEXT # method signature code snip.
   - code TEXT      # method body code snip.
5. MethodAnnotation - contains class method annotations.
   columns:
   - id INT         # primary key.
   - method_id TEXT # foreign key to method table.
   - code TEXT      # method annotations code snip.
6. MethodParameter - contains class method parameters.
   columns:
   - id INT           # primary key.
   - method_id TEXT   # foreign key to method table.
   - name TEXT        # parameter name.
   - type TEXT        # parameter type.

An example query to fetch the definition (code) for class named "Shape":
```sql
SELECT code FROM Class WHERE name = 'Shape';
```
An example query to fetch the definition (code) for a method named "onMessage":
```sql
SELECT code FROM Method WHERE name = 'onMessage';
```

## Issues
{issues}

## Output
Return a list of steps in markdown grouped by issue number. Steps to fetch code MUST be expressed using SQL.
Each step should include your rational for fetching the code and how the code should be changed but do NOT
make the change. Do not include any INSERT, UPDATE or DELETE SQL statements.
"""

plan5 = """
You are an expert java programming assistant.

I will provided a set of issues to be addressed in java code.
For each issue, you will provide a tree-sitter query used to fetch the nodes with
text needed to fix the issue.
```

## Issues
{issues}

## Output
Return a list of steps in markdown grouped by issue number. 
Steps to fetch code MUST be expressed using tree-sitter queries.
Each step should include your rationale for fetching the code and how the code should be changed.
Identify tree-sitter query markdown using `tq`. 
Example:
```tq
```
"""


def plan():
    prompt = PromptTemplate(template=plan5)
    chain = LLMChain(llm=llm, prompt=prompt)
    reply = chain.invoke({"issues": issues})
    output = reply["text"]
    print("OUTPUT:\n%s" % output)


class Step(object):
    def __init__(self):
        self.issues = []
        self.queries = []


class Architect(object):
    fetch_prompt = """
    You are an expert java programming assistant.

    I will provided a set of issues to be addressed in java code.
    For each issue, you will provide a tree-sitter query used to fetch the nodes with
    text needed to fix the issue.
    ```

    ## Issues
    {issues}

    ## Output
    Return a list of steps in YAML grouped by issue number. 
    Steps to fetch code MUST be expressed using tree-sitter queries.
    The YAML schema for each step is:
    - issues (array of int): List of issue numbers.
    - queries (object): List of queries.
      - query (multiline string): tree-sitter query.
      - reason (string): Rationale for the query.
    """

    def __init__(self, path):
        java = tree_sitter_java.language()
        self.language = tree_sitter.Language(java)
        self.parser = tree_sitter.Parser(self.language)
        with open(path, "r") as file:
            content = file.read()
        tree = self.parser.parse(bytes(content, "utf8"))
        self.root = tree.root_node

    def query(self, q):
        tq = tree_sitter.Query(self.language, q)
        captured = tq.captures(self.root)
        for capture in captured:
            node, name = capture
            print(
                f"Matched ({name}) code:{node.text.decode('utf8')} @ {node.start_byte}/{node.end_byte}"
            )

    def fetch(self):
        prompt = PromptTemplate(template=self.fetch_prompt)
        chain = LLMChain(llm=llm, prompt=prompt)
        reply = chain.invoke({"issues": issues})
        output = reply["text"]
        print("OUTPUT:\n%s" % output)

        pattern = r"(```yaml)(.+)(```)"
        matched = re.findall(pattern, output, re.DOTALL)
        for m in matched:
            content = m[1]
            steps = yaml.safe_load(content)

    def patch(self):
        pass


if __name__ == "__main__":
    architect = Architect(path="./planner/mdb.java")
    architect.fetch()
