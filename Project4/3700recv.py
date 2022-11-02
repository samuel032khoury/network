#!/usr/bin/env -S python3 -u

import argparse, socket, time, json, select, sys
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
        self.ack_log = dict()
        self.msg_buf = dict()

    def send(self, message):
        self.socket.sendto(json.dumps(message).encode(),
                          (self.remote_host, self.remote_port))

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def ack_msg(self, msg):
        data = msg["data"]
        print(data, end='', flush=True)
        ack_packet = {"type": "ack" , "ack_num": msg["seq_num"]}
        self.send(ack_packet)
        self.ack_num += len(msg['data'])
        self.ack_log[msg["seq_num"]] = ack_packet

    def ack_all(self):
        for _ in range(len(self.msg_buf)):
            min_seq_num, msg = min(self.msg_buf.items(), key=lambda d:d[0])
            if min_seq_num != self.ack_num:
                return
            self.ack_msg(msg)
            self.msg_buf.pop(min_seq_num)

    def run(self):
        while True:
            socks = select.select([self.socket], [], [])[0]
            for conn in socks:
                packet, addr = conn.recvfrom(65535)

                # Grab the remote host/port if we don't alreadt have it
                if self.remote_host is None:
                    self.remote_host = addr[0]
                    self.remote_port = addr[1]

                try:
                    msg = json.loads(packet.decode())
                    
                    if (msg["type"] == "msg"):
                        msg_seq_num = msg["seq_num"]
                        data_hash = sha256(msg["data"].encode()).hexdigest()
                        if data_hash != msg["hash"]:
                            raise ValueError
                        if(msg_seq_num == self.ack_num):
                            self.log("Received data message %s" % msg)
                            self.ack_msg(msg)
                        elif (msg_seq_num not in self.msg_buf):
                            if (msg_seq_num not in self.ack_log):
                                self.log("Buffered data message %s" % msg)
                                self.msg_buf[msg_seq_num] = msg
                            else:
                                self.log("Reack data message %s" % msg)
                                self.send(self.ack_log[msg_seq_num])
                    elif msg["type"] == "fin":
                        while (self.msg_buf):
                            self.ack_all()
                    else:
                        self.log("[Error] Invalid Message Type!")
                        sys.exit(1)
                except (ValueError, KeyError) as err:
                    self.log("Dropped corrupted message %s" % msg)
            self.ack_all()

        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='receive data')
    args = parser.parse_args()
    sender = Receiver()
    sender.run()
