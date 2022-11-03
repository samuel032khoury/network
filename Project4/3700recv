#!/usr/bin/env -S python3 -u
import argparse, socket, time, json, select, struct, sys, math
from hashlib import sha256

class Receiver:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 0))
        self.port = self.socket.getsockname()[1]
        self.log("Bound to port %d" % self.port)

        self.remote_host = None
        self.remote_port = None

        self.ack_num = 0 # tracking the ack number for the ACK packet
        self.msg_buff = {} # messages that need to be ACKed
        self.msg_hist = [] # messages that have already been ACKed

    # sends packets (ACKs) to the sender
    def send(self, message):
        self.socket.sendto(json.dumps(message).encode(), 
                           (self.remote_host, self.remote_port))

    # log the message to the console
    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    # launch the recive side - receives packets from the sender and sends ACKs
    def run(self):
        while True:
            socks = select.select([self.socket], [], [])[0]
            for conn in socks:
                msg = self.recv_packet(conn)

                # if recived a corrupted msg, discard it and skip this iteration
                if not msg:
                    continue
                msg_seq_num = msg["seq_num"]
                # We only process packets that has not been acked
                if msg_seq_num not in self.msg_hist:
                    # if the packet has nevern been seen, we it to the buffer
                    if msg_seq_num not in self.msg_buff:
                        self.log("Received packet '%s'" % msg)
                        self.msg_buff[msg_seq_num] = msg
                    
                    # if the packet appears to be one that has been acked, send
                    # an ACK again
                    else: 
                        self.send({ "type": "ack", "ack_num": msg_seq_num})
                        continue

                # Always send back an ack
                self.send({ "type": "ack", "ack_num": msg_seq_num})

                # clear the buffer
                for seq_num in sorted(self.msg_buff):
                    # find the message that has the same sequence number as the 
                    # tracked ack number, print it out and send back an ACK
                    data = self.msg_buff[seq_num]["data"]
                    if seq_num == self.ack_num:
                        print(data, end='', flush=True)
                        # incrementing the ack number
                        self.ack_num += len(data) 
                        # since the ACK has been sent, remove the message from 
                        # the buffer and add it to the message history
                        self.msg_buff.pop(seq_num) 
                        self.msg_hist.append(seq_num) 
                    
                    # leave all the ahead packet the in the buffer
                    else:
                        break

                

        return

    # receive packets from the sender
    def recv_packet(self, conn):
        packet, addr = conn.recvfrom(65535)
        packet = packet.decode()

        if self.remote_host is None:
            self.remote_host = addr[0]
            self.remote_port = addr[1]

        # check the integrity of the packet
        try:
            msg = json.loads(packet)
            # if fails the hash verification, the packet is corrupted
            if sha256(msg["data"].encode()).hexdigest() != msg["hash"]:
                raise ValueError

        except (ValueError, KeyError) as err:
            # corrupted packets are dropped so the sender can retransmit them
            self.log("Dropped corrupted packet '%s'" % packet)
            return None
        return msg

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='receive data')
    args = parser.parse_args()
    reciver = Receiver()
    reciver.run()