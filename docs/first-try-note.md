# Try starting AutoRnD from the README, and tell us where you got stuck

You are the first person other than the builder to try this. Nobody has seen a stranger start
it, and that is what we need to know. An agent did it once and it worked in about five minutes,
but an agent is not you.

## The rules

1. **Use only the README.** Do not ask the person who sent you this, and do not read the code.
   If the README does not tell you, that is the finding.
2. **Write down the time** when you finish each step, and write down **every place you stopped,
   guessed or were confused**, even if you got past it.
3. **Do not fix anything quietly.** If you work around something, say what you did.
4. **Never send anyone your key.** Not in a message, not in a screenshot. Hide it.

## What you need

- A computer with `git` and Python 3.11 or later. Check with `python3 --version`.
- An API key for [OpenRouter](https://openrouter.ai) or another OpenAI-compatible provider,
  with a few dollars on it. A question costs about one cent.
- Six model names from that provider, one for each tier the README lists. AutoRnD ships none and
  recommends none. If you do not know what to pick, `docs/MODELS.md` shows what the builder used.
  If you cannot choose, that is a finding too.
- About 40 minutes.

## What to do

1. Open the [README](../README.md) and follow **Quick Start**, step by step.
2. When the server is up, open `http://localhost:8100/` in a browser.
3. Ask the sample question in the README ("Ask a Question and Read the Answer"), either from the
   page or with the `curl` line.
4. Ask one question of your own from your own field, one that names its rule or standard.
5. Read the answer and its **confirmations** and **cautions**. Do they make sense to you?

## What to send back

- **How far you got:** the server running, the first answer, your own question.
- **Minutes** each step took.
- **Every place you stopped or guessed,** and what you did.
- **Every error message,** copied exactly (leave your key out).
- **Whether the answer and its cautions were clear** to someone who is not the builder.
- **One thing you would change** in the README.

Thank you. A short, honest "I got stuck at step 3 because..." is more use than a polished report.
