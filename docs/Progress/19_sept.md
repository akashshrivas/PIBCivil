# PIBCivil — Progress Log

---

## 19 September 2026

### 🎯 Planned
- Build the `extract` stage of the pipeline: pull PIB press releases, store them date-wise, and start a backfill mechanism for past dates
- Get a working RSS-based discovery + fetch flow
- Design and implement date-wise (and month-wise) storage
- Handle the "RSS only shows ~20 items" gap with polling + a proper backfill path for full daily coverage

### ✅ Done

**1. RSS-based discovery (`pipeline/extract/rss_fetcher.py`)**
- Found PIB's real RSS feed: `https://pib.gov.in/RssMain.aspx?ModId=6&reg=3&lang=1`
- Uses `feedparser` to pull `PRID` + title from each feed item
- Feed only contains title + link (no date, no description) — date is filled in separately when needed via `article_fetcher`

**2. Article content fetcher (`pipeline/extract/article_fetcher.py`)**
- Given a PRID, fetches `PressReleasePage.aspx?PRID=...` and parses out ministry, title, posted-on date (raw string), body text, translation links
- Returns a `RawArticle` pydantic model

**3. Date cleaning (`pipeline/clean/date_cleaner.py`)**
- Parses PIB's raw date string (e.g. `"01 FEB 2023 1:35PM"`) into a real `datetime`, using a regex rather than a single `strptime` format (PIB's spacing isn't fully consistent)

**4. Date-wise storage (`pipeline/storage/storage_manager.py`)**
- Layout decided: `data/raw/<YYYY>/<MM>/<DD>.json` — **one file per day**, containing an array of that day's articles (not one file per PRID)
- Saving **merges** into the existing day file by PRID, so re-running never duplicates or wipes earlier saves
- `list_by_day()` / `list_by_month()` helpers added for reading it back

**5. "Seen" tracking (`pipeline/storage/seen_tracker.py`)**
- Flat file (`data/.state/seen_prids.txt`) recording every PRID already fetched
- Prevents re-fetching/re-saving the same release across repeated runs

**6. Pipeline orchestration (`pipeline/pipeline.py`)**
- `python pipeline.py` — one-shot run: RSS discover → fetch new-only → save
- `python pipeline.py --loop` — polls every 5 minutes (keeps up with the RSS feed's ~20-item cap so nothing gets pushed off before being seen)
- `python pipeline.py --backfill YYYY-MM-DD` — catch-up fetch for one past date, wired to `backfill_fetcher.py`

**7. Backfill fetcher — partially working (`pipeline/extract/backfill_fetcher.py`)**
- `allRel.aspx` (the date-filterable listing page) needs a real browser — its date filter is 3 separate `<select>` dropdowns (Day/Month/Year) that trigger ASP.NET postbacks on change, not a plain URL
- Built with Playwright
- **Day dropdown confirmed working**: `#ContentPlaceHolder1_ddlday`

**Issues hit along the way**
- Initially assumed no RSS feed existed → found the real one
- RSS feed has no date field at all → solved with optional `article_fetcher` lookup per item
- `ImportError`/`ModuleNotFoundError` from relative import + missing `__init__.py` → fixed
- RSS feed capped at ~20 items total → mitigated with polling + seen-tracking (not a 100% guarantee)
- Storage design changed from per-PRID files to per-day files mid-way, per requirement
- `allRel.aspx`'s date filter turned out to be dropdown-based with postbacks, not a text field + button as first assumed

### ⏳ Remaining
- [ ] Find real IDs for Month and Year dropdowns on `allRel.aspx` (Day confirmed: `#ContentPlaceHolder1_ddlday`; Month/Year guesses were wrong, script times out on Month)
- [ ] Get `backfill_fetcher.py` fully working end to end for one test date
- [ ] Wire confirmed backfill into `pipeline.py --backfill` and test with `data/raw/.../DD.json` output
- [ ] Backfill a small range of past days once working (17th, 18th, etc.)
- [ ] Start on `parse/` stage (currently `article_fetcher.py` does parsing itself — should split out)
- [ ] `clean/text_cleaner.py` and `clean/html_cleaner.py` still empty
- [ ] `dedup/`, `classify/`, `transform/` (besides dates), `storage/database_writer.py` — not started