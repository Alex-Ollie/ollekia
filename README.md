# ollekia

This is just the async rewrite I did of the Internet Archive Python wrapper for my own use case.
It does search/download/fetch. I hadn’t used Python in years when I rewrote it.

Feel free to use it, rewrite it, tell me how bad my Python is (don’t be too harsh... I get my feelings hurt easy).

I haven’t tested it in a bit. Currently swamped with Kodiak v1, one of the subsystems of the larger OLLIE Project — a long-term effort to build an open intelligence pipeline for correlating and preserving data that tends to slip through the cracks.

There’s likely dead code in some places. This isn’t polished. It’s ugly, and moody. And I’m definitely not a fan of Python.
I’ll get back to it eventually. And when I do, this README will change to something *slightly* less depressing.

USE AT OWN RISK

My Python code is like a microwaveable meal: convenient, functional, and probably unhealthy if you look too close. Probably only appetizing if you're high.

If you improve it, send a PR. I’ll probably merge it while sighing at Python.


regards,
Alex
08/Oct/2025


## ONE LAST NOTE:<br />
I included two files:<br />
`search_expr.py` <br />
*and* <br />
`search_param_full.json`

The json file is an example of a full and complex archive.org query and search_expr.py is a simple piece of code to translate it into a query to search. 
Unfortunately I don't have the output of the translation to show. And I'm a lazy bitch right now to run it. But it did work last I tried it. If you want to automate commplex searches based on that json structure, those two files will allow you to use it. You may be able to do it with the wrapper search file. I dunno, again I'm just being a lazy bitch. I commented it a bit ago because I'd inevitably forget. I did forget. But the comments did help.
