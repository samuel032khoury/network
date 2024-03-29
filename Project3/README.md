# Project 3 - BGP Router

## High-Level Approach

The program is written in python and runs on the command line with one argument, which is the name of the configuration file. The program runs in a simulator that takes care of creating neighboring routers and domain sockets to connect to them, runs the router program with the appropriate command line arguments, sends various messages, asks the router to “dump” its forwarding table, and finally closing the router.

```
$ ./run [config-file]
```

## Design
The program receives a configuration file from the command line, opens sockets to receive packet data from the network, and sends a “handshake” message to each neighboring router to let the neighbor know it is up. It then checks the type of message (packet) received and chooses a course of action according to the type:

- update </br>

    These messages tell the router how to forward data packets to destinations in the network. Whenever the router receives a route announcement, it saves a copy of the announcement in the update log, adds an entry to the forwarding table, and sends copies of the announcement to neighboring routers.

- data </br>
    These messages tell the router to determine a route to send a packet from one user to another. The router determines which route (if any) in the forwarding table is the best route to use to forward the data to the destination IP (by following the five rules to break a tie in case of overlapping entries in the forwarding table) and whether the data packet is being forwarded legally.

- dump </br>

    These messages tell the router to respond with a “table” message that contains a copy of the current routing announcement cache in the router. The entries in this table are aggregated, i.e., if there are two or more entries in the forwarding table that are adjacent numerically, forward to the same next-hop router, and have the same attributes, then the two entries are aggregated into a single entry.

- withdraw </br>

    These messages tell the router that a neighboring router may need to withdraw an announcement. The neighbor will send a withdraw message to the router in this case. The router saves a copy of the withdrawal in the withdrawLog, removes the dead entry from the forwarding table, and sends copies of the withdrawal to neighboring routers. If entries in the forwarding table are aggregated, they are disaggregated if a withdrawal message is received.

The program was designed modularly, with various functions performing sub-tasks for each message received. This made debugging the program simpler and ensured readability. Some challenges were faced in understanding the aggregation and disaggregation of table entries, but these were solved by running through simpler examples and debugging manually.

## Testing
Testing for this program was done manually by running through the given configuration files and performing logical tasks (e.g., converting IPs to binary and vice-versa) on smaller examples and then translating them to the entire project. 

