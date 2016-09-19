# Model Your Data with Aerospike

This project contains code examples for typical modeling patterns with [Aerospike](http://http://www.aerospike.com). It is recommended that you read the accompanying posts at [Link](http://www.aerospike.com) before running the examples. The are a total of seven parts in Model Data with Aerospike series, each covering one of the topics below within a subdirectory: 

* **Part One: Embedding and Linking** - Encapsulation and Embedding, Linking, Denormalization
* **Part Two: the Faceting Pattern** - Important metrics and trends, aggregations of key quantitative and qualitative information sources
* **Applying Part Three: State Machines & Queues** - Ensuring that transitions between states happen in a consistent way
* **Part Four: Inventory Control**
* **Part Five: Bucketing**
* **Part Six:  Debit and Credit Transactions**
* **Part Seven: Re-Parenting & Bi-Directional Associations** - Re-Parenting, Bi-Directional and Many-To-Many Associations


## Getting Started

Running the examples requires a local or remote Aerospike installation. In addition, the code is written in Python and requires a suitable Python environment. Please see [Introduction - Python Client](http://www.aerospike.com/docs/client/python) and [Getting Started](http://www.aerospike.com/docs/client/python/start) for details on installing the Aerospike server and Python Client. 

## Running the Examples
Clone the [Data Modeling](https://github.com/aerospike/data-modeling) project

```git clone https://github.com/aerospike/data-modeling```

cd to one of the example directories: activity\_stream, credit\_debit, docker, faceting, inventory, reparenting, or state_machines

```
cd inventory
```

Run **'python all.py'** to execute the example

```java
python all.py
```

(Optional) From the root dir, run **'python util.py'** to remove the data

```
python util.py
```
