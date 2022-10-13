#!/usr/bin/env -S python3 -u

import argparse, socket, time, copy, json, select, struct, sys, math
from collections import defaultdict

class Router:

    relations = {}
    sockets = {}
    ports = {}
    updateLog = []
    routingTable = defaultdict(list)

    def __init__(self, asn, connections):
        print("Router at AS %s starting up" % asn)
        self.asn = asn
        for relationship in connections:
            port, neighbor, relation = relationship.split("-")
            self.sockets[neighbor] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sockets[neighbor].bind(('localhost', 0))
            self.ports[neighbor] = int(port)
            self.relations[neighbor] = relation
            self.send(neighbor, json.dumps({ "type": "handshake", "src": self.routerOf(neighbor), "dst": neighbor, "msg": {}  }))

    def routerOf(self, dst):
        quads = list(int(qdn) for qdn in dst.split('.'))
        quads[3] = 1
        return "%d.%d.%d.%d" % (quads[0], quads[1], quads[2], quads[3])

    def send(self, network, message):
        self.sockets[network].sendto(message.encode('utf-8'), ('localhost', self.ports[network]))

    def update(self, src, packet):
        # log the update
        self.updateLog.append(packet)
        # put the update msg (as JSON) on the routing table
        self.routingTable[src].append(packet['msg'])

    def announce(self, src, packet):
        # compose a forwarding update message
        def composeForwardingMessage(dst):
            outUpdate = copy.deepcopy(packet['msg'])
            outUpdate['ASPath'].insert(0, self.asn)
            outUpdate.pop('localpref', None)
            outUpdate.pop('origin', None)
            outUpdate.pop('selfOrigin', None)
            outPacket = {
                'src': self.routerOf(dst),
                'dst': dst,
                'type': "update",
                'msg': outUpdate
            }
            return json.dumps(outPacket)
        
        # NOTE: Currently assume all neighbors are customers
        # announce the updates to other networks
        for host in self.sockets.keys():
            if host != src:
                msg = composeForwardingMessage(host)
                self.send(host, msg)

    def matchPrefix(self, dst):
        def ipToBin(ipAddr:str) -> str:
            return ''.join(list(map(lambda quad: format(int(quad), '08b'),ipAddr.split('.'))))
        matchedList = []
        for neighbor, nets in self.routingTable.items():
            for net in nets:
                dstBin = ipToBin(dst)
                networkBin = ipToBin(net['network'])
                netmaskBin = ipToBin(net['netmask'])
                matchingLength = 0
                for mask, expect, actual in zip(netmaskBin, networkBin, dstBin):
                    mask = int(mask)
                    expect = int(expect)
                    actual = int(actual)
                    if bool(mask) and (expect == actual):
                        matchingLength += 1
                    elif bool(mask) and (expect != actual):
                        # Abort
                        break
                    else:
                        matchedList.append((neighbor, matchingLength, net))
                        # Teminate
                        break
        return matchedList
    
    def findBestRoute(self, longestmatch):
        bestLocalPref = max(longestmatch, key = lambda x: x[2]['localpref'])[2]['localpref']
        bestRoutes = list(filter(lambda x: x[2]['localpref'] == bestLocalPref, longestmatch))
        if len(bestRoutes) == 1:
            return bestRoutes[0]
        bestRoutes = list(filter(lambda x: x[2]['selfOrigin'], bestRoutes))
        if len(bestRoutes) == 1:
            return bestRoutes[0]
        if True:
            # MORE ROUTE CHOOSING HERE
            pass
        return min(bestRoutes, key = lambda x: x[0])

    def forwardData(self, src, packet):
        # NOTE: This might not work as expected
        def composeNoRouteMessage():
            noRoutepacket = {
                'src' : self.routerOf(src),
                'dst' : packet['src'],
                'type': "no route",
                "msg" : {}
            }
            return json.dumps(noRoutepacket)
            

        dst = packet['dst']
        matches = self.matchPrefix(dst)
        if not matches:
            msg = composeNoRouteMessage()
            self.send(src, msg)
        else:
            longestmatchLength = max(matches, key=lambda x: x[1])[1]
            longestmatches = list(filter(
                lambda x: x[1] == longestmatchLength,matches))
            dstSock = longestmatches[0][0] if len(longestmatches) == 1 else self.findBestRoute(longestmatches)[0]
            msg = json.dumps(packet)
            self.send(dstSock, msg)

    def dumpTable(self, src):
        def expandTable(table):
            expanded = []
            for peer, nets in table:
                for net in nets:
                    expanded.append((peer, net))
            return expanded
        data = list(map(lambda neighbor : {
            "peer":neighbor[0],
            "network":neighbor[1]["network"],
            "netmask":neighbor[1]["netmask"],
            "localpref":neighbor[1]["localpref"],
            "origin":neighbor[1]["origin"],
            "selfOrigin":neighbor[1]["selfOrigin"],
            "ASPath":neighbor[1]["ASPath"],
            },expandTable(self.routingTable.items())))
        table = {
            "src": self.routerOf(src),
            "dst": src,
            "type": "table",
            "msg": data
        }
        msg = json.dumps(table)
        self.send(src, msg)

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
                    self.forwardData(srcif, packet)
                elif msgType == 'dump':
                    self.dumpTable(srcif)
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='route packets')
    parser.add_argument('asn', type=int, help="AS number of this router")
    parser.add_argument('connections', metavar='connections', type=str, nargs='+', help="connections")
    args = parser.parse_args()
    router = Router(args.asn, args.connections)
    router.run()

