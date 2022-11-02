#!/usr/bin/env -S python3 -u

import argparse, socket, time, json, select, sys
from hashlib import sha256

DATA_SIZE = 1375

class Sender:
    def __init__(self, host, port):
        self.host = host
        self.remote_port = int(port)
        self.log("Sender starting up using port %s" % self.remote_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 0))
        self.waiting = False
        self.adv_window = 5
        self.sender_seq_num = 0
        self.pending_pkts = dict()
        self.rtt = 0.6

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def send(self, message):
        self.socket.sendto(json.dumps(message).encode(),
                          (self.host, self.remote_port))

    def recv_msg(self, conn):
        packet, addr = conn.recvfrom(65535)
        packet = packet.decode()
        try:
            msg = json.loads(packet)
            self.log("Received message '%s'" % packet)
            return msg
        except ValueError:
            self.log("Dropped corrupted message '%s'" % packet)
            return None


    def run(self):

        while True:
            sockets = ([self.socket, sys.stdin] if not self.waiting
                  else [self.socket])

            socks = select.select(sockets, [], [], 0.1)[0]

            for conn in socks:
                if conn == self.socket:
                    msg = self.recv_msg(conn)
                    if msg and msg["ack_num"] in self.pending_pkts:
                        self.pending_pkts.pop(msg["ack_num"])
                        self.waiting = False
                if conn == sys.stdin:
                    data = sys.stdin.read(DATA_SIZE)
                    if len(data) == 0:
                        self.send({"type":"fin"})
                        while True:
                            for cur_pkt in self.pending_pkts.copy().values():
                                self.log("Resending message '%s'" % msg)
                                self.send(cur_pkt['msg'])
                                msg = self.recv_msg(self.socket)
                                if msg and msg["ack_num"] in self.pending_pkts:
                                        self.pending_pkts.pop(msg["ack_num"])
                            if not self.pending_pkts:
                                break
                        self.log("All done!")
                        sys.exit(0)
                    if (self.sender_seq_num not in self.pending_pkts):
                        msg = {
                            "type": "msg",
                            "data": data,
                            "seq_num": self.sender_seq_num,
                            "hash": sha256(data.encode()).hexdigest()
                         }
                        self.pending_pkts[self.sender_seq_num] = {
                            "msg":msg,
                            "time": time.time()
                        }
                        self.log("Sending message '%s'" % msg)
                        self.send(msg)
                        self.sender_seq_num += len(msg["data"])
                    if len(self.pending_pkts) == self.adv_window:
                        self.waiting = True
            for cur_seq, cur_pkt in self.pending_pkts.copy().items():
                if(cur_pkt["time"] + self.rtt < time.time()):
                    self.log("Resending message '%s'" % msg)
                    self.send(cur_pkt['msg'])
                    self.pending_pkts[cur_seq]["time"] = time.time()
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='send data')
    parser.add_argument('host', type=str, help="Remote host to connect to")
    parser.add_argument('port', type=int, help="UDP port number to connect to")
    args = parser.parse_args()
    sender = Sender(args.host, args.port)
    sender.run()
