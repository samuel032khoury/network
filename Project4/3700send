#!/usr/bin/env -S python3 -u
from hashlib import sha256
import argparse, socket, time, json, select, struct, sys, math
from typing import Any, Dict

DATA_SIZE = 1375

class Sender:
    def __init__(self, host, port):
        self.host = host
        self.remote_port = int(port)
        self.log("Sender starting up using port %s" % self.remote_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 0))
        self.waiting = False

        self.rtt = 0.5 # initial RTT
        self.cwnd = 2 # initial size of congestion window
        self.seq_num = 0
        self.pkt_buff = dict()

    # logs messages to the console
    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    # sends packets to the receiver
    def send(self, message):
        self.socket.sendto(json.dumps(message).encode(),
                          (self.host, self.remote_port))

    # launch the send side - sends packets and receives acks from the receiver
    def run(self):
        while True:
            sockets = [self.socket] if self.waiting else [self.socket,sys.stdin]
            socks = select.select(sockets, [], [], 0.1)[0]

            for conn in socks:
                if conn == self.socket:
                    # receive a packet from the receiver
                    self.recv_packet(conn)
                elif conn == sys.stdin:
                    data = sys.stdin.read(DATA_SIZE)
                    # if data is not empty, create a packet and send it
                    if data:
                        self.send_packet(data)
                    # if no more data to send and the buffer has been cleared 
                    # (all teh sent packets has been acked), exit the program
                    elif not self.pkt_buff:
                        self.log("All done!")
                        sys.exit(0) 

            # tracks packets that have not been acked but are timed-out
            timeout_pkts = dict()
            # tracks packets that have not been acked and are not timed-out 
            pending_pkts = dict()

            # for every packet in the buffer add it to timeout_pkts if it's 
            # timed-out, otherwise add it to pending_pkts if it's not timed-out
            for packet in self.pkt_buff.values():
                pkt_seq = packet["msg"]["seq_num"]
                if time.time() - packet["time"] > (2 * self.rtt):
                    timeout_pkts[pkt_seq] = packet
                else:
                    pending_pkts[pkt_seq] = packet


            # if there are timed-out packets, find the one with the lowest 
            # sequence number and retransmit it
            retransmission = (None if not timeout_pkts 
                        else timeout_pkts[min(timeout_pkts)]["msg"])
            # flip the waiting flag to true if there are timed-out packets or
            # the packets currently in transmission is of the size of the 
            # congestion window
            self.waiting =  timeout_pkts or len(pending_pkts) >= self.cwnd

            # checks if a packet can be retransmitted provided that the window 
            # has not reached its threshold with the packets currently in 
            # transmission (not timed-out)
            if retransmission and len(pending_pkts) < self.cwnd:
                self.log("Resending packet '%s'" % retransmission)
                self.send(retransmission)
                self.pkt_buff[retransmission["seq_num"]]["time"] = time.time()
                # shrinking the window to half of the size if the network is
                # congested
                self.cwnd /= 2

    # send a msg packet to the reciever, and increment the sequence number
    def send_packet(self, data):
        self.log("Sending message '%s'" % data)
        message = { 
            "type": "msg",
            "seq_num": self.seq_num,
            "data": data,
            "hash": sha256(data.encode()).hexdigest() # for integrity check
        }

        self.send(message)
        self.pkt_buff[self.seq_num] = {
            "msg":message,
            "time": time.time() # the time at which the packet is sent
        }
        # incrementing the sequence number for the next packet
        self.seq_num += DATA_SIZE 

    # receives packets (ACKS) from the receiver
    def recv_packet(self, conn):
        packet, addr = conn.recvfrom(65535)
        packet = packet.decode()

        try:
            message = json.loads(packet)
            if message["type"] == "ack":
                self.log("Received ACK packet '%s'" % packet)
                ack_num = message["ack_num"]
                # calculate the new RTT based on the time of the most recent ACK
                if ack_num in self.pkt_buff:
                    new_rtt = time.time() - self.pkt_buff[ack_num]["time"]
                    # dynamically adjust the rtt (ALPHA = 0.875) and 
                    # the cwnd (linearly)
                    self.rtt = 0.875 * self.rtt + 0.125 * new_rtt
                    self.cwnd += 1
                    self.pkt_buff.pop(ack_num)
                else:
                    self.log("Received duplicate ACK packet '%s'" % packet)
            else:
                raise Exception("Unknown packet type")
        except (ValueError, KeyError) as err: 
            # drop a packet if the data cannot be converted to JSON or
            # doesn't have the expected JSON schema
            self.log("Dropped corrupted packet '%s'" % packet)


  
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="send data")
    parser.add_argument("host", type=str, help="Remote host to connect to")
    parser.add_argument("port", type=int, help="UDP port number to connect to")
    args = parser.parse_args()
    sender = Sender(args.host, args.port)
    sender.run()