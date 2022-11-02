#!/usr/bin/env -S python3 -u

import argparse, socket, time, json, select, struct, sys, math, hashlib

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
        self.in_flight_packets = dict() # seqNum -> {data, time}
        self.acked_packets = []
        self.last_sending_time = time.time()

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def send(self, message):
        self.socket.sendto(json.dumps(message).encode('utf-8'), (self.host, self.remote_port))

    def run(self):
        def recv_msg(conn):
            k, addr = conn.recvfrom(65535)
            packet = k.decode('utf-8')
            try:
                msg = json.loads(packet)
                self.log("Received message '%s'" % packet)
                return msg
            except ValueError:
                self.log("Received corrupted message '%s'" % packet)
                return None


        while True:
            sockets = [self.socket, sys.stdin] if not self.waiting else [self.socket]

            socks = select.select(sockets, [], [], 0.1)[0]

            for conn in socks:
                if conn == self.socket:
                    msg = recv_msg(conn)
                    if msg and msg["ack_num"] in self.in_flight_packets:
                        self.in_flight_packets.pop(msg["ack_num"])
                        self.waiting = False
                elif conn == sys.stdin:
                    data = sys.stdin.read(DATA_SIZE)
                    if len(data) == 0:
                        self.send({"type":"fin"})
                        while True:
                            for (seq_num, sent_packet) in self.in_flight_packets.copy().items():
                                self.log("Resending message '%s'" % msg)
                                self.send(sent_packet['msg'])
                                if (seq_num in self.in_flight_packets):
                                    self.in_flight_packets[seq_num]["time"] = time.time()
                                msg = recv_msg(self.socket)
                                if msg and msg["ack_num"] in self.in_flight_packets:
                                        self.in_flight_packets.pop(msg["ack_num"])
                            if len(self.in_flight_packets) == 0:
                                break
                        self.log("All done!")
                        sys.exit(0)
                    if (self.sender_seq_num not in self.in_flight_packets):
                        msg = { "type": "msg", "data": data, "seq_num": self.sender_seq_num, "hash": hashlib.sha256(data.encode('utf-8')).hexdigest()}
                        self.in_flight_packets[self.sender_seq_num] = {
                            "msg":msg,
                            "time": time.time()
                        }
                        self.log("Sending message '%s'" % msg)
                        self.send(msg)
                        self.sender_seq_num += len(msg["data"])
                    if len(self.in_flight_packets) == self.adv_window:
                        self.waiting = True
            for seq_num, sent_packet in [item for item in self.in_flight_packets.items()]:
                if(sent_packet["time"] + 0.4 < time.time()):
                    self.log("Resending message '%s'" % msg)
                    self.send(sent_packet['msg'])
                    self.in_flight_packets[seq_num]["time"] = time.time()
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='send data')
    parser.add_argument('host', type=str, help="Remote host to connect to")
    parser.add_argument('port', type=int, help="UDP port number to connect to")
    args = parser.parse_args()
    sender = Sender(args.host, args.port)
    sender.run()
