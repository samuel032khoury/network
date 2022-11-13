# README
# Project 5 - Web Crawler

## Running the Program

The program is written in python and runs on the command line with 2 optional arguments for the server and the port to crawl, and 2 positional arguments for the username and password to log in to Fakebook. 

We use the default server _proj5.3700.network_ and default port _443_ when they are not specified on the command line.


```shell
$ ./3700crawler <-s server> <-p port> <username> <password>
```

## Design
The program first attempts to log into Fakebook using the supplied username and password from the command line. Upon successful login, we retrieve the first available link and redirect the crawler to this link. Each link that the crawler encounters is now added to the frontier, and all of the pages corresponding to these links in the frontier are parsed line by line. 

As the crawler progresses, if we encounter a link during parsing which redirects to another page on the same server (i.e. it has the tag `'<a href="/fakebook'`), we add it to the frontier provided that it is not already present in the log.

We attempt to visit each link in the frontier to parse the content on its corresponding page. However, if we receive status codes that do not indicate success (200), we attempt to revisit the page (in case of a 503 internal server error) or remove the link from the frontier (in case of a 404 no page found or 403 forbidden access).

During the parsing of pages, if we encounter a header with `class='secret_flag'`, we retrieve the 64 characters corresponding to the respective flag and add it to the set of flags.

Once we have collected all 5 secret flags, the program terminates gracefully.

The program was designed modularly, with various functions performing sub-tasks for each message received. This made debugging the program simpler and ensured readability. Some challenges were faced in understanding how to construct HTTP messages, but these were solved by running through simpler examples and debugging manually. 

## Testing
Testing for this program was done manually by performing logical tasks (e.g., parsing content to find the relevant flag and link headers) on smaller examples and then translating them to the entire project. 

