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

        self.ack_num = 0 # corresponds to the sequence number of the received packet
        self.msg_buff = {} # messages that need to be ACKed
        self.msg_hist = [] # messages that have already been ACKed


    # sends packets (ACKs) to the sender
    def send(self, message):
        self.socket.sendto(json.dumps(message).encode(), (self.remote_host, self.remote_port))

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    # receives packets from the sender and sends ACKs
    def run(self):
        while True:
            socks = select.select([self.socket], [], [])[0]
            for conn in socks:
                msg = self.recv_packet(conn)
                if not msg:
                    continue

                # if the packet is received intact, send an ACK to the sender
                if msg["seq_num"] in self.msg_buff:
                    self.send({ "type": "ack", "ack_num": msg["seq_num"]})

                # add the message to the buffer to send an ACK
                elif msg["seq_num"] not in self.msg_hist:
                    self.log("Received packet '%s'" % msg)
                    self.msg_buff[msg["seq_num"]] = msg

                # find the packet with the minimum sequence number to send ACKs in order
                for seq_num in sorted(self.msg_buff):
                    if seq_num == self.ack_num:
                        print(self.msg_buff[seq_num]["data"], end='', flush=True)
                        self.ack_num += len(self.msg_buff[seq_num]["data"]) # incrementing the ack number for the next packet
                        self.msg_buff.pop(seq_num) 
                        self.msg_hist.append(seq_num) # since the ACK has been sent, remove the message from the buffer and add it to the message history
                    else:
                        break

                # Always send back an ack
                self.send({ "type": "ack", "ack_num": msg["seq_num"]})

        return
        
    # receive packets from the sender
    def recv_packet(self, conn):
        packet, addr = conn.recvfrom(65535)
        packet = packet.decode()

        if self.remote_host is None:
            self.remote_host = addr[0]
            self.remote_port = addr[1]

        try:
            msg = json.loads(packet)

            # if the hash of the packet data does not match the data, the packet is corrupted
            if sha256(msg["data"].encode()).hexdigest() != msg["hash"]:
                raise ValueError

        except (ValueError, KeyError) as err:
            # corrupted packets are dropped so that the sender can retransmit them
            self.log("Dropped corrupted packet '%s'" % packet)
            return None
        return msg

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='receive data')
    args = parser.parse_args()
    reciver = Receiver()
    reciver.run()