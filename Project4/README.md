# README
# Project 4 - Reliable Transport Protocol

## High-Level Approach

The program is written in python and runs on the command line with one argument, which is the name of the configuration file. The program runs in a simulator that emulates an unreliable network.

```
$ ./run [config-file]
```

## Design
The program receives a  configuration file from the command line, and the program transfers the file reliably between two nodes -the sender and the receiver. The program transfers data between the nodes in the form of JSON objects. The sender sends a message which contain properties such as the message data, the sequence number of the message, and the hash of the data in the message to ensure that non-corrupted data is received.

The receiver, on ensuring that a packet is received correctly and in order, then sends an acknowledgement message to the sender signifying that the packet with the given sequence number was received correctly.

If the sender does not receive an ACK for a packet within a given amount of time (signified by the dynamic RTT), it assumes that the packet was either dropped or corrupted and attempts to retransmit it until it is received successfully.

The sender also dynamically adjusts the RTT and the window size to send packets which avoids congestion and makes the program more efficient.

When the sender has no more packets left to send, it signifies this to the receiver by sending a "fin" message and the program terminates gracefully.

The program was designed modularly, with various functions performing sub-tasks for each message received. This made debugging the program simpler and ensured readability. Some challenges were faced in understanding how to ensure reliable data is transferred and knowing when packets are dropped, but these were solved by running through simpler examples and debugging manually. We also faced some challenges in implementing the dynamic RTT and window scaling.

## Testing
Testing for this program was done manually by running through the given configuration files and performing logical tasks (e.g., checking message data is what we expected it to be) on smaller examples and then translating them to the entire project. 
