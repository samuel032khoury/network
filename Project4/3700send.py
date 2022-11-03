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
        self.cwnd = 2
        self.seq_num = 0
        self.pending_pkts = dict()
        self.rtt = 0.5

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def send(self, message):
        self.socket.sendto(json.dumps(message).encode(),
                          (self.host, self.remote_port))

    def recv_ack(self, conn):
        packet, addr = conn.recvfrom(65535)
        packet = packet.decode()
        try:
            ack = json.loads(packet)
            if ack["ack_num"] in self.pending_pkts:
                self.log("Received ACK '%s'" % packet)
                new_rtt = time.time() - self.pending_pkts[ack["ack_num"]]["time"]
                self.log("DEBUG2 " + str(new_rtt))
                self.rtt = (1 - 0.2) * self.rtt + 0.2 * new_rtt
                self.cwnd += 1
                self.log("DEBUG " + str(self.rtt))
                return ack
            else:
                self.log("Received duplicated ACK '%s'" % packet)
                return None
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
                    for cur_seq, cur_pkt in self.pending_pkts.copy().items():
                        if(cur_pkt["time"] + 2 * self.rtt < time.time()):
                            self.log("Resending message '%s'" % cur_pkt['msg'])
                            self.send(cur_pkt['msg'])
                            self.cwnd /= 2
                            self.pending_pkts[cur_seq]["time"] = time.time()
                    ack = self.recv_ack(conn)
                    if ack and ack["ack_num"] in self.pending_pkts:
                        self.pending_pkts.pop(ack["ack_num"])
                        self.waiting = False
                if conn == sys.stdin:
                    data = sys.stdin.read(DATA_SIZE)
                    if len(data) == 0:
                        self.send({"type":"fin"})
                        while True:
                            for cur_pkt in self.pending_pkts.copy().values():
                                self.log("Resending message '%s'" % cur_pkt['msg'])
                                self.send(cur_pkt['msg'])
                                ack = self.recv_ack(self.socket)
                                if ack and ack["ack_num"] in self.pending_pkts:
                                        self.pending_pkts.pop(ack["ack_num"])
                            if not self.pending_pkts:
                                break
                        self.log("All done!")
                        sys.exit(0)
                    if (self.seq_num not in self.pending_pkts):
                        msg = {
                            "type": "msg",
                            "data": data,
                            "seq_num": self.seq_num,
                            "hash": sha256(data.encode()).hexdigest()
                         }
                        self.pending_pkts[self.seq_num] = {
                            "msg":msg,
                            "time": time.time()
                        }
                        self.log("Sending message '%s'" % msg)
                        self.send(msg)
                        self.seq_num += len(msg["data"])
                    if len(self.pending_pkts) == self.cwnd:
                        self.waiting = True
            for cur_seq, cur_pkt in self.pending_pkts.copy().items():
                if(cur_pkt["time"] + 2 * self.rtt < time.time()):
                    self.log("Resending message '%s'" % cur_pkt['msg'])
                    self.send(cur_pkt['msg'])
                    self.recv_ack()
                    self.cwnd /= 2
                    self.pending_pkts[cur_seq]["time"] = time.time()
            
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='send data')
    parser.add_argument('host', type=str, help="Remote host to connect to")
    parser.add_argument('port', type=int, help="UDP port number to connect to")
    args = parser.parse_args()
    sender = Sender(args.host, args.port)
    sender.run()
