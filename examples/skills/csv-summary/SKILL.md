---
name: csv-summary
description: Summarize a CSV file - row count, column types, missing values and a few example rows. Use when the user asks what is in a CSV, wants a quick profile of a spreadsheet export, or asks to describe a .csv file.
---

# CSV summary

1. Read the first 200 lines of the file.
2. Report: number of rows (count the file if small), each column with its inferred type,
   how many values are empty per column, and three example rows.
3. Keep the summary under 20 lines. Do not modify the file.
