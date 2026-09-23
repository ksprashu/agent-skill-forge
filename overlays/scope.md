## In the forge

`scope` answers one question: is this diff still the change we agreed to make?

**Feed it the intent.** The comparison is only as good as the stated intent you give it. Use
the acceptance file from `done` if there is one, rather than re-typing a summary from memory.

**Runs offline.** No network, no writes to the working tree, index, commits, or branches.
Safe to run on anything.

**When it fires.** Before opening a pull request, and any time a fix starts touching files
you did not expect. Three subsystems for a one-line fix is the signal.
