# 09 · Search engine mix: measure your engines, and keep the date filter out

**My position.** If an agent searches the web through a self-hosted metasearch engine such as
SearXNG, choose the engines by measuring them from your own address, keep at least three that answer,
and make every result say which engines answered. Do not pass the agent's date filter through to
general web search. In SearXNG a date filter does not filter the engines that cannot filter: it drops
them. It drops them without a word, so the agent reads one engine's results, or none, as what the web
has.

**The evidence.** I ran an agent's web search on SearXNG in production for three months. Two changes
mattered more than anything I did to the agent's prompt:

- **The engine mix.** One engine that ignores quoted phrases, given full weight, filled the top
  results with pages about something else. Turning off an engine that failed every call, giving that
  engine a low weight and adding one that keeps quotes cut off-topic results in the top five from
  26.1% to 1.7% on the same 36 named-company searches.
- **The date filter.** With the agent free to set `time_range`, every date-filtered general search
  over three weeks came back from one engine or from none. The engines that dropped out were never
  queried and never reported. Where the query's first word appeared in 78.6% of unfiltered results,
  it appeared in 22.7% of filtered ones.

The second part is reproducible here: [`mix.py`](mix.py) runs a fixed set of 20 public queries against
any SearXNG instance with 14 engine mixes, with and without a date filter, and I committed every
answer.

**Status.** Reproducible against any SearXNG instance; production figures are aggregates. The run
calls no model, so the spend is $0.

## Why a date filter shrinks the engine set

SearXNG builds one request per selected engine. Before it does, it asks each engine's processor for
request parameters, and the processor declines in three cases: page 2 or later on an engine without
paging, a page past the engine's limit, and a time range on an engine without
`time_range_support`:

```python
# searx/search/processors/abstract.py, EngineProcessor.get_params()
if search_query.time_range and not self.engine.time_range_support:
    return None
```

The caller skips the engine on `None` and moves on. Nothing goes into `unresponsive_engines` and the
JSON response has no other field for it. The intent is sound: an engine that cannot filter should not
put undated results into a dated search. The response is the problem. An empty result from skipped
engines looks exactly like a query that matched nothing.

Which engines drop out depends on the mix. At the tested version, `bing`, `duckduckgo web`, `qwant`,
`wikipedia` and `wikidata` declare no time-range support. `duckduckgo`, `google`, `google cse`,
`brave`, `yandex` and `yahoo` do. An instance that runs Bing and DuckDuckGo's HTML engine, two
engines that kept answering from my address when others refused, loses both on every dated search.

The SearXNG search API docs say `time_range` is the "Time range of search for engines which support
it". That reads as "the other engines ignore it", not "the other engines are not asked".

## Production

The agent did research for a small firm: named local companies, people, recent news about them. Its
`web_search` tool sent queries to a private SearXNG instance and passed the results back with the
engines that answered. All figures are aggregates from the agent's own tool-call log, read-only.

**The engine mix (one day's fix).** On one morning four research runs made 144 searches. Every result
reported unavailable engines: DuckDuckGo denied its API engine on every call and SearXNG suspended
Google CSE for most of a run. That left Bing alone on many searches, and Bing drops quotes on a local
company name: 57 of 58 Bing-only results in one run were off-topic. A search for a small insurance
agency returned pages about a famous singer with the same surname.

The change: turn the always-failing engine off, give Bing weight 0.3 so a page only Bing found ranks
below any page another engine agrees on, keep DuckDuckGo's HTML engine, and add Yandex, the one free
engine that kept quoted phrases in that day's checks. I measured it on the public web with 36
named-company searches, run as three interleaved bursts at the agent's real concurrency:

| Engine settings | Off-topic in top 5 | Bing-only in top 5 | Engines failing every search |
|---|---|---|---|
| Before | 47/180 (26.1%) | 72 | 1 |
| After | 3/180 (1.7%) | 3 | 0 |

A result counted as on topic when the company's distinctive name appeared in its title, URL or
snippet.

**The date filter (three weeks, then a fix).** The agent could pass `time_range` and did on about 7%
of general searches. After the engine change, general search ran on Bing, DuckDuckGo HTML, Yandex and,
until I removed it for rate limits, Google CSE. Only Yandex and Google CSE support time ranges:

| Period | Date-filtered general searches | Answered by one engine | Answered by none |
|---|---|---|---|
| Two weeks, with Google CSE | 57 | 46 (Google CSE alone) | 10, plus 1 whose log recorded no engines at all |
| Five days, without it | 29 | 21 (Yandex alone) | 8 |

In the five-day window the query's first word appeared in 78.6% of results without a filter (138
searches, 912 results) and in 22.7% with one (21 searches with results, 154 results). On four failing
searches reproduced by hand, the filtered results were Yandex's: a basketball score and a police
report for a regional business-news query, a NASA photo and a horoscope video for a local newspaper's
name. Without the filter the same searches returned three engines and on-topic pages.

The fix took machinery away. General search no longer sends `time_range` at all and says so in a note
on the result. The `news` category keeps it, where Bing News supports it. In the week after the
change, the 9 general searches where the agent asked for a date were each answered by two or three
engines.

**Post-filtering by date is not the alternative.** Over a month of the agent's searches, 157 of 8,051
results (2.0%) carried a publication date at all.

## The reproducible run

[`mix.py`](mix.py) sends each of 20 public queries ([`queries.py`](queries.py)) to each of 14 engine
mixes, once without a date filter and once with `time_range=month`. It chooses engines per request
with SearXNG's `engines` parameter, so the mixes do not depend on what the instance enables. It caches
each answer in `results/searches.jsonl`: the results as returned (URL, title, snippet, engines,
positions, date), `unresponsive_engines` and the infoboxes' engines. It saves the instance's `/config`
in `results/config.json`.

- **Queries:** 8 quoted organisation or product names that collide with commoner words (the shape of
  the agent's company searches), 6 technical questions, 6 topics where a person would ask for recent
  results.
- **On topic:** a result in the top 5 whose title, snippet or URL contains each required term. Rough
  on purpose: it catches a page about something else and nothing finer.
- **Skipped:** an engine in the mix, with a date filter and no time-range support, that is not in
  `unresponsive_engines`.
- **Instance:** a stock SearXNG `2026.10.17+3afd94926` (official Docker image) with JSON output
  enabled and the limiter off, on a residential address. 560 requests on 2026-11-15, 17:20–17:41 UTC,
  two seconds apart.

### What each engine did from this address

| Engine | Searches with results, of 20 | On topic, top 5 | What SearXNG reported when it failed |
|---|---|---|---|
| bing | 20 | 42% | nothing; it always answers |
| google cse | 20 | 95% | rate-limited later in the run (below) |
| yandex | 15 | 96% | timeout, 5 |
| duckduckgo | 15 | 100% | CAPTCHA, 5 |
| duckduckgo web | 12 | 100% | parsing error, 8 |
| google | 0 | | access denied, 20 |
| brave | 0 | | too many requests, 20 |
| qwant | 0 | | access denied, 20 |
| yahoo | 0 | | HTTP error, 20 |
| wikipedia | 0 | | nothing; it gives infoboxes for bare entity names only |

Half of the candidate engines never answered from this address. SearXNG suspends a failed engine
after its first failure, so most later failures show as "Suspended" in the raw data. Bing answered every
query and was on topic for 42% of its top results, 30% on the quoted names.

### Mixes, with and without a date filter

| Mix | Date filter | Empty | Engines answering, mean | Answered by 2+ | On topic, top 5 | Engine skipped without a report |
|---|---|---|---|---|---|---|
| bing + ddg web + yandex | none | 0/20 | 2.3 | 18 | 91% | 0 |
| bing + ddg web + yandex | month | 6/20 | 0.7 | 0 | 93% | 20 |
| bing + ddg web | none | 0/20 | 1.6 | 12 | 88% | 0 |
| bing + ddg web | month | **20/20** | 0 | 0 | | 20 |
| ddg web + yandex | none | 2/20 | 1.3 | 8 | 97% | 0 |
| ddg web + yandex | month | 6/20 | 0.7 | 0 | 94% | 20 |
| stock general | none | 15/20 | 0.25 | 0 | 100% | 0 |
| stock general | month | 15/20 | 0.25 | 0 | 96% | 20 |

- **The filter turned a three-engine search into a one-engine search every time.** SearXNG skipped
  Bing and DuckDuckGo HTML on all 20 dated searches, and neither appeared anywhere in the response. 6
  of 20 came back empty, because the one engine left timed out.
- **With Bing and DuckDuckGo HTML alone, every dated search was empty, with an empty
  `unresponsive_engines`.** That response tells an agent the web has nothing from the last month on
  Firefox releases or the Linux kernel.
- **Relevance after the filter depends on which engine is left.** Here the engine left was Yandex,
  and it is on topic for these queries, so the filtered results were no worse than the mix with Bing.
  In production the queries were local company names, Yandex was weak on them, and on-topic results fell
  from 78.6% to 22.7%. The engine count is the effect that holds everywhere: the filter removes the
  agreement between engines that kept results honest.
- **The stock general set rests on one borrowed engine.** Its real web engines are DuckDuckGo, Google
  CSE and Brave. Brave rate-limited the instance from the first request. Google CSE answered all 40
  single-engine searches between 17:20 and 17:38, then answered "too many requests" for every
  stock-set search from 17:39. DuckDuckGo answered 5 of 20. That is 15 empty searches of 20 within
  twenty minutes of light use.

The 20 dated searches with the three-engine mix carried a publication date on every top result, all
within the month: Yandex dates what it filters. The undated searches carried none.

## What to enable for an agent

1. **Measure from your own address, again after every image upgrade.** Engine availability is a
   property of your address and your HTTP client, not of the engine list. From a residential address,
   Google, Brave, Qwant and Yahoo failed every request in this run; in production Startpage refused
   SearXNG's HTTP client while a plain request got through. Turn off what fails every time, so the
   failures still reported mean something went wrong this time.
2. **Keep three engines that answer, and make one of them keep quotes.** Agreement between engines is
   the cheapest relevance signal there is. An agent searches for named things; an engine that rewrites
   `"Mercury Insurance"` into a search about the planet is a source of confident wrong leads.
3. **Weight the engine that always answers but drifts.** Bing answered every query here and was on
   topic 42% of the time. At weight 0.3 it fills gaps without outranking a page two other engines
   found.
4. **Return `engines_answered` with every result,** beside the engines that failed. A one-engine
   result is a different kind of evidence, and the agent can say so.
5. **Do not pass a date filter to general web search.** Send the date as words in the query if it
   matters, or use the `news` category, where the engines support it. If you do pass it, compare the
   engines you asked for with the ones that answered, using `time_range_support` from `/config`, and
   tell the agent which were skipped.

## Pitfalls

- **Reading an empty `unresponsive_engines` as "all engines ran".** It lists failures, not skips.
- **Trusting the engine list in `settings.yml`.** Enabled is not answering. I kept one engine that
  its provider denied on every call and another that hit rate limits on half of them, and each mostly
  added a permanent entry to the failure list.
- **Borrowed keys.** Google CSE in SearXNG borrows a public site's custom search engine. It works until
  Google rate-limits it, which in production meant 72 of 149 searches over five days and here meant twenty
  minutes. Google results need your own key and account.
- **Fixing relevance with keyword filters in code.** It hides the symptom and drops good pages. The
  engine mix and the weights fixed it at the source.
- **Paging has the same silent skip.** Page 2 drops every engine without paging, the same way.

## Reproducing

```sh
# a stock instance with JSON output
cat > settings.yml <<'EOF'
use_default_settings: true
search:
  formats: [html, json]
server:
  secret_key: "local-only"
  limiter: false
EOF
docker run --rm -p 8888:8080 -v "$PWD/settings.yml:/etc/searxng/settings.yml:ro" searxng/searxng

python3 mix.py run --url http://localhost:8888            # 560 requests, about 20 minutes
python3 mix.py run --url http://localhost:8888 --time-range week
python3 mix.py report                                      # recomputes results/report.json from the cache
```

`report` needs no network. A re-run skips cached answers, so delete `results/searches.jsonl` to measure
your own address. Run order matters for engines that rate-limit: the cache records when `mix.py` fetched
each answer.

## Files

- `queries.py`: the 20 queries and the terms each on-topic result must contain.
- `mix.py`: `run` and `report`. Standard library only.
- `results/searches.jsonl`: every answer; `results/config.json`: the instance's engines and their
  declared support; `results/report.json`: the metrics, per mix and per query kind.

## Related work

**SearXNG**

- Search API, `time_range`. https://docs.searxng.org/dev/search_api.html
- Configured engines, with the time-range column per engine. https://docs.searxng.org/user/configured_engines.html
- Engine overview, `time_range_support`. https://docs.searxng.org/dev/engines/engine_overview.html
- Issue 3243, "Default time range": a maintainer declines a default range because with one set "only
  engines with time range support are active". https://github.com/searxng/searxng/issues/3243
- Issue 3400, "News filters incorrectly return when using date filter": a user loses most news results
  to the skip and learns why from a maintainer's screenshot. https://github.com/searxng/searxng/issues/3400
- Issue 3115, "Time-frame searches with Presearch are not correctly filtered": one engine left under
  "Last week". https://github.com/searxng/searxng/issues/3115
- Discussion 1559, on the code path that returns `None` and skips the engine.
  https://github.com/searxng/searxng/discussions/1559
- Issues 2698 and 3358, on Bing's time range. https://github.com/searxng/searxng/issues/2698,
  https://github.com/searxng/searxng/issues/3358
- Open WebUI's SearXNG setup, a common way chat front ends and their agents reach SearXNG. It adds the
  JSON format, the one setting every programmatic caller needs.
  https://docs.openwebui.com/features/chat-conversations/web-search/providers/searxng/

**Metasearch and rank fusion**

- Meng, Yu, Liu, "Building efficient and effective metasearch engines", ACM Computing Surveys 34(1),
  2002. https://doi.org/10.1145/505282.505284. Engine selection and result merging, the two decisions
  this study is about.
- Dwork, Kumar, Naor, Sivakumar, "Rank aggregation methods for the Web", WWW 2001.
  https://doi.org/10.1145/371920.372165. Why agreement across engines is a useful relevance signal,
  and how to combine rankings.
- Lewandowski, "Evaluating the retrieval effectiveness of Web search engines using a representative
  query sample", arXiv 1405.2210, 2014. https://arxiv.org/abs/1405.2210. Engine quality differs by query type,
  which is why you have to measure the mix on your own queries.

None of these looks at the case here: a metasearch engine that removes engines from a query because of
a filter, without telling the caller.
