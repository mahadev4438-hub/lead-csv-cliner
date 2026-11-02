# Security and data handling

The cleaner does not make network requests, send email, or upload lead data.
It writes reports to a new local directory. Input files remain unchanged.

Treat input files and reports as sensitive. The `.gitignore` excludes typical
data/report paths, but it is not a data-loss prevention system. Do not attach
real contacts, credentials, or private datasets to public issues.

For a reproducible bug, use a minimal fictional CSV. If the problem would expose
sensitive information, use GitHub's **Report a vulnerability** option if the
maintainer has enabled it. Otherwise open a public issue requesting a private
contact channel without posting exploit details or personal data.

The tool prefixes common spreadsheet-formula indicators with an apostrophe.
Spreadsheet import/edit/export behavior varies; this is a precaution, not a
guarantee across every spreadsheet application. Source files may still contain
dangerous formulas. The tool does not assess whether a contact may legally be
used for outreach, and it does not verify mailbox deliverability.
