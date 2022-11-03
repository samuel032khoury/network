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
        self.socket.sendto(json.dumps(message).encode('utf-8'), (self.host, self.remote_port))

    # sends packets and receives acks from the receiver
    def run(self):
        while True:
            sockets = [self.socket, sys.stdin] if not self.waiting else [self.socket]
            socks = select.select(sockets, [], [], 0.1)[0]

            for conn in socks:
                if conn == self.socket:
                    # receive a packet from the receiver
                    self.receive_packet(conn)
                elif conn == sys.stdin:
                    data = sys.stdin.read(DATA_SIZE)
                    # create a packet and send it
                    if data:
                        ## REFACTOR
                        self.log("Sending message '%s'" % data)
                        message = { 
                            "type": "msg",
                            "seq_num": self.seq_num,
                            "data": data,
                            "hash": sha256(data.encode('utf-8')).hexdigest() # to check whether the packet is corrupted on the receiver's end
                        }

                        self.send(message)
                        self.pkt_buff[self.seq_num] = {
                            "msg":message,
                            "time": time.time() # the time at which the packet is sent
                        }

                        self.seq_num += DATA_SIZE # incrementing the sequence number for the next packet

                    # if there are no more packets to send, exit the program gracefully
                    elif not self.pkt_buff:
                        self.log("All done!")
                        sys.exit(0) 

            ## REFACTOR
            # stores packets that have not been acked and are timed-out to retransmit them
            timeout_pkts = []
            # stores packets that have not been acked and are not timed-out 
            pending_pkts = []
            for packet in self.pkt_buff.values():
                (timeout_pkts if time.time() - packet["time"] > (2 * self.rtt) else pending_pkts).append(packet)


            # if there are timed-out packets, find the one with the lowest sequence number to retransmit in order
            timeout_pkt = None if not timeout_pkts else min(timeout_pkts, key=lambda x: x["msg"]["seq_num"])["msg"]
            # flip self.waiting if there are timed-out packets or the packets currently in 
            # transmission exceed the size of the congestion window
            self.waiting =  timeout_pkts or len(pending_pkts) >= self.cwnd

            # checks if a packet can be retransmitted provided that the window has not reached its
            # threshold with the packets currently in transmission (not timed-out)
            if timeout_pkt and len(pending_pkts) < self.cwnd:
                self.log("Resending packet '%s'" % timeout_pkt)
                self.send(timeout_pkt)
                self.pkt_buff[timeout_pkt["seq_num"]]["time"] = time.time()
                self.cwnd/=2 # shrinking the window since the network is congested

    # receives packets (ACKS) from the receiver
    def receive_packet(self, conn):
        packet, addr = conn.recvfrom(65535)
        packet = packet.decode('utf-8')

        try:
            message = json.loads(packet)
            if message["type"] == "ack":
                self.log("Received ACK packet '%s'" % packet)

                # calculate the new RTT based on the time of the most recent ACK
                if message["ack_num"] in self.pkt_buff:
                    new_rtt = time.time() - self.pkt_buff[message["ack_num"]]["time"]
                    self.rtt = 0.8 * self.rtt + 0.2 * new_rtt
                    self.cwnd += 1 # increase the window size since the network is not congested
                    self.pkt_buff.pop(message["ack_num"])
                else:
                    self.log("Received duplicate ACK packet '%s'" % packet)
            else:
                raise Exception("Unknown packet type")
        except (ValueError, KeyError) as err: # exception occurs only when the packet is corrupted and cannot be converted to JSON
            self.log("Dropped corrupted packet '%s'" % packet)


  
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='send data')
    parser.add_argument('host', type=str, help="Remote host to connect to")
    parser.add_argument('port', type=int, help="UDP port number to connect to")
    args = parser.parse_args()
    sender = Sender(args.host, args.port)
    sender.run()