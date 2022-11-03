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
        self.cwnd = 2
        self.seq_num = 0
        self.rtt = 0.5

        self.pending_pkts = dict()


    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def send(self, message):
        self.socket.sendto(json.dumps(message).encode('utf-8'), (self.host, self.remote_port))

    def run(self):
        while True:

            sockets = [self.socket, sys.stdin] if self.waiting else [self.socket]

            socks = select.select(sockets, [], [], 0.1)[0]
            for conn in socks:
                if conn == self.socket:
                    self.receive_packet(conn)
                elif conn == sys.stdin:
                    data = sys.stdin.read(DATA_SIZE)
        
                    if len(data) == 0 and not self.pending_pkts:
                        self.log("All done!")
                        sys.exit(0) 
                    elif len(data) == 0:
                        continue
                    else:
                        self.log("Sending message '%s'" % data)
                        message = { 
                            "type": "msg",
                            "seq_num": self.seq_num,
                            "data": data,
                            "hash": sha256(data.encode('utf-8')).hexdigest()
                        }
                        self.send(message)
                        self.pending_pkts[self.seq_num] = {
                            "msg":message,
                            "time": time.time()
                        }
                        self.seq_num += DATA_SIZE

            timeout_pkts = filter(lambda item: time.time() - item[1]["time"] > 2*self.rtt, self.pending_pkts.items())
            timeout_pkts = map(lambda item: self.pending_pkts[item[0]]['msg'], timeout_pkts)
            timeout_pkts = list(timeout_pkts)
            flying_pkts = list(filter(lambda packet: (time.time() - packet["time"]) < 2*self.rtt, self.pending_pkts.values()))
            self.waiting = (not timeout_pkts) and len(flying_pkts) < self.cwnd
            
            timeout_packet = None if not timeout_pkts else min(timeout_pkts, key=lambda x: x["seq_num"])

            if timeout_packet and len(flying_pkts) < self.cwnd:
                self.log("Resending packet '%s'" % timeout_packet)
                self.send(timeout_packet)
                self.pending_pkts[timeout_packet["seq_num"]]['msg'] = timeout_packet
                self.pending_pkts[timeout_packet["seq_num"]]["time"] = time.time()
                self.cwnd/=2

    def receive_packet(self, conn):
        packet, addr = conn.recvfrom(65535)
        packet = packet.decode('utf-8')

        try:
            message = json.loads(packet)
            if message["type"] == "ack":
                self.log("Received ACK packet '%s'" % packet)

                if message["ack_num"] in self.pending_pkts:
                    new_rtt = time.time() - self.pending_pkts[message["ack_num"]]["time"]
                    self.rtt = 0.8 * self.rtt + 0.2 * new_rtt

                    self.pending_pkts.pop(message["ack_num"])

                    self.cwnd += 1
                else:
                    self.log("Received duplicate ACK packet '%s'" % packet)
            else:
                raise Exception("Unknown packet type")
        except (ValueError, KeyError) as err:
            self.log("Dropped corrupted packet '%s'" % packet)


  
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='send data')
    parser.add_argument('host', type=str, help="Remote host to connect to")
    parser.add_argument('port', type=int, help="UDP port number to connect to")
    args = parser.parse_args()
    sender = Sender(args.host, args.port)
    sender.run()