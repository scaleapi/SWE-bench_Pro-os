Scan every scripts/instance_*.sh and extract all apt-get install -y package lists. Handle multi-line backslash-continuation blocks, but stop collecting tokens at the first && within a block — anything after && is a chained shell command, not a package name. Only accept valid Debian package name tokens (lowercase, letters/digits/+/-/., max 40 chars).

Group packages by project prefix in the filename (ansible__ansible, internetarchive__openlibrary, qutebrowser__qutebrowser). Promote packages that appear in all three projects to a "Core" section. Deduplicate across sections so each package appears only once (Core wins, then ansible, then openlibrary, then qutebrowser).

Exclude google-chrome-stable from the main install — it needs a special apt source and belongs in a commented-out block at the bottom.

Write the result to install_system_deps.sh as a single apt-get install -y \ call with inline backtick comments labelling each section, followed by rm -rf /var/lib/apt/lists/* and the commented Chrome block.