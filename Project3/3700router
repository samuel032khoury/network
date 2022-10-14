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

    # stores the relationships between the current router and its neighboring router
    relations = {}
    # stores the socket connections between the current router and its neighboring router
    sockets = {}
    # stores the interfaces the neighboring router connecting into
    ports = {}
    # the router's routing table
    routingTable = {}
    # list for update logs
    updateLog = []
    # list for withdraw logs
    withdrawLog = []

    # Initialize the router
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

    # Log the withdraw and revoke an entry(s) from the routing table by disaggregating the table
    def withdraw(self, packet):
        # Disaggregate the routing table by reproducing by the latest update logs and withdraw logs
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
            # aggregate the table again so it's compact enough
            self.aggregate(target = src)

        self.withdrawLog.append(packet)
        src = packet['src']
        disaggregate(src)

    # Announce the update/revoke message to the router's neighbor
    # A message is announced only if it's from a customer or the destination is a customer
    def announce(self, src, packet, update):
        # Compose a forwarding message
        # Message format and content can be different depending on the announce type (Update/Revoke)
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
        
        # announce the message to other neighbors
        for host in self.sockets.keys():
            if host != src:
                if self.relations[host] == "cust" or self.relations[src] == "cust":
                    msg = composeForwardingMessage(host)
                    self.send(host, msg)

    # Aggregate all possible entries on the routing table that are adjacent numerically, forward to
    # the same next-hop router, and  have the same attributes
    def aggregate(self, target=None):
        # Determine if two networks have the same localpref, origin, selfOrigin, and ASPath
        def sameAttr(netOne, netTwo):
            return (netOne["localpref"] == netTwo["localpref"] 
                and netOne["origin"] == netTwo["origin"] 
                and netOne["selfOrigin"] == netTwo["selfOrigin"] 
                and netOne["ASPath"] == netTwo["ASPath"])
        # Determine if two networks are adjacent: have the same netmask and have same network prefix
        def adjacentNets(netOne, netTwo):
            if netOne['netmask'] != netTwo['netmask']:
                return False
            netMskBin = ipToBin(netOne['netmask'])
            netOneNwBin = ipToBin(netOne['network'])
            netTwoNwBin = ipToBin(netTwo['network'])
            diffPos = netOneNwBin.rfind('1')
            return netOneNwBin[:diffPos] == netTwoNwBin[: diffPos]

        # if no specific aggregate target, aggregate the entire routing table
        targetList = [target] if target else self.routingTable.keys()
        for currNeighbor in targetList:
            # at most merge n - 1 times, n as the total number of the routing entries for a neighbor
            maxMergeCount = len(self.routingTable[currNeighbor]) - 1
            for _ in range(maxMergeCount):
                currRoutesList = self.routingTable[currNeighbor]
                traversed = True
                # look into all possible combination of paired networks and see if any of them can
                # be merged
                for (netOne, netTwo) in list(combinations(currRoutesList, 2)):
                    # two networks can be merged only if they have same attributes and adjacent
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
                        # add the merged route to current neighbor's route list, and remove old ones 
                        currRoutesList.append(aggregatedRoute)
                        currRoutesList.remove(netOne)
                        currRoutesList.remove(netTwo)
                        traversed = False
                        break
                # The entire list is traversed without entering in the merging branch implies
                # everything has been merged. We thus break current neighbor's merging iteration
                if traversed:
                    break

    # Forward the data per the routing table, only forward if the src or the dest is a customer
    # A no-route message will be sent if there isn't a available route
    def forwardData(self, src, packet):
        # Match the destination network prefix with all entries in the routing table
        def matchPrefix(dst):
            matches = []
            for neighbor, routes in self.routingTable.items():
                for route in routes:
                    dstBin = ipToBin(dst)
                    networkBin = ipToBin(route['network'])
                    netmaskBin = ipToBin(route['netmask'])
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
                            matches.append((neighbor, matchingLength, route))
                            # Terminate the match
                            break
            # The returned list consists of tuples of neighbor connection address, the length of 
            # the matched prefix, and the route meta information
            return matches
        
        # Find the best forwarding route
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
            # default fall back to find the lowest neighbor IP address
            return min(bestRoutes, key = lambda x: x[0])

        # Compose a message that notifies the sender our router cannot route the message
        def composeNoRouteMessage():
            noRoutePacket = {
                'src' : self.routerOf(src),
                'dst' : packet['src'],
                'type': "no route",
                "msg" : {}
            }
            return json.dumps(noRoutePacket)
        
        # find all possible routes by matching the prefix of the destination of the message
        dst = packet['dst']
        matches = matchPrefix(dst)

        # if no available route, send back a no-route message
        if not matches:
            dst = src
            msg = composeNoRouteMessage()
        # otherwise find the best route and get the network address
        else:
            dst = findBestRoute(matches)[0]
            msg = json.dumps(packet)
        # if neither the destination or the source is a customer, we stop fowarding the message,
        # and send back a no-route message
        if (self.relations[dst] != 'cust' and self.relations[src] != 'cust'):
            dst = src
            msg = composeNoRouteMessage()
        self.send(dst, msg)

    # Dump all entries in the table, and send it back to the request source
    def dumpTable(self, src):
        # Restructure the routing table from one to one (list of routes) to one to many (routes)
        def expandRoutingTable(routingTable):
            expanded = []
            for neighbor, routes in routingTable.items():
                for route in routes:
                    expanded.append((neighbor, route))
            # The returned list consists of pairs of neighbor connection address and
            # the route information
            return expanded

        data = list(map(lambda entry : {
            "peer":entry[0],
            "network":entry[1]["network"],
            "netmask":entry[1]["netmask"],
            "localpref":entry[1]["localpref"],
            "origin":entry[1]["origin"],
            "selfOrigin":entry[1]["selfOrigin"],
            "ASPath":entry[1]["ASPath"],
            },expandRoutingTable(self.routingTable)))
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
    parser.add_argument('connections', metavar='connections',
     type=str, nargs='+', help="connections")
    args = parser.parse_args()
    router = Router(args.asn, args.connections)
    router.run()