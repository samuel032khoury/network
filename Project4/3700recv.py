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


        self.ack_num = 0
        self.msg_hist = {}

    def send(self, message):
        self.socket.sendto(json.dumps(message).encode(), (self.remote_host, self.remote_port))

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def run(self):
        while True:
            socks = select.select([self.socket], [], [])[0]
            for conn in socks:
                packet, addr = conn.recvfrom(65535)

                if self.remote_host is None:
                    self.remote_host = addr[0]
                    self.remote_port = addr[1]

                packet = packet.decode()

                try:
                    msg = json.loads(packet)
                    if sha256(msg["data"].encode()).hexdigest() != msg["hash"]:
                        raise ValueError
                except (ValueError, KeyError) as err:
                    self.log("Dropped corrupted packet '%s'" % packet)
                    continue
                if msg["seq_num"] in self.msg_hist:
                    self.send({ "type": "ack", "ack_num": msg["seq_num"]})
                    continue

                self.log("Received packet '%s'" % msg)
                self.msg_hist[msg["seq_num"]] = msg

                for seq_num in sorted(self.msg_hist):
                    if seq_num == self.ack_num:
                        print(self.msg_hist[seq_num]["data"], end='', flush=True)
                        self.ack_num += len(self.msg_hist[seq_num]["data"])
                        self.msg_hist.pop(seq_num)
                    elif (seq_num > self.ack_num):
                        break

                # Always send back an ack
                self.send({ "type": "ack", "ack_num": msg["seq_num"]})

        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='receive data')
    args = parser.parse_args()
    reciver = Receiver()
    reciver.run()