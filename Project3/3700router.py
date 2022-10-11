#!/usr/bin/env -S python3 -u

import argparse, socket, time, copy, json, select, struct, sys, math

class Router:

    relations = {}
    sockets = {}
    ports = {}
    updateLog = []
    routingTable = {}

    def __init__(self, asn, connections):
        print("Router at AS %s starting up" % asn)
        self.asn = asn
        for relationship in connections:
            port, neighbor, relation = relationship.split("-")
            self.sockets[neighbor] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sockets[neighbor].bind(('localhost', 0))
            self.ports[neighbor] = int(port)
            self.relations[neighbor] = relation
            self.send(neighbor, json.dumps({ "type": "handshake", "src": self.our_addr(neighbor), "dst": neighbor, "msg": {}  }))

    def our_addr(self, dst):
        quads = list(int(qdn) for qdn in dst.split('.'))
        quads[3] = 1
        return "%d.%d.%d.%d" % (quads[0], quads[1], quads[2], quads[3])

    def send(self, network, message):
        self.sockets[network].sendto(message.encode('utf-8'), ('localhost', self.ports[network]))

    def update(self, src, packet):
        # log the update
        self.updateLog.append(packet)
        # put update msg (JSON) on the routing table
        self.routingTable[src] = packet['msg']



    def announce(self, src, packet):
        # compose a forwarding update message
        def composeForwardingMessage(ip):
            outUpdate = copy.deepcopy(packet['msg'])
            outUpdate['ASPath'].insert(0, self.asn)
            outUpdate.pop('localpref')
            outUpdate.pop('origin')
            outUpdate.pop('selfOrigin')
            outPacket = {
                'src': self.our_addr(ip),
                'dst': ip,
                'type': "update",
                'msg': outUpdate
            }
            return json.dumps(outPacket)
        # announce the updates to other networks
        for host in self.sockets.keys():
            if host != src:
                msg = composeForwardingMessage(host)
                self.send(host, msg)

    def run(self):
        while True:
            socks = select.select(self.sockets.values(), [], [], 0.1)[0]
            for conn in socks:
                k, addr = conn.recvfrom(65535) # 
                srcif = None
                for sock in self.sockets:
                    if self.sockets[sock] == conn:
                        srcif = sock
                        break
                msg = k.decode('utf-8')

                print("Received message '%s' from %s" % (msg, srcif))

                packet = json.loads(msg)
                msgType = packet['type']   
                if msgType == 'update':
                    self.update(srcif, packet)
                    self.announce(srcif, packet)
                elif msgType == 'data':
                    # TODO
                    pass
                elif msgType == 'dump':
                    # TODO
                    pass
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='route packets')
    parser.add_argument('asn', type=int, help="AS number of this router")
    parser.add_argument('connections', metavar='connections', type=str, nargs='+', help="connections")
    args = parser.parse_args()
    router = Router(args.asn, args.connections)
    router.run()

