# Contributing

This is an early project. Small, useful improvements are welcome: a reproducible
CSV bug, clearer instructions, or a focused feature backed by tests.

1. Open an issue describing the problem and expected behavior before proposing
   a large change. Use fictional data and `.example` email/domain names.
2. Create a branch with a descriptive name and make a focused change.
3. Run `python3 -m unittest discover -s tests -v` and the README sample.
4. Update the README if parsing, classification, or output rules change.
5. Open a pull request describing the problem, resulting behavior, and tests.

Keep the core offline and avoid new runtime dependencies unless they solve a
specific need. Never add real lead lists, passwords, API keys, or mailbox checks
to tests. Include edge cases where data might be lost or misclassified.

Contributions are licensed under the repository's MIT License. Be clear about
any AI assistance, borrowed code, and the checks you actually ran. Do not claim
usage, results, or maintenance activity that has not happened.

Possible future work (not implemented): streaming large CSVs and an optional
local file-picker interface. Discuss scope before starting.
