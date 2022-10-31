#!/usr/bin/env -S python3 -u

import argparse, socket, time, json, select, struct, sys, math

class Receiver:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 0))
        self.port = self.socket.getsockname()[1]
        self.log("Bound to port %d" % self.port)

        self.remote_host = None
        self.remote_port = None
        self.recv_msg_buff = dict()
        self.recv_msg_hist = []
        self.last_packet_time = None

    def send(self, message):
        self.socket.sendto(json.dumps(message).encode('utf-8'),
                         (self.remote_host, self.remote_port))

    def log(self, message):
        sys.stderr.write(message + "\n")
        sys.stderr.flush()

    def run(self):
        self.last_packet_time = time.time()
        while True:
            socks = select.select([self.socket], [], [])[0]
            for conn in socks:
                data, addr = conn.recvfrom(65535)

                # Grab the remote host/port if we don't alreadt have it
                if self.remote_host is None:
                    self.remote_host = addr[0]
                    self.remote_port = addr[1]

                msg = json.loads(data.decode('utf-8'))
                if (msg["type"] == "msg" and msg["seq_num"] not in self.recv_msg_buff and
                     msg["seq_num"] not in self.recv_msg_hist):
                    self.log("Received data message %s" % msg)
                    self.recv_msg_buff[msg["seq_num"]] = msg
                    self.last_packet_time = time.time()
            if (len(self.recv_msg_buff) == 4 
                or self.last_packet_time + 0.5 < time.time() 
                or msg["type"] == "fin"):
                for _ in range(len(self.recv_msg_buff)):
                    # pick up the packet with the smallest seq
                    min_seq_num, msg = min(self.recv_msg_buff.items(), key=lambda d:d[0])
                    data = msg["data"]
                    # Print out the data to stdout
                    print(data, end='', flush=True)
                    # Always send back an ack
                    self.send({ "type": "ack" , "ack_num": min_seq_num})
                    self.recv_msg_buff.pop(min_seq_num)
                    self.recv_msg_hist.append(min_seq_num)


        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='receive data')
    args = parser.parse_args()
    sender = Receiver()
    sender.run()
