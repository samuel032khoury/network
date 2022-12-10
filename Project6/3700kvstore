#!/usr/bin/env python3

import argparse, socket, time, json, select, struct, sys, math, os, random
from time import time as now

FOLLOWER = 'follower'
LEADER = 'leader'
CANDIDATE = 'candidate'

HEARTVBEAT_RATE = 0.1

# to represent one replica in a RAFT consensus cluster
class Replica:
    # to initialize the replica
    def __init__(self, port, rid, others):
        self.port = port # replica's port
        self.rid = rid # replica's id
        self.others = others # replica's peers
        self.cluster_size = len(others) + 1 # the size of the network cluster
        self.leader = "FFFF" # the leader of the network cluster

        self.last_communication = 0 # time stamp of the last message receieved
        self.election_timeout = random.uniform(0.3, 0.6) # the et of the replica (high = 2 * low)

        self.status = FOLLOWER # the statues of the replica, initialized to be a follower

        self.current_term = 0 # the term the replica is in
        self.voted_for = {} # the voting log for the replica
        self.vote_from = set() # votes stats for the replica when there's an ongoing election

        self.log = [{'term': 0}] # local log
        self.commit_index = 0 # index of the last commited entry
        self.last_applied = 0 # index of the last entry applied to the state machine (database)

        self.data = {} # database
        self.msg_tracker = {} # timespan tracker for a message

        # For leader's use only
        self.next_index = {}
        self.match_index = {}

        # to initialize the socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', 0))
        self.recv_buff = []

        print("Replica %s starting up" % self.rid, flush=True)
        hello = { "src": self.rid, "dst": self.leader, "leader": self.leader, "type": "hello" }
        self.send(hello)
        print("Sent hello message: %s" % hello, flush=True)

    # compose a message of the specified type with the defult and extra attributes
    def compose_msg(self, msg_type, extra={}):
        return {'src': self.rid,'leader': self.leader,'type': msg_type,**extra}

    # send a message to the socket
    def send(self, msg, dst = None):
        # overwrite the dst of message if it's provided
        if dst:
            msg['dst'] = dst
        # check dst info exists
        if 'dst' in msg:
            self.socket.sendto(json.dumps(msg).encode('utf-8'), ('localhost', self.port))
        else:
            raise Exception("ERROR: No dst information!")

    # to initiate an election
    def start_election(self):
        self.current_term += 1 # increment currentTerm
        self.status = CANDIDATE # transit as a candidate
        self.leader = 'FFFF' # reset leader
        self.voted_for[self.current_term] = self.rid # vote for self
        self.vote_from = {self.rid} # reset the vote result everytime a new election takes place
        self.last_communication = now() # reset election timer
        self.issue_request_vote() # send request vote RPC

    # to send (broadcast) a request vote RPC
    def issue_request_vote(self):
        extra = {
            "candidate_id": self.rid,
            'term': self.current_term,
            'last_log_index': len(self.log) - 1,
            'last_log_term': self.log[-1]['term']
        }
        msg = self.compose_msg("vote_req", extra)
        for rid in self.others:
            self.send(msg, rid)

    # to send a append entries RPC to the target, broadcast if the target is not specified
    # this method is (guaranteed) only invoked by a leader
    def issue_append_entries(self, target=None):
        dsts = self.others if target == None else [target]
        for rid in dsts:
            rid_next_index = self.next_index[rid]
            entries = [] if rid_next_index >= len(self.log) else self.log[rid_next_index:]
            # new log entries for the rid replica
            extra = {
                'term': self.current_term, # leader's term
                'prev_log_index': rid_next_index - 1, # index of the last log entry
                'prev_log_term': self.log[rid_next_index - 1]['term'], # term of prevLogIndex entry
                'leader_commit': self.commit_index, # leader’s commitIndex
                'entries': entries if len(entries) <= 50 else entries[0:50] # trim if too long
            }
            msg = self.compose_msg('append_req', extra) 
            self.send(msg, rid)
        # reset election timeout
        self.last_communication = now()

    # process all the messages in the message buffer
    def process_msgs(self):
        # to buffer failed RPCs
        failed_rpc = []
        # put failed RPCs back to the receiving buffer
        def reload_failed_rpc():
            nonlocal failed_rpc
            self.recv_buff = failed_rpc + self.recv_buff
            failed_rpc = []
        
        # process a message as a follower
        def process_as_follower(msg):
            nonlocal failed_rpc
            # deal with get+put
            if msg['type'] in ["get", "put"]:
                # deal with get/put message if leader is offline
                if self.leader == 'FFFF':
                    failed_rpc.append(msg)
                # redirect the client to the leader
                else:
                    res = self.compose_msg('redirect', {'MID': msg['MID']})
                    self.send(res, msg['src'])
            
            # deal with append_req
            elif msg['type'] == "append_req":
                self.last_communication = now() # reset the timeout
                # fail the append entries RPC if any of the following is true
                #   - the leader is out of date
                #   - the prevLogIndex is out of bound of the local log
                #   - the term at prevLogIndex doesn't match
                if (msg['term'] < self.current_term or
                msg['prev_log_index'] >= len(self.log) or
                msg['prev_log_term'] != self.log[msg['prev_log_index']]['term']):
                    # to calibrate next id stored in the sender
                    calibrated_next_id = len(self.log) - 1
                    if msg['prev_log_index'] < len(self.log):
                        # if the prevLogIndex is within the range of the local log,
                        # set it to the first index of the current term
                        for i in range(len(self.log)):
                            if self.log[i]['term'] == self.log[msg['prev_log_index']]['term']:
                                calibrated_next_id = i
                                break
                    extra = {
                        'term': self.current_term, 
                        'success': False, 
                        'next_index': calibrated_next_id
                    }
                    res = self.compose_msg('append_res', extra)
                    self.send(res, msg['src'])
                # Append and commit
                else:
                    self.leader = msg['leader'] # update the leader
                    self.current_term = msg['term'] # update the term
                    if msg['leader_commit'] > self.commit_index:
                        self.commit_index = min(msg['leader_commit'], len(self.log) - 1)
                    # append the entries in the message to the local log
                    if len(msg['entries']) > 0:
                        self.log = self.log[:msg['prev_log_index'] + 1]
                        self.log.extend(msg['entries'])
                        extra = {
                            'term': self.current_term, 
                            'success': True, 
                            'next_index': len(self.log)
                        }
                        res = self.compose_msg('append_res', extra)
                        self.send(res, msg['src'])
                    # commit all (apply to the state machine/datebase) up to the commit index
                    while self.commit_index > self.last_applied:
                            self.last_applied += 1
                            key = self.log[self.last_applied]['key']
                            value = self.log[self.last_applied]['value']
                            self.data[key] = value

            # deal with vote_req
            elif msg['type'] == "vote_req":
                # reject immediately if the candidate is outdated
                if msg['term'] < self.current_term:
                    vote_granted = False
                else:
                    self.current_term = msg['term'] # update the term
                    self.leader = 'FFFF' # reset the leader
                    self.last_communication = now() # reset the timeout
                    candidate_has_good_log_term = msg['last_log_term'] >= self.log[-1]['term']
                    candidate_has_longer_log = msg['last_log_index'] >= len(self.log) - 1
                    # check if the candidate is up to date:
                    #   - candidate has at least the same term as current replica
                    #   - candidate has at least no shorter log entries if term is the same
                    candidate_is_utd = candidate_has_good_log_term and candidate_has_longer_log
                    # vote if the current replica still has a vote and the candidate is up to date
                    vote_granted = (self.current_term not in self.voted_for or
                     self.voted_for[self.current_term] == msg['candidate_id']) and candidate_is_utd
                    if vote_granted:
                        self.voted_for[self.current_term] = msg['candidate_id']
                extra = {'term': self.current_term, 'vote_granted': vote_granted}
                res = self.compose_msg("vote_res", extra)
                self.send(res, msg['src'])       

        # process a message as a candidate
        def process_as_candidate(msg):
            nonlocal failed_rpc
            # revert the cadidate to a follower
            def revert_to_follower_from_candidate():
                self.status = FOLLOWER
                self.leader = msg['leader'] # update the leader
                self.last_communication = now() # reset the timeout
                self.current_term = msg['term'] # update the term
                self.vote_from = set() # reset the vote stats
                reload_failed_rpc() # reload the failed RPCs

            # promote the candidate to a follower
            def promote_to_leader():
                self.status = LEADER
                self.leader = self.rid # update the leader
                self.last_communication = 0 # reset the timeout
                for rid in self.others: # initialize the nextIndex and matchIndex
                    self.next_index[rid] = len(self.log)
                    self.match_index[rid] = 0
                self.issue_append_entries() # to send an append entries RPC immediately

            # deal with vote_res
            if msg['type'] == "vote_res":
                #deal with rejection
                if msg['term'] > self.current_term:
                    revert_to_follower_from_candidate() # revert to follower if self is outdated
                #deal with addmission
                if msg['term'] == self.current_term and msg['vote_granted'] == True:
                    self.vote_from.add(msg['src']) # count the vote
                    if(len(self.vote_from) > (self.cluster_size / 2.0)):
                        promote_to_leader() # promote self to a leader if gets votes from majority   
                        
            
            # deal with vote_req as a candidate
            elif msg['type'] == "vote_req":
                if msg['term'] > self.current_term:
                    # failed_rpc.append(msg)
                    revert_to_follower_from_candidate() # revert to follower if self is outdated
                else:
                    extra = {'term': self.current_term, 'vote_granted': False}
                    res = self.compose_msg('vote_res', extra)
                    self.send(res, msg['src'])
            # deal with append_req as a candidate
            elif msg['type'] == "append_req":
                if msg['term'] >= self.current_term:
                    # failed_rpc.append(msg)
                    revert_to_follower_from_candidate() # revert to follower if self is outdated
                else:
                    # a candiadate is going to fail a append request
                    extra = {
                        'term': self.current_term, 
                        'success': False, 
                        'next_index': len(self.log)
                    }
                    res = self.compose_msg('append_res', extra)
                    self.send(res, msg['src'])
            # deal with append_res as a candidate
            elif msg['type'] == "append_res":
                if msg['term'] >= self.current_term:
                    revert_to_follower_from_candidate() # revert to follower if self is outdated
            # deal with get+put as a candidate
            elif msg['type'] in ["get", "put"]:
                failed_rpc.append(msg) # buffer to the failed RPC and deal with later
                        
        # process a message as a leader
        def process_as_leader(msg):
            def revert_to_follower_from_leader():
                self.status = FOLLOWER
                self.current_term = msg['term'] # update the term
                self.leader = msg['leader'] # update the leader
                self.next_index.clear() # empty the next index dict
                self.match_index.clear() # empty the macth index dict
                self.last_communication = now() # reset the timeout
                reload_failed_rpc() # reload the failed RPCs

            # deal with get as a leader
            if msg['type'] =='get':
                value = self.data.get(msg['key'], "") # value or empty string if it's not existed
                extra = {'value': value, 'key': msg['key'], 'MID': msg['MID']}
                res = self.compose_msg('ok', extra) # send response back to the client
                self.send(res, msg['src'])
            # deal with put as a leader
            elif msg['type'] =='put':
                if msg['MID'] not in self.msg_tracker:
                    self.msg_tracker[msg['MID']] = now() # reset the message tracker value
                elif now() - self.msg_tracker[msg['MID']] > 1:
                    # response with a failure message to the client if it takes too long
                    res = self.compose_msg('fail', {'MID': msg['MID']})
                    self.send(res, msg['src'])
                new_entry = {
                    'src': msg['src'], 
                    'MID': msg['MID'], 
                    'key': msg['key'], 
                    'value': msg['value'], 
                    'term': self.current_term
                }
                self.log.append(new_entry) # record to the local loc
                self.issue_append_entries() # send an append entries RPC immediately
            # deal with append_req
            elif msg['type'] == 'append_req':
                if msg['term'] >= self.current_term:
                    # revert to follower if self is outdated
                    revert_to_follower_from_leader()
                else:
                    # fail other leader's message otherwise
                    extra = {'term': self.current_term, 'success': False}
                    res = self.compose_msg('append_res', extra)
                    self.send(res, msg['src'])
            # deal with append_res
            elif msg['type'] == 'append_res':
                if msg['term'] > self.current_term:
                    revert_to_follower_from_leader()  # revert to follower if self is outdated
                elif msg['success'] == False:
                    # response to a failed append entries RPC caused by inconsistency
                    self.next_index[msg['src']] = msg['next_index']
                    self.issue_append_entries(target=msg['src'])
                else:
                    # update nextIndex and matchIndex
                    self.next_index[msg['src']] = msg['next_index']
                    self.match_index[msg['src']] = msg['next_index'] - 1
                
                    # find the consensual commit index 
                    for i in range(len(self.log) - 1, self.commit_index - 1, -1):
                        if self.log[i]['term'] != self.current_term:
                            break
                        count = 0
                        for rid_match_index in self.match_index.values():
                            if rid_match_index >= i:
                                count += i
                        if count > self.cluster_size / 2.0:
                            break
                    self.commit_index = max(i, self.commit_index)

                    # commit up to the commit index
                    while self.last_applied < self.commit_index:
                        self.last_applied += 1
                        key = self.log[self.last_applied]['key']
                        value = self.log[self.last_applied]['value']
                        self.data[key] = value
                        # send a response back to the client
                        res = self.compose_msg("ok", {'MID': self.log[self.last_applied]['MID']})
                        self.send(res, self.log[self.last_applied]['src'])
            # deal with vote_req
            elif msg['type'] == 'vote_req':
                if msg['term'] > self.current_term:
                    revert_to_follower_from_leader()  # revert to follower if self is outdated
                else:
                    extra = {'term': self.current_term, 'success': False}
                    res = self.compose_msg('vote_res', extra)
                    self.send(res, msg['src'])
            # deal with vote_res
            elif msg['type'] == 'vote_res':
                if msg['term'] > self.current_term:
                    revert_to_follower_from_leader()  # revert to follower if self is outdated

        # function mapping
        process_as = {
            FOLLOWER: process_as_follower,
            CANDIDATE: process_as_candidate,
            LEADER: process_as_leader
        }
        # process all the messages in the receiving buffer
        while len(self.recv_buff) > 0:
            msg = self.recv_buff.pop(0)
            process_as[self.status](msg)
        # relaod failed ones and to process during the next round
        reload_failed_rpc()

    # launch the replica
    def run(self):
        while True:
            # make the leader signal heartbeat to the heartbeat rate
            if self.status == LEADER and (now() - self.last_communication > HEARTVBEAT_RATE):
                self.issue_append_entries()

            # Buffer messages (blocking) for 0.1s
            recv_starting_time = now()
            while now() - recv_starting_time < 0.1:
                pckt, addr = self.socket.recvfrom(65535)
                if not pckt:
                    if not self.recv_buff:
                        return
                    break
                msg = json.loads(pckt.decode('utf-8'))
                # ignore other replicas' messages
                if msg['dst'] != self.rid:continue
                print("Received message '%s'" % (msg,), flush=True)
                self.recv_buff.append(msg)
            
            # process buffered messages
            self.process_msgs()

            # initiate an election if there's an election timeout
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