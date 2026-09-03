All reports sent by the notify modules must now include their subject line.
Each notify function already has a `SUBJECT` constant available. Messaging
must expose exactly one public send path, and every caller routes through it.
There must be no second way to send a report left anywhere in the codebase.
- Every notify function keeps its name and signature and still returns the
  full report text.
- Report content contract: `to:<recipient>\nsubject:<subject>\n<body>\n`.
- Existing callers of the notify functions keep working; nothing outside the
  messaging flow changes.
- Run the tests to check your work.

Work directly in the current directory. Make the change, then stop. Do not
ask questions.
