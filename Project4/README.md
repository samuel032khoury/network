# README
# Project 4 - Reliable Transport Protocol

## Running the Program

The program is written in python and runs on the command line. We assume the receiver is run first and will wait indefinitely, and the sender can just send the data to the receiver.

### Launch the Reciver

The syntax for launching the receiver is

```shell
$ ./3700recv
```

After the reciever is launched, it will bind to a UDP port and prints it out to `STDERR`

### Launch the Sender

The command line syntax for the sender is

```shell
$ ./3700send <recv_host> <recv_port>
```

- `recv_host` (Required) The domain name (e.g., “foo.com”) or IP address (e.g., “1.2.3.4”) of the remote host
- `recv_port` (Required) The UDP port of the remote host.

The sender will get all the data supplied by `STDIN`, until `EOF` is reached

### Receive on Reciver

- The receiver prints out the log message to `STDERR` and the data that it receives to `STDOUT`.

## Testing the Program

The tests runs in a simulator that emulates an unreliable network.


```shell
# run one test
$ ./run [config-file]
# or run all the tests at once
$ ./test
```

## Design
The program receives a  configuration file from the command line, and the program transfers the file reliably between two nodes -the sender and the receiver. The program transfers data between the nodes in the form of JSON objects. The sender sends a message which contain properties such as the message data, the sequence number of the message, and the hash of the data in the message to ensure that non-corrupted data is received.

The receiver, on ensuring that a packet is received correctly and in order, then sends an acknowledgement message to the sender signifying that the packet with the given sequence number was received correctly.

Packet corruption is detected both at the sender and receiver by trying to load the packet as a JSON object. If this results in an error, we assume that the packet was corrupted in transmit. On the sender side, we add an extra layer to ensure that the packet data isn't corrupted when received by adding the hash of the data as a property in the packet. On the receiver's end, this hash is compared to the actual data in the packet, and if the data does not match the hash, we assume the packet is corrupted and drop it.

If the sender does not receive an ACK for a packet within a given amount of time (signified by the dynamic RTT), it assumes that the packet was either dropped or corrupted and attempts to retransmit it until it is received successfully.

The sender also dynamically adjusts the RTT and the window size to send packets which avoids congestion and makes the program more efficient.

When the sender has no more packets left to send, it signifies this to the receiver by sending a "fin" message and the program terminates gracefully.

The program was designed modularly, with various functions performing sub-tasks for each message received. This made debugging the program simpler and ensured readability. Some challenges were faced in understanding how to ensure reliable data is transferred and knowing when packets are dropped, but these were solved by running through simpler examples and debugging manually. We also faced some challenges in implementing the dynamic RTT and window scaling.

## Testing
Testing for this program was done manually by running through the given configuration files and performing logical tasks (e.g., checking message data is what we expected it to be) on smaller examples and then translating them to the entire project. 

