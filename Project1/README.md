# Project1 - Socket Basics

## High-Level Approach

- The program is written in python and runs on the command line with two optional arguments (port, secureFlag) and two positional arguments (hostname, username).

    ```shell
    $ ./client < -p port > < -s > <hostname> <Northeastern-username>
    ```

- The default port is set to 27993 (if SSL is not specified) or 27994 (if SSL is specified). 

- The program communicates with the remote server with JSON-formatted objects to play the wordle game.

- The program was designed defensively so it only parses valid replies (replies with proper "type") from the server. If the reply is not valid, it will raise an error and terminate the program.

### Gussing Strategy

- The program makes its guess in two rounds: filtering round and targeting round.

  - #### Filter Round

    - The program has included 16 words (in list `filterWords`) from the wordlist that covers every letter two times. The program will iterate over this list and send a guess request to the server with each of them. In this case, we can filter out letters that are not in the correct word, filter in (i) letters that are in the correct word but not at the correct position, and (ii) letters that are in the correct word AND at the correct position. 
      - All of the information above will be saved into dedicated variables.
        - `alphabet` is a **list** of **char** that stores all the letters filtered in -- this is the constrained (smaller) list of letters that make up the correct word.

        - `nullPlace` is a **list** (size of 5) of **set**s where each of them includes **char**s that should not be placed at the corresponding position -- this helps narrow down the guessing list in the targeting round.
        - `final` is a list (size of 5) of **char**, with a default value of an empty string. Once a letter is secured at a position, the empty string will be replaced with that char.

    - After running the filter round, we completely formed the `alphabet` and the `nullPlace`, and partially formed the `final`.
      - If the correct word happens to occur in the `filterWords`, or the `final` is completely formed by the end of the filter round where we are certain about the correct word and can send it to the server, we get the 'bye' message from the server, read (and output) the flag from the reply, and terminate the program without worrying about the process below.

    - With the information from the filter round, we can generate a **list** of **set**s, where each of them includes *possible* **char** for a corresponding position (by filtering out **char**s in the `nullSpace` at a position from the `alphabet` and keeping the rest of the alphabet for that position). We then generate all the possible permutations (with itertools) of letters at positions left empty in the `final`. We iterate over all permutations, filling the current permutation in (a copy of) `final`, check if it makes up a word against the [word list](https://3700.network/projects/project1-words.txt) provided -- ignore if not, save into the `targetWords` if yes.

  - #### Targeting Round

    - By the rule of wordle, the correct word has to be in the `targetWord` (if it hasn't been revealed during the filtering round). We then iterate over the `targetWord` and make guesses -- one of them will pass the wordle check, allowing us to get the 'bye' message (and the secret flag) from the server.


## Testing

I manually ran the program 50+ times with different configurations (specifically, run it with/out the SSL flag). The program returns **exactly one line of output** (the secret flag) as expected every time.
