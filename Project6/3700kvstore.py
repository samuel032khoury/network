#!/usr/bin/env python3

import argparse, socket, time, json, select, struct, sys, math, os
import numpy as np
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
        self.last_communication = now()
        self.election_timeout = np.random.uniform(0.3, 0.6) # high = 2 * low

        self.status = FOLLOWER

        self.current_term = 0
        self.voted_for = {}
        self.vote_from = set()

        self.log = [{'term': 0, 'command':None}]
        self.commit_index = 0
        self.last_applied = 0

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
        extra = {
            'term': self.current_term,
            'leader_id': self.leader,
        }
        if init:
            extra.update({
                'prev_log_index': len(self.log),
                'prev_log_term': self.log[-1]['term'],
                'entries': [],
                'leader_commit': self.commit_index})
        else:
            pass
        msg = self.compose_msg("append_req", extra)
        self.broadcast(msg)
        self.last_communication = now()

    def process_msgs(self):
        if not self.recv_buff:return
        def process_as_follower(msg):
            if msg['type'] == 'vote_req':
                if msg['term'] < self.current_term:
                    vote_granted = False
                else:
                    self.current_term = msg['term']
                    self.leader = 'FFFF'
                    candidate_has_higher_log_term = msg['last_log_term'] >= self.log[-1]['term']
                    candidate_has_longer_log = msg['last_log_index'] >= len(self.log) - 1
                    candidate_is_utd = candidate_has_higher_log_term and candidate_has_longer_log
                    vote_granted = (self.current_term not in self.voted_for or
                     self.voted_for[self.current_term] == msg['candidate_id']) and candidate_is_utd
                    if vote_granted:
                        self.voted_for[self.current_term] = msg['candidate_id']
                res = self.compose_msg("vote_res", {'term': self.current_term, 'vote_granted': vote_granted})
                res['dst'] = msg['src']
                self.send(res)

        def process_as_candidate(msg):
            if msg['type'] == 'vote_res':
                if msg['term'] == self.current_term and msg['vote_granted'] == True:
                    self.vote_from.add(msg['src'])
                    if(len(self.vote_from) > (self.cluster_size / 2.0)):
                        self.status = LEADER
                        self.leader = self.rid
                        for rid in self.others:
                            self.next_index[rid] = len(self.log)
                            self.match_index[rid] = 0
                        self.issue_append_entries(init = True)
                        


        def process_as_leader(msg):
            pass
        process_as = {
            FOLLOWER: process_as_follower,
            CANDIDATE: process_as_candidate,
            LEADER: process_as_leader
        }
        ### integrate failed while stable
        failed = []
        for msg in self.recv_buff:
            process_as[self.status](msg)
        self.recv_buff = failed.copy()


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

            if self.status == FOLLOWER and (now() - self.last_communication > self.election_timeout):
                self.start_election()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='run a key-value store')
    parser.add_argument('port', type=int, help="Port number to communicate")
    parser.add_argument('id', type=str, help="ID of this replica")
    parser.add_argument('others', metavar='others', type=str, nargs='+', help="IDs of other replicas")
    args = parser.parse_args()
    replica = Replica(args.port, args.id, args.others)
    replica.run()
