#!/usr/bin/env -S python3 -u

import argparse, socket, time, json, select, struct, sys, math

DATA_SIZE = 1375

class Sender:
    def __init__(self, host, port):
        self.host = host
        self.remote_port = int(port)
        self.log("Sender starting up using port %s" % self.remote_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 0))
        self.waiting = False
        self.sender_seq_num = 0
        self.sent_packets = dict()

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def send(self, message):
        self.socket.sendto(json.dumps(message).encode('utf-8'), (self.host, self.remote_port))

    def run(self):
        while True:
            sockets = [self.socket, sys.stdin] if not self.waiting else [self.socket]

            socks = select.select(sockets, [], [], 0.1)[0]

            for conn in socks:
                # response from the recv
                if conn == self.socket:
                    k, addr = conn.recvfrom(65535)
                    msg = k.decode('utf-8')

                    self.log("Received message '%s'" % msg)
                    msg = json.loads(msg)
                    if msg["ack_num"] in self.sent_packets:
                        self.sent_packets.pop(msg["ack_num"])
                        self.waiting = False
                elif conn == sys.stdin:
                    data = sys.stdin.read(DATA_SIZE)
                    if len(data) == 0:
                        self.send({"type":"fin"})
                        while(len(self.sent_packets) > 0):
                            k, addr = self.socket.recvfrom(65535)
                            msg = k.decode('utf-8')
                            self.log("Received message At'%s'" % msg)
                            msg = json.loads(msg)
                            if msg["ack_num"] in self.sent_packets:
                                self.sent_packets.pop(msg["ack_num"])
                        self.log("All done!")
                        sys.exit(0)
                    
                    if (self.sender_seq_num not in self.sent_packets):
                        msg = { "type": "msg", "data": data , "seq_num": self.sender_seq_num}
                        self.send(msg)
                        self.log("Sending message '%s'" % msg)
                        self.sent_packets[self.sender_seq_num] = {
                            "msg":msg,
                            "time":time.time()
                        }
                        self.sender_seq_num += len(msg["data"])

                    if len(self.sent_packets) == 4:
                        self.waiting = True
            for sent_packet in self.sent_packets.values():
                if(sent_packet["time"] + 1 < time.time()):
                    self.send(sent_packet['msg'])

        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='send data')
    parser.add_argument('host', type=str, help="Remote host to connect to")
    parser.add_argument('port', type=int, help="UDP port number to connect to")
    args = parser.parse_args()
    sender = Sender(args.host, args.port)
    sender.run()
