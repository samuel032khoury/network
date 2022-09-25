# Project2 - FTP

## High-Level Approach
- The program is written in python and runs on the command line with 2, or 3, positional arguments, depending on the FTP command (1st argument of the program).

### Usage

```shell
$ ./3700ftp <ftp-reg-command> <ftp-URL> #or
$ ./3700ftp <ftp-file-transmission-related-command> <ftp-URL> <local-file-path> #or
$ ./3700ftp <ftp-file-transmission-related-command>  <local-file-path> <ftp-URL>
```

### Design

- The program starts with parsing the command line arguments; the process determines what FTP command will be sent (to the socket, in the later stage), the URL address, and the local-file path (if exists). It also infers the file transmission direction (if the FTP mode is file transmission related).

  - File transmission-related FTP mode includes `cp` and `mv`. Note `ls` is an exception -- although it involves data transmission, there isn't a FILE involved; we treat it as an (exceptional) control command for simplicity.
- The program then parses the username, password, server, port, and remote path from the given URL.
- The program then connects with the server using a (the command) socket and login with the credential.
- The program then sends a command to the server.
  - If the command doesn't involve data transmission, i.e., `rm`, `rmdir`, or `mkdir`, the program will send a command message and print out the response.
  - If the command involves data transmission, the program will request the server to open a data transmission socket for it and attempts to connect with the data socket. If successful, the program will send/receive the data from the remote server and printout/save them to a file, depending on which command is used.
    - If the command is `mv`, the program will also perform a file deletion on the source side (remote if downloading, local if uploading).
- Finally, the program sends a `QUIT` message to close the (command) socket and return.


## Testing

The testing for this program was done manually. Different FTP commands were run several times with various file-name/dir-path, and it was observed that the program could perform those tasks perfectly. The program will terminate and quit elegantly if something goes wrong between the server and the client. The program throws exceptions only when the user wrongly uses the program, e.g., providing insufficient arguments, providing extraneous arguments, using a non-recognizable command, etc.
