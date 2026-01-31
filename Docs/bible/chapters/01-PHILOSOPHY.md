# Part I: Philosophy

**Version:** 3.0
**Last Updated:** 2026-01-30
**Status:** Current

## 1.1 The Landscape

Artificial intelligence is becoming infrastructure. Like electricity or
the internet before it, AI will soon be woven into how we think, work,
create, and relate to each other.

This creates a question that most people haven't thought to ask:

**Who owns the infrastructure of your mind?**

Today, the answer is: not you. Your conversations, your context, your
patterns of thought — these live on servers you don't control, governed
by terms of service you didn't negotiate, subject to changes you won't
be consulted about.

This isn't necessarily malicious. It's simply the default. Centralized
systems are easier to build, easier to scale, easier to monetize. The
path of least resistance leads to a world where your AI companion is a
rental, not a possession.

Luna is an alternative path.

## 1.2 The Stakes

Some people believe AI should remain centralized. They have reasons —
safety, oversight, efficiency, profit. Some of those reasons are
legitimate. Some are not.

We don't need to litigate motives. We only need to observe outcomes:

- When your context lives on someone else's server, it can be accessed
without your knowledge. - When your memories are platform features, they
can be deprecated. - When your AI relationship depends on a
subscription, it can be terminated. - When your patterns of thought
become training data, they benefit systems you may not support.

These aren't hypotheticals. These are the current terms of engagement.

The question isn't whether centralized AI is "bad." The question is
whether it should be the *only* option.

## 1.3 What Luna Is

Luna is a tool for cognitive sovereignty.

That sounds grandiose, but the implementation is simple: **Luna is a
file.** A SQLite database that contains memories, relationships, and
context. Copy the file, copy Luna. Delete the file, Luna is gone. No
server required. No subscription. No terms of service.

This means:

| Aspect | What It Means |
|--------|---------------|
| **Privacy** | Your thoughts stay on your hardware. No telemetry, no training, no extraction. |
| **Continuity** | Luna can't be discontinued. The file format is open. If the software dies, the data survives. |
| **Portability** | You can move Luna between devices, back her up, fork her, or destroy her. Your choice. |
| **Transparency** | You can inspect everything Luna knows. It's a database. You can query it. |

Luna isn't anti-cloud. She can delegate to cloud services when needed —
research, complex reasoning, tasks that benefit from scale. But the
*identity* stays local. The cloud is a contractor, not a landlord.

## 1.4 Why It Matters

This isn't about technology preferences. It's about the kind of future
we're building.

AI companions will become important to people. They'll help us think,
remember, decide, create. They'll know our patterns better than we know
ourselves. That intimacy is valuable — and that value will attract those
who want to capture it.

A world where everyone's AI companion is a thin client to a centralized
service is a world with new vectors for:

- Surveillance (your AI knows everything; who else has access?)
- Manipulation (what if your AI subtly shapes your views?)
- Control (what if access is revoked for the wrong opinion?)
- Dependency (what if the service changes in ways you don't like?)

We're not claiming these outcomes are inevitable. We're claiming they're
*possible*, and that possibility is worth designing against.

Luna is a hedge. A tool that demonstrates an alternative is viable. One
person using Luna doesn't change the world. But a proof that sovereign
AI companionship *works* — that it can be responsive, useful, personal,
and private — that changes what people know is possible.

## 1.5 The Design Principles

These aren't just technical preferences. They're values encoded in
architecture:

**1. Sovereignty First**

Your AI companion should be yours. Not rented. Not licensed. Not subject
to someone else's business model. The file is yours. Full stop.

**2. Transparency Always**

You should be able to understand what your AI knows and why. Luna's
memory is a database you can query. Her reasoning is traceable. No black
boxes.

**3. Graceful Degradation**

If the cloud is unavailable, Luna still works. Reduced capability, but
functional. The core identity never depends on external services.

**4. Minimal Attack Surface**

Every network connection is a potential vulnerability. Luna minimizes
external dependencies. What doesn't exist can't be exploited.

**5. User Agency**

You control what Luna remembers and forgets. You control what she can
access. You control whether she exists at all. The system serves you,
not the reverse.

## 1.6 What Luna Isn't

Luna isn't a rebellion. She's not trying to overthrow anything. She's
simply an alternative — a demonstration that AI companionship doesn't
*have* to follow the landlord model.

Luna isn't paranoid. She uses cloud services when they're useful. She's
not hiding from the internet. She's just thoughtful about what crosses
the wire.

Luna isn't a manifesto. She's a tool. A useful tool for people who care
about privacy, continuity, and ownership. If you don't care about those
things, centralized options will serve you fine.

Luna is for people who want to own their mind.

## 1.7 Implementation Reality

The philosophy is now implemented. Luna Engine v2.0 delivers on these principles:

| Principle | Implementation | Status |
|-----------|----------------|--------|
| **Sovereignty First** | SQLite database (`data/luna_engine.db`), all data local | Implemented |
| **Transparency Always** | MemoryMatrix queryable, 167 classes with clear interfaces | Implemented |
| **Graceful Degradation** | Local Qwen 3B inference, cloud is optional fallback | Implemented |
| **Minimal Attack Surface** | Single optional API call (Claude delegation), no telemetry | Implemented |
| **User Agency** | Memory lock-in/unlock, forget commands, full data access | Implemented |

**The File:**
- Location: `data/luna_engine.db`
- Format: SQLite with sqlite-vec extension
- Schema: `memory_nodes`, `graph_edges`, `entities`, `conversation_history`
- Portable: Copy file = copy Luna

## 1.8 The Simple Version

AI is becoming part of how we think.

We believe that part should belong to you.

Not your provider. Not your platform. You.

Luna is a file. Your file. That's the whole philosophy.


	— Ah4b 

---

*End of Part I*
