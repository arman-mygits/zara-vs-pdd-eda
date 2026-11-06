# Data hygiene - shape audit ledger

| step                                              |   rows |   cols |   row_delta | note                                         |
|:--------------------------------------------------|-------:|-------:|------------:|:---------------------------------------------|
| A1. cached Adj Close (union calendar)             |    991 |      3 |    nan      |                                              |
| A2. cached Volume (union calendar)                |    991 |      3 |      0.0000 |                                              |
| A3. trimmed to common listing window              |    991 |      3 |      0.0000 | leading/trailing boundary NaNs only          |
| A4. forward-filled (holiday alignment)            |    991 |      3 |      0.0000 | 43 cells imputed, 0 rows lost                |
| A5. volume reindexed onto the price calendar      |    991 |      3 |      0.0000 | closed sessions kept as NaN - never ffilled  |
| B1a. daily returns (row 1 is NaN by construction) |    991 |      3 |      0.0000 |                                              |
| B1b. daily returns after boundary trim            |    990 |      3 |     -1.0000 | -1 row by design (no t-1 for the first date) |
| B2. cumulative growth, base 100                   |    991 |      3 |      1.0000 | +1 anchor row at base 100                    |
| B3/B4. calendar + BBC_Season event mask           |    990 |      8 |     -1.0000 | 257/990 rows flagged as BBC season (26.0%)   |
| B6. tidy long panel (ticker x date)               |   2970 |     11 |  1,980.0000 | expected 2970 rows -> OK                     |
