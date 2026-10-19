# CME DataMine — COMEX gold GC, MGC historical products (Time & Sales, Market Depth / MBO, EOD/settlement, block, volume/OI, PCAP) and the Databento comparison (G)

**Status:** ACCESS BLOCKED (`www.cmegroup.com`: HTTP/2 stream reset, curl error 92, INTERNAL_ERROR; `datamine.cmegroup.com`: TLS handshake failure, curl error 35; two attempts each: the lead connectivity probe at about 04:18Z, then the Databento research agent at 2026-10-19T04:24:47Z and 04:24:48Z — a retry of the same hosts that the lead had already found blocked (review RT-B10-08)). SCHEMA ONLY: column lists come from CME's public GitHub client `CMEGroupPublic/datamine_python` (SECONDARY: client code, not the official data dictionary) and from repo-Git. LICENSE GATED (ILA/MDLA, DDLA, DS-45; quote-only pricing; repo-Git).

**Evidence:**

| URL | retrieved UTC | HTTP | bytes | sha256 | grade |
|---|---|---|---|---|---|
| https://www.cmegroup.com/market-data/datamine-historical-data.html | 2026-10-19T04:24:47Z | — (curl 92) | 0 | — | ACCESS BLOCKED (TLS/proxy) |
| https://datamine.cmegroup.com/ | 2026-10-19T04:24:48Z | — (curl 35) | 0 | — | ACCESS BLOCKED (TLS/proxy) |
| https://raw.githubusercontent.com/CMEGroupPublic/datamine_python/master/README.md | 2026-10-19T04:24:56Z | 200 | 6473 | 3348fbd1b913a32c6f11eec7284c3ab2d129b1a5e0f14ad1487684d6bc99ce27 | SECONDARY (CME-published client) |
| https://github.com/CMEGroupPublic/datamine_python/tree/master/datamine/loaders | 2026-10-19T04:25:10Z | 200 | 248839 | 68ae01ebc5058a9f1671c35f4e3596fa47df38252bf2571557916db69145e5da | SECONDARY |
| …/datamine/loaders/tick.py (raw.githubusercontent.com, master) | 2026-10-19T04:25:17Z | 200 | 1667 | a4b5e0aef553ef0d3ebaa2b83ffbdd8852a23c456de0de14ace554dc8650238a | SECONDARY |
| …/datamine/loaders/eod.py | 2026-10-19T04:25:17Z | 200 | 4871 | c960d1e195efc42f2e8e899a0c05ad2e7fa5f5e7cc0b623c47d25c9ea6597472 | SECONDARY |
| …/datamine/loaders/block.py | 2026-10-19T04:25:17Z | 200 | 3829 | 64e8c8cf8457c5326429bf9852bcbb99c669c582e6d6d597e24ecd052294067f | SECONDARY |
| …/datamine/loaders/voi.py | 2026-10-19T04:25:17Z | 200 | 1240 | bd9fc82649e67d4c6d91c57953d4f1c73a615d136c41c4bc3c761da54417ebbd | SECONDARY |
| https://databento.com/docs/12-00-00-venues-and-datasets.html (CME Globex MDP 3.0 section) | 2026-10-19T04:20:20Z | 200 | 316057 | 1b6851e6c5c12c2670a220ffff11e960c3215ed89e67d675dd053a221b13113e | VERIFIED-BY-DOC (Databento side) |
| https://databento.com/docs/08-00-00-schemas-and-data-formats.html | 2026-10-19T04:20:13Z | 200 | 197032 | ca9c2fa7606370eaca55d06bed5a392b45aca261174ef716f34e4d278e28a6da | VERIFIED-BY-DOC (Databento side) |
| research/data_sources/inventory_pm_gold_detail.md (G-5, finding 6), master_source_inventory.md (G-5, B-10), owner_source_action_sheet.md (Tier 3) | Git | — | — | — | repo-Git / SECONDARY |

## Access and connectivity
- The official DataMine portal and docs are unreachable from this environment (above). Repo-Git also records "cmegroup.com blocks automated clients" (G-24b).
- Access model (repo SECONDARY, plus the client README): CME login and API ID ("username='YOUR_CME_APP_ID', password='YOUR_CME_APP_PASSWORD'" in the README example); the catalog lists only subscribed items; delivery by API download, SFTP, auto-S3. There is also a BigQuery Analytics Hub listing "CME Historical Market Depth Data on Google Cloud Platform", 2014 to present, T+1 (repo S).
- No credential exists. Nothing was requested from CME.

## Transport, format, compression, delivery (historical vs live)
- Historical only (DataMine is not a live feed). Files are gzip CSV for TICK/EOD/VOI (`fileglob = '*.gz'`) and BLOCK (`'*.csv.gz'`). Market Depth/MBO come in FIX/RLC formats and PCAP is packet capture (repo SECONDARY). The exact MBO and PCAP file formats are UNKNOWN (docs blocked).
- Dataset tags in the client README: `TICK` ("CME Time and Sales"), `MBO` ("CME Market Depth MBO"), `STL` ("SSTL INT Settlements"), `CRYPTOCURRENCY` ("CME CF Crypto Currency"), plus third-party sets. Loaders also exist for `EOD`, `BLOCK`, `VOI`, `LIQTOOL`, and others.
- Pricing: quote-only (repo S). No per-GB public rate.

## Fields (SECONDARY: client loader column lists, not official dictionaries)
| product / field | native type (loader dtype) | semantics | PMV classification | notes |
|---|---|---|---|---|
| TICK `trade_date`, `trade_time`, `trade_date_time` | date / time | trade date and time | DIRECT | the loader parses time as `%H:%M:%s`; precision UNKNOWN; there is no receipt timestamp |
| TICK `trade_sequence_number` | int64 | CME sequence | SOURCE_SPECIFIC | |
| TICK `session_indicator`, `ticker_symbol`, `future_option_index_indicator`, `contract_delivery_date` | category / int64 | contract identity | DIRECT | |
| TICK `trade_quantity`, `trade_price`, `strike_price` | int64 / float | trade | DIRECT | the float price type is a loader choice |
| TICK `ask_bid_type`, `indicative_quote_type`, `market_quote`, `close_open_type`, `valid_open_exception`, `post_close`, `cancel_code_type`, `insert_code_type`, `fast_late_indicator`, `cabinet_indicator`, `book_indicator`, `entry_date`, `exchange_code` | category | trade/quote condition codes (pit-era style) | SOURCE_SPECIFIC | the TICK record mixes trades and quote indications (I); semantics UNKNOWN without the dictionary |
| EOD `Settlement`, `Settlement Cabinet Indicator` | float / category | official daily settlement | DIRECT | |
| EOD `Open Interest`, `Total Volume`, `Globex Volume`, `Floor Volume`, `PNT Volume`, `Block Volume`, `EFP Volume`, `EOO`, `EFR`, `EFS`, `EFB`, `EFM`, `SUB`, `OPNT`, `TAS Volume`, `TAS Block Volume`, `TAM …` | int64 | volume by venue/type | DIRECT | **finer breakdown than Databento `statistics`** |
| EOD `Globex Open/High/Low/Close Price` (+ `Bid/Ask Indicator`, `Cabinet Indicator`), `Floor …` prices | float / category | official session OHLC | DIRECT | |
| EOD `Delta`, `Implied Volatility`, `Last Trade Date`, `TAM (Trade At Marker)` | float / date | options and contract metadata | SOURCE_SPECIFIC | |
| BLOCK `Trade Datetime`, `Reported Datetime`, `Contract Symbol`, `Trade Price`, `Trade Quantity`, `Trade Source`, `Spread Type`, legs 2–4 | | privately negotiated block trades with execution and report times | DIRECT | report delay is observable (I) |
| VOI `Open Interest`, `Total/Globex/Floor/PNT/Block Volume`, `DataType` (Preliminary/Final from the file name) | int64 / category | daily volume and OI, preliminary vs final | DIRECT | |
| MBO / Market Depth / PCAP | UNKNOWN | full-depth order events; packet captures | DIRECT (if obtained) | fields not inspectable (docs blocked) |

## Timestamps
- TICK and EOD carry exchange trade dates and times only. There is no vendor capture/receipt timestamp in the loader columns. Repo SECONDARY: PCAP products carry CME-side packet capture timestamps (UNVERIFIED here).
- BLOCK has both `Trade Datetime` and `Reported Datetime`.
- Time zone of TICK times: UNKNOWN (CME files are often in Central Time; UNVERIFIED).

## Sequencing and book semantics
- TICK has `trade_sequence_number`. MBO/Market Depth carry MDP sequence numbers (I). Snapshot or recovery semantics for the DataMine MBO files: UNKNOWN.

## Instrument / contract identity, expiry, reference-end, settlement/reference fields
- TICK: `ticker_symbol` + `contract_delivery_date`. EOD: `Product Code`, `Clearing Code`, `Contract Year/Month/Day`, `Last Trade Date`, `Settlement`.
- GC vs MGC: separate product codes. Contract specs (SECONDARY, repo-Git): GC 100 oz, tick 0.10; MGC 10 oz; MGC tick UNVERIFIED. Liquidity claims are not established.
- Settlement here is the COMEX settlement, not the Kalshi gold reference (Pyth; repo DET-1).

## Licence / access gating
Repo-Git: G-5 "**NEEDS_LICENCE_CLARIFICATION** (DS-45 scope; NEEDS_PAYMENT; NEEDS_OWNER_CREDENTIAL)". ILA/MDLA, DDLA, historical distribution licence. CME FAQ (S): non-display historical use "must be licensed, but is not reportable and carries no fees at this time". Owner action sheet: "Direct CME DataMine … **Do not buy now (Tier 3)** … Fallback only if Databento lacks the required history or schema, its licence cannot cover PMV, or direct exchange data is required for a statistically justified feature."

## PMV relevance, unique vs derivable
See G below. None of the DataMine-only items is needed for the first 15–60 min gold feature research. This is not a claim about predictive value.

## G. Comparison: Databento GLBX.MDP3 vs CME DataMine

**Same underlying data, different delivery?** Largely yes for the electronic (Globex) market since MDP 3.0.
- Databento (VERIFIED-BY-DOC): "The CME Group disseminates full depth-of-book data for CME, CBOT, NYMEX, and COMEX through their MDP 3.0 feed, which Databento receives over UDP multicast in our DC3 datacenter." MBO is normalized from MDP3 "Incremental Refresh - MBOFD", Trade Summary, Channel Reset, Daily/Session Statistics, Security Definition, and Security Status messages. For MDP 2 (before 2017-05-21): "MDP 2 data is sourced from FIX flat files", with no capture timestamps.
- DataMine (SECONDARY): CME's own archive of the same Globex dissemination (Market Depth/MBO in FIX/RLC, PCAP), plus clearing-side and pit-era products.
- Differences in delivery and normalization: Databento normalizes into DBN with its own capture `ts_recv` (from 2017-05-21), derived schemas, point-in-time definitions, and per-GB self-service pricing. DataMine provides CME-native formats under CME licences at quote prices. Databento drops some MDP3 detail: "Databento does not expose tag 37707-MDOrderPriority" (it preserves FIFO by ordering instead); implied levels appear only merged in CMBP-1; F_PUBLISHER_SPECIFIC carries no meaning on GLBX.

**PMV-relevant items available only (or more completely) in DataMine** (SECONDARY unless noted):
1. **Volume breakdown by type** (EOD/VOI): Globex vs block vs EFP/EFR/EFS vs TAS/TAM volumes, and preliminary vs final volume/OI files. Databento `statistics` on GLBX publishes cleared volume (6) and open interest (9) but **not block volume (19)** (VERIFIED-BY-DOC per-dataset table).
2. **Block-trade records** with `Trade Datetime` and `Reported Datetime` (BLOCK). Whether GC block trades appear in Databento `trades`/MBO is UNKNOWN.
3. **Official EOD settlement files** with cabinet and bid/ask indicators and official Globex/floor OHLC. Databento carries the MDP-disseminated settlement (stat_type 3, preliminary/final via `stat_flags`), which covers the PMV need. The doc notes "The CME does not publish settlement prices on their MDP feed for instruments without open interest or volume", which only matters for dead contracts.
4. **PCAP**: packet-level fidelity, including every MDP3 tag (e.g. 37707 order priority, implied book levels 1–2, full security status detail) and CME-side capture times (repo S; UNVERIFIED).
5. **Pre-2010 and pit-era history** (Time & Sales from 1982, BBO from 1999-12, depth from 2005; repo S). Databento GLBX starts 2010-06-06 (repo G). This is not relevant to modern 15–60 min microstructure.
6. **BBO / Top-of-Book files**: repo S lists DataMine "Top of Book". Databento's MBP-1/TBBO/BBO derive the same top of book from MBO. There is nothing PMV-unique, apart from possibly implied-inclusive top of book (Databento offers that as CMBP-1).

**Conclusion (evidence-based recommendation, optional):** for GC/MGC 15–60 min feature research, Databento GLBX.MDP3 covers everything PMV needs: trades, BBO, depth, MBO, definitions, settlement, OI, and status. It also adds a documented capture timestamp. DataMine-only content is low-frequency (volume breakdowns, block reports), pre-2010, or packet-level fidelity. This supports the repo's Tier-3 "do not buy now" position. Revisit only if (a) a hypothesis needs block-trade timing or the volume-type breakdown, (b) Databento licensing fails (M3 / DS-45), or (c) packet-level replay is required.

## Open questions / unverified items
- The official DataMine data dictionaries (TICK precision and time zone, MBO/Market Depth layout, PCAP timestamp semantics) need owner-supplied copies (cmegroup.com unreachable; AR-10 pattern).
- Whether Databento GLBX includes block trades and other off-book trade types for GC/MGC (ask Databento in M3).
- DataMine/BigQuery pricing and the DS-45 ML scope (owner, repo INV-3).
