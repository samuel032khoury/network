# grant the append entries rpc
def grant_append(self, msg):
    if self.state != LEADER:
        return
    self.next_indexes[msg[SRC]] = msg[NEXT_IDX]
    self.match_indexes[msg[SRC]] = msg[NEXT_IDX] - 1

    # check if the log of the match index is correct
    i = len(self.log) - 1
    while i >= 0:
        if self.log[i][TERM] == self.term:
            count = 0
            for server in self.match_indexes:
                if self.match_indexes[server] >= i:
                    count += 1
            if count >= ((len(self.others) + 1) // 2):
                break
        i -= 1

    # update the commit index
    if i > self.commit_index:
        self.commit_index = i
        self.apply_commit()

def reject_append(self, msg):
    if self.state != LEADER:
        return

    # ensure term is the same
    if msg[TERM] > self.term:
        self.state = FOLLOWER

    # then select the longest log
    if NEXT_IDX in msg: 
        self.next_indexes[msg[SRC]] = msg[NEXT_IDX]
    else:
        self.next_indexes[msg[SRC]] = self.next_indexes[msg[SRC]] - 1
    self.send_append_entries([msg[SRC]])

# received append entries rpc from the server, will update its state if is the first time hearing from the leader
def append_entries(self, msg):
    if msg[TERM] >= self.term:
        self.term = msg[TERM]
        self.state = FOLLOWER
        self.leader = msg[LEADER]
        self.vote = None
        self.votes = []
        for msg in self.no_leader_queue:
            self.send(self.client_msg(msg[SRC], 'redirect', msg[MID]))
        self.no_leader_queue = []

    if self.state == FOLLOWER: # do vote
        rejection = {
            SRC: self.id,
            DST: msg[SRC],
            LEADER: self.leader,
            TYPE: 'reject_append',
            TERM: self.term
        }

        # grant message
        grant = {
            SRC: self.id,
            DST: msg[SRC],
            LEADER: self.leader,
            TYPE: 'grant_append',
            TERM: self.term
        }

        # if term doesn't match, ask for an older log
        if msg[TERM] < self.term:
            self.send(rejection)
            return

        self.last_append = time.time()
        prev_log_index = msg[PREV_LOG_IDX]
        prev_log_term = msg[PREV_LOG_TERM]

        # if log index is not the one the server is looking for that can match with the leader
        # send a reject
        if len(self.log) - 1 < prev_log_index:
            self.send(rejection)
            return

        # check the log for the term, if not equals, reject
        if prev_log_term != self.log[prev_log_index][TERM]:
            for i in range(len(self.log)):
                if self.log[i][TERM] == self.log[prev_log_index][TERM]:
                    rejection[NEXT_IDX] = i
                    break
                else:
                    rejection[NEXT_IDX] = len(self.log) - 1
            self.send(rejection)
            return

        # if everything matches
        new_entries = msg[ENTRIES]
        self.log = self.log[: prev_log_index + 1] # dump the extra log
        self.log.extend(new_entries) # append to leader's log

        commit = msg[COMMIT]

        if commit > self.commit_index:
            self.commit_index = min(commit, len(self.log) - 1)
        grant[NEXT_IDX] = len(self.log)

        # if there are no entries in the server, grand the append
        if msg[ENTRIES] != 0:
            self.send(grant)
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            key = self.log[self.last_applied][KEY]
            value = self.log[self.last_applied][VALUE]
            self.database[key] = value

# check if a command can be executed, will be executed if majority agree
def apply_commit(self):
    while self.last_applied < self.commit_index:
        self.last_applied += 1
        key = self.log[self.last_applied][KEY]
        value = self.log[self.last_applied][VALUE]
        self.database[key] = value
        if self.state == LEADER:
            msg = self.client_msg(self.log[self.last_applied][CLIENT], 'ok', self.log[self.last_applied][MID])
            self.send(msg)

