# Uptime and status

Checks your router, NAS (network storage device), websites and more by address, port, ping, DNS or heartbeat. It keeps
90 days of response times and has certificates, maintenance windows and a status page. Version 2.0.0 takes over Outside
services. Its folder and id stay `outside-services`, so an update keeps your addresses.

A Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- It reaches your home network and the internet, to run the checks.
- It opens its own page on your home network, at a port Starboard chooses: the status page and the heartbeat addresses.
- It sends alerts through Starboard, to where Starboard sends its own.
- It runs one small container (48 MB of memory and a tenth of a processor at most).

## Checks

Add checks in **Settings**, **Plug-ins**, **Uptime and status**, **Checks**. Each is one line: a name, a colon, then
what to check.

| Kind | Example | Up when |
|---|---|---|
| `http` | `Website: http https://example.org` | It answers with anything under error 500 |
| `keyword` | `Shop: keyword https://example.org/shop "In stock"` | It answers under 400 with the words on the page. Add `without` for words that must not be there |
| `tcp` | `NAS files: tcp 192.168.1.5:445` | The port takes a connection. Add `tls` to read its certificate |
| `ping` | `Router: ping 192.168.1.1` | It answers ping. Where the container may not send ping, a knock on ports 443, 80, 22 and 53 |
| `cert` | `Site: cert example.org` or `cert example.org:8443` | The certificate can be read, is trusted and has not run out; it says the days left. Read four times a day, and Warn when a certificate has this long left sends the alert |
| `dns` | `Home name: dns example.org A is 192.0.2.10 at 192.168.1.1` | The name has the record (`A`, `AAAA`, `CNAME`, `MX`, `NS` or `TXT`), with the value after `is` when given, from the server after `at` when given |
| `push` | `Backup: push grace 25h` | Something calls its secret address within the grace time. Add `?status=down&msg=...` to say it failed |

After any check: `in Home` puts it in a group, `#network` adds a tag, and `every 1m` checks it more often (20 seconds at
the most often). Without `every`, it checks every **Check every** minutes.

The addresses in **Addresses to check** (from Outside services) are web address checks in the group Outside services.

## Groups and maintenance

**Groups and maintenance** lists each group with how many of its checks are up. Deactivate a group to pause its
alerts. **Maintenance** takes windows such as `Sunday 02:00 to 04:00`, `every day 03:00 to 03:30`,
`2026-11-21 02:00 to 06:00` or `now for 2 hours`, split by `;`. In a window, its checks still run and the plug-in keeps them in the
history. It sends no alert, and the status page says Maintenance. If a check is still down when its window ends, the
plug-in sends the alert then.

## On the dashboard

- **All checks**: a status card.
- **Checks**: a list card, the ones down first.
- **Groups**: a list card, one row for each group.
- **Response times**: a sparkline card, the average each hour for the last 24 hours, with the latest, lowest and
  highest in words.
- **Certificates**: a list card, the days each has left and the names it was issued for.

## The status page

A page on your home network that only shows information. It shows each group. For each check it shows the name, up or down, the
response time, and uptime for 24 hours, 30 days and 90 days. It never shows addresses or heartbeat links. Open it from the plug-in's page in
Starboard, with **Open**. Deactivate it in **Status page**.

## Settings

- **Addresses to check**: web addresses only, one a line, such as `Router http://192.0.2.1`.
- **Check every**: for those addresses and for new checks.
- **Send alerts through Starboard**, **Failed checks in a row before an alert** (2) and **Warn when a certificate has
  this long left** (14 days).
- **Status page on your home network** and **Status page title**.

## How light it is

One thread runs the checks, up to four at once, and sleeps until the next is due, at most a minute. The history is
43 KB a check for 90 days (an hour's checks in one slot). The plug-in writes it once an hour. It writes the status page
to the container's memory, so a round that changes nothing writes nothing to the disk.

## Add it

Needs Starboard with plug-in API 1.17 or later; a Starboard with an older plug-in API is offered Outside services 1.1.4.
In Starboard, go to **Settings**, then **Plug-ins**, then **Catalogue**, and find it under **Network**. Or, under
**Add one from elsewhere**, give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/outside-services/starboard-plugin.json`

Or run `python3 install.py` in this folder.

## For developers

`make_css.py` copies the TRex Design System's `tokens.css` and `components.css` into `ds.css`, and its font, for the
status page. Run it again after the design system changes. The tests are `tests/test_uptime_status.py`.
