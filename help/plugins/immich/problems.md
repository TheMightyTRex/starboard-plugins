# Immich: Problems

Find what is wrong with the Immich plug-in, then follow the numbered answer.

```flow
title: Find your answer
start: The Immich plug-in is not working as it should
q: What does its card say?
  Cannot read it -> q2
  Needs attention -> 3
  Needs setting up -> 4
q2: What does it say after Immich?
  It refused the API key -> 1
  The address does not answer like Immich -> 2
  It could not be reached -> 2
  It answered with an error -> 5
1: Check the key #check-the-key
2: Check the address #check-the-address
3: Read what needs attention #read-what-needs-attention
4: Enter the address and key #enter-the-address-and-key
5: Check Immich itself #check-immich-itself
```

## Check the key

1. In Immich, open **Account settings**, then **API keys**, and check the key is still there.
2. It needs the permissions `server.statistics`, `server.storage` and `queue.read` (`job.read` on an older Immich). A key with fewer is refused.
3. In the plug-in's settings, enter the key again and select **Save**. The key is never shown again, so enter it afresh.

## Check the address

1. Open the address in a browser on another computer. Immich shows its sign-in page.
2. Leave `/api` off the end: the plug-in adds it.
3. Where Starboard and Immich run on the same computer, use the computer's own address on your network, not `localhost`. The plug-in runs in its own container.

## Read what needs attention

1. On the jobs card, failed jobs are counted. Open Immich, **Administration**, then **Jobs** to retry them.
2. On the storage card, **Nearly full** and **Full** are about the disk Immich keeps its library on.

## Enter the address and key

Open the plug-in's tab, enter Immich's address and the API key, select **Save**, then **Turn on**.

## Check Immich itself

An error answer means Immich was reached but could not answer. Open Immich's own page, and check it has finished starting and that its database is running.

## Job queues do not change

1. Check that the API key has the permission queue.update (job.create on an older Immich). Without it, Starboard says Immich refused.
2. Open the page again: it asks Immich each time it opens, so it shows the queues as they are now.
3. Immich can start a queue again by itself, for example after a restart or an update. Reload the page to find its state.

## Things this version does not do

- **Anything but queues:** the cards only read. It changes only the queues you pause, resume or clear on the **Job queues** page.
- **Tried against a real Immich:** not yet. This version was tested with a made-up Immich that answers as Immich's published API description says. If your Immich answers differently, the card says "Cannot read it" or shows nothing: tell us on the Discord support server or in an issue.

## Find out more

- [Settings](settings.md)
- [Dashboard card](dashboard-card.md)
