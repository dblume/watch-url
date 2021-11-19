[![License](https://img.shields.io/badge/license-MIT_license-blue.svg)](https://raw.githubusercontent.com/dblume/watch-url/main/LICENSE.txt)
![python3.x](https://img.shields.io/badge/python-3.x-green.svg)

## Receive a notification when a URL changes

With this script you can receive a notification when a URL changes.

## Before You Start

If you have a site that is expected to change every once in a while, you should
consider providing an RSS or Atom feed for the site. That [feed should support
HTTP Conditional GETs](https://fishbowl.pastiche.org/2002/10/21/http_conditional_get_for_rss_hackers).

If no RSS/Atom feed, then please consider providing a web API.

This script is a last resort, for sites that change but don't provide either of
the two features mentioned above.

## Getting Started

1. Rename watch\_url.json.sample to watch\_url.json.
2. Customize the notification command in watch\_url.json. (More on this below.)
3. Launch the script into the background, and disown it.

You can specify an output file for logs with the -o flag, like so:

    $ ./watch_url.py -o watch_url.log https://ncase.me/ &
    [1] 12345
    $ disown 12345

It'll send a test notification after about 10 seconds just so you can see that
it's working. The next notifications it sends will be because something went wrong
or the site changed.

## Example Logs

    2020-02-09 15:56:54 INFO PID=14324 Started.
    2020-02-09 15:56:54 INFO ETag="31c-4ee12cb17cfc0" last_modified=Sat, 21 Dec 2013 22:19:51 GMT
    2020-02-09 15:57:05 INFO Sending a notification that we're running.
    2020-02-09 15:58:09 INFO Sending notification of site change.
    2020-02-09 15:58:09 INFO Exiting. Duration = 75s.

## Example Notification

This notification was sent by email to a phone company that converts email to SMS.

    FRM: user@domainwithemail.com
    SUBJ: Site changed
    MSG: https://ncase.me/
         From watch_url.py

## Customizing watch\_url.json

The configuration file looks like this:

    {
       "notification":[
          "ssh",
          "user@domainwithemail.com",
          "printf 'URL\\nFrom watch_url.py' | mail -s 'MSG' 5555550100@txt.phoneco.net"
       ]
    }

The one key, "notification", points to a list that can be passed to Python's
subprocess.run(). In this example, it sends a "mail" command via ssh to a system
that can email an account at an address that converts email to text.

## Is it any good?

[Yes](https://news.ycombinator.com/item?id=3067434). Especially because it's polite.
It sends `If-Modified-Since` headers when it detects `Last-Modified` headers, and
it sends `If-None-Match` headers when it detects `ETag` headers. It then gracefully
handles the 304 "Not Modified" response code.

## Licence

This software uses the [MIT license](https://raw.githubusercontent.com/dblume/watch-url/master/LICENSE.txt)
