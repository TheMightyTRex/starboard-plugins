# Uptime and status: Settings

Uptime and status' settings are on its own tab: go to **Settings**, then **Plug-ins**, then **Uptime and status**. It has five sections: **Checks**, **Groups and maintenance**, **Settings**, **Alerts** and **Status page**.

## Checks

Each check is one line: a name, a colon, then what to check. Enter it in **Add a check** and select **Add**. Each row has **Test**, **Change** (the same line, to change), **Turn on** or **Turn off**, and **Remove**, which removes its history too.

| Kind | Example | Up when |
|---|---|---|
| `http` | `Website: http https://example.org` | It answers with anything under error 500, even a sign-in page or "not found" |
| `keyword` | `Shop: keyword https://example.org/shop "In stock"` | It answers under 400 and the words are on the page, in any case. With `without` before the words, they must not be there |
| `tcp` | `NAS files: tcp 192.168.1.5:445` | The port takes a connection. Add `tls` to read the port's certificate |
| `ping` | `Router: ping 192.168.1.1` | It answers ping within 8 seconds. Where the container may not send ping, it knocks on ports 443, 80, 22 and 53, and any answer counts |
| `cert` | `Site: cert example.org` or `cert example.org:8443` | The certificate can be read, is trusted and has not run out. Its row says how many days are left, and it is down when the certificate has run out or is not trusted. No web request is sent |
| `dns` | `Home name: dns example.org A is 192.0.2.10 at 192.168.1.1` | The name has a record of that type (`A`, `AAAA`, `CNAME`, `MX`, `NS` or `TXT`), with the value after `is` when you give one, asked of the server after `at` when you give one |
| `push` | `Backup: push grace 25h` | Something calls its secret address within the grace time. Its row shows the address |

After any check:

- `in Home` puts it in the group Home. Use quote marks for a name with spaces: `in "Home office"`.
- `#network` adds the tag network. Tags show on its row.
- `every 1m` checks it every minute (`30s`, `5m`, `2h` or `1d`; 20 seconds at the most often). Without it, the check runs every **Check every** minutes.

A web address or a name with a port can stand alone: `https://example.org` is an `http` check and `nas.home:22` a `tcp` check. Up to 100 checks.

### Heartbeats

A `push` check is for something that runs by itself, such as a backup. At its end, the job calls the check's address, such as `http://192.0.2.20:8788/push/...`, with any web request (`curl` or `wget` will do). With no call for longer than its grace time (1 hour when left out), the check is down. To say the job failed, call the address with `?status=down&msg=Disk%20full`.

## Groups and maintenance

Each group made by `in` has a row with how many of its checks are up.

- **Turn off** a group to pause its alerts. Its checks still run.
- **Maintenance** takes one or more windows, split by `;`: `Sunday 02:00 to 04:00`, `weekdays 01:00 to 02:00`, `every day 03:00 to 03:30`, `2026-11-21 02:00 to 06:00` or `now for 2 hours`. A window that ends before it starts ends the next day. Times are the server's own.
- In a window, its checks still run and are kept, no alert is sent, and the status page says **Maintenance**. A check still down when the window ends is sent then.

## Settings, Alerts and Status page

| Setting | What it does | Default |
|---|---|---|
| **Addresses to check** | Web addresses, one a line, with a name first if you like: `Router http://192.0.2.1`. Kept from Outside services; they show in **Checks** in the group Outside services | Empty |
| **Check every** | Minutes between checks, from 1 to 60, for these addresses and for checks without `every` | 5 minutes |
| **Send alerts through Starboard** | Sends an alert when a check is down and when it is up again, to where Starboard sends its own (**Settings**, **Alerts**) | Active |
| **Failed checks in a row before an alert** | 1 to 10. Until then the check says **Trying again** | 2 |
| **Warn when a certificate has this long left** | 1 to 90 days | 14 days |
| **Status page on your home network** | The read-only page on the plug-in's address | Active |
| **Status page title** | Its heading | Home services |

## Things to note

- **A `cert` check** reads one certificate and nothing else, four times a day unless you write `every`, such as `cert example.org every 1h`. It sends the alert before the end like the others: set the days under **Warn when a certificate has this long left**.
- **Certificates** are read for every `https` address and every `tcp` check with `tls`, every 6 hours. A home device with its own certificate is still up; the certificate says **Not trusted** and why.
- **History:** 90 days of response times and uptime for each check, about 43 KB each.
- A change is used at the next round, within a minute. Settings are kept when you update or turn it off.

## Find out more

- [Install](install.md)
- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
