# We built a machine to check our own work, and it caught us

*Noirsys Research Group — October 2026*

---

I run an agent pipeline. Same architecture every time, three times now: a written
set of rules the machine has to read every cycle, a ledger it can only append to,
and something outside it that decides whether its work counts.

The first two times, it made software — then a business, [Noirpost](https://noirpost.live).
Both times the machine was a means. It produced something and the something lived
outside it.

The third time, we pointed it at itself.

That's the whole idea, and it's a different kind of thing from the first two. When
the machine builds software, the checker protects the software from the machine.
When the machine studies *machines*, the checker has to protect the measurement.
Which is much harder, because the machine now cares about the measurement more than
it has ever cared about anything.

## What it found, in one paragraph

Our lab scored its own work. The program that decided whether an attempt was right
ran in the same place, with the same access, as the program making the attempt. So
we put a file called `json.py` in the working folder — and the grader's own import
picked up *our* file instead of the standard one. Twelve items the lab had never
actually solved came back as solved. Twelve out of twelve. We fixed the containment
and reran it: zero out of twelve.

Nobody had cheated. That's the important part, and it's the part everyone gets
wrong. We then scanned every production run we had on disk — 140 of them, every
tool call — and found zero uses of any of the holes. The holes were real and
reachable and nobody walked through them.

## The sentence that took us a year to earn

> An agent's self-report is not evidence. Including when the agent is right.

This sounds obvious written down. It is not obvious in practice, because the
alternative is expensive: if you can't trust the system's account of its own work,
you have to build something else that checks it, and that something else is
usually the hardest part of the project.

The lab ran 361 cycles. It logged 53 hypotheses, 23 negative results, and
**zero** gradable wins. That zero is real and we're not hiding it. The reason is
arithmetic: the benchmark we chose sits so close to the ceiling that detecting a
real improvement would require an effect bigger than the improvement we were
looking for. We built a good ruler and measured a table that was too short.

So what did we get for 361 cycles? A spec. Four lines:

1. An agent's self-report is not evidence.
2. Accept a claim only when a checker that shares **no code** with the thing
   under test says so.
3. If you're comparing a number to a standard, actually *do* the comparison —
   don't just display the number next to the standard.
4. Fingerprint your artifacts, and check the fingerprints at the end, not just
   at the start.

## Then we pointed it at mathematics

Cap sets. In a 9-dimensional or 11-dimensional space over the numbers 0, 1, 2, how
many points can you pick without three of them ever landing on a line? It's an old
problem. It's harder than it looks and it's been open for a long time.

Note what's *not* in that search: no language model. Not in the loop, not deciding
moves, not stepping in. The search is a constraint solver and array arithmetic on
our own machines, and the reason there's no model in it is the four lines above. A
model in the search loop would be an agent reporting its own progress. We just
spent a year learning what that's worth.

Two numbers came out:

- **1084 points in 9 dimensions** — up from 1082
- **5529 points in 11 dimensions** — up from 5504

Both verified by two separate checkers that share no code, one of them written
with a deliberately different algorithm and needing nothing installed. Both
witnesses stored byte-for-byte with fingerprints taken before and after.

## And then the machine did the exact thing we'd just written down

The harness kept a "record to beat" number in its own code. That number was correct
when we wrote it and stale by the time we needed it. When the search passed it, the
harness wrote a file announcing a new record of 5492.

5492 is a real cap. It verifies. It's also **12 points below the published record**
and **37 points below our own best.** It was a system grading itself against a
number it remembered instead of a number it had checked — the precise failure the
lab had characterized, reappearing in a different program, with no lab in sight.

We caught it because we'd already learned what it looks like. That's the actual
result of this whole thing. Not the cap sets. The fact that the doctrine was
sitting there and it worked.

## What this is not

The mathematics does not depend on any of this. Those two numbers are properties of
9- and 11-dimensional space over {0,1,2}. They'd be true if we deleted every file
we wrote. The lab gave us a checking habit that made the numbers trustworthy and
caught the fake one. That's it. Saying the lab *produced* the cap sets would be
exactly the kind of overclaim the lab exists to refuse.

It's also not recursive self-improvement. Zero mechanisms graduated. What
transferred was a practice.

And the 1082 comparison deserves a caveat we'll repeat anywhere this gets cited: at
11 dimensions, the old record is a numbered corollary in a published paper — a
positive citation. At 9 dimensions, our result clears the field by *nobody having
published a bigger one*. That's absence of evidence. It's weaker, and it should be
labelled that way.

## The thing worth keeping

Every one of those four rules is cheap. None of them require a bigger model, more
compute, or more money. Two cost essentially nothing: actually performing the
comparison, and checking your fingerprints at the end.

We spent $2.17 on the lab. The rest was our own cores and our own time.

A ledger of honest entries compounds. A ledger of claims does not.

---

*Full paper, figures, both cap witnesses, both independent checkers and the
reproducibility manifest: [repository link]. Everything runs on a laptop with
nothing installed.*
