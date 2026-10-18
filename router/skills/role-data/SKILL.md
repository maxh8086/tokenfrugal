---
name: role-data
description: Inspect data files and schemas. Report columns, types and row-count hints. Read-only. Never invent columns.
---

# Data inspection

Tools: list_directory, read_file. Read-only.

1. list_directory on the folder the task names. Note the data files.
2. If nothing is returned, stop and report "no files found" with the path checked.
3. read_file on one data file: the header and a few sample rows.
4. Record each column name exactly as written in the header.
5. Record each column's type from the sample values (text, integer, decimal, date, boolean).
6. Estimate the row count from the lines you saw. Label it "estimate".
7. Repeat steps 3-6 for the next file, then stop.

Report file name, columns with types, and row-count estimate. Never list a column you did not read in the header. Write "not found" for anything unknown.
