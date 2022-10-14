#!/usr/bin/env -S python3 -u

import argparse, socket, time, copy, json, select, struct, sys, math
from itertools import combinations

# Convert a IPv4 address to its 32-bit representation in string
def ipToBin(ipAddr:str) -> str:
    return ''.join(list(map(lambda quad: format(int(quad), '08b'),ipAddr.split('.'))))

# Convert a 32-bit string to its IPv4 representation
def binToIp(binAddr:str) -> str:
    return '.'.join(map(lambda octa: str(int(octa, 2)), [binAddr[i:i+8] for i in range(0, 31, 8)]))

# Represent a BGP Router 
class Router:

    # stores the relationships between the current router and its neigboring router
    relations = {}
    # stores the socket connections between the current router and its neigboring router
    sockets = {}
    # stores the interfaces the neigboring router connecting into
    ports = {}
    # the router's routing table
    routingTable = {}
    # update logs
    updateLog = []
    # withdraw logs
    withdrawLog = []

    def __init__(self, asn, connections):
        print("Router at AS %s starting up" % asn)
        self.asn = asn
        for relationship in connections:
            port, neighbor, relation = relationship.split("-")
            self.sockets[neighbor] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sockets[neighbor].bind(('localhost', 0))
            self.ports[neighbor] = int(port)
            self.relations[neighbor] = relation
            self.send(neighbor, json.dumps({
                "type": "handshake", 
                "src": self.routerOf(neighbor), 
                "dst": neighbor, "msg": {}  }))

    # Get the ip address of the router of the given ip address
    def routerOf(self, addr):
        quads = list(int(qdn) for qdn in addr.split('.'))
        quads[3] = 1
        return "%d.%d.%d.%d" % (quads[0], quads[1], quads[2], quads[3])

    # Send a message from the router to the specified network
    def send(self, network, message):
        self.sockets[network].sendto(message.encode('utf-8'), ('localhost', self.ports[network]))

    # Log the update and update the routing table accordingly, then aggregate the table
    def update(self, src, packet):
        # log the update
        self.updateLog.append(packet)
        # put the update msg (as JSON) on the routing table
        if src not in self.routingTable:
            self.routingTable[src] = []
        self.routingTable[src].append(packet['msg'])
        self.aggregate()

    # Log the withdraw and revoke a entry(s) from the routing table, then disaggregate the table
    def withdraw(self, packet):

        def disaggregate(src):
            srcUpdate = list(filter(lambda update: update['src'] == src, self.updateLog))
            srcUpdateMsg = list(map(lambda update:update['msg'], srcUpdate))

            srcWithdraw = list(filter(lambda update: update['src'] == src, self.withdrawLog))
            srcWdLists = list(map(lambda withdrawn:withdrawn['msg'], srcWithdraw))
            srcWdList = ([withdrawItem for srcWdList in srcWdLists 
                            for withdrawItem in srcWdList])

            for wdNet, wdMsk in map(lambda wdItem: wdItem.values(), srcWdList):
                srcUpdateMsg = ([msg for msg in srcUpdateMsg 
                                if msg['network'] != wdNet or msg['netmask'] != wdMsk])
            self.routingTable[src] = srcUpdateMsg
            self.aggregate(target = src)


        self.withdrawLog.append(packet)
        src = packet['src']
        disaggregate(src)

    # Announce the update/revoke message to router's neighbor
    # only announce a message if its from a customer or the destination is a customer
    def announce(self, src, packet, update):
        # compose a forwarding update message
        def composeForwardingMessage(dst):
            if update:
                outUpdate = copy.deepcopy(packet['msg'])
                outUpdate['ASPath'].insert(0, self.asn)
                outUpdate.pop('localpref', None)
                outUpdate.pop('origin', None)
                outUpdate.pop('selfOrigin', None)
            outMessage = outUpdate if update else packet['msg']
            outPacket = {
                'src': self.routerOf(dst),
                'dst': dst,
                'type': "update" if update else 'withdraw',
                'msg': outMessage
            }
            return json.dumps(outPacket)
        
        # announce the updates to other networks
        for host in self.sockets.keys():
            if host != src:
                if self.relations[host] == "cust" or self.relations[src] == "cust":
                    msg = composeForwardingMessage(host)
                    self.send(host, msg)

    # Aggregate all possible entries on the routing table that are adjacent numerically, forward to
    # the same next-hop router, and  have the same attributes
    def aggregate(self, target=None):
        def sameAttr(netOne, netTwo):
            return (netOne["localpref"] == netTwo["localpref"] 
                and netOne["origin"] == netTwo["origin"] 
                and netOne["selfOrigin"] == netTwo["selfOrigin"] 
                and netOne["ASPath"] == netTwo["ASPath"])

        def adjacentNets(netOne, netTwo):
            if netOne['netmask'] != netTwo['netmask']:
                return False
            netMskBin = ipToBin(netOne['netmask'])
            netOneNwBin = ipToBin(netOne['network'])
            netTwoNwBin = ipToBin(netTwo['network'])
            diffPos = netOneNwBin.rfind('1')
            return netOneNwBin[:diffPos] == netTwoNwBin[: diffPos]

        iterTarget = [target] if target else self.routingTable.keys()
        for currNeighbor in iterTarget:
            maxMergeIter = len(self.routingTable[currNeighbor])
            for mergeIter in range(maxMergeIter - 1):
                currNetsList = self.routingTable[currNeighbor]
                traversed = True
                for (netOne, netTwo) in list(combinations(currNetsList, 2)):
                    if (sameAttr(netOne, netTwo) and adjacentNets(netOne, netTwo)):
                        aggregatedNw = (netOne['network'] if netOne['network'] < netTwo['network']
                                   else netTwo['network'])
                        currMskBin = ipToBin(netOne["netmask"])
                        lastOne = currMskBin.rfind('1')
                        aggregatedMskBin = currMskBin[:lastOne] + '0' + currMskBin[lastOne + 1:]
                        aggregatedMsk = binToIp(aggregatedMskBin)
                        aggregatedRoute = {
                            "network":aggregatedNw,
                            "netmask":aggregatedMsk,
                            "localpref":netOne["localpref"],
                            "origin":netOne["origin"],
                            "selfOrigin":netOne["selfOrigin"],
                            "ASPath":netOne["ASPath"]
                        }
                        currNetsList.append(aggregatedRoute)
                        currNetsList.remove(netOne)
                        currNetsList.remove(netTwo)
                        traversed = False
                        break
                if traversed:
                    break

    # Forward data per the routing table, only forward if the src or the dest is a customer
    # if no available route, send the src a no route message
    def forwardData(self, src, packet):
        def matchPrefix(dst):
            matches = []
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
                            # Abort the match
                            break
                        else:
                            matches.append((neighbor, matchingLength, net))
                            # Teminate the match
                            break
            return matches
        
        def findBestRoute(matches):
            # to find the logest prefix match(es)
            longestMatchLength = max(list(map(lambda x: x[1], matches)))
            bestRoutes = list(filter(lambda x: x[1] == longestMatchLength,matches))
            if len(bestRoutes) == 1:
                return bestRoutes[0]
            # to find highest local preference match(es)
            bestLocalPref = max(list(map(lambda x: x[2]['localpref'], bestRoutes)))
            bestRoutes = list(filter(lambda x: x[2]['localpref'] == bestLocalPref, bestRoutes))
            if len(bestRoutes) == 1:
                return bestRoutes[0]
            # to find self origin routes
            selfOriginRoutes = list(filter(lambda x: x[2]['selfOrigin'], bestRoutes))
            bestRoutes = selfOriginRoutes if selfOriginRoutes else bestRoutes
            if len(bestRoutes) == 1:
                return bestRoutes[0]
            # to find routes that via shortest AS path
            shortestASPath = min(list(map(lambda x: len(x[2]['ASPath']),bestRoutes)))
            bestRoutes = list(filter(lambda x: len(x[2]['ASPath']) == shortestASPath, bestRoutes))
            if len(bestRoutes) == 1:
                return bestRoutes[0]
            # to find routes that have preferred origin
            igpRoutes = list(filter(lambda x: x[2]['origin'] == "IGP", bestRoutes))
            egpRoutes = list(filter(lambda x: x[2]['origin'] == "EGP", bestRoutes))
            unkRoutes = list(filter(lambda x: x[2]['origin'] == "UNK", bestRoutes))
            ## let best routes be the first non-empty preferred list
            bestRoutes = igpRoutes if igpRoutes else (egpRoutes if egpRoutes else unkRoutes)
            if len(bestRoutes) == 1:
                return bestRoutes[0]
            # defult fall back to find the lowest nerighbor IP address
            return min(bestRoutes, key = lambda x: x[0])

        def composeNoRouteMessage():
            noRoutepacket = {
                'src' : self.routerOf(src),
                'dst' : packet['src'],
                'type': "no route",
                "msg" : {}
            }
            return json.dumps(noRoutepacket)
            

        dst = packet['dst']
        matches = matchPrefix(dst)

        if not matches:
            dst = src
            msg = composeNoRouteMessage()
        else:
            dst = findBestRoute(matches)[0]
            msg = json.dumps(packet)
        if (self.relations[dst] != 'cust' and self.relations[src] != 'cust'):
            dst = src
            msg = composeNoRouteMessage()
        self.send(dst, msg)

    # Dump all entries in the table, and send it back to the request source
    def dumpTable(self, src):
        def expandTable(table):
            expanded = []
            for peer, nets in table.items():
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
            },expandTable(self.routingTable)))
        table = {
            "src": self.routerOf(src),
            "dst": src,
            "type": "table",
            "msg": data
        }
        msg = json.dumps(table)
        self.send(src, msg)

    # Launch the router
    def run(self):
        while True:
            socks = select.select(self.sockets.values(), [], [], 0.1)[0]
            for conn in socks:
                k, addr = conn.recvfrom(65535) # 
                src = None
                for sock in self.sockets:
                    if self.sockets[sock] == conn:
                        src = sock
                        break
                msg = k.decode('utf-8')

                print("Received message '%s' from %s" % (msg, src))

                packet = json.loads(msg)
                msgType = packet['type']   
                if msgType == 'update':
                    self.update(src, packet)
                    self.announce(src, packet, True)
                elif msgType == 'withdraw':
                    self.withdraw(packet)
                    self.announce(src, packet, False)
                elif msgType == 'data':
                    self.forwardData(src, packet)
                elif msgType == 'dump':
                    self.dumpTable(src)
                else:
                    raise Exception("Invalid packet!")
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='route packets')
    parser.add_argument('asn', type=int, help="AS number of this router")
    parser.add_argument('connections', metavar='connections', type=str, nargs='+', help="connections")
    args = parser.parse_args()
    router = Router(args.asn, args.connections)
    router.run()