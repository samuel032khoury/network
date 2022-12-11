# Project 6 - Distributed Key-Value Database

## Running the Program

The program is written in python and runs on the command line. The simulator in which the program is run passes parameters to each replica representing the UDP port number the replica should connect to, the ID of the replica, and the IDs of all other replicas in the system. All replica IDs are unique four-digit hexadecimal numbers (e.g., 0AA1 or F29A).


The simulator runs the following command to launch our datastore:

```shell
$ ./3700kvstore <UDP port> <your ID> <ID of second replica> [<ID of third replica> ...]]
```

## Testing the Program

The tests run in a simulator that emulates a network and all necessary sockets, executes several copies of the datastore with the appropriate command line arguments, routes messages between the datastore replicas, and generates requests from clients.


```shell
# run one test
$ ./run <path-to-test-config-file>
# or run all the tests at once
$ ./run all
```

## High-level Approach

Our datastore follows the RAFT consensus protocol to accept put()s from clients and retrieve the corresponding data when a get() is issued. To ensure that data is not lost when a process crashes, we replicate all data from clients and ensure consistency (clients always receive correct answers to get() requests) and high availability (clients execute put() and get() requests at any time with low latency) using RAFT.

We followed the RAFT paper to create our program modularly. First, we added support for responding to client get() and put() requests and then implemented the RAFT election protocol with the different types (FOLLOWER, CANDIDATE, LEADER) of servers. We added a heartbeat to detect leader failures and begin the new election process and added the ability to send empty AppendEntries RPC to act as a keep-alive message from the leader.

Then, we created a transaction log and a dictionary containing key/value pairs from clients and ensured that a leader answers get() and put() requests as expected, and added support for AppendEntries RPC calls to send data to replicas and commit only when a quorum is in agreement. If there are failed/dropped commits or leader failures on a lossy network, these commits are retried. Supports for additional restrictions from sections 5.4.1 and 5.4.2 of the RAFT paper were also added, and the AppendEntries RPC call was modified to implement batching.

Following the RAFT paper proved to be helpful in designing our program section by section, and the paper served as a guide in implementing the RAFT protocol for our data store.


## Challenges
We faced difficulties in understanding the order of implementation, especially for the different message types such as vote requests, append requests, and so on. A lot of these different types of messages relied on each other's message format, which made figuring out the order of implementation particularly difficult, since this also posed a problem with testing modularly and resulted in having to implement handling of all message types before testing. 


## Testing
Testing for this program was done manually by running through the given configuration files and performing logical tasks (e.g., checking message and replica data is what we expected it to be) on smaller examples and then translating them to the entire project. 

