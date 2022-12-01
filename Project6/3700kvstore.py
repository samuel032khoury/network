#!/usr/bin/env python3

import argparse, socket, time, json, select, struct, sys, math, os, random
from time import time as now

HEARTVBEAT_RATE = 0.1

FOLLOWER = 'follower'
LEADER = 'leader'
CANDIDATE = 'candidate'

class Replica:
    def __init__(self, port, rid, others):
        self.port = port
        self.rid = rid
        self.others = others
        self.cluster_size = len(others) + 1

        self.leader = "FFFF"
        self.last_communication = 0
        self.election_timeout = random.uniform(0.3, 0.6) # high = 2 * low

        self.status = FOLLOWER

        self.current_term = 0
        self.voted_for = {}
        self.vote_from = set()

        self.log = [{'term': 0, 'command':None}]
        self.commit_index = 0
        self.last_applied = 1

        self.data = {}

        # For leader's use only
        self.next_index = {}
        self.match_index = {}

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', 0))
        self.recv_buff = []

        print("Replica %s starting up" % self.rid, flush=True)
        hello = { "src": self.rid, "dst": self.leader, "leader": self.leader, "type": "hello" }
        self.send(hello)
        print("Sent hello message: %s" % hello, flush=True)

    def compose_msg(self, msg_type, extra={}):
        msg = {
            'src': self.rid,
            'leader': self.leader,
            'type': msg_type,
            **extra
        }
        return msg

    def send(self, msg):
        self.socket.sendto(json.dumps(msg).encode('utf-8'), ('localhost', self.port))

    def broadcast(self, msg):
        for rid in self.others:
            msg['dst'] = rid
            self.send(msg)

    def start_election(self):
        self.current_term += 1
        self.status = CANDIDATE
        self.leader = 'FFFF'
        if self.current_term in self.voted_for:
            raise Exception("A replica only has one vote for each term!")
        self.voted_for[self.current_term] = self.rid
        self.vote_from = {self.rid} # reset the vote result everytime a new election takes place
        self.last_communication = now()
        self.issue_request_vote()

    def issue_request_vote(self):
        extra = {
            "candidate_id": self.rid,
            'term': self.current_term,
            'last_log_index': len(self.log) - 1,
            'last_log_term': self.log[-1]['term']
        }
        msg = self.compose_msg("vote_req", extra)
        self.broadcast(msg)

    # only invoked by a leader
    def issue_append_entries(self, init=False):
        if init:
            extra ={
                'term': self.current_term,
                'prev_log_index': 0,
                'prev_log_term': 0,
                'entries': [],
                'leader_commit': self.commit_index
            }
            msg = self.compose_msg("append_req", extra)
            self.broadcast(msg)
        else:
            for rid in self.others:
                entries = [] if self.next_index[rid] >= len(self.log) else self.log[self.next_index[rid]:]
                extra = {
                    'term': self.current_term,
                    'prev_log_index': self.next_index[rid] - 1, 
                    'prev_log_term': self.log[self.next_index[rid] - 1]['term'], 
                    'leader_commit': self.commit_index,
                    'entries': entries if len(entries) <= 10 else entries[0:10]
                }
                msg = self.compose_msg('append_req', extra)
                msg['dst'] = rid
                self.send(msg)
        self.last_communication = now()

    def process_msgs(self):
        if not self.recv_buff:return

        failed_rpc = []
        def reload_failed_rpc():
            nonlocal failed_rpc
            self.recv_buff += failed_rpc.copy()
            failed_rpc = []
        
        # process a message as a follower
        def process_as_follower(msg):
            nonlocal failed_rpc
            # deal with get+put
            if msg['type'] in ["get", "put"]:
                if self.leader == 'FFFF':
                    failed_rpc.append(msg)
                else:
                    res = self.compose_msg('redirect', {'MID': msg['MID']})
                    res['dst'] = msg['src']
                    self.send(res)
            
            # deal with append_req
            elif msg['type'] == "append_req":
                self.last_communication = now()
                if msg['term'] < self.current_term or msg['prev_log_index'] >= len(self.log) or msg['prev_log_term'] != self.log[msg['prev_log_index']]['term']:
                    extra = {'term': self.current_term, 'success': False, 'next_index': self.commit_index}
                    res = self.compose_msg('append_res', extra)
                    res['dst'] = msg['src']
                    self.send(res)
                else:
                    self.leader = msg['leader']
                    self.current_term = msg['term']
                    if len(msg['entries']) > 0:
                        self.log = self.log[:msg['prev_log_index'] + 1]
                        for entry in msg['entries']:
                            self.log.append(entry)
                    if msg['leader_commit'] > self.commit_index:
                        self.commit_index = min(msg['leader_commit'], len(self.log) - 1)
                        while self.commit_index > self.last_applied:                        # apply all log messages between last_applied and our (possibly new) commit_index
                            self.data[self.log[self.last_applied]['key']] = self.log[self.last_applied]['value']
                            self.last_applied += 1
                    extra = {'term': self.current_term, 'success': True, 'next_index': len(self.log)}
                    res = self.compose_msg('append_res', extra)
                    res['dst'] = msg['src']
                    self.send(res)

            # deal with vote_req
            elif msg['type'] == "vote_req":
                if msg['term'] < self.current_term:
                    vote_granted = False
                else:
                    self.current_term = msg['term']
                    self.leader = 'FFFF'
                    self.last_communication = now()
                    candidate_has_good_log_term = msg['last_log_term'] >= self.log[-1]['term']
                    candidate_has_longer_log = msg['last_log_index'] >= len(self.log) - 1
                    candidate_is_utd = candidate_has_good_log_term and candidate_has_longer_log
                    vote_granted = (self.current_term not in self.voted_for or
                     self.voted_for[self.current_term] == msg['candidate_id']) and candidate_is_utd
                    if vote_granted:
                        self.voted_for[self.current_term] = msg['candidate_id']
                res = self.compose_msg("vote_res", {'term': self.current_term, 'vote_granted': vote_granted})
                res['dst'] = msg['src']
                self.send(res)       

        # process a message as a candidate
        def process_as_candidate(msg):
            nonlocal failed_rpc

            def revert_to_follower():
                self.status = FOLLOWER
                self.current_term = msg['term']
                self.vote_from = set()
                self.leader = msg['leader']
                self.last_communication = now()

            # deal with vote_res
            if msg['type'] == "vote_res":
                #deal with rejection
                if msg['term'] > self.current_term:
                    revert_to_follower()
                    reload_failed_rpc()

                #deal with addmission
                if msg['term'] == self.current_term and msg['vote_granted'] == True:
                    self.vote_from.add(msg['src'])
                    if(len(self.vote_from) > (self.cluster_size / 2.0)):
                        self.status = LEADER
                        self.leader = self.rid
                        self.last_communication = 0
                        for rid in self.others:
                            self.next_index[rid] = len(self.log)
                            self.match_index[rid] = 0
                        self.issue_append_entries(init = True)
            
            # deal with vote_req
            elif msg['type'] == "vote_req":
                if msg['term'] > self.current_term:
                    revert_to_follower()
                    failed_rpc.append(msg)
                    reload_failed_rpc()
                else:
                    extra = {'term': self.current_term, 'vote_granted': False}
                    res = self.compose_msg('vote_res', extra)
                    res['dst'] = msg['src']
                    self.send(res)
            # deal with append_req
            elif msg['type'] == "append_req":
                if msg['term'] >= self.current_term:
                    revert_to_follower()
                    failed_rpc.append(msg)
                    reload_failed_rpc()
                else:
                    extra = {'term': self.current_term, 'success': False}
                    res = self.compose_msg('append_res', extra)
                    res['dst'] = msg['src']
                    self.send(res)
            # deal with append_res
            elif msg['type'] == "append_res":
                if msg['term'] >= self.current_term:
                    revert_to_follower()
                    reload_failed_rpc()
            # deal with get+put
            elif msg['type'] in ["get", "put"]:
                failed_rpc.append(msg)
                        
        # process a message as a leader
        def process_as_leader(msg):
            def revert_to_follower():
                self.status = FOLLOWER
                self.current_term = msg['term']
                self.leader = msg['leader']
                self.next_index.clear()
                self.match_index.clear()
                self.last_communication = now()
            # leader get + put (implement mutex later)
            if msg['type'] =='get':
                value = self.data.get(msg['key'], "")
                extra = {'value': value, 'key': msg['key'], 'MID': msg['MID']}
                res = self.compose_msg('ok', extra)
                res['dst'] = msg['src']
                self.send(res)
            elif msg['type'] =='put':
                new_entry = {
                    'src': msg['src'], 
                    'MID': msg['MID'], 
                    'key': msg['key'], 
                    'value': msg['value'], 
                    'term': self.current_term
                }
                self.log.append(new_entry)
            # deal with append_req
            elif msg['type'] == 'append_req':
                if msg['term'] >= self.current_term:
                    revert_to_follower()
                    failed_rpc.append(msg)
                    reload_failed_rpc()
                else:
                    extra = {'term': current_term, 'success': False}
                    res = self.compose_msg('append_res', extra)
                    res['dst'] = msg['src']
                    self.send(res)
            # deal with append_res
            elif msg['type'] == 'append_res':
                if msg['term'] > self.current_term:
                    revert_to_follower()
                    reload_failed_rpc()
                elif msg['success'] == False:
                    self.next_index[msg['src']] = msg['next_index']
                else:
                    self.next_index[msg['src']] = msg['next_index']
                    self.match_index[msg['src']] = msg['next_index'] - 1
                
                # leader commit 
                for i in range(self.commit_index+1, len(self.log)):
                    count = 0
                    for rid in self.others:
                        if self.match_index[rid] >= i and self.log[i]['term'] == self.current_term:
                            count = count + 1
                    if count > self.cluster_size / 2.0:
                        self.commit_index = i
                    else:
                        break
                while self.last_applied < self.commit_index:
                    self.data[self.log[self.last_applied]['key']] = self.log[self.last_applied]['value']
                    res = self.compose_msg("ok", {'MID': self.log[self.last_applied]['MID']})
                    res['dst'] = self.log[self.last_applied]['src']
                    self.send(res)
                    self.last_applied += 1

            # deal with vote_req
            elif msg['type'] == 'vote_req':
                if msg['term'] > self.current_term:
                    revert_to_follower()
                    failed_rpc.append(msg)
                    reload_failed_rpc()
                else:
                    extra = {'term': current_term, 'success': False}
                    res = self.compose_msg('append_res', extra)
                    res['dst'] = msg['src']
                    self.send(res)
            # deal with vote_res
            elif msg['type'] == 'vote_res':
                if msg['term'] > self.current_term:
                    revert_to_follower()
                    reload_failed_rpc()

        process_as = {
            FOLLOWER: process_as_follower,
            CANDIDATE: process_as_candidate,
            LEADER: process_as_leader
        }
        while len(self.recv_buff) > 0:
            msg = self.recv_buff.pop(0)
            process_as[self.status](msg)
        reload_failed_rpc()

    def run(self):
        while True:
            if self.status == LEADER and (now() - self.last_communication > HEARTVBEAT_RATE):
                self.issue_append_entries()
            
            data, addr = self.socket.recvfrom(65535)
            if not data:
                return
            msg = json.loads(data.decode('utf-8'))
            print("Received message '%s'" % (msg,), flush=True)
            self.recv_buff.append(msg)

            time_stamp = now()
            while now() - time_stamp < 0.1:
                data, addr = self.socket.recvfrom(65535)
                if not data:
                    break
                msg = json.loads(data.decode('utf-8'))
                if msg['dst'] != self.rid:continue
                print("Received message '%s'" % (msg,), flush=True)
                self.recv_buff.append(msg)
            
            self.process_msgs()

            if self.status != LEADER and (now() - self.last_communication > self.election_timeout):
                self.start_election()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='run a key-value store')
    parser.add_argument('port', type=int, help="Port number to communicate")
    parser.add_argument('id', type=str, help="ID of this replica")
    parser.add_argument('others', metavar='others', type=str, nargs='+', help="IDs of other replicas")
    args = parser.parse_args()
    replica = Replica(args.port, args.id, args.others)
    replica.run()
